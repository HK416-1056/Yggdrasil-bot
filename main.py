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
    TextMessage as LineTextMessage,
    ImageMessage as LineImageMessage
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
    # 1. 終極防護：忽略機器人自己，以及「Webhook 發送的訊息」
    if message.author.bot or message.webhook_id: 
        return
    
    # 2. 徹底阻擋私訊：只允許來自伺服器 (Guild) 的訊息
    if not message.guild: 
        return 

    print(f"DEBUG: 偵測到 Discord 伺服器訊息! 內容: {message.content}")

    messages_to_send = []
    
    # 處理文字
    if message.content:
        messages_to_send.append(LineTextMessage(text=f"[{message.author.display_name}]: {message.content}"))
    elif not message.content and message.attachments:
        messages_to_send.append(LineTextMessage(text=f"[{message.author.display_name}] 傳送了圖片/附件:"))

    # 處理圖片與附件轉發給 LINE
    for att in message.attachments:
        # 如果是圖片，使用 LINE 的原生圖片格式顯示
        if att.content_type and att.content_type.startswith('image/'):
            messages_to_send.append(LineImageMessage(
                original_content_url=att.url,
                preview_image_url=att.url
            ))
        else:
            # 如果是一般檔案，傳送網址
            messages_to_send.append(LineTextMessage(text=f"[附件]: {att.url}"))

    # LINE 限制一次 API 呼叫最多只能推播 5 個對話泡泡
    if not messages_to_send:
        return
    messages_to_send = messages_to_send[:5]

    try:
        with ApiClient(configuration) as api_client:
            line_api = MessagingApi(api_client)
            line_api.push_message(PushMessageRequest(
                to=LINE_GROUP_ID, 
                messages=messages_to_send
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

# 同時接收文字與圖片事件
@handler.add(MessageEvent, message=(TextMessageContent, ImageMessageContent))
def handle_message(event):
    # 1. 徹底阻擋 LINE 私訊：只允許群組 (group)
    if getattr(event.source, 'type', None) != 'group':
        print(f"DEBUG: 收到 LINE 的 {getattr(event.source, 'type', 'unknown')} 訊息 (非群組)，已成功阻擋。")
        return
    
    group_id = event.source.group_id
    user_id = event.source.user_id
    
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
        pass # 忽略獲取名字失敗的錯誤

    # 若為文字訊息
    if isinstance(event.message, TextMessageContent):
        requests.post(DISCORD_WEBHOOK, json={
            "content": event.message.text, 
            "username": f"{user_name} (LINE)"
        })
        print("DEBUG: LINE 文字成功轉發至 Discord")

    # 若為圖片訊息
    elif isinstance(event.message, ImageMessageContent):
        try:
            print("DEBUG: 準備下載 LINE 圖片...")
            with ApiClient(configuration) as api_client:
                blob_api = MessagingApiBlob(api_client)
                # 從 LINE 伺服器獲取圖片二進位資料
                image_data = blob_api.get_message_content(event.message.id)
                
                # 透過表單格式上傳至 Discord Webhook
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