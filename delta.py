import requests
from config import BASE_URL, BTC_SYMBOL, ETH_SYMBOL


def get_ticker(symbol):

    try:

        url = f"{BASE_URL}/tickers/{symbol}"

        r = requests.get(url, timeout=10)

        r.raise_for_status()

        data = r.json()

        if not data.get("success", False):
            return None

        return data["result"]

    except Exception as e:

        return {
            "error": str(e)
        }


def get_btc():

    return get_ticker(BTC_SYMBOL)


def get_eth():

    return get_ticker(ETH_SYMBOL)


def market_summary():

    btc = get_btc()
    eth = get_eth()

    return {

        "BTC": btc,

        "ETH": eth

    }
