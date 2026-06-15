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
    # 【自動偵測與自首功能】
    if event.source.type == 'group':
        group_id = event.source.group_id
        # 若發現訊息進來但還沒設定過 ID，機器人會直接告訴你它看到了什麼
        print(f"\n>>> 偵測到群組 ID: {group_id} <<<\n")
        
        # 如果你還沒設定 LINE_GROUP_ID，這行會把 ID 傳回 LINE 給你看
        if not os.getenv("LINE_GROUP_ID"):
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"你的群組 ID 是: {group_id} \n請將此 ID 填入 Render 的 LINE_GROUP_ID 環境變數中！")
            )

    # 轉發到 Discord
    try:
        profile = line_bot_api.get_group_member_profile(event.source.group_id, event.source.user_id) if event.source.type == 'group' else line_bot_api.get_profile(event.source.user_id)
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