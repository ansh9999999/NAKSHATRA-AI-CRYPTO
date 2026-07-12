from analysis.indicators import ema, rsi, macd, trend

last_alert = None


def generate_signal(df):

    global last_alert

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    price = float(close.iloc[-1])

    ema9 = float(ema(close, 9).iloc[-1])
    ema21 = float(ema(close, 21).iloc[-1])

    rsi_value = float(rsi(close).iloc[-1])

    macd_line, signal_line, histogram = macd(close)

    macd_value = float(macd_line.iloc[-1])
    macd_signal = float(signal_line.iloc[-1])

    score = 0
    reasons = []

    # EMA
    bullish = ema9 > ema21

    if bullish:
        score += 25
        reasons.append("EMA Bullish")
    else:
        score += 25
        reasons.append("EMA Bearish")

    # RSI
    if bullish and 55 <= rsi_value <= 68:
        score += 20
        reasons.append("Healthy RSI")

    elif (not bullish) and 32 <= rsi_value <= 45:
        score += 20
        reasons.append("Healthy Bearish RSI")

    # MACD
    if bullish and macd_value > macd_signal:
        score += 25
        reasons.append("MACD Bullish")

    elif (not bullish) and macd_value < macd_signal:
        score += 25
        reasons.append("MACD Bearish")

    # Volume Spike
    avg_volume = volume.tail(20).mean()

    if volume.iloc[-1] > avg_volume * 1.5:
        score += 15
        reasons.append("Volume Spike")

    # Breakout
    highest = high.tail(20).max()
    lowest = low.tail(20).min()

    if bullish and price >= highest * 0.999:
        score += 15
        reasons.append("Resistance Breakout")

    if (not bullish) and price <= lowest * 1.001:
        score += 15
        reasons.append("Support Breakdown")

    # Final Signal
    signal = "WAIT"

    if bullish and score >= 80:
        signal = "BIG BUY"

    elif (not bullish) and score >= 80:
        signal = "BIG SELL"

    # Duplicate alert block
    if signal == last_alert:
        signal = "WAIT"

    else:
        if signal != "WAIT":
            last_alert = signal

    return {

        "price": round(price,2),

        "trend": trend(close),

        "signal": signal,

        "confidence": score,

        "ema9": round(ema9,2),

        "ema21": round(ema21,2),

        "rsi": round(rsi_value,2),

        "macd": round(macd_value,4),

        "macd_signal": round(macd_signal,4),

        "reasons": reasons

    }
