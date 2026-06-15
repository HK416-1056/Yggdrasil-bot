import os
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

app = Flask(__name__)

# 環境變數設定
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
    # 1. 偵測 ID 並回傳給 LINE (防止 ID 未知導致無法轉發)
    if event.source.type == 'group' and not os.getenv("LINE_GROUP_ID"):
        group_id = event.source.group_id
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"偵測到群組 ID: {group_id} \n請將此 ID 填入 Render 的 LINE_GROUP_ID 環境變數中！")
        )
        return

    # 2. 獲取使用者名稱
    try:
        if event.source.type == 'group':
            profile = line_bot_api.get_group_member_profile(event.source.group_id, event.source.user_id)
        else:
            profile = line_bot_api.get_profile(event.source.user_id)
        user_name = profile.display_name
    except:
        user_name = "LINE 使用者"

    # 3. 轉發到 Discord 並紀錄狀態
    if DISCORD_WEBHOOK:
        try:
            payload = {"content": event.message.text, "username": f"{user_name} (LINE)"}
            res = requests.post(DISCORD_WEBHOOK, json=payload, timeout=5)
            print(f"DEBUG: Discord Webhook 狀態碼: {res.status_code}")
        except Exception as e:
            print(f"DEBUG: Discord 發送錯誤: {e}")

if __name__ == "__main__":
    # 強制綁定 0.0.0.0 以適應 Render 的外網請求
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)