import os
import discord
from linebot import LineBotApi
from linebot.models import TextSendMessage

# 1. 從環境變數讀取金鑰
DISCORD_TOKEN = os.getenv("DISCORDBOT_TOKEN")
LINE_ACCESS_TOKEN = os.getenv("LINEBOT_ACCESS_TOKEN")
LINE_GROUP_ID = os.getenv("LINE_GROUP_ID")
DISCORD_CHANNEL_ID = os.getenv("MESSAGE_CHANNEL_ID")

# 2. 初始化 LINE 官方 API (取代舊版的 lotify)
line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)

# 3. 初始化 Discord 機器人 (啟用讀取訊息意圖)
intents = discord.Intents.default()
intents.message_content = True 
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"成功登入！Discord 機器人已上線：{client.user}")

@client.event
async def on_message(message):
    # 排除機器人自己的訊息
    if message.author == client.user:
        return

    # ⚠️ 極度重要：排除 Webhook 發送的訊息，避免雙向無限迴圈洗版
    if message.webhook_id is not None:
        return

    # 如果有設定特定 Discord 頻道 ID，則只轉發該頻道的訊息
    if DISCORD_CHANNEL_ID and str(message.channel.id) != str(DISCORD_CHANNEL_ID):
        return

    # 組合訊息格式：[Discord使用者名稱]: 訊息內容
    formatted_message = f"[{message.author.display_name}]: {message.content}"
    
    # 若有附件則加上提示文字
    if message.attachments:
        formatted_message += "\n(發送了附件，請至 Discord 查看)"

    try:
        # 使用官方 Messaging API 主動推播 (Push Message) 至指定群組
        line_bot_api.push_message(
            LINE_GROUP_ID,
            TextSendMessage(text=formatted_message)
        )
        print(f"轉發成功: {formatted_message}")
    except Exception as e:
        print(f"轉發失敗，錯誤訊息: {e}")

# 啟動 Discord 機器人服務
if __name__ == "__main__":
    if not DISCORD_TOKEN or not LINE_ACCESS_TOKEN or not LINE_GROUP_ID:
        print("【系統錯誤】缺少 DISCORDBOT_TOKEN, LINEBOT_ACCESS_TOKEN 或 LINE_GROUP_ID 環境變數")
    else:
        client.run(DISCORD_TOKEN)