from fastapi import FastAPI
import os
import requests

from analysis.indicators import indicator_summary
from analysis.signal import generate_signal
from history import get_history
import scheduler
app = FastAPI(
    title="NAKSHATRA AI CRYPTO",
    description="AI Crypto Analysis API",
    version="2.1"
)

API_KEY = os.getenv("DELTA_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

BASE_URL = "https://api.india.delta.exchange/v2"


def send_telegram(message):

    if not BOT_TOKEN or not CHAT_ID:
        return {
            "success": False,
            "error": "Telegram variables missing"
        }

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    data = {
        "chat_id": CHAT_ID,
        "text": message
    }

    r = requests.post(url, data=data)

    return r.json()


@app.get("/")
def home():
    return {
        "project": "NAKSHATRA AI CRYPTO",
        "status": "Running",
        "api_key_found": API_KEY is not None,
        "telegram": BOT_TOKEN is not None
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

        df = get_dataframe()

        return generate_signal(df)

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


def get_dataframe():
    return get_history(
        symbol="BTCUSD",
        resolution="5m",
        limit=200
    )


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


@app.get("/telegram")
def telegram():

    try:

        df = get_dataframe()

        signal = generate_signal(df)

        message = f"""
🚀 NAKSHATRA AI CRYPTO

📊 Symbol : BTCUSD
💰 Price : {signal['price']}

📈 Trend : {signal['trend']}
🎯 Signal : {signal['signal']}
✅ Confidence : {signal['confidence']}%

RSI : {signal['rsi']}
EMA9 : {signal['ema9']}
EMA21 : {signal['ema21']}

Reasons:
- {'\n- '.join(signal['reasons'])}
"""

        result = send_telegram(message)

        return {
            "success": True,
            "telegram": result
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }
@app.get("/debug")
def debug():

    try:

        df = get_dataframe()

        return {
            "success": True,
            "rows": len(df),
            "columns": list(df.columns),
            "head": df.head(3).to_dict(orient="records"),
            "tail": df.tail(3).to_dict(orient="records")
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }
