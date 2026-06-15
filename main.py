import os
import threading
import asyncio
import discord
import requests
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, PushMessageRequest, TextMessage as LineTextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent

app = Flask(__name__)

# --- 設定 ---
configuration = Configuration(access_token=os.getenv("LINEBOT_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINEBOT_SECRET"))
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
LINE_GROUP_ID = os.getenv("LINE_GROUP_ID")

# --- Discord ---
intents = discord.Intents.default()
intents.message_content = True 
discord_client = discord.Client(intents=intents)

# 新增：監視機器人是否真的成功登入並看到伺服器
@discord_client.event
async def on_ready():
    print(f"DEBUG: 機器人已成功連線，帳號: {discord_client.user}")
    for guild in discord_client.guilds:
        print(f"DEBUG: 機器人所在的伺服器: {guild.name}")

@discord_client.event
async def on_message(message):
    # 新增：監視是否真的有「聽到」頻道內的講話
    print(f"DEBUG: 偵測到 Discord 訊息! 內容: {message.content} 來自: {message.author}")
    
    if message.author == discord_client.user: return
    
    # 組合文字與圖片附件網址
    text = f"[{message.author.display_name}]: {message.content}"
    if message.attachments:
        for att in message.attachments:
            text += f"\n[附件圖片/檔案]: {att.url}"

    try:
        with ApiClient(configuration) as api_client:
            line_api = MessagingApi(api_client)
            line_api.push_message(PushMessageRequest(
                to=LINE_GROUP_ID, 
                messages=[LineTextMessage(text=text)]
            ))
            print("DEBUG: 成功轉發至 LINE!")
    except Exception as e:
        print(f"DEBUG: Discord 轉 LINE 發生錯誤: {e}")

# --- Flask ---
@app.route("/", methods=['GET'])
def health(): return "OK", 200

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except Exception as e:
        print(f"Callback 錯誤: {e}")
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    if DISCORD_WEBHOOK:
        requests.post(DISCORD_WEBHOOK, json={
            "content": event.message.text, 
            "username": "LINE User"
        })

# --- 啟動核心 ---
def run_discord():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    discord_client.run(DISCORD_TOKEN)

# 這裡是關鍵：將線程啟動從 Flask app 邏輯中分離出來
if not hasattr(app, 'discord_started'):
    threading.Thread(target=run_discord, daemon=True).start()
    app.discord_started = True

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)