import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

BASE_URL = "https://api.india.delta.exchange/v2"
TIMEOUT = 20
SUPPORTED = {"BTCUSD": "BTC", "ETHUSD": "ETH"}
RESOLUTIONS = {"5m": 300, "15m": 900, "1h": 3600, "1d": 86400, "1w": 604800}


def _get(path: str, params: Optional[dict] = None) -> dict:
    r = requests.get(f"{BASE_URL}{path}", params=params or {}, headers={"Accept": "application/json"}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def get_ticker(symbol: str = "BTCUSD") -> dict:
    symbol = symbol.upper()
    if symbol not in SUPPORTED:
        raise ValueError("Unsupported crypto symbol")
    data = _get(f"/tickers/{symbol}").get("result") or {}
    return {
        "symbol": symbol,
        "ltp": _num(data.get("close") or data.get("mark_price")),
        "mark_price": _num(data.get("mark_price")),
        "volume": _num(data.get("volume")),
        "open_interest": _num(data.get("oi") or data.get("open_interest")),
        "change_24h": _num(data.get("price_change_24h") or data.get("ltp_change_24h")),
        "raw": data,
    }


def get_candles(symbol: str = "BTCUSD", resolution: str = "5m", limit: int = 250) -> List[dict]:
    symbol = symbol.upper()
    if symbol not in SUPPORTED or resolution not in RESOLUTIONS:
        return []
    seconds = RESOLUTIONS[resolution]
    limit = max(50, min(int(limit), 500))
    end = int(time.time())
    end -= end % seconds
    start = end - (limit * seconds)
    try:
        data = _get("/history/candles", {"symbol": symbol, "resolution": resolution, "start": start, "end": end})
        rows = []
        for c in data.get("result", []) or []:
            rows.append({
                "time": int(c["time"]),
                "open": float(c["open"]),
                "high": float(c["high"]),
                "low": float(c["low"]),
                "close": float(c["close"]),
                "volume": float(c.get("volume", 0) or 0),
            })
        rows.sort(key=lambda x: x["time"])
        return rows[-limit:]
    except Exception as e:
        print(f"Delta history error {symbol} {resolution}: {e}")
        return []


def _num(v: Any) -> Optional[float]:
    try:
        return round(float(v), 8) if v is not None else None
    except (TypeError, ValueError):
        return None


def _expiry_from_product(p: dict) -> Optional[str]:
    for key in ("expiry", "expiry_date", "maturity_date"):
        value = p.get(key)
        if value:
            text = str(value)[:10]
            try:
                datetime.strptime(text, "%Y-%m-%d")
                return text
            except ValueError:
                pass
    m = re.search(r"-(\d{6})$", str(p.get("symbol", "")))
    if m:
        try:
            return datetime.strptime(m.group(1), "%d%m%y").date().isoformat()
        except ValueError:
            return None
    return None


def _nearest_expiry(asset: str) -> Optional[str]:
    try:
        data = _get("/products", {
            "contract_types": "call_options,put_options",
            "states": "live,upcoming",
            "page_size": 100,
        })
        today = datetime.now(timezone.utc).date()
        expiries = set()
        for p in data.get("result", []) or []:
            sym = str(p.get("symbol", ""))
            underlying = str(p.get("underlying_asset_symbol", ""))
            if underlying.upper() != asset.upper() and not sym.startswith((f"C-{asset}-", f"P-{asset}-")):
                continue
            exp = _expiry_from_product(p)
            if exp and datetime.strptime(exp, "%Y-%m-%d").date() >= today:
                expiries.add(exp)
        return sorted(expiries)[0] if expiries else None
    except Exception as e:
        print(f"Delta expiry discovery error {asset}: {e}")
        return None


def get_option_chain(symbol: str = "BTCUSD") -> dict:
    symbol = symbol.upper()
    asset = SUPPORTED.get(symbol)
    if not asset:
        return {"status": "NOT_SUPPORTED", "rows": []}
    expiry = _nearest_expiry(asset)
    params = {
        "contract_types": "call_options,put_options",
        "underlying_asset_symbols": asset,
    }
    if expiry:
        params["expiry_date"] = datetime.strptime(expiry, "%Y-%m-%d").strftime("%d-%m-%Y")
    try:
        result = _get("/tickers", params).get("result", []) or []
        rows = []
        for x in result:
            opt = str(x.get("contract_type", ""))
            if opt not in ("call_options", "put_options"):
                continue
            rows.append({
                "symbol": x.get("symbol"),
                "type": "CE" if opt == "call_options" else "PE",
                "strike": _num(x.get("strike_price")),
                "ltp": _num(x.get("close") or x.get("mark_price")),
                "mark_price": _num(x.get("mark_price")),
                "oi": _num(x.get("oi") or x.get("open_interest")) or 0,
                "volume": _num(x.get("volume")) or 0,
                "iv": _num((x.get("greeks") or {}).get("iv") or x.get("mark_volatility")),
                "delta": _num((x.get("greeks") or {}).get("delta")),
            })
        rows = [r for r in rows if r["strike"] is not None]
        rows.sort(key=lambda r: (r["strike"], r["type"]))
        actual_expiry = expiry
        if not actual_expiry and rows:
            m = re.search(r"-(\d{6})$", str(rows[0].get("symbol", "")))
            if m:
                actual_expiry = datetime.strptime(m.group(1), "%d%m%y").date().isoformat()
        return {"status": "OK" if rows else "EMPTY", "symbol": symbol, "underlying": asset, "expiry": actual_expiry, "rows": rows}
    except Exception as e:
        return {"status": "ERROR", "symbol": symbol, "underlying": asset, "expiry": expiry, "rows": [], "error": str(e)}


def get_btc():
    return get_ticker("BTCUSD")


def get_eth():
    return get_ticker("ETHUSD")
