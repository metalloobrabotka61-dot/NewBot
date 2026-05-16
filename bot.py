import requests
import time
from datetime import datetime

# ========== НАСТРОЙКИ ==========
TELEGRAM_TOKEN = "8302482854:AAFVRh7y6B7yIX0IVRnLy7Om30uPu_cyGw4"
CHAT_ID = "694614387"

TOP_GAINERS_COUNT = 10
MIN_24H_CHANGE = 5.0
RSI_1H_MIN = 70
CHANGE_4H_MIN = 2.0
VOLUME_24H_MIN = 500_000
CHECK_INTERVAL = 3600
# =================================

# Словарь соответствий символов (верхний регистр) -> ID монеты на CoinGecko
SYMBOL_TO_ID = {
    "SOL": "solana",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "MATIC": "matic-network",
    "DOT": "polkadot",
    "AVAX": "avalanche-2",
    "LINK": "chainlink",
    "LTC": "litecoin",
    "NEAR": "near",
    "ATOM": "cosmos",
    "FIL": "filecoin",
    "ALGO": "algorand",
    "VET": "vechain",
    "ICP": "internet-computer",
    "EGLD": "elrond",
    "THETA": "theta-token",
    "FTM": "fantom",
    "SAND": "the-sandbox",
    "MANA": "decentraland",
    "AXS": "axie-infinity",
    "ENJ": "enjincoin",
    "ZIL": "zilliqa",
    "KLAY": "klay-token",
    "CHZ": "chiliz",
    "ONE": "harmony",
    "ICX": "icon",
    "XTZ": "tezos",
    "AAVE": "aave",
    "BCH": "bitcoin-cash",
    "EOS": "eos",
    "TRX": "tron",
    "XLM": "stellar",
    "ZEC": "zcash",
    "DASH": "dash",
    "NEO": "neo",
    "ONT": "ontology",
    "QTUM": "qtum",
    "WAVES": "waves",
    "KSM": "kusama",
    "RUNE": "thorchain",
    "PEPE": "pepe",
    "WIF": "dogwifhat",
    "BONK": "bonk",
    "FLOKI": "floki",
    "NOT": "notcoin",
    "TON": "the-open-network",
    "OP": "optimism",
    "ARB": "arbitrum",
    "SUI": "sui",
    "APT": "aptos",
    "INJ": "injective-protocol",
    "SEI": "sei-network",
    "TIA": "celestia",
    "PYTH": "pyth-network",
    "JUP": "jupiter",
    "ONDO": "ondo-finance",
    "STRK": "starknet",
    "ENA": "ethena",
    "ETHFI": "ether-fi",
    "1000LUNC": "terra-luna-classic",
    "LUNA2": "terra-luna-2",
    "USTC": "terrausd",
    "ANC": "anchor-protocol",
    "MIR": "mirror-protocol"
}

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})
    except:
        pass

def get_with_retries(url, max_retries=3, delay=2):
    for attempt in range(max_retries):
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            if r.status_code == 200:
                return r.json()
            else:
                print(f"Попытка {attempt+1}: статус {r.status_code}")
        except Exception as e:
            print(f"Попытка {attempt+1}: {e}")
        time.sleep(delay * (attempt+1))
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
    if (rsi_1h > RSI_1H_MIN and change_4h > CHANGE_4H_MIN and 
        coin['volume_24h'] > VOLUME_24H_MIN):
        reasons = [
            f"RSI 1h = {rsi_1h} (>{RSI_1H_MIN}) – зона перекупленности",
            f"рост за 4ч = {change_4h:.2f}% (>{CHANGE_4H_MIN}%) – импульс может ослабнуть",
            f"объём 24ч = {coin['volume_24h']/1e6:.2f}M USDT – высокая ликвидность"
        ]
        explanation = " ".join(reasons) + ". Вероятна коррекция вниз."
        msg = f"""
🔻 <b>SHORT СИГНАЛ</b> <b>{coin['symbol']}</b> | {coin['price']:.4f}

<b>RSI 1h:</b> {rsi_1h}
<b>Изменение 24h:</b> +{coin['change_24h']:.2f}%
<b>Изменение 4h:</b> +{change_4h:.2f}%
<b>Объём 24h:</b> {coin['volume_24h']/1e6:.2f}M USDT

💡 <b>Логическое обоснование:</b> {explanation}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return msg
    return None

def main():
    send_telegram("🚀 Бот (лидеры роста → SHORT-сигналы) запущен.")
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
            time.sleep(1)
        for msg in signals:
            send_telegram(msg)
            time.sleep(2)
        print(f"Цикл завершён. Жду {CHECK_INTERVAL // 60} минут.\n")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()