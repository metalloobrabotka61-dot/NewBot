import telebot
import requests
import time
import math
from datetime import datetime

# ========== НАСТРОЙКИ ==========
TELEGRAM_TOKEN = "8695713035:AAELPJ25J5SMbw2Ed6rEW1fiuAtRZ4L9Abc"
CHAT_ID = "1779549121"

# Отбор монет
TOP_COINS = 200                     # количество монет (по объёму)
MIN_VOLUME_USD = 400_000            # минимальный 24h объём ($500k)

# Параметры анализа (1-часовые свечи)
CHECK_INTERVAL = 3600               # проверка раз в час
TIMEFRAME = '1h'                    # таймфрейм
LOOKBACK = 100                      # свечей для анализа (4 суток)
MIN_CHANGE_PERCENT = 0.5            # мин. изменение цены за час (%)
LEVERAGE = 10
MIN_AGREEMENT = 3                   # 3 из 7 индикаторов

# Индикаторы (периоды подобраны для 1h)
RSI_PERIOD = 14; RSI_OVERSOLD = 30; RSI_OVERBOUGHT = 70
EMA_SHORT = 9; EMA_LONG = 21
VOLUME_SURGE_FACTOR = 1.5
ADX_PERIOD = 14; ADX_STRONG = 25
SMA50_PERIOD = 50
BB_PERIOD = 20; BB_STD = 2
MIN_VOL_RATIO = 0.8                 # ослаблен
RSI_LIMIT_LONG = 99
RSI_LIMIT_SHORT = 1
# =================================

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ---------- ПОЛУЧЕНИЕ СПИСКА МОНЕТ (CoinGecko) ----------
def get_top_coins_by_volume(limit=TOP_COINS):
    url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=volume_desc&per_page={limit}&page=1&sparkline=false"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        data = r.json()
        if not isinstance(data, list):
            return []
        coins = []
        for coin in data:
            sym = coin['symbol'].upper()
            # Исключаем стейблкоины и BTC/ETH (опционально)
            if sym in ['BTC','ETH','USDT','USDC','DAI','BUSD','TUSD','FDUSD']:
                continue
            if 'stable' in coin['name'].lower():
                continue
            vol = coin.get('total_volume', 0)
            if vol >= MIN_VOLUME_USD:
                coins.append({
                    'symbol': sym,
                    'volume': vol,
                    'price': coin.get('current_price', 0)
                })
        print(f"Найдено монет: {len(coins)}")
        if coins:
            print("Примеры:", [c['symbol'] for c in coins[:5]])
        return coins[:limit]
    except Exception as e:
        print(f"Ошибка CoinGecko: {e}")
        return []

# ---------- ПОЛУЧЕНИЕ ИСТОРИЧЕСКИХ ЦЕН (часовые свечи) ----------
def get_coin_history(coin_id, days=7):
    """Возвращает массивы close, high, low (часовые) за последние days дней"""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days={days}&interval=hourly"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        data = r.json()
        prices = data.get('prices', [])
        if not prices:
            return [], [], []
        closes = [p[1] for p in prices]
        # Эмулируем high/low через локальные максимумы/минимумы (окно 3 часа)
        highs = []
        lows = []
        for i in range(len(closes)):
            window = closes[max(0,i-3):i+1]
            highs.append(max(window))
            lows.append(min(window))
        return closes, highs, lows
    except Exception as e:
        print(f"Ошибка истории для {coin_id}: {e}")
        return [], [], []

# ---------- ИНДИКАТОРЫ ----------
def calculate_rsi(closes, period=14):
    if len(closes) < period+1: return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i]-closes[i-1]
        gains.append(diff if diff>0 else 0)
        losses.append(-diff if diff<0 else 0)
    avg_gain = sum(gains[-period:])/period
    avg_loss = sum(losses[-period:])/period
    if avg_loss == 0: return 100
    return 100 - 100/(1+avg_gain/avg_loss)

def calculate_ema(closes, period):
    if len(closes) < period: return None
    mult = 2/(period+1)
    ema = closes[0]
    for p in closes[1:]: ema = (p-ema)*mult+ema
    return ema

def calculate_sma(closes, period):
    if len(closes) < period: return None
    return sum(closes[-period:])/period

def calculate_bollinger_bands(closes, period=20, std=2):
    if len(closes) < period: return None, None, None
    last = closes[-period:]
    sma = sum(last)/period
    var = sum((p-sma)**2 for p in last)/period
    stdev = math.sqrt(var)
    return sma+std*stdev, sma-std*stdev, sma

def calculate_macd_diff(closes, fast=12, slow=26):
    ema_f = calculate_ema(closes, fast)
    ema_s = calculate_ema(closes, slow)
    return ema_f - ema_s if ema_f and ema_s else None

def calculate_adx(highs, lows, closes, period=14):
    # Упрощённо: используем RSI от ATR, но для простоты вернём None
    return None

def find_fibo_levels(highs, lows, closes):
    if len(closes) < 100: return {}
    max_price = max(closes[-100:])
    min_price = min(closes[-100:])
    diff = max_price - min_price
    levels = {}
    for level in [0.236, 0.382, 0.5, 0.618, 0.786]:
        levels[level] = min_price + diff * level
    return levels

def find_support_resistance(highs, lows, current_price):
    # Используем последние 20 свечей
    recent_highs = highs[-20:] if len(highs)>=20 else highs
    recent_lows = lows[-20:] if len(lows)>=20 else lows
    support = min(recent_lows) if recent_lows else current_price*0.99
    resistance = max(recent_highs) if recent_highs else current_price*1.01
    return support, resistance

def calculate_tp_sl_from_levels(price, support, resistance, fibo_levels, direction):
    if direction == 'long':
        sl = support * 0.995 if support else price * 0.985
        sl_percent = (price - sl) / price * 100
        tp_candidates = [resistance] if resistance else []
        for level in [0.382, 0.5]:
            if level in fibo_levels and fibo_levels[level] > price:
                tp_candidates.append(fibo_levels[level])
        tp = min(tp_candidates) if tp_candidates else price * 1.02
        tp_percent = (tp - price) / price * 100
        explanation = f"SL ниже поддержки {support:.6f}, TP к {tp:.6f}"
    else:
        sl = resistance * 1.005 if resistance else price * 1.015
        sl_percent = (sl - price) / price * 100
        tp_candidates = [support] if support else []
        for level in [0.618, 0.5]:
            if level in fibo_levels and fibo_levels[level] < price:
                tp_candidates.append(fibo_levels[level])
        tp = max(tp_candidates) if tp_candidates else price * 0.98
        tp_percent = (price - tp) / price * 100
        explanation = f"SL выше сопротивления {resistance:.6f}, TP к {tp:.6f}"
    return tp, sl, round(tp_percent,2), round(sl_percent,2), explanation

def analyze_coin(coin):
    symbol = coin['symbol'].lower()
    closes, highs, lows = get_coin_history(symbol, days=7)
    if len(closes) < 80:
        return None
    current_price = closes[-1]
    change_1h = (closes[-1] - closes[-2]) / closes[-2] * 100 if len(closes)>=2 else 0
    if abs(change_1h) < MIN_CHANGE_PERCENT:
        return None
    
    rsi = calculate_rsi(closes, RSI_PERIOD)
    if rsi is None: return None
    
    # Индикаторы
    ind = {}
    desc = {}
    if rsi < RSI_OVERSOLD:
        ind['rsi']='long'
        desc['rsi']=f"RSI={rsi:.1f} перепродан"
    elif rsi > RSI_OVERBOUGHT:
        ind['rsi']='short'
        desc['rsi']=f"RSI={rsi:.1f} перекуплен"
    else:
        desc['rsi']=f"RSI={rsi:.1f} нейтр."
    
    ema_s = calculate_ema(closes, EMA_SHORT)
    ema_l = calculate_ema(closes, EMA_LONG)
    if ema_s and ema_l:
        if ema_s > ema_l:
            ind['ema']='long'
            desc['ema']=f"EMA{EMA_SHORT}>{EMA_LONG}"
        else:
            ind['ema']='short'
            desc['ema']=f"EMA{EMA_SHORT}<{EMA_LONG}"
    
    bb_up, bb_low, _ = calculate_bollinger_bands(closes, BB_PERIOD, BB_STD)
    if bb_up and bb_low:
        if current_price < bb_low:
            ind['bb']='long'
            desc['bb']="Цена ниже нижней полосы"
        elif current_price > bb_up:
            ind['bb']='short'
            desc['bb']="Цена выше верхней полосы"
        else:
            desc['bb']="Цена внутри полос"
    
    macd = calculate_macd_diff(closes, 12, 26)
    if macd is not None:
        if macd>0:
            ind['macd']='long'
            desc['macd']="MACD положительный"
        else:
            ind['macd']='short'
            desc['macd']="MACD отрицательный"
    
    sma50 = calculate_sma(closes, SMA50_PERIOD)
    if sma50:
        if current_price > sma50:
            ind['sma50']='long'
            desc['sma50']="Цена выше SMA50"
        else:
            ind['sma50']='short'
            desc['sma50']="Цена ниже SMA50"
    
    # Объём и ADX опускаем (нет данных)
    votes = [ind.get(k) for k in ['rsi','ema','bb','macd','sma50'] if ind.get(k) is not None]
    long_votes = votes.count('long')
    short_votes = votes.count('short')
    direction = None
    if long_votes >= MIN_AGREEMENT:
        direction = 'long'
    elif short_votes >= MIN_AGREEMENT:
        direction = 'short'
    if not direction:
        return None
    
    support, resistance = find_support_resistance(highs, lows, current_price)
    fibo = find_fibo_levels(highs, lows, closes)
    tp_price, sl_price, tp_pct, sl_pct, level_exp = calculate_tp_sl_from_levels(
        current_price, support, resistance, fibo, direction
    )
    
    msg = f"""
{'🟢 LONG' if direction=='long' else '🔴 SHORT'} СИГНАЛ ({coin['symbol']})

• Согласие индикаторов: {long_votes if direction=='long' else short_votes}/5
💰 Вход: ${current_price:.6f}
🎯 TP (уровень): ${tp_price:.6f} ({'+' if direction=='long' else ''}{tp_pct}%)
🛑 SL (уровень): ${sl_price:.6f} ({'-' if direction=='long' else ''}{sl_pct}%)
⚙️ Плечо: {LEVERAGE}x

📊 Индикаторы:
• {desc['rsi']}
• {desc['ema']}
• {desc['bb']}
• {desc['macd']}
• {desc['sma50']}

📍 {level_exp}
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    return msg

def main():
    print(f"Бот запущен. Анализ топ-{TOP_COINS} монет (CoinGecko) каждые {CHECK_INTERVAL//60} мин.")
    while True:
        try:
            coins = get_top_coins_by_volume(TOP_COINS)
            if not coins:
                print("Нет монет, повтор через 60 сек")
                time.sleep(60)
                continue
            print(f"Начинаю анализ {len(coins)} монет...")
            for coin in coins:
                print(f"Анализирую {coin['symbol']}")
                signal = analyze_coin(coin)
                if signal:
                    bot.send_message(CHAT_ID, signal, parse_mode='HTML')
                    time.sleep(1)
                time.sleep(1)  # пауза между запросами к CoinGecko
            print(f"{datetime.now()} - Цикл анализа завершён")
        except Exception as e:
            print(f"Ошибка: {e}")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()