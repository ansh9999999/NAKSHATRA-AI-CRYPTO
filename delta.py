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
            "open": _float(result.get("open", 0)),
            "high": _float(result.get("high", 0)),
            "low": _float(result.get("low", 0)),
            "oi": _float(result.get("oi", 0)),
            "change_24h": _float(result.get("ltp_change_24h", 0)),
            "ltp_change_24h": _float(result.get("ltp_change_24h", 0)),
            "timestamp": result.get("timestamp"),
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
# PUBLIC OPTION CHAIN
# ==========================================================
def _option_expiry_from_symbol(sym):
    import re
    m = re.search(r"-(\d{6})$", str(sym or ""))
    return m.group(1) if m else None


def _expiry_to_display(exp):
    if not exp:
        return None
    s = str(exp)
    if len(s) == 6 and s.isdigit():
        return f"{s[0:2]}-{s[2:4]}-20{s[4:6]}"
    return s


def get_option_chain(symbol="BTCUSD", expiry_date=None):
    """Fetch the current/future public Delta option chain for one expiry.

    No authentication is required. Returns normalized rows for the signal engine.
    """
    import re
    from datetime import datetime
    symbol = str(symbol).upper().strip()
    underlying = re.sub(r"USD$", "", symbol)
    try:
        params = {
            "contract_types": "call_options,put_options",
            "underlying_asset_symbols": underlying,
        }
        if expiry_date:
            params["expiry_date"] = expiry_date
        r = session.get(f"{BASE_URL}/tickers", params=params, timeout=TIMEOUT)
        r.raise_for_status()
        payload = r.json()
        raw = payload.get("result") or []
        if not isinstance(raw, list):
            raw = []

        rows = []
        expiries = []
        for x in raw:
            if not isinstance(x, dict):
                continue
            typ = str(x.get("contract_type", "")).lower()
            if typ not in ("call_options", "put_options"):
                continue
            strike = _float(x.get("strike_price"), None)
            if strike is None:
                continue
            sym = x.get("symbol", "")
            exp = x.get("expiry_date") or x.get("expiry")
            if not exp:
                code = _option_expiry_from_symbol(sym)
                exp = _expiry_to_display(code)
            if exp:
                expiries.append(str(exp))
            close = _float(x.get("close"), 0.0)
            mark = _float(x.get("mark_price"), 0.0)
            q = x.get("quotes") or {}
            bid = _float(q.get("best_bid"), 0.0)
            ask = _float(q.get("best_ask"), 0.0)
            # Delta can return close=0 for an option with no recent trade.
            # Prefer mark, then midpoint, so UI does not show fake zero LTP.
            if close > 0:
                ltp = close
            elif mark > 0:
                ltp = mark
            elif bid > 0 and ask > 0:
                ltp = (bid + ask) / 2.0
            else:
                ltp = 0.0
            greeks = x.get("greeks") or {}
            rows.append({
                "symbol": sym,
                "type": "CE" if typ == "call_options" else "PE",
                "contract_type": typ,
                "strike": strike,
                "strike_price": strike,
                "expiry": exp,
                "expiry_date": exp,
                "ltp": ltp,
                "close": close,
                "mark_price": mark,
                "best_bid": bid,
                "best_ask": ask,
                "volume": _float(x.get("volume"), 0.0),
                "oi": _float(x.get("oi"), 0.0),
                "oi_value": _float(x.get("oi_value"), 0.0),
                "oi_value_usd": _float(x.get("oi_value_usd"), 0.0),
                "iv": _float(x.get("mark_iv"), 0.0),
                "delta": _float(greeks.get("delta"), 0.0),
                "gamma": _float(greeks.get("gamma"), 0.0),
                "theta": _float(greeks.get("theta"), 0.0),
                "vega": _float(greeks.get("vega"), 0.0),
                "spot_price": _float(x.get("spot_price"), 0.0),
            })

        # If all expiries were returned, select the nearest future expiry.
        if not expiry_date and rows:
            parsed = []
            for e in set(expiries):
                try:
                    parsed.append((datetime.strptime(e, "%d-%m-%Y"), e))
                except Exception:
                    pass
            if parsed:
                now = datetime.utcnow().date()
                future = [(d, e) for d, e in parsed if d.date() >= now]
                chosen = min(future or parsed)[1]
                rows = [x for x in rows if x.get("expiry") == chosen]
                expiry_date = chosen
        elif expiry_date:
            rows = [x for x in rows if str(x.get("expiry")) == str(expiry_date)] or rows

        return {
            "status": "OK" if rows else "NO_DATA",
            "symbol": symbol,
            "underlying": underlying,
            "expiry": expiry_date or (rows[0].get("expiry") if rows else None),
            "rows": rows,
            "count": len(rows),
            "source": "delta_public_option_tickers",
        }
    except Exception as exc:
        print(f"Delta option chain error [{symbol}]: {exc}")
        return {"status": "ERROR", "symbol": symbol, "rows": [], "count": 0, "message": str(exc)}
