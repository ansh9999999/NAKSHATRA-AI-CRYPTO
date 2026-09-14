import re
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
            "mark_price": _float(result.get("mark_price", price)),
            "volume": _float(result.get("volume", 0)),
            "volume_24h": _float(result.get("volume_24h", result.get("volume", 0))),
            "change_24h": result.get("price_change_24h", result.get("change_24h", result.get("price_change"))),
            "day_high": result.get("high", result.get("day_high")),
            "day_low": result.get("low", result.get("day_low")),
            "oi": result.get("oi"),
            "open_interest": result.get("oi", result.get("open_interest")),
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


# ==========================================================
# DELTA OPTION CHAIN
# ==========================================================

def _option_expiry_from_symbol(symbol):
    """Return DD-MM-YYYY from Delta option symbol C-BTC-90000-310126."""
    text = str(symbol or "").strip().upper()
    m = re.search(r"-(\d{6})$", text)
    if not m:
        return None
    raw = m.group(1)
    try:
        day, month, year = int(raw[:2]), int(raw[2:4]), int(raw[4:6])
        year += 2000
        return f"{day:02d}-{month:02d}-{year:04d}"
    except Exception:
        return None


def get_option_chain(symbol="BTCUSD", expiry_date=None):
    """
    Fetch and normalize Delta's public option-chain tickers.

    IMPORTANT:
    Delta's option-chain endpoint is public and does not require API-key
    authentication.  The API returns rows using fields such as
    contract_type/strike_price/close/oi.  The signal engine consumes a
    normalized CE/PE schema, so this function performs that translation.

    When no expiry is supplied, the endpoint is queried without an expiry
    filter and the nearest expiry present in the returned option symbols is
    selected. This avoids relying on the /products pagination order.
    """
    symbol = str(symbol).upper().strip()
    underlying = symbol
    if underlying.endswith("USD"):
        underlying = underlying[:-3]
    elif underlying.endswith("_INR"):
        underlying = underlying[:-4]
    underlying = underlying.strip()
    if not underlying:
        return {"status": "ERROR", "symbol": symbol, "rows": [], "reason": "Invalid underlying"}

    try:
        params = {
            "contract_types": "call_options,put_options",
            "underlying_asset_symbols": underlying,
        }
        if expiry_date:
            params["expiry_date"] = str(expiry_date)

        r = session.get(
            f"{BASE_URL}/tickers",
            params=params,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        payload = r.json() or {}
        raw_rows = payload.get("result", []) or []
        if not isinstance(raw_rows, list):
            raw_rows = []

        normalized = []
        for row in raw_rows:
            if not isinstance(row, dict):
                continue
            contract_type = str(row.get("contract_type") or "").lower()
            option_symbol = str(row.get("symbol") or "").upper()
            if contract_type not in ("call_options", "put_options"):
                if option_symbol.startswith("C-"):
                    contract_type = "call_options"
                elif option_symbol.startswith("P-"):
                    contract_type = "put_options"
                else:
                    continue

            option_type = "CE" if contract_type == "call_options" else "PE"
            strike = _float(row.get("strike_price"), 0.0)
            if strike <= 0:
                parts = option_symbol.split("-")
                if len(parts) >= 4:
                    strike = _float(parts[-2], 0.0)
            if strike <= 0:
                continue

            expiry = row.get("expiry_date") or row.get("expiry") or _option_expiry_from_symbol(option_symbol)
            ltp = _float(row.get("close"), 0.0)
            if ltp <= 0:
                ltp = _float(row.get("mark_price"), 0.0)

            quotes = row.get("quotes") or {}
            greeks = row.get("greeks") or {}
            iv = quotes.get("ask_iv") or quotes.get("bid_iv") or row.get("mark_vol")

            normalized.append({
                "symbol": option_symbol,
                "type": option_type,
                "contract_type": contract_type,
                "strike": strike,
                "strike_price": strike,
                "expiry": str(expiry) if expiry else None,
                "expiry_date": str(expiry) if expiry else None,
                "ltp": ltp,
                "close": ltp,
                "mark_price": _float(row.get("mark_price"), ltp),
                "volume": _float(row.get("volume"), 0.0),
                "oi": _float(row.get("oi"), 0.0),
                "oi_value": _float(row.get("oi_value"), 0.0),
                "spot_price": _float(row.get("spot_price"), 0.0),
                "iv": _float(iv, 0.0),
                "delta": _float(greeks.get("delta"), 0.0),
                "gamma": _float(greeks.get("gamma"), 0.0),
                "theta": _float(greeks.get("theta"), 0.0),
                "vega": _float(greeks.get("vega"), 0.0),
            })

        # Select nearest expiry if no explicit expiry was requested.
        if not expiry_date:
            expiry_values = sorted({
                r["expiry"] for r in normalized
                if r.get("expiry")
            })
            if expiry_values:
                expiry_date = expiry_values[0]
                normalized = [r for r in normalized if r.get("expiry") == expiry_date]
        else:
            # Keep a consistent display value when API returns a different
            # representation on individual rows.
            normalized = [r for r in normalized if not r.get("expiry") or str(r.get("expiry")) == str(expiry_date)]

        normalized.sort(key=lambda r: (float(r.get("strike") or 0), r.get("type") or ""))

        return {
            "status": "OK" if normalized else "NO_DATA",
            "symbol": symbol,
            "underlying": underlying,
            "expiry": expiry_date,
            "rows": normalized,
            "count": len(normalized),
            "source": "delta_public_option_tickers",
        }

    except Exception as exc:
        print(f"Delta option chain error [{symbol}]: {exc}")
        return {
            "status": "ERROR",
            "symbol": symbol,
            "underlying": underlying,
            "expiry": expiry_date,
            "rows": [],
            "count": 0,
            "reason": str(exc),
        }
