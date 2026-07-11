import pandas as pd

from delta import get_candles


def get_history(
    symbol="BTCUSD",
    resolution="5m",
    limit=200
):

    candles = get_candles(
        symbol=symbol,
        resolution=resolution,
        limit=limit
    )

    df = pd.DataFrame(candles)

    # Delta API keys
    rename = {}

    if "open" in df.columns:
        rename["open"] = "open"

    if "high" in df.columns:
        rename["high"] = "high"

    if "low" in df.columns:
        rename["low"] = "low"

    if "close" in df.columns:
        rename["close"] = "close"

    if "volume" in df.columns:
        rename["volume"] = "volume"

    df = df.rename(columns=rename)

    numeric_cols = [
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]

    for col in numeric_cols:

        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            )

    df = df.dropna()

    df = df.reset_index(drop=True)

    return df
