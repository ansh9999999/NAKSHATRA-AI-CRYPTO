from fastapi import FastAPI
import os
import requests
import pandas as pd

from analysis.indicators import indicator_summary
from analysis.signal import generate_signal

app = FastAPI(
    title="NAKSHATRA AI CRYPTO",
    description="AI Crypto Analysis API",
    version="2.0"
)

API_KEY = os.getenv("DELTA_API_KEY")
BASE_URL = "https://api.india.delta.exchange/v2"


@app.get("/")
def home():
    return {
        "project": "NAKSHATRA AI CRYPTO",
        "status": "Running",
        "api_key_found": API_KEY is not None
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/btc")
def btc():

    try:

        r = requests.get(f"{BASE_URL}/tickers/BTCUSD")

        data = r.json()["result"]

        return {

            "success": True,

            "result": data

        }

    except Exception as e:

        return {

            "success": False,

            "error": str(e)

        }


@app.get("/signal")
def signal():

    try:

        r = requests.get(f"{BASE_URL}/tickers/BTCUSD")

        btc = r.json()["result"]

        change = float(btc["mark_change_24h"])

        if change > 2:
            signal = "BUY"

        elif change < -2:
            signal = "SELL"

        else:
            signal = "WAIT"

        return {

            "symbol": "BTCUSD",

            "price": btc["mark_price"],

            "change_24h": change,

            "signal": signal

        }

    except Exception as e:

        return {

            "error": str(e)

        }


def get_dataframe():

    r = requests.get(f"{BASE_URL}/tickers/BTCUSD")

    data = r.json()["result"]

    price = float(data["mark_price"])

    df = pd.DataFrame({

        "close": [price] * 60,

        "high": [price * 1.002] * 60,

        "low": [price * 0.998] * 60

    })

    return df


@app.get("/analysis")
def analysis():

    try:

        df = get_dataframe()

        indicators = indicator_summary(df)

        signal = generate_signal(df)

        return {

            "success": True,

            "indicators": indicators,

            "signal": signal

        }

    except Exception as e:

        return {

            "success": False,

            "error": str(e)

        }
