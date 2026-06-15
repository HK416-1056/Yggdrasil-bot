import os
import threading
import asyncio
import discord
import requests
import signal
import sys
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

@discord_client.event
async def on_message(message):
    if message.author == discord_client.user: return
    try:
        with ApiClient(configuration) as api_client:
            line_api = MessagingApi(api_client)
            line_api.push_message(PushMessageRequest(to=LINE_GROUP_ID, messages=[LineTextMessage(text=f"[{message.author.display_name}]: {message.content}")]))
    except Exception as e:
        print(f"Discord 轉 LINE 錯誤: {e}")

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
        requests.post(DISCORD_WEBHOOK, json={"content": event.message.text, "username": "LINE User"})

# --- 啟動機制 ---
def run_discord():
    # 確保 Discord 運行在獨立的迴圈
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    discord_client.run(DISCORD_TOKEN)

if __name__ == "__main__":
    # 使用線程啟動 Discord，並設置為守護線程
    t = threading.Thread(target=run_discord)
    t.daemon = True
    t.start()
    
    # 啟動 Flask，使用 Gunicorn 以外的直接運行方式
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)