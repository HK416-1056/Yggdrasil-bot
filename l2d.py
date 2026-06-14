import os
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage

app = Flask(__name__)

LINE_ACCESS_TOKEN = os.getenv("LINEBOT_ACCESS_TOKEN")
LINE_SECRET = os.getenv("LINEBOT_SECRET")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_SECRET)

@app.route("/", methods=['GET'])
def home():
    return "伺服器正常運作中！", 200

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
    # 🎯 核心功能：印出群組 ID
    if event.source.type == 'group':
        print(f"\n=====================================")
        print(f"🎉 成功抓到群組 ID: {event.source.group_id}")
        print(f"=====================================\n")
    
    # 取得使用者名稱並轉發到 Discord Webhook
    try:
        if event.source.type == 'group':
            profile = line_bot_api.get_group_member_profile(event.source.group_id, event.source.user_id)
        else:
            profile = line_bot_api.get_profile(event.source.user_id)
        user_name = profile.display_name
    except:
        user_name = "LINE 使用者"

    if DISCORD_WEBHOOK:
        data = {
            "content": event.message.text,
            "username": f"{user_name} (LINE)"
        }
        requests.post(DISCORD_WEBHOOK, json=data)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
