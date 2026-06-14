#!/bin/bash

# 啟動 Discord 到 LINE 的監聽程序 (背景執行)
echo "Starting Discord to LINE bot (d2l.py)..."
python d2l.py &

# 啟動 LINE 到 Discord 的 Webhook 伺服器 (前景執行，維持 Port 佔用)
echo "Starting LINE to Discord server (l2d.py)..."
python l2d.py