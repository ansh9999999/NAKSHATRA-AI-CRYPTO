from fastapi import FastAPI
import os
import requests

app = FastAPI(
    title="NAKSHATRA AI CRYPTO",
    description="AI Crypto Analysis API",
    version="1.0"
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
        data = r.json()

        return {
            "success": True,
            "result": data["result"]
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
import pandas as pd
import numpy as np
