import os
import threading
import discord
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# --- 設定區域 ---
app = Flask(__name__)
LINE_ACCESS_TOKEN = os.getenv("LINEBOT_ACCESS_TOKEN")
LINE_SECRET = os.getenv("LINEBOT_SECRET")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
LINE_GROUP_ID = os.getenv("LINE_GROUP_ID")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_SECRET)

# --- Discord 轉 LINE 的邏輯 (Thread) ---
intents = discord.Intents.default()
intents.message_content = True 
discord_client = discord.Client(intents=intents)

@discord_client.event
async def on_message(message):
    if message.author == discord_client.user or message.webhook_id is not None:
        return
    if DISCORD_CHANNEL_ID and str(message.channel.id) != str(DISCORD_CHANNEL_ID):
        return

    formatted_message = f"[{message.author.display_name}]: {message.content}"
    if message.attachments:
        formatted_message += "\n(發送了附件，請至 Discord 查看)"

    try:
        line_bot_api.push_message(LINE_GROUP_ID, TextSendMessage(text=formatted_message))
    except Exception as e:
        print(f"Discord 轉 LINE 失敗: {e}")

def run_discord_bot():
    discord_client.run(DISCORD_TOKEN)

# --- LINE 轉 Discord 的邏輯 (Flask) ---
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    if event.source.type == 'group' and not LINE_GROUP_ID:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"群組 ID: {event.source.group_id}"))
        return

    try:
        profile = line_bot_api.get_group_member_profile(event.source.group_id, event.source.user_id) if event.source.type == 'group' else line_bot_api.get_profile(event.source.user_id)
        user_name = profile.display_name
    except:
        user_name = "LINE 使用者"

    if DISCORD_WEBHOOK:
        requests.post(DISCORD_WEBHOOK, json={"content": event.message.text, "username": f"{user_name} (LINE)"}, timeout=10)

# --- 主程式啟動 ---
if __name__ == "__main__":
    # 啟動 Discord 執行緒
    threading.Thread(target=run_discord_bot, daemon=True).start()
    # 啟動 Flask 伺服器
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)