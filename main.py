import os
import threading
import asyncio
import discord
import requests
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, 
    ApiClient, 
    MessagingApi, 
    MessagingApiBlob, 
    PushMessageRequest, 
    TextMessage as LineTextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent

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
async def on_ready():
    print(f"DEBUG: Discord 機器人已成功連線，帳號: {discord_client.user}")

@discord_client.event
async def on_message(message):
    # 1. 忽略機器人自己的訊息
    if message.author == discord_client.user: return
    
    # 2. 關掉私訊，只接受群組(伺服器)訊息
    if not message.guild: return 

    print(f"DEBUG: 偵測到 Discord 伺服器訊息! 內容: {message.content}")

    # 組合文字與圖片附件網址
    text = f"[{message.author.display_name}]: {message.content}"
    if message.attachments:
        for att in message.attachments:
            text += f"\n[附件圖片/檔案]: {att.url}"

    # 避免只有傳圖片沒有文字時，第一行多出空白的 []
    if not message.content and message.attachments:
        text = f"[{message.author.display_name}] 傳送了圖片/附件:"
        for att in message.attachments:
            text += f"\n{att.url}"

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

# --- Flask / LINE ---
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

# 同時處理文字與圖片訊息
@handler.add(MessageEvent, message=(TextMessageContent, ImageMessageContent))
def handle_message(event):
    # 1. 關掉私訊，只處理來自「群組 (group)」的訊息
    if getattr(event.source, 'type', None) != 'group':
        print("DEBUG: 收到 LINE 私訊，已忽略。")
        return
    
    group_id = event.source.group_id
    user_id = event.source.user_id
    
    # 💡 抓取群組 ID 的關鍵：將這串 C 開頭的代碼複製到 Render 的 LINE_GROUP_ID 變數中
    print(f"DEBUG: 收到 LINE 群組訊息! 該群組的 ID 是: {group_id}")

    if not DISCORD_WEBHOOK:
        return

    # 嘗試取得發言者名稱
    user_name = "LINE 使用者"
    try:
        with ApiClient(configuration) as api_client:
            line_api = MessagingApi(api_client)
            profile = line_api.get_group_member_profile(group_id, user_id)
            user_name = profile.display_name
    except Exception as e:
        print(f"DEBUG: 獲取 LINE 用戶名稱失敗: {e}")

    # 如果是文字訊息
    if isinstance(event.message, TextMessageContent):
        requests.post(DISCORD_WEBHOOK, json={
            "content": event.message.text, 
            "username": f"{user_name} (LINE)"
        })
        print("DEBUG: LINE 文字成功轉發至 Discord")

    # 如果是圖片訊息
    elif isinstance(event.message, ImageMessageContent):
        try:
            with ApiClient(configuration) as api_client:
                blob_api = MessagingApiBlob(api_client)
                # 取得圖片的二進位資料
                image_data = blob_api.get_message_content(event.message.id)
                
                # 透過 multipart/form-data 上傳至 Discord Webhook
                files = {
                    "file": ("image.jpg", image_data, "image/jpeg")
                }
                requests.post(DISCORD_WEBHOOK, data={"username": f"{user_name} (LINE)"}, files=files)
                print("DEBUG: LINE 圖片成功轉發至 Discord")
        except Exception as e:
            print(f"DEBUG: LINE 圖片轉發失敗: {e}")

# --- 啟動核心 ---
def run_discord():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    discord_client.run(DISCORD_TOKEN)

if not hasattr(app, 'discord_started'):
    threading.Thread(target=run_discord, daemon=True).start()
    app.discord_started = True

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)