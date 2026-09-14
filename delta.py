"""
NAKSHATRA AI v4.0
Delta Exchange India - Market Data Helper

This file provides:
- Live ticker
- Live price
- Mark price
- Volume
- Candle history
- Safe timestamp handling

IMPORTANT:
This is the ROOT delta.py.
It is NOT broker/delta.py.
"""

import time
import requests
import pandas as pd


# ==========================================================
# DELTA EXCHANGE INDIA
# ==========================================================

BASE_URL = "https://api.india.delta.exchange/v2"

TIMEOUT = 15


# ==========================================================
# HTTP SESSION
# ==========================================================

session = requests.Session()

session.headers.update({
    "User-Agent": "NAKSHATRA-AI/4.0",
    "Accept": "application/json",
})


# ==========================================================
# SAFE NUMBER
# ==========================================================

def _float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


# ==========================================================
# SAFE TIMESTAMP
# ==========================================================

def _timestamp_seconds(value):
    """
    Convert Delta timestamp safely to seconds.

    Supports:
    - seconds
    - milliseconds
    - microseconds
    """

    try:
        ts = int(value)
    except Exception:
        return None

    # milliseconds
    if ts > 10_000_000_000:
        ts = ts // 1000

    # microseconds
    if ts > 10_000_000_000:
        ts = ts // 1000

    return ts


# ==========================================================
# LIVE TICKER
# ==========================================================

def get_ticker(symbol="BTCUSD"):
    """
    Get live ticker from Delta Exchange India.
    """

    symbol = str(symbol).upper().strip()

    try:
        url = f"{BASE_URL}/tickers/{symbol}"

        response = session.get(
            url,
            timeout=TIMEOUT
        )

        response.raise_for_status()

        payload = response.json()

        result = payload.get("result")

        if not result:
            return None

        price = (
            result.get("close")
            or result.get("mark_price")
            or result.get("spot_price")
        )

        return {
            "symbol": result.get("symbol", symbol),
            "price": _float(price),
            "mark_price": _float(
                result.get("mark_price", price)
            ),
            "volume": _float(
                result.get("volume", 0)
            ),
        }

    except Exception as exc:

        print(
            f"Delta ticker error [{symbol}]: {exc}"
        )

        return None


# ==========================================================
# CURRENT PRICE
# ==========================================================

def get_current_price(symbol="BTCUSD"):
    """
    Return only current market price.
    """

    ticker = get_ticker(symbol)

    if not ticker:
        return None

    price = ticker.get("price")

    if price is None:
        return None

    return float(price)


# ==========================================================
# CANDLE RESOLUTION
# ==========================================================

RESOLUTION_SECONDS = {

    "1m": 60,

    "3m": 180,

    "5m": 300,

    "15m": 900,

    "30m": 1800,

    "1h": 3600,

    "2h": 7200,

    "4h": 14400,

    "6h": 21600,

    "12h": 43200,

    "1d": 86400,

    "1w": 604800,

}


# ==========================================================
# GET CANDLES
# ==========================================================

def get_candles(
    symbol="BTCUSD",
    resolution="5m",
    limit=200
):
    """
    Download historical candles.

    Returns pandas DataFrame.

    Columns:
        timestamp
        open
        high
        low
        close
        volume
    """

    symbol = str(symbol).upper().strip()
    resolution = str(resolution).lower().strip()

    if resolution not in RESOLUTION_SECONDS:
        resolution = "5m"

    try:
        limit = int(limit)
    except Exception:
        limit = 200

    limit = max(10, min(limit, 1000))

    candle_seconds = RESOLUTION_SECONDS[resolution]

    # ------------------------------------------------------
    # IMPORTANT
    # Delta history API expects start/end timestamps.
    # ------------------------------------------------------

    now = int(time.time())

    end = now - (now % candle_seconds)

    start = end - (
        limit * candle_seconds
    )

    url = f"{BASE_URL}/history/candles"

    params = {
        "symbol": symbol,
        "resolution": resolution,
        "start": start,
        "end": end,
    }

    try:

        response = session.get(
            url,
            params=params,
            timeout=TIMEOUT
        )

        response.raise_for_status()

        payload = response.json()

        rows = payload.get("result", [])

        if not rows:
            print(
                f"Delta: no candles "
                f"{symbol} {resolution}"
            )

            return pd.DataFrame()

        df = pd.DataFrame(rows)

        if df.empty:
            return pd.DataFrame()

        # --------------------------------------------------
        # TIMESTAMP
        # --------------------------------------------------

        if "time" in df.columns:

            df["timestamp"] = (
                df["time"]
                .apply(_timestamp_seconds)
            )

        elif "timestamp" in df.columns:

            df["timestamp"] = (
                df["timestamp"]
                .apply(_timestamp_seconds)
            )

        else:

            print(
                f"Delta: timestamp missing "
                f"{symbol} {resolution}"
            )

            return pd.DataFrame()

        # --------------------------------------------------
        # OHLCV
        # --------------------------------------------------

        numeric_columns = [
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]

        for column in numeric_columns:

            if column in df.columns:

                df[column] = pd.to_numeric(
                    df[column],
                    errors="coerce"
                )

            else:

                # Missing volume should not kill
                # the complete candle dataset.
                if column == "volume":

                    df[column] = 0.0

                else:

                    print(
                        f"Delta: missing {column} "
                        f"{symbol} {resolution}"
                    )

                    return pd.DataFrame()

        # --------------------------------------------------
        # CLEAN
        # --------------------------------------------------

        df.dropna(
            subset=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
            ],
            inplace=True
        )

        if df.empty:
            return pd.DataFrame()

        # --------------------------------------------------
        # DATETIME
        # --------------------------------------------------

        df["datetime"] = pd.to_datetime(
            df["timestamp"],
            unit="s",
            utc=True
        )

        # --------------------------------------------------
        # SORT
        # --------------------------------------------------

        df.sort_values(
            "timestamp",
            inplace=True
        )

        df.reset_index(
            drop=True,
            inplace=True
        )

        # --------------------------------------------------
        # FINAL COLUMN ORDER
        # --------------------------------------------------

        columns = [
            "timestamp",
            "datetime",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]

        available = [
            column
            for column in columns
            if column in df.columns
        ]

        df = df[available]

        print(
            f"Delta candles OK: "
            f"{symbol} {resolution} "
            f"rows={len(df)}"
        )

        return df

    except requests.RequestException as exc:

        print(
            f"Delta candle request error "
            f"[{symbol} {resolution}]: {exc}"
        )

        return pd.DataFrame()

    except Exception as exc:

        print(
            f"Delta candle error "
            f"[{symbol} {resolution}]: {exc}"
        )

        return pd.DataFrame()


# ==========================================================
# ALIAS
# ==========================================================

def get_history(
    symbol="BTCUSD",
    resolution="5m",
    limit=200
):
    """
    Compatibility wrapper.
    """

    return get_candles(
        symbol=symbol,
        resolution=resolution,
        limit=limit
    )


# ==========================================================
# MULTI TIMEFRAME
# ==========================================================

def get_multi_timeframe_history(
    symbol="BTCUSD",
    limit=200
):
    """
    Return all supported analysis timeframes.
    """

    timeframes = [
        "5m",
        "15m",
        "1h",
        "1d",
        "1w",
    ]

    result = {}

    for timeframe in timeframes:

        result[timeframe] = get_candles(
            symbol=symbol,
            resolution=timeframe,
            limit=limit
        )

    return result


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 60)
    print("NAKSHATRA AI - DELTA CONNECTION TEST")
    print("=" * 60)

    # ------------------------------------------------------
    # BTC ticker
    # ------------------------------------------------------

    btc = get_ticker("BTCUSD")

    print("\nBTC TICKER:")
    print(btc)

    # ------------------------------------------------------
    # ETH ticker
    # ------------------------------------------------------

    eth = get_ticker("ETHUSD")

    print("\nETH TICKER:")
    print(eth)

    # ------------------------------------------------------
    # BTC candles
    # ------------------------------------------------------

    candles = get_candles(
        "BTCUSD",
        "5m",
        20
    )

    print("\nBTC 5M CANDLES:")

    if candles.empty:

        print("NO CANDLE DATA")

    else:

        print(
            candles.tail(5).to_string(
                index=False
            )
        )

    print("=" * 60)
