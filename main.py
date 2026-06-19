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
# 新增：匯入 FileMessageContent 
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent, FileMessageContent

app = Flask(__name__)

# --- 設定 ---
configuration = Configuration(access_token=os.getenv("LINEBOT_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINEBOT_SECRET"))
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
LINE_GROUP_ID = os.getenv("LINE_GROUP_ID")
MESSAGE_CHANNEL_ID = os.getenv("MESSAGE_CHANNEL_ID")  # 指定轉發的 Discord 頻道 ID

# --- Discord ---
intents = discord.Intents.default()
intents.message_content = True 
discord_client = discord.Client(intents=intents)

@discord_client.event
async def on_ready():
    print(f"DEBUG: Discord 機器人已成功連線，帳號: {discord_client.user}")

@discord_client.event
async def on_message(message):
    # 1. 忽略機器人自己與 Webhook 發送的訊息
    if message.author.bot or message.webhook_id: 
        return
    
    # 2. 徹底阻擋 Discord 私訊：只允許來自伺服器的訊息
    if not message.guild: 
        return 

    # 3. 指定頻道過濾：若有設定特定頻道 ID，則只轉發該頻道的訊息，其餘頻道直接忽略
    if MESSAGE_CHANNEL_ID and str(message.channel.id) != MESSAGE_CHANNEL_ID:
        return

    print(f"DEBUG: 偵測到指定 Discord 頻道訊息! 內容: {message.content}")

    messages_to_send = []
    
    # 處理文字
    if message.content:
        messages_to_send.append(LineTextMessage(text=f"[{message.author.display_name}]: {message.content}"))
    elif not message.content and message.attachments:
        messages_to_send.append(LineTextMessage(text=f"[{message.author.display_name}] 傳送了圖片/附件:"))

    # 處理圖片與附件轉發給 LINE
    for att in message.attachments:
        if att.content_type and att.content_type.startswith('image/'):
            messages_to_send.append(LineImageMessage(
                original_content_url=att.url,
                preview_image_url=att.url
            ))
        else:
            messages_to_send.append(LineTextMessage(text=f"[附件]: {att.url}"))

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
            print("DEBUG: 成功轉發至 LINE 目標對象!")
    except Exception as e:
        print(f"DEBUG: Discord 轉 LINE 發生錯誤: {e}")


# --- 獨立的背景處理函數 ---
def forward_text_to_discord(text, user_name):
    requests.post(DISCORD_WEBHOOK, json={
        "content": text, 
        "username": f"{user_name} (LINE)"
    })
    print("DEBUG: [背景] LINE 文字成功轉發至 Discord")

def forward_image_to_discord(message_id, user_name):
    try:
        print("DEBUG: [背景] 準備下載 LINE 圖片...")
        with ApiClient(configuration) as api_client:
            blob_api = MessagingApiBlob(api_client)
            image_data = blob_api.get_message_content(message_id)
            
            files = {"file": ("image.jpg", image_data, "image/jpeg")}
            requests.post(DISCORD_WEBHOOK, data={"username": f"{user_name} (LINE)"}, files=files)
            print("DEBUG: [背景] LINE 圖片成功轉發至 Discord")
    except Exception as e:
        print(f"DEBUG: [背景] LINE 圖片轉發失敗: {e}")

# 新增：處理一般檔案轉發與大小限制
def forward_file_to_discord(message_id, file_name, file_size, user_name):
    # 檢查檔案大小 (25MB = 25 * 1024 * 1024 = 26214400 bytes)
    MAX_SIZE = 25 * 1024 * 1024
    
    if file_size and file_size > MAX_SIZE:
        error_msg = f"⚠️ [{user_name}] 傳送的檔案「{file_name}」超過 25MB 限制，無法轉發至 Discord。"
        print(f"DEBUG: [背景] {error_msg}")
        
        # 發送報錯通知到 Discord
        requests.post(DISCORD_WEBHOOK, json={
            "content": error_msg, 
            "username": "系統通知"
        })
        
        # 發送報錯通知回 LINE
        try:
            with ApiClient(configuration) as api_client:
                line_api = MessagingApi(api_client)
                line_api.push_message(PushMessageRequest(
                    to=LINE_GROUP_ID, 
                    messages=[LineTextMessage(text=error_msg)]
                ))
        except Exception as e:
            print(f"DEBUG: 傳送錯誤提示回 LINE 失敗: {e}")
        return

    # 若大小合乎規範，則開始下載並轉發
    try:
        print(f"DEBUG: [背景] 準備下載 LINE 檔案 ({file_name})...")
        with ApiClient(configuration) as api_client:
            blob_api = MessagingApiBlob(api_client)
            file_data = blob_api.get_message_content(message_id)
            
            # 以免 LINE 沒提供 file_size，下載後做二次檢查
            if len(file_data) > MAX_SIZE:
                print("DEBUG: [背景] 下載後發現檔案大於 25MB，取消轉發。")
                return

            files = {"file": (file_name, file_data)}
            requests.post(DISCORD_WEBHOOK, data={"username": f"{user_name} (LINE)"}, files=files)
            print("DEBUG: [背景] LINE 檔案成功轉發至 Discord")
    except Exception as e:
        print(f"DEBUG: [背景] LINE 檔案轉發失敗: {e}")


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
        abort(400)
    return 'OK'

# 修改：將 FileMessageContent 加入監聽名單
@handler.add(MessageEvent, message=(TextMessageContent, ImageMessageContent, FileMessageContent))
def handle_message(event):
    # 徹底阻擋 LINE 私訊：只允許群組 (group)
    if getattr(event.source, 'type', None) != 'group':
        print(f"DEBUG: 收到 LINE 非群組訊息，已成功濾除。")
        return
    
    group_id = event.source.group_id
    user_id = event.source.user_id

    if not DISCORD_WEBHOOK:
        return

    user_name = "LINE 使用者"
    try:
        with ApiClient(configuration) as api_client:
            line_api = MessagingApi(api_client)
            profile = line_api.get_group_member_profile(group_id, user_id)
            user_name = profile.display_name
    except Exception:
        pass 

    # 使用執行緒將轉發任務丟到背景，讓 Flask 能在秒級內回覆 LINE 200 OK
    if isinstance(event.message, TextMessageContent):
        threading.Thread(target=forward_text_to_discord, args=(event.message.text, user_name), daemon=True).start()

    elif isinstance(event.message, ImageMessageContent):
        threading.Thread(target=forward_image_to_discord, args=(event.message.id, user_name), daemon=True).start()
        
    # 新增：接收到一般檔案時的處理
    elif isinstance(event.message, FileMessageContent):
        file_name = event.message.file_name
        file_size = getattr(event.message, 'file_size', None) # 取得檔案大小（bytes）
        threading.Thread(target=forward_file_to_discord, args=(event.message.id, file_name, file_size, user_name), daemon=True).start()


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