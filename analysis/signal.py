from analysis.indicators import (
    ema,
    rsi,
    macd,
    trend
)


def generate_signal(df):

    close = df["close"]

    price = float(close.iloc[-1])

    ema9 = float(ema(close, 9).fillna(0).iloc[-1])
    ema21 = float(ema(close, 21).fillna(0).iloc[-1])

    rsi_value = float(rsi(close).fillna(50).iloc[-1])

    macd_line, signal_line, histogram = macd(close)

    macd_value = float(macd_line.fillna(0).iloc[-1])
    macd_signal = float(signal_line.fillna(0).iloc[-1])

    score = 0
    reasons = []

    # EMA
    if ema9 > ema21:
        score += 30
        reasons.append("EMA9 above EMA21")
    else:
        reasons.append("EMA9 below EMA21")

    # RSI
    if 50 <= rsi_value <= 70:
        score += 30
        reasons.append(f"RSI Bullish ({round(rsi_value,2)})")

    elif rsi_value < 30:
        score += 15
        reasons.append("RSI Oversold")

    elif rsi_value > 70:
        reasons.append("RSI Overbought")

    else:
        reasons.append("Neutral RSI")

    # MACD
    if macd_value > macd_signal:
        score += 40
        reasons.append("MACD Bullish")
    else:
        reasons.append("MACD Bearish")

    # Final Signal
    if score >= 80:
        signal = "STRONG BUY"

    elif score >= 60:
        signal = "BUY"

    elif score >= 40:
        signal = "WAIT"

    else:
        signal = "SELL"

    return {

        "price": round(price, 2),

        "trend": trend(close),

        "signal": signal,

        "confidence": score,

        "ema9": round(ema9, 2),

        "ema21": round(ema21, 2),

        "rsi": round(rsi_value, 2),

        "macd": round(macd_value, 4),

        "macd_signal": round(macd_signal, 4),

        "reasons": reasons

    }
