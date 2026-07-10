from fastapi import FastAPI
import requests
import os

app = FastAPI(
    title="NAKSHATRA AI CRYPTO",
    version="1.0"
)

BASE_URL = "https://api.india.delta.exchange/v2"


@app.get("/")
def home():
    return {
        "project": "NAKSHATRA AI CRYPTO",
        "status": "Running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/btc")
def btc():

    try:

        url = f"{BASE_URL}/tickers/BTCUSD"

        r = requests.get(url, timeout=10)

        data = r.json()["result"]

        return {

            "symbol": "BTCUSD",

            "price": data["mark_price"],

            "change_24h": data["mark_change_24h"],

            "volume": data["volume"]

        }

    except Exception as e:

        return {

            "error": str(e)

        }


@app.get("/eth")
def eth():

    try:

        url = f"{BASE_URL}/tickers/ETHUSD"

        r = requests.get(url, timeout=10)

        data = r.json()["result"]

        return {

            "symbol": "ETHUSD",

            "price": data["mark_price"],

            "change_24h": data["mark_change_24h"],

            "volume": data["volume"]

        }

    except Exception as e:

        return {

            "error": str(e)

        }


@app.get("/signal")
def signal():

    try:

        url = f"{BASE_URL}/tickers/BTCUSD"

        r = requests.get(url, timeout=10)

        btc = r.json()["result"]

        change = float(btc["mark_change_24h"])

        if change >= 3:

            sig = "STRONG BUY"

        elif change >= 1:

            sig = "BUY"

        elif change <= -3:

            sig = "STRONG SELL"

        elif change <= -1:

            sig = "SELL"

        else:

            sig = "WAIT"

        return {

            "symbol": "BTCUSD",

            "price": btc["mark_price"],

            "change_24h": change,

            "signal": sig

        }

    except Exception as e:

        return {

            "error": str(e)

        }
