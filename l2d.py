import os
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage

app = Flask(__name__)
line_bot_api = LineBotApi(os.getenv("LINEBOT_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINEBOT_SECRET"))

@app.route("/callback", methods=['POST'])
def callback():
    handler.handle(request.get_data(as_text=True), request.headers['X-Line-Signature'])
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    # 這一行會直接把 ID 傳回給你，這是最直接的 ID 獲取方式
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"你的 ID 是: {event.source.sender_id} | 群組: {getattr(event.source, 'group_id', '無') }"))

if __name__ == "__main__":
    app.run(port=int(os.environ.get('PORT', 5000)))