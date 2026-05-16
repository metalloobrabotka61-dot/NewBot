import requests
import time
from datetime import datetime

# ========== НАСТРОЙКИ ==========
TELEGRAM_TOKEN = "8695713035:AAELPJ25J5SMbw2Ed6rEW1fiuAtRZ4L9Abc"
CHAT_ID = "694614387"

TOP_GAINERS_COUNT = 3       # анализируем только топ-3 растущих монеты
MIN_24H_CHANGE = 5.0
RSI_1H_MIN = 70
CHANGE_4H_MIN = 2.0
VOLUME_24H_MIN = 500_000
CHECK_INTERVAL = 3600       # 2 часа
DELAY_BETWEEN_COINS = 10    # пауза между анализом монет (сек)
# =================================

SYMBOL_TO_ID = {
    "SOL": "solana", "XRP": "ripple", "ADA": "cardano", "DOGE": "dogecoin",
    "MATIC": "matic-network", "DOT": "polkadot", "AVAX": "avalanche-2",
    "LINK": "chainlink", "LTC": "litecoin", "NEAR": "near", "ATOM": "cosmos",
    "FIL": "filecoin", "ALGO": "algorand", "VET": "vechain", "ICP": "internet-computer",
    "EGLD": "elrond", "THETA": "theta-token", "FTM": "fantom", "SAND": "the-sandbox",
    "MANA": "decentraland", "AXS": "axie-infinity", "ENJ": "enjincoin", "ZIL": "zilliqa",
    "KLAY": "klay-token", "CHZ": "chiliz", "ONE": "harmony", "ICX": "icon",
    "XTZ": "tezos", "AAVE": "aave", "BCH": "bitcoin-cash", "EOS": "eos",
    "TRX": "tron", "XLM": "stellar", "ZEC": "zcash", "DASH": "dash",
    "NEO": "neo", "ONT": "ontology", "QTUM": "qtum", "WAVES": "waves",
    "KSM": "kusama", "RUNE": "thorchain", "PEPE": "pepe", "WIF": "dogwifhat",
    "BONK": "bonk", "FLOKI": "floki", "NOT": "notcoin", "TON": "the-open-network",
    "OP": "optimism", "ARB": "arbitrum", "SUI": "sui", "APT": "aptos",
    "INJ": "injective-protocol", "SEI": "sei-network", "TIA": "celestia",
    "PYTH": "pyth-network", "JUP": "jupiter", "ONDO": "ondo-finance",
    "STRK": "starknet", "ENA": "ethena", "ETHFI": "ether-fi",
    "1000LUNC": "terra-luna-classic", "LUNA2": "terra-luna-2", "USTC": "terrausd",
    "ANC": "anchor-protocol", "MIR": "mirror-protocol", "OSMO": "osmosis",
    "LAB": "lab", "PROS": "pros", "STORJ": "storj", "ORCA": "orca", "ZBT": "zbt"
}

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})
    except:
        pass

def get_with_retries(url, max_retries=5, initial_delay=5):
    for attempt in range(max_retries):
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 429:
                wait = initial_delay * (2 ** attempt)  # 5,10,20,40,80 сек
                print(f"Ошибка 429, жду {wait} сек...")
                time.sleep(wait)
                continue
            else:
                print(f"Попытка {attempt+1}: статус {r.status_code}")
        except Exception as e:
            print(f"Попытка {attempt+1}: {e}")
        if attempt < max_retries - 1:
            time.sleep(initial_delay * (attempt+1))
    return None

def get_top_gainers():
    url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=volume_desc&per_page=100&page=1&sparkline=false"
    data = get_with_retries(url)
    if not isinstance(data, list):
        return []
    exclude = ['btc', 'eth', 'usdt', 'usdc', 'dai', 'busd', 'tusd', 'fdusd']
    gainers = []
    for coin in data:
        sym = coin['symbol'].upper()
        if sym in ['BTC','ETH','USDT','USDC','DAI','BUSD','TUSD','FDUSD']:
            continue
        if coin['id'] in exclude:
            continue
        change = coin.get('price_change_percentage_24h', -100)
        if change >= MIN_24H_CHANGE:
            coin_id = SYMBOL_TO_ID.get(sym, coin['id'])
            gainers.append({
                'id': coin_id,
                'symbol': sym,
                'change_24h': change,
                'price': coin['current_price'],
                'volume_24h': coin['total_volume']
            })
    gainers.sort(key=lambda x: x['change_24h'], reverse=True)
    return gainers[:TOP_GAINERS_COUNT]

def get_historical_prices(coin_id, days=2):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days={days}&interval=hourly"
    data = get_with_retries(url)
    if data and 'prices' in data:
        return [p[1] for p in data['prices']]
    return []

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        gains.append(diff if diff > 0 else 0)
        losses.append(-diff if diff < 0 else 0)
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    return round(100 - 100 / (1 + avg_gain / avg_loss), 2)

def analyze_coin(coin):
    prices = get_historical_prices(coin['id'], days=2)
    if len(prices) < 30:
        return None
    rsi_1h = calculate_rsi(prices, 14)
    if rsi_1h is None:
        return None
    if len(prices) >= 5:
        change_4h = (prices[-1] - prices[-5]) / prices[-5] * 100
    else:
        change_4h = 0

    cond_rsi = rsi_1h > RSI_1H_MIN
    cond_change = change_4h > CHANGE_4H_MIN
    cond_volume = coin['volume_24h'] > VOLUME_24H_MIN

    if cond_rsi and cond_change and cond_volume:
        # --- Динамический расчёт уровней ---
        # Стоп-лосс: половина от роста за 4ч (но не менее 0.5% и не более 2%)
        stop_loss_percent = max(0.5, min(2.0, change_4h / 2))
        # Тейк-профит: от стоп-лосса × 2 до × 3 (но не более 5%)
        tp_min_percent = min(5.0, stop_loss_percent * 2)
        tp_max_percent = min(8.0, stop_loss_percent * 3)

        confidence = sum([cond_rsi, cond_change, cond_volume])
        confidence_text = "🔴 НИЗКАЯ" if confidence < 2 else "🟡 СРЕДНЯЯ" if confidence == 2 else "🟢 ВЫСОКАЯ"
        risk_reward = round((tp_min_percent / stop_loss_percent), 1)

        msg = f"""

 📈  🔻 SHORT СИГНАЛ 🔻                  


<b>Монета:</b> {coin['symbol']}
<b>Цена входа:</b> ${coin['price']:.6f}

📊 <b>Ключевые показатели</b>

 RSI 1h:      {rsi_1h:.1f} {"🔴" if rsi_1h>70 else "🟢"} 
 Рост 24ч:    +{coin['change_24h']:.2f}% 
 Рост 4ч:     +{change_4h:.2f}%          
 Объём 24ч:   {coin['volume_24h']/1e6:.2f}M USDT 


🎯 <b>Рекомендация</b>
• Размер позиции: <b>1.0%</b> депозита
• Стоп-лосс:     <b>{stop_loss_percent:.1f}%</b> (цена +{stop_loss_percent:.1f}%)
• Тейк-профит:   <b>от -{tp_min_percent:.1f}%</b> до <b>-{tp_max_percent:.1f}%</b>

💡 <b>Обоснование</b>
{"" if not cond_rsi else f"• RSI 1h ({rsi_1h:.1f}) находится в зоне перекупленности (>70)."}
{"" if not cond_change else f"• Рост за 4 часа ({change_4h:.2f}%) указывает на возможное истощение импульса."}
{"" if not cond_volume else f"• Объём торгов ({coin['volume_24h']/1e6:.2f}M) подтверждает ликвидность."}
<b>Уверенность сигнала:</b> {confidence_text}

⚠️ <b>Риск-менеджмент</b>
Рекомендуемое соотношение риск/прибыль: 1:{risk_reward:.1f}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return msg
    return None

def main():
    send_telegram("🚀 Бот (лидеры роста → SHORT-сигналы) запущен с консервативными настройками.")
    while True:
        print(f"\n[{datetime.now()}] Поиск монет с ростом > {MIN_24H_CHANGE}%...")
        gainers = get_top_gainers()
        if not gainers:
            print("Нет монет, жду 30 минут.")
            time.sleep(1800)
            continue
        print(f"Найдено лидеров роста: {len(gainers)}")
        signals = []
        for coin in gainers:
            print(f"Анализ {coin['symbol']}...")
            try:
                msg = analyze_coin(coin)
                if msg:
                    signals.append(msg)
            except Exception as e:
                print(f"Ошибка {coin['symbol']}: {e}")
            time.sleep(DELAY_BETWEEN_COINS)
        for msg in signals:
            send_telegram(msg)
            time.sleep(2)
        print(f"Цикл завершён. Жду {CHECK_INTERVAL // 60} минут.\n")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()