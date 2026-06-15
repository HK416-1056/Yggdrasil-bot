import os
import threading
import asyncio
import discord
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageMessage

app = Flask(__name__)

# --- 設定 ---
LINE_ACCESS_TOKEN = os.getenv("LINEBOT_ACCESS_TOKEN")
LINE_SECRET = os.getenv("LINEBOT_SECRET")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
LINE_GROUP_ID = os.getenv("LINE_GROUP_ID")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_SECRET)

# --- Discord 轉 LINE (d2l) ---
intents = discord.Intents.default()
intents.message_content = True 
discord_client = discord.Client(intents=intents)

@discord_client.event
async def on_message(message):
    # 檢查頻道與來源
    if message.author == discord_client.user: return
    if DISCORD_CHANNEL_ID and str(message.channel.id) != str(DISCORD_CHANNEL_ID): return

    # 處理文字與附件
    content = message.content
    if message.attachments:
        attachment_url = message.attachments[0].url
        content += f"\n[附件]: {attachment_url}"

    try:
        line_bot_api.push_message(LINE_GROUP_ID, TextSendMessage(text=f"[{message.author.display_name}]: {content}"))
        print(f"DEBUG: Discord 轉發成功")
    except Exception as e:
        print(f"DEBUG: Discord 轉發失敗: {e}")

# --- LINE 轉 Discord (l2d) ---
@app.route("/", methods=['GET'])
def health_check(): return "OK", 200

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except Exception as e:
        print(f"DEBUG: Webhook 錯誤: {e}")
    return 'OK'

# 處理文字訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    payload = {"content": event.message.text, "username": "LINE 使用者"}
    requests.post(DISCORD_WEBHOOK, json=payload)

# 處理圖片訊息
@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    # 取得圖片內容 (需透過 API 取得)
    message_content = line_bot_api.get_message_content(event.message.id)
    # 將圖片透過 Webhook 轉發
    payload = {"content": "收到一張 LINE 圖片", "username": "LINE 使用者"}
    # 注意：Discord Webhook 的 json 參數不直接支援傳送二進位圖片，這裡先傳文字提示
    requests.post(DISCORD_WEBHOOK, json=payload)
    print("DEBUG: 已收到並提示 LINE 圖片")

# --- 啟動 ---
def run_discord():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    discord_client.run(DISCORD_TOKEN)

if __name__ == "__main__":
    threading.Thread(target=run_discord, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))