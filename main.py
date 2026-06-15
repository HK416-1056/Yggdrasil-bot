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

# --- Discord 機器人 ---
intents = discord.Intents.default()
intents.message_content = True 
discord_client = discord.Client(intents=intents)

@discord_client.event
async def on_message(message):
    if message.author == discord_client.user: return
    # 簡單轉發
    formatted = f"[{message.author.display_name}]: {message.content}"
    with ApiClient(configuration) as api_client:
        line_api = MessagingApi(api_client)
        line_api.push_message(PushMessageRequest(to=LINE_GROUP_ID, messages=[LineTextMessage(text=formatted)]))

# --- LINE 轉 Discord ---
@app.route("/", methods=['GET'])
def health(): return "OK", 200

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except Exception as e:
        print(f"Error: {e}")
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    if DISCORD_WEBHOOK:
        requests.post(DISCORD_WEBHOOK, json={"content": event.message.text, "username": "LINE User"})

if __name__ == "__main__":
    threading.Thread(target=lambda: discord_client.run(DISCORD_TOKEN), daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))