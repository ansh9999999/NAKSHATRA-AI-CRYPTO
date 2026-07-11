import requests
import pandas as pd
from config import BASE_URL, BTC_SYMBOL


def get_btc_history():

    url = f"{BASE_URL}/tickers/{BTC_SYMBOL}"

    r = requests.get(url, timeout=10)

    data = r.json()["result"]

    price = float(data["mark_price"])

    df = pd.DataFrame({
        "close": [price] * 100,
        "high": [price * 1.002] * 100,
        "low": [price * 0.998] * 100
    })

    return df
