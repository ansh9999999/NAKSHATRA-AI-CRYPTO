import pandas as pd
from delta import get_candles


def get_history(symbol="BTCUSD", resolution="5m", limit=250):
    df = pd.DataFrame(get_candles(symbol, resolution, limit))
    if df.empty:
        return df
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
