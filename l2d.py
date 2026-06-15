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
    # --- 全面診斷區塊：強制印出所有 ID ---
    print(f"\n[DEBUG] 收到訊息!")
    print(f"訊息來源類型: {event.source.type}")
    print(f"Sender ID (User): {event.source.sender_id}")
    if hasattr(event.source, 'group_id'):
        print(f"🎉 發現群組 ID (group_id): {event.source.group_id}")
    if hasattr(event.source, 'room_id'):
        print(f"🎉 發現房間 ID (room_id): {event.source.room_id}")
    print(f"=====================================\n")
    # ------------------------------------
    
    # 取得使用者名稱並轉發到 Discord
    user_name = "LINE 使用者"
    try:
        if event.source.type == 'group':
            profile = line_bot_api.get_group_member_profile(event.source.group_id, event.source.sender_id)
            user_name = profile.display_name
        elif event.source.type == 'room':
            profile = line_bot_api.get_room_member_profile(event.source.room_id, event.source.sender_id)
            user_name = profile.display_name
        else:
            profile = line_bot_api.get_profile(event.source.sender_id)
            user_name = profile.display_name
    except Exception as e:
        print(f"取得名稱失敗 (這不影響轉發): {e}")

    if DISCORD_WEBHOOK:
        data = {
            "content": event.message.text,
            "username": f"{user_name} (LINE)"
        }
        res = requests.post(DISCORD_WEBHOOK, json=data)
        print(f"Discord 轉發狀態: {res.status_code}")

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)