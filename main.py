import os
import threading
import asyncio
import discord
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

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

# --- Discord 轉 LINE ---
intents = discord.Intents.default()
intents.message_content = True 
discord_client = discord.Client(intents=intents)

@discord_client.event
async def on_ready():
    print(f"DEBUG: Discord 機器人已成功登入為 {discord_client.user}")

@discord_client.event
async def on_message(message):
    if message.author == discord_client.user or message.webhook_id is not None:
        return
    if DISCORD_CHANNEL_ID and str(message.channel.id) != str(DISCORD_CHANNEL_ID):
        return

    formatted_message = f"[{message.author.display_name}]: {message.content}"
    try:
        line_bot_api.push_message(LINE_GROUP_ID, TextSendMessage(text=formatted_message))
        print(f"DEBUG: 成功轉發至 LINE: {message.content}")
    except Exception as e:
        print(f"DEBUG: 轉發至 LINE 失敗: {e}")

# --- LINE 轉 Discord ---
@app.route("/", methods=['GET'])
def health_check():
    return "Bot is running!", 200

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    print(f"DEBUG: 收到 LINE 請求") # 確認請求是否有進來
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    # 轉發至 Discord
    if DISCORD_WEBHOOK:
        user_name = "LINE 使用者"
        try:
            # 嘗試取得用戶名稱 (這裡不強制中斷)
            profile = line_bot_api.get_group_member_profile(event.source.group_id, event.source.user_id) if event.source.type == 'group' else line_bot_api.get_profile(event.source.user_id)
            user_name = profile.display_name
        except:
            pass
        
        payload = {"content": event.message.text, "username": f"{user_name} (LINE)"}
        res = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
        print(f"DEBUG: Discord Webhook 回應狀態: {res.status_code}")

# --- 啟動機制 ---
def run_discord():
    # 在新的事件迴圈中執行 Discord
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    discord_client.run(DISCORD_TOKEN)

if __name__ == "__main__":
    # 使用線程啟動 Discord
    threading.Thread(target=run_discord, daemon=True).start()
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)