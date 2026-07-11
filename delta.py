import requests
import time

from config import BASE_URL

SESSION = requests.Session()


def get_ticker(symbol="BTCUSD"):

    url = f"{BASE_URL}/tickers/{symbol}"

    r = SESSION.get(url, timeout=15)
    r.raise_for_status()

    return r.json()["result"]


def get_candles(
    symbol="BTCUSD",
    resolution="5m",
    limit=200
):

    now = int(time.time())

    seconds = {
        "1m": 60,
        "3m": 180,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
        "2h": 7200,
        "4h": 14400,
        "6h": 21600,
        "1d": 86400,
    }

    candle_seconds = seconds[resolution]

    start = now - (limit * candle_seconds)

    url = f"{BASE_URL}/history/candles"

    params = {
        "resolution": resolution,
        "symbol": symbol,
        "start": start,
        "end": now
    }

    r = SESSION.get(
        url,
        params=params,
        timeout=20
    )

    r.raise_for_status()

    data = r.json()

    if not data["success"]:
        raise Exception("Delta API Error")

    return data["result"]


def get_btc():

    return get_ticker("BTCUSD")


def get_eth():

    return get_ticker("ETHUSD")
