import requests
import time
from datetime import datetime

# ========== НАСТРОЙКИ ==========
TELEGRAM_TOKEN = "8695713035:AAELPJ25J5SMbw2Ed6rEW1fiuAtRZ4L9Abc"
CHAT_ID = "694614387"

TOP_GAINERS_COUNT = 6        # анализируем 6 лучших по росту
MIN_24H_CHANGE = 5.0         # минимальный рост за 24ч (%)
RSI_1H_MIN = 70
CHANGE_4H_MIN = 2.0
VOLUME_24H_MIN = 500_000
CHECK_INTERVAL = 7200        # 2 часа (можно уменьшить до 3600)
DELAY_BETWEEN_COINS = 10     # пауза между анализом монет (сек)
MAX_MARKET_CAP = 500_000_000 # исключаем монеты с капой > $500M
# =================================

# ---------- ПОЛУЧЕНИЕ СПИСКА ФЬЮЧЕРСНЫХ ПАР С BINGX ----------
def get_bingx_futures_symbols():
    """
    Получает список всех фьючерсных пар (USDT-M) с BingX.
    Возвращает множество символов в формате 'BTCUSDT'.
    """
    url = "https://open-api.bingx.com/openApi/swap/v2/quote/contracts"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            print(f"Ошибка получения списка фьючерсов BingX: HTTP {r.status_code}")
            return set()
        data = r.json()
        if data.get('code') != 0:
            print(f"Ошибка API BingX: {data.get('msg')}")
            return set()
        # Извлекаем символы из ответа
        symbols = set()
        for contract in data.get('data', []):
            # Нас интересуют только USDT-M фьючерсы
            if contract.get('quoteAsset') == 'USDT':
                symbols.add(contract['symbol'])
        print(f"Загружено {len(symbols)} фьючерсных пар с BingX")
        return symbols
    except Exception as e:
        print(f"Ошибка соединения с BingX: {e}")
        return set()

# ---------- ПОЛУЧЕНИЕ СПИСКА МОНЕТ ДЛЯ АНАЛИЗА ----------
def get_midcap_coins():
    """Получает список монет с капитализацией < MAX_MARKET_CAP из топ-500 по капитализации."""
    all_coins = []
    for page in range(1, 3):  # страницы 1 и 2 по 250 монет
        url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page={page}&sparkline=false"
        data = get_with_retries(url)
        if not isinstance(data, list):
            continue
        for coin in data:
            sym = coin['symbol'].upper()
            if sym in ['BTC','ETH','USDT','USDC','DAI','BUSD','TUSD','FDUSD']:
                continue
            market_cap = coin.get('market_cap', 0)
            if market_cap > MAX_MARKET_CAP:
                continue
            change = coin.get('price_change_percentage_24h')
            if change is None:
                continue  # пропускаем монеты без данных
            all_coins.append({
                'symbol': sym,
                'id': coin['id'],
                'market_cap': market_cap,
                'volume': coin['total_volume'],
                'price': coin['current_price'],
                'change_24h': change
            })
        time.sleep(2)
    # Сортируем по росту за 24ч (убывание)
    all_coins.sort(key=lambda x: x['change_24h'], reverse=True)
    return all_coins

def filter_by_bingx_futures(coins, futures_symbols):
    """
    Оставляет только монеты, которые есть в списке фьючерсов BingX.
    Символы в coins представлены как 'BTC', а в futures_symbols как 'BTCUSDT'.
    """
    filtered = []
    for coin in coins:
        if f"{coin['symbol']}USDT" in futures_symbols:
            filtered.append(coin)
    print(f"Из {len(coins)} монет после фильтрации по фьючерсам BingX осталось {len(filtered)}")
    return filtered

def get_top_gainers():
    # Шаг 1: Получаем список фьючерсных пар BingX
    bingx_futures = get_bingx_futures_symbols()
    if not bingx_futures:
        print("Не удалось получить список фьючерсов BingX. Фильтрация отключена.")
        # Если список не загрузился, возвращаем все монеты (но так лучше не делать)
        coins = get_midcap_coins()
        gainers = [c for c in coins if c['change_24h'] >= MIN_24H_CHANGE]
        print(f"Найдено монет с ростом > {MIN_24H_CHANGE}%: {len(gainers)}")
        return gainers[:TOP_GAINERS_COUNT]

    # Шаг 2: Получаем монеты из CoinGecko
    all_coins = get_midcap_coins()
    # Шаг 3: Фильтруем только те, что есть на фьючерсах BingX
    filtered_coins = filter_by_bingx_futures(all_coins, bingx_futures)
    # Шаг 4: Оставляем только те, которые выросли более чем на MIN_24H_CHANGE
    gainers = [c for c in filtered_coins if c['change_24h'] >= MIN_24H_CHANGE]
    print(f"Найдено монет с ростом > {MIN_24H_CHANGE}%: {len(gainers)}")
    return gainers[:TOP_GAINERS_COUNT]

# ---------- ФУНКЦИИ ДЛЯ РАБОТЫ С API ----------
def get_with_retries(url, max_retries=5, initial_delay=5):
    for attempt in range(max_retries):
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 429:
                wait = initial_delay * (2 ** attempt)
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
    cond_volume = coin['volume'] > VOLUME_24H_MIN

    if cond_rsi and cond_change and cond_volume:
        # Динамический стоп-лосс и тейк
        stop_loss_percent = max(0.5, min(2.0, change_4h / 2))
        tp_min_percent = min(5.0, stop_loss_percent * 2)
        tp_max_percent = min(8.0, stop_loss_percent * 3)

        confidence = sum([cond_rsi, cond_change, cond_volume])
        confidence_text = "🔴 НИЗКАЯ" if confidence < 2 else "🟡 СРЕДНЯЯ" if confidence == 2 else "🟢 ВЫСОКАЯ"
        risk_reward = round((tp_min_percent / stop_loss_percent), 1)

        msg = f"""

   🔻 SHORT СИГНАЛ 🔻                  


<b>Монета:</b> {coin['symbol']}
<b>Цена входа:</b> ${coin['price']:.6f}

📊 <b>Ключевые показатели</b>

 RSI 1h:      {rsi_1h:.1f} {"🔴" if rsi_1h>70 else "🟢"} 
 Рост 24ч:    +{coin['change_24h']:.2f}% 
 Рост 4ч:     +{change_4h:.2f}%          
 Объём 24ч:   {coin['volume']/1e6:.2f}M USDT 


🎯 <b>Рекомендация</b>
• Размер позиции: <b>1.0%</b> депозита
• Стоп-лосс:     <b>{stop_loss_percent:.1f}%</b> (цена +{stop_loss_percent:.1f}%)
• Тейк-профит:   <b>от -{tp_min_percent:.1f}%</b> до <b>-{tp_max_percent:.1f}%</b>

💡 <b>Обоснование</b>
{"" if not cond_rsi else f"• RSI 1h ({rsi_1h:.1f}) находится в зоне перекупленности (>70)."}
{"" if not cond_change else f"• Рост за 4 часа ({change_4h:.2f}%) указывает на возможное истощение импульса."}
{"" if not cond_volume else f"• Объём торгов ({coin['volume']/1e6:.2f}M) подтверждает ликвидность."}
<b>Уверенность сигнала:</b> {confidence_text}

⚠️ <b>Риск-менеджмент</b>
Рекомендуемое соотношение риск/прибыль: 1:{risk_reward:.1f}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return msg
    return None

def main():
    send_telegram("🚀 Бот (фьючерсы BingX, SHORT-сигналы) запущен.")
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