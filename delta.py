import requests
import time

BASE_URL = "https://api.india.delta.exchange/v2"


def get_candles(symbol="BTCUSD", resolution="5m", limit=200):

    seconds = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
        "4h": 14400,
        "1d": 86400,
    }

    candle_seconds = seconds.get(resolution, 300)

    now = int(time.time())

    # Last completed candle
    end = now - (now % candle_seconds)

    start = end - (limit * candle_seconds)

    url = f"{BASE_URL}/history/candles"

    params = {
        "symbol": symbol,
        "resolution": resolution,
        "start": start,
        "end": end,
    }

    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()

        if not data.get("success"):
            return []

        result = []

        for c in data["result"]:
            result.append({
                "time": c["time"],
                "open": float(c["open"]),
                "high": float(c["high"]),
                "low": float(c["low"]),
                "close": float(c["close"]),
                "volume": float(c["volume"])
            })

        result.sort(key=lambda x: x["time"])

        return result

    except Exception as e:
        print("Delta Error:", e)
        return []


def get_latest_price(symbol="BTCUSD"):

    candles = get_candles(symbol, "1m", 2)

    if len(candles) == 0:
        return None

    return candles[-1]["close"]
