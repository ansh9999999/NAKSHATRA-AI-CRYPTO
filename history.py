"""Fast/resilient Delta Exchange India historical data layer."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import pandas as pd
import requests
from logger import logger

BASE_URL = "https://api.india.delta.exchange/v2"
RESOLUTIONS = ("5m", "15m", "1h", "4h", "1d")
TIMEOUT_SECONDS = 8
RETRIES = 1
_CACHE = {}
_CACHE_TTL = 8

def _empty():
    return pd.DataFrame(columns=["timestamp","open","high","low","close","volume"])

def _fetch_history(symbol, resolution="5m", limit=200):
    key=(symbol.upper(),resolution,int(limit)); now=time.time()
    cached=_CACHE.get(key)
    if cached and now-cached[0] < _CACHE_TTL: return cached[1].copy()
    seconds={"1m":60,"3m":180,"5m":300,"15m":900,"30m":1800,"1h":3600,"2h":7200,"4h":14400,"6h":21600,"12h":43200,"1d":86400,"1w":604800}.get(resolution)
    if seconds is None: return _empty()
    end=int(time.time()); start=end-int(limit)*seconds
    params={"symbol":symbol.upper(),"resolution":resolution,"start":start,"end":end}
    last=None
    for attempt in range(RETRIES+1):
        try:
            r=requests.get(f"{BASE_URL}/history/candles",params=params,timeout=TIMEOUT_SECONDS); r.raise_for_status()
            rows=(r.json() or {}).get("result") or []
            if not isinstance(rows,list) or not rows: raise ValueError("No candle data")
            df=pd.DataFrame(rows)
            if "time" in df.columns and "timestamp" not in df.columns: df.rename(columns={"time":"timestamp"},inplace=True)
            for c in ["open","high","low","close","volume","timestamp"]:
                if c in df.columns: df[c]=pd.to_numeric(df[c],errors="coerce")
            req=["timestamp","open","high","low","close"]
            if any(c not in df.columns for c in req): raise ValueError("Missing candle columns")
            df.dropna(subset=req,inplace=True); df.sort_values("timestamp",inplace=True); df.reset_index(drop=True,inplace=True)
            _CACHE[key]=(time.time(),df.copy()); return df
        except Exception as exc:
            last=exc
            if attempt<RETRIES: time.sleep(.2)
    logger.warning("HISTORY FAILED %s %s: %s",symbol,resolution,last); return _empty()

def get_history(symbol="BTCUSD",resolution="5m",limit=200): return _fetch_history(symbol,resolution,limit)

def get_multi_timeframe_history(symbol,limit=200):
    result={tf:_empty() for tf in RESOLUTIONS}
    with ThreadPoolExecutor(max_workers=len(RESOLUTIONS)) as pool:
        jobs={pool.submit(_fetch_history,symbol,tf,limit):tf for tf in RESOLUTIONS}
        for job in as_completed(jobs):
            tf=jobs[job]
            try: result[tf]=job.result()
            except Exception as exc: logger.warning("TIMEFRAME ERROR %s %s: %s",symbol,tf,exc)
    return result
