import requests
import time
from datetime import datetime

TELEGRAM_TOKEN = "8695713035:AAELPJ25J5SMbw2Ed6rEW1fiuAtRZ4L9Abc"
CHAT_ID = "694614387"

COINS = ["SOL", "XRP", "ADA", "DOGE", "MATIC", "DOT", "AVAX", "LINK"]

def send(t):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": t, "parse_mode": "HTML"})

def get_klines(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}USDT&interval=4h&limit=2"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if len(data) == 2:
            return float(data[0][4]), float(data[1][4])
    except:
        pass
    return None, None

def scan():
    send("🔄 Сканирование...")
    for sym in COINS:
        old, new = get_klines(sym)
        if old is None:
            continue
        change = (new - old) / old * 100
        if change > 0.5:
            send(f"🔻 {sym} вырос на {change:.2f}% за 4ч | цена {new:.4f}")
        time.sleep(1)
    send("✅ Цикл завершён")

if __name__ == "__main__":
    send("🚀 Бот запущен на Render")
    while True:
        scan()
        time.sleep(3600)