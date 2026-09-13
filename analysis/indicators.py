import numpy as np
import pandas as pd


def ema(s, period): return s.ewm(span=period, adjust=False).mean()
def sma(s, period): return s.rolling(period).mean()


def rsi(close, period=14):
    d = close.diff()
    gain = d.clip(lower=0)
    loss = -d.clip(upper=0)
    ag = gain.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    al = loss.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    rs = ag / al.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50)


def macd(close):
    fast = ema(close, 12); slow = ema(close, 26)
    line = fast - slow; sig = ema(line, 9)
    return line, sig, line - sig


def atr(high, low, close, period=14):
    tr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False, min_periods=period).mean().fillna(0)


def trend(close):
    if len(close) < 50: return "DATA INSUFFICIENT"
    e9, e21, e50 = ema(close,9).iloc[-1], ema(close,21).iloc[-1], ema(close,50).iloc[-1]
    if e9 > e21 > e50: return "STRONG BULLISH"
    if e9 < e21 < e50: return "STRONG BEARISH"
    if e9 > e21: return "BULLISH"
    if e9 < e21: return "BEARISH"
    return "SIDEWAYS"


def indicator_summary(df):
    if df.empty: return {"status":"NO_DATA"}
    c,h,l = df.close,df.high,df.low
    ml,ms,mh = macd(c)
    return {
        "price": round(float(c.iloc[-1]),2), "ema9": round(float(ema(c,9).iloc[-1]),2),
        "ema21": round(float(ema(c,21).iloc[-1]),2), "ema50": round(float(ema(c,50).iloc[-1]),2),
        "ema200": round(float(ema(c,200).iloc[-1]),2), "rsi": round(float(rsi(c).iloc[-1]),2),
        "macd": round(float(ml.iloc[-1]),5), "macd_signal": round(float(ms.iloc[-1]),5),
        "histogram": round(float(mh.iloc[-1]),5), "atr": round(float(atr(h,l,c).iloc[-1]),2),
        "trend": trend(c), "rows": len(df)
    }
