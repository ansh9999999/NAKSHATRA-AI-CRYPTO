from delta import get_btc, get_eth


def get_market_data():

    btc = get_btc()
    eth = get_eth()

    return {
        "BTC": btc,
        "ETH": eth
    }


def market_status():

    data = get_market_data()

    return {
        "status": "LIVE",
        "markets": data
    }
