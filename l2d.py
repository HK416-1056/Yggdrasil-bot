import os
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

app = Flask(__name__)

LINE_ACCESS_TOKEN = os.getenv("LINEBOT_ACCESS_TOKEN")
LINE_SECRET = os.getenv("LINEBOT_SECRET")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_SECRET)

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
    # --- 自動抓取 ID 並回傳給 LINE ---
    if event.source.type == 'group':
        group_id = event.source.group_id
        # 若機器人發現這是一個群組，且我們還沒設定 LINE_GROUP_ID，它會主動回傳 ID
        if not os.getenv("LINE_GROUP_ID"):
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"偵測到群組 ID: {group_id} \n請將此 ID 填入 Render 的 LINE_GROUP_ID 環境變數中！")
            )
            return # 回傳後結束，避免重複 Token 錯誤

    # --- 原本的轉發邏輯 ---
    try:
        if event.source.type == 'group':
            profile = line_bot_api.get_group_member_profile(event.source.group_id, event.source.user_id)
        else:
            profile = line_bot_api.get_profile(event.source.user_id)
        user_name = profile.display_name
    except:
        user_name = "LINE 使用者"

    if DISCORD_WEBHOOK:
        requests.post(DISCORD_WEBHOOK, json={
            "content": event.message.text,
            "username": f"{user_name} (LINE)"
        })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))