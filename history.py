"""
NAKSHATRA AI CRYPTO
Multi-Timeframe Historical Data Engine
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import time

import pandas as pd
import requests

from logger import logger


# ==========================================================
# DELTA EXCHANGE INDIA
# ==========================================================

BASE_URL = "https://api.india.delta.exchange/v2"

RESOLUTIONS = (
    "5m",
    "15m",
    "1h",
    "4h",
    "1d",
)

DEFAULT_LIMIT = 200
TIMEOUT_SECONDS = 10
RETRIES = 1

_CACHE = {}
_CACHE_TTL = 8


# ==========================================================
# ENDPOINT
# ==========================================================

def _endpoint():
    return f"{BASE_URL}/history/candles"


# ==========================================================
# EMPTY DATAFRAME
# ==========================================================

def _empty():
    return pd.DataFrame(
        columns=[
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
    )


# ==========================================================
# FETCH HISTORY
# ==========================================================

def _fetch_history(
    symbol,
    resolution="5m",
    limit=DEFAULT_LIMIT,
):

    symbol = str(symbol).upper()
    resolution = str(resolution)

    key = (
        symbol,
        resolution,
        int(limit),
    )

    now = time.time()

    # ------------------------------------------------------
    # CACHE
    # ------------------------------------------------------

    cached = _CACHE.get(key)

    if cached:

        cache_time, cached_df = cached

        if now - cache_time < _CACHE_TTL:
            return cached_df.copy()

    # ------------------------------------------------------
    # CANDLE INTERVAL
    # ------------------------------------------------------

    interval_seconds = {
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
    }.get(resolution)

    if interval_seconds is None:

        logger.warning(
            "Unsupported resolution: %s",
            resolution,
        )

        return _empty()

    # ------------------------------------------------------
    # TIME RANGE
    # ------------------------------------------------------

    end = int(time.time())

    start = end - (
        int(limit) * interval_seconds
    )

    params = {
        "symbol": symbol,
        "resolution": resolution,
        "start": start,
        "end": end,
    }

    url = _endpoint()

    last_error = None

    # ------------------------------------------------------
    # REQUEST
    # ------------------------------------------------------

    for attempt in range(RETRIES + 1):

        try:

            response = requests.get(
                url,
                params=params,
                timeout=TIMEOUT_SECONDS,
            )

            response.raise_for_status()

            payload = response.json()

            rows = payload.get("result") or []

            if not isinstance(rows, list):

                raise ValueError(
                    "Invalid Delta candle response"
                )

            if not rows:

                raise ValueError(
                    f"No candles for {symbol} {resolution}"
                )

            df = pd.DataFrame(rows)

            if df.empty:
                return _empty()

            # --------------------------------------------------
            # TIMESTAMP
            # --------------------------------------------------

            if (
                "time" in df.columns
                and "timestamp" not in df.columns
            ):

                df.rename(
                    columns={
                        "time": "timestamp"
                    },
                    inplace=True,
                )

            # --------------------------------------------------
            # NUMERIC DATA
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
                        errors="coerce",
                    )

            # --------------------------------------------------
            # REQUIRED DATA
            # --------------------------------------------------

            required_columns = [
                "timestamp",
                "open",
                "high",
                "low",
                "close",
            ]

            missing = [
                column
                for column in required_columns
                if column not in df.columns
            ]

            if missing:

                raise ValueError(
                    f"Missing candle columns: {missing}"
                )

            # --------------------------------------------------
            # CLEAN
            # --------------------------------------------------

            df.dropna(
                subset=required_columns,
                inplace=True,
            )

            if "volume" not in df.columns:

                df["volume"] = 0.0

            df["volume"] = pd.to_numeric(
                df["volume"],
                errors="coerce",
            ).fillna(0.0)

            # --------------------------------------------------
            # SORT
            # --------------------------------------------------

            df.sort_values(
                "timestamp",
                inplace=True,
            )

            df.reset_index(
                drop=True,
                inplace=True,
            )

            # --------------------------------------------------
            # CACHE
            # --------------------------------------------------

            _CACHE[key] = (
                time.time(),
                df.copy(),
            )

            logger.info(
                "HISTORY OK %s %s rows=%s",
                symbol,
                resolution,
                len(df),
            )

            return df

        except Exception as exc:

            last_error = exc

            logger.warning(
                "HISTORY ERROR %s %s attempt=%s: %s",
                symbol,
                resolution,
                attempt + 1,
                exc,
            )

            if attempt < RETRIES:

                time.sleep(0.25)

    # ------------------------------------------------------
    # FAILED
    # ------------------------------------------------------

    logger.warning(
        "HISTORY FAILED %s %s: %s",
        symbol,
        resolution,
        last_error,
    )

    return _empty()


# ==========================================================
# SINGLE TIMEFRAME
# ==========================================================

def get_history(
    symbol="BTCUSD",
    resolution="5m",
    limit=DEFAULT_LIMIT,
):

    return _fetch_history(
        symbol,
        resolution,
        limit,
    )


# ==========================================================
# MULTI TIMEFRAME
# ==========================================================

def get_multi_timeframe_history(
    symbol,
    limit=DEFAULT_LIMIT,
):

    symbol = str(symbol).upper()

    result = {
        timeframe: _empty()
        for timeframe in RESOLUTIONS
    }

    # ------------------------------------------------------
    # PARALLEL FETCH
    # ------------------------------------------------------

    with ThreadPoolExecutor(
        max_workers=len(RESOLUTIONS)
    ) as executor:

        jobs = {
            executor.submit(
                _fetch_history,
                symbol,
                timeframe,
                limit,
            ): timeframe

            for timeframe in RESOLUTIONS
        }

        for job in as_completed(jobs):

            timeframe = jobs[job]

            try:

                result[timeframe] = job.result()

            except Exception as exc:

                logger.exception(
                    "MTF ERROR %s %s: %s",
                    symbol,
                    timeframe,
                    exc,
                )

                result[timeframe] = _empty()

    return result
