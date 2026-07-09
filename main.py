from fastapi import FastAPI
import os
import requests

app = FastAPI()

API_KEY = os.getenv("DELTA_API_KEY")

@app.get("/")
def home():
    try:
        r = requests.get(
            "https://api.india.delta.exchange/v2/tickers/BTCUSD"
        )
        data = r.json()

        return {
            "status": "Running",
            "api_key_found": API_KEY is not None,
            "btc_data": data
        }

    except Exception as e:
        return {"error": str(e)}
