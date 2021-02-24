import json
import requests
import re
from bs4 import BeautifulSoup
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters,CallbackQueryHandler
from telegraph import Telegraph

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.182 Safari/537.36"}


def parseBook(bookcode, chaptercode):
    book = {}
    book["bookcode"] = bookcode
    book["chaptercode"] = chaptercode
    baseurl = f'https://www.biquge.com.cn/book/{bookcode}/{chaptercode}.html'
    html = requests.get(baseurl, headers=headers).text
    soup = BeautifulSoup(html, 'html.parser')
    book["bookname"] = soup.find_all("div", class_="con_top")[0].find_all("a")[2].text
    book["chaptername"] = soup.find("h1").text
    return book


# 添加追更小说 /add <bookcode> <chaptercode>
def addBook(update, context):
    bookcode = context.args[0]
    chaptercode = context.args[1]
    book = parseBook(bookcode, chaptercode)
    with open('config.json', 'r', encoding="utf-8") as f:
        books = json.load(f)
    f.close()
    books.append(book)
    with open('config.json', 'w', encoding="utf-8") as f:
        f.write(json.dumps(books, ensure_ascii=False, indent=4, separators=(',', ' : ')))
    f.close()

# 删除追更小说 /add <bookcode>
def delBook(update,context):
    delBookCode=''.join(context.args)
    with open("config.json","r",encoding="utf-8") as f:
        books = json.load(f)
    f.close()
    for index,book in enumerate(books):
        if book["bookcode"] == delBookCode:
            break
    books.pop(index)
    with open('config.json', 'w', encoding="utf-8") as f:
        f.write(json.dumps(books, ensure_ascii=False, indent=4, separators=(',', ' : ')))
    f.close()

# 显示所有在追小说
def showBooks(update, context):
    with open('config.json', 'r', encoding="utf-8") as f:
        books = json.load(f)
    f.close()
    booksInfo = "您的书架里有以下小说：\n"
    for book in books:
        booksInfo += f'{book["bookname"]}  /b{book["bookcode"]} \n'
    update.message.reply_text(booksInfo)

# 获取最新章节的章节名和多少章未读
def getLatest(bookcode,chaptercode):
    bookurl=f"https://www.biquge.com.cn/book/{bookcode}/"
    html=requests.get(bookurl,headers=headers).text
    soup=BeautifulSoup(html,"html.parser")
    latestChapter=soup.find("meta", attrs={"property": "og:novel:latest_chapter_name"}).get("content")
    for index,chapter in enumerate(soup.find_all("dd")):
        if chaptercode in str(chapter):
            break
    left=len(soup.find_all("dd"))-1-index
    return latestChapter,left


def bookDetail(update, context):
    bookcode = update.message.text.replace('/b', '')
    with open('config.json', 'r', encoding="utf-8") as f:
        books = json.load(f)
    f.close()
    for book in books:
        if book["bookcode"] == bookcode:
            break
    latestChapter,left=getLatest(book["bookcode"],book["chaptercode"])
    bookinfo=f'{book["bookname"]} \n已读章节: {book["chaptername"]} \n最新章节: {latestChapter}\n共计{left}章未读'
    key = InlineKeyboardButton('获取未读章节并更新', callback_data=f"{book['bookcode']}|{book['chaptercode']}")
    keyboard = InlineKeyboardMarkup([[key]])
    update.message.reply_text(bookinfo,reply_markup=keyboard)

def publish(chapterurl):
    html = requests.get(chapterurl, headers=headers).text
    soup = BeautifulSoup(html, "html.parser")
    title=soup.find("h1").text
    content=str(soup.find(id="content")).replace("<div id=\"content\">",'').replace('</div>','')

    telegraph = Telegraph()
    telegraph.create_account(short_name='novelbot')
    response = telegraph.create_page(
        title,
        html_content =content
    )
    return 'https://telegra.ph/{}'.format(response['path'])

def updateConfig(bookurl):
    with open('config.json', 'r', encoding="utf-8") as f:
        books = json.load(f)
    f.close()
    html = requests.get(bookurl).text
    res = re.search("<p>最新章节：<a href=\"/book/(.*?)/(.*?).html\" target=\"_blank\">(.*?)</a></p>", html)
    for book in books:
        if book["bookcode"] == res.group(1):
            book["chaptercode"]=res.group(2)
            book["chaptername"] = res.group(3)
            break
    with open('config.json', 'w', encoding="utf-8") as f:
        f.write(json.dumps(books, ensure_ascii=False, indent=4, separators=(',', ' : ')))
    f.close()

# /b<bookcode>后点击嵌入式按钮回调后的函数，用于输出一本小说所有的未读章节，并且更新配置的json文件
def getUpdate(update,context):
    query = update.callback_query
    bookcode,chaptercode=query.data.split('|')
    bookurl = f"https://www.biquge.com.cn/book/{bookcode}/"
    html=requests.get(bookurl,headers=headers).text
    soup=BeautifulSoup(html,"html.parser")
    for index,chapter in enumerate(soup.find_all("dd")):
        if chaptercode in str(chapter):
            break
    unread=""
    for i in soup.find_all("dd")[index+1:]:
        unread+=publish("https://www.biquge.com.cn"+i.find("a").get('href'))+'\n'
    context.bot.send_message(chat_id=update.effective_chat.id, text=unread)
    updateConfig(bookurl)



if __name__ == '__main__':
    updater = Updater("<token>")
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler('add', addBook))
    dispatcher.add_handler(CommandHandler('del', delBook))
    dispatcher.add_handler(CommandHandler('show', showBooks))
    dispatcher.add_handler(MessageHandler(Filters.regex('^(/b)'), bookDetail))
    dispatcher.add_handler(CallbackQueryHandler(getUpdate))
    updater.start_polling()
    updater.idle()