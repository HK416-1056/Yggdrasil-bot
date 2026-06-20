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
    ImageMessage as LineImageMessage,
    VideoMessage as LineVideoMessage,   
    AudioMessage as LineAudioMessage    
)
# 新增了 VideoMessageContent 和 AudioMessageContent
from linebot.v3.webhooks import (
    MessageEvent, 
    TextMessageContent, 
    ImageMessageContent, 
    VideoMessageContent, 
    AudioMessageContent, 
    FileMessageContent
)

app = Flask(__name__)

# --- 設定 ---
configuration = Configuration(access_token=os.getenv("LINEBOT_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINEBOT_SECRET"))
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
LINE_GROUP_ID = os.getenv("LINE_GROUP_ID")
MESSAGE_CHANNEL_ID = os.getenv("MESSAGE_CHANNEL_ID")  # 指定轉發的 Discord 頻道 ID

# 預設影片預覽圖
DEFAULT_VIDEO_PREVIEW_URL = "https://via.placeholder.com/1024x768.png?text=Video+Preview"

# --- Discord ---
intents = discord.Intents.default()
intents.message_content = True 
discord_client = discord.Client(intents=intents)

@discord_client.event
async def on_ready():
    print(f"DEBUG: Discord 機器人已成功連線，帳號: {discord_client.user}")

@discord_client.event
async def on_message(message):
    if message.author.bot or message.webhook_id: 
        return
    if not message.guild: 
        return 
    if MESSAGE_CHANNEL_ID and str(message.channel.id) != MESSAGE_CHANNEL_ID:
        return

    print(f"DEBUG: 偵測到指定 Discord 頻道訊息! 內容: {message.content}")
    messages_to_send = []
    
    if message.content:
        messages_to_send.append(LineTextMessage(text=f"[{message.author.display_name}]: {message.content}"))
    elif not message.content and message.attachments:
        messages_to_send.append(LineTextMessage(text=f"[{message.author.display_name}] 傳送了附件:"))

    for att in message.attachments:
        content_type = att.content_type or ""

        if content_type.startswith('image/'):
            messages_to_send.append(LineImageMessage(
                original_content_url=att.url,
                preview_image_url=att.url
            ))
        elif content_type.startswith('video/') and 'mp4' in content_type:
            messages_to_send.append(LineVideoMessage(
                original_content_url=att.url,
                preview_image_url=DEFAULT_VIDEO_PREVIEW_URL
            ))
            messages_to_send.append(LineTextMessage(
                text=f"🎬 [影片附件]: {att.filename}\n🔗 若無法播放，請點此觀看: {att.url}"
            ))
        elif content_type.startswith('audio/'):
            duration_ms = getattr(att, 'duration_secs', 60) * 1000
            messages_to_send.append(LineAudioMessage(
                original_content_url=att.url,
                duration=int(duration_ms)
            ))
        else:
            file_message = (
                f"📁 [附件檔案]: {att.filename}\n"
                f"🔗 點此下載: {att.url}\n"
                f"(⚠️ 提醒: Discord 附件連結通常會在 24 小時後失效)"
            )
            messages_to_send.append(LineTextMessage(text=file_message))

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
        if hasattr(e, 'status') and hasattr(e, 'body'):
            print(f"❌ [錯誤] LINE API 拒絕了這則訊息！狀態碼: {e.status}")
            print(f"❌ [錯誤] 詳細原因: {e.body}")
        else:
            print(f"DEBUG: Discord 轉 LINE 發生錯誤: {e}")


# --- 獨立的背景處理函數 ---
def forward_text_to_discord(text, user_name):
    requests.post(DISCORD_WEBHOOK, json={"content": text, "username": f"{user_name} (LINE)"})
    print("DEBUG: [背景] LINE 文字成功轉發至 Discord")

def forward_image_to_discord(message_id, user_name):
    try:
        with ApiClient(configuration) as api_client:
            blob_api = MessagingApiBlob(api_client)
            image_data = blob_api.get_message_content(message_id)
            files = {"file": ("image.jpg", image_data, "image/jpeg")}
            requests.post(DISCORD_WEBHOOK, data={"username": f"{user_name} (LINE)"}, files=files)
            print("DEBUG: [背景] LINE 圖片成功轉發至 Discord")
    except Exception as e:
        print(f"DEBUG: [背景] LINE 圖片轉發失敗: {e}")

# 新增：專門處理影片的轉發函數
def forward_video_to_discord(message_id, user_name):
    try:
        print("DEBUG: [背景] 準備下載 LINE 影片...")
        with ApiClient(configuration) as api_client:
            blob_api = MessagingApiBlob(api_client)
            video_data = blob_api.get_message_content(message_id)
            
            # 檢查是否超過 Discord 25MB 限制
            if len(video_data) > 25 * 1024 * 1024:
                error_msg = f"⚠️ [{user_name}] 傳送的影片超過 25MB 限制，無法轉發至 Discord。"
                requests.post(DISCORD_WEBHOOK, json={"content": error_msg, "username": "系統通知"})
                return

            files = {"file": ("video.mp4", video_data, "video/mp4")}
            requests.post(DISCORD_WEBHOOK, data={"username": f"{user_name} (LINE)"}, files=files)
            print("DEBUG: [背景] LINE 影片成功轉發至 Discord")
    except Exception as e:
        print(f"DEBUG: [背景] LINE 影片轉發失敗: {e}")

# 新增：專門處理語音的轉發函數
def forward_audio_to_discord(message_id, user_name):
    try:
        print("DEBUG: [背景] 準備下載 LINE 語音...")
        with ApiClient(configuration) as api_client:
            blob_api = MessagingApiBlob(api_client)
            audio_data = blob_api.get_message_content(message_id)
            
            if len(audio_data) > 25 * 1024 * 1024:
                return

            files = {"file": ("audio.m4a", audio_data, "audio/mp4")}
            requests.post(DISCORD_WEBHOOK, data={"username": f"{user_name} (LINE)"}, files=files)
            print("DEBUG: [背景] LINE 語音成功轉發至 Discord")
    except Exception as e:
        print(f"DEBUG: [背景] LINE 語音轉發失敗: {e}")

def forward_file_to_discord(message_id, file_name, file_size, user_name):
    MAX_SIZE = 25 * 1024 * 1024
    if file_size and file_size > MAX_SIZE:
        error_msg = f"⚠️ [{user_name}] 傳送的檔案「{file_name}」超過 25MB 限制，無法轉發至 Discord。"
        requests.post(DISCORD_WEBHOOK, json={"content": error_msg, "username": "系統通知"})
        return

    try:
        print(f"DEBUG: [背景] 準備下載 LINE 檔案 ({file_name})...")
        with ApiClient(configuration) as api_client:
            blob_api = MessagingApiBlob(api_client)
            file_data = blob_api.get_message_content(message_id)
            
            if len(file_data) > MAX_SIZE:
                return

            files = {"file": (file_name, file_data)}
            requests.post(DISCORD_WEBHOOK, data={"username": f"{user_name} (LINE)"}, files=files)
            print("DEBUG: [背景] LINE 檔案成功轉發至 Discord")
    except Exception as e:
        print(f"DEBUG: [背景] LINE 檔案轉發失敗: {e}")


# --- Flask / LINE Webhook ---
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

# 這裡也補上了 VideoMessageContent 和 AudioMessageContent
@handler.add(MessageEvent, message=(TextMessageContent, ImageMessageContent, VideoMessageContent, AudioMessageContent, FileMessageContent))
def handle_message(event):
    if getattr(event.source, 'type', None) != 'group':
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

    # 依照訊息類型丟到對應的背景處理
    if isinstance(event.message, TextMessageContent):
        threading.Thread(target=forward_text_to_discord, args=(event.message.text, user_name), daemon=True).start()
    elif isinstance(event.message, ImageMessageContent):
        threading.Thread(target=forward_image_to_discord, args=(event.message.id, user_name), daemon=True).start()
    elif isinstance(event.message, VideoMessageContent):
        threading.Thread(target=forward_video_to_discord, args=(event.message.id, user_name), daemon=True).start()
    elif isinstance(event.message, AudioMessageContent):
        threading.Thread(target=forward_audio_to_discord, args=(event.message.id, user_name), daemon=True).start()
    elif isinstance(event.message, FileMessageContent):
        file_name = event.message.file_name
        file_size = getattr(event.message, 'file_size', None)
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