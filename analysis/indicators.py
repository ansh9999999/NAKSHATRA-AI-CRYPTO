import pandas as pd
import numpy as np


def ema(close, period):
    return close.ewm(span=period, adjust=False).mean()


def sma(close, period):
    return close.rolling(period).mean()


def rsi(close, period=14):

    delta = close.diff()

    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    value = 100 - (100 / (1 + rs))

    value = value.fillna(50)

    return value


def macd(close):

    ema12 = ema(close, 12)
    ema26 = ema(close, 26)

    macd_line = ema12 - ema26
    signal_line = ema(macd_line, 9)
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


def atr(high, low, close, period=14):

    high_low = high - low
    high_close = abs(high - close.shift())
    low_close = abs(low - close.shift())

    tr = pd.concat(
        [high_low, high_close, low_close],
        axis=1
    ).max(axis=1)

    return tr.rolling(period).mean().fillna(0)


def trend(close):

    ema9 = ema(close, 9).iloc[-1]
    ema21 = ema(close, 21).iloc[-1]
    ema50 = ema(close, 50).iloc[-1]

    if ema9 > ema21 > ema50:
        return "STRONG BULLISH"

    elif ema9 < ema21 < ema50:
        return "STRONG BEARISH"

    elif ema9 > ema21:
        return "BULLISH"

    elif ema9 < ema21:
        return "BEARISH"

    return "SIDEWAYS"


def indicator_summary(df):

    close = df["close"]
    high = df["high"]
    low = df["low"]

    macd_line, signal_line, hist = macd(close)

    return {

        "price": round(float(close.iloc[-1]), 2),

        "ema9": round(float(ema(close, 9).fillna(0).iloc[-1]), 2),

        "ema21": round(float(ema(close, 21).fillna(0).iloc[-1]), 2),

        "ema50": round(float(ema(close, 50).fillna(0).iloc[-1]), 2),

        "rsi": round(float(rsi(close).iloc[-1]), 2),

        "macd": round(float(macd_line.fillna(0).iloc[-1]), 4),

        "macd_signal": round(float(signal_line.fillna(0).iloc[-1]), 4),

        "histogram": round(float(hist.fillna(0).iloc[-1]), 4),

        "atr": round(float(atr(high, low, close).iloc[-1]), 2),

        "trend": trend(close)

    }
