import os
import discord
from linebot import LineBotApi
from linebot.models import TextSendMessage

# 從環境變數讀取金鑰
DISCORD_TOKEN = os.getenv("DISCORDBOT_TOKEN")
LINE_ACCESS_TOKEN = os.getenv("LINEBOT_ACCESS_TOKEN")
LINE_GROUP_ID = os.getenv("LINE_GROUP_ID")
DISCORD_CHANNEL_ID = os.getenv("MESSAGE_CHANNEL_ID")

# 初始化 LINE API
line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)

# 初始化 Discord 機器人
intents = discord.Intents.default()
intents.message_content = True 
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"成功登入！Discord 機器人已上線：{client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.webhook_id is not None:
        return

    if DISCORD_CHANNEL_ID and str(message.channel.id) != str(DISCORD_CHANNEL_ID):
        return

    formatted_message = f"[{message.author.display_name}]: {message.content}"
    if message.attachments:
        formatted_message += "\n(發送了附件，請至 Discord 查看)"

    try:
        # 使用官方 API 推播至 LINE
        line_bot_api.push_message(
            LINE_GROUP_ID,
            TextSendMessage(text=formatted_message)
        )
        print(f"轉發成功: {formatted_message}")
    except Exception as e:
        print(f"轉發失敗: {e}")

if __name__ == "__main__":
    if not DISCORD_TOKEN or not LINE_ACCESS_TOKEN or not LINE_GROUP_ID:
        print("【錯誤】缺少 DISCORDBOT_TOKEN, LINEBOT_ACCESS_TOKEN 或 LINE_GROUP_ID")
    else:
        client.run(DISCORD_TOKEN)