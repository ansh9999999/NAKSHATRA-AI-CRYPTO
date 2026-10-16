"""Public, read-only global crypto market monitor.

This module is intentionally separate from Delta's trading/analysis modules.
It uses public market endpoints only; no API keys or order placement.
Unavailable providers are reported as unavailable rather than filled with fake data.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import math
import threading
import time
from typing import Any

import requests
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/global-market", tags=["global-market"])
TIMEOUT = (2.5, 4.0)
CACHE_SECONDS = 12
_cache: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()
_session = requests.Session()
_session.headers.update({"User-Agent": "NakshatraAI-GlobalMonitor/1.0", "Accept": "application/json"})


def _get(url: str, params: dict | None = None) -> dict:
    response = _session.get(url, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Unexpected provider response")
    return payload


def _num(value: Any) -> float | None:
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def _row(name: str, market: str, price: Any, change: Any, volume: Any, source: str,
         status: str = "OK", note: str | None = None) -> dict:
    return {"exchange": name, "market": market, "price": _num(price), "change_24h_pct": _num(change),
            "volume_24h": _num(volume), "source": source, "status": status, "note": note}


def _binance_spot(symbol: str) -> dict:
    p = _get("https://api.binance.com/api/v3/ticker/24hr", {"symbol": symbol})
    return _row("Binance", "Spot", p.get("lastPrice"), p.get("priceChangePercent"), p.get("quoteVolume"), "Binance Spot")


def _binance_futures(symbol: str) -> dict:
    p = _get("https://fapi.binance.com/fapi/v1/ticker/24hr", {"symbol": symbol})
    return _row("Binance", "Futures", p.get("lastPrice"), p.get("priceChangePercent"), p.get("quoteVolume"), "Binance USD-M Futures")


def _coinbase(symbol: str) -> dict:
    product = "BTC-USD" if symbol.startswith("BTC") else "ETH-USD"
    ticker = _get(f"https://api.exchange.coinbase.com/products/{product}/ticker")
    stats = _get(f"https://api.exchange.coinbase.com/products/{product}/stats")
    last = _num(ticker.get("price")); open24 = _num(stats.get("open"))
    change = ((last / open24) - 1) * 100 if last and open24 else None
    return _row("Coinbase", "Spot", last, change, stats.get("volume"), f"Coinbase Exchange {product}")


def _kraken(symbol: str) -> dict:
    pair = "XBTUSD" if symbol.startswith("BTC") else "ETHUSD"
    p = _get("https://api.kraken.com/0/public/Ticker", {"pair": pair})
    if p.get("error"):
        raise ValueError("Kraken: " + ", ".join(p["error"]))
    result = p.get("result") or {}
    ticker = next(iter(result.values()), {})
    last = _num((ticker.get("c") or [None])[0]); open24 = _num(ticker.get("o"))
    change = ((last / open24) - 1) * 100 if last and open24 else None
    volume = _num((ticker.get("v") or [None, None])[1])
    return _row("Kraken", "Spot", last, change, volume, f"Kraken public ticker {pair}")


def _bybit(symbol: str) -> dict:
    p = _get("https://api.bybit.com/v5/market/tickers", {"category": "linear", "symbol": symbol})
    if p.get("retCode") not in (0, None):
        raise ValueError(str(p.get("retMsg", "Bybit API error")))
    ticker = ((p.get("result") or {}).get("list") or [{}])[0]
    row = _row("Bybit", "USDT Perpetual", ticker.get("lastPrice"), _num(ticker.get("price24hPcnt")) * 100 if _num(ticker.get("price24hPcnt")) is not None else None,
                ticker.get("turnover24h"), f"Bybit V5 linear {symbol}")
    row["open_interest"] = _num(ticker.get("openInterest"))
    row["funding_rate_pct"] = _num(ticker.get("fundingRate")) * 100 if _num(ticker.get("fundingRate")) is not None else None
    return row


def _okx(symbol: str) -> dict:
    base = "BTC" if symbol.startswith("BTC") else "ETH"
    p = _get("https://www.okx.com/api/v5/market/ticker", {"instId": f"{base}-USDT-SWAP"})
    if p.get("code") not in ("0", 0, None):
        raise ValueError(str(p.get("msg", "OKX API error")))
    ticker = ((p.get("data") or [{}])[0])
    last = _num(ticker.get("last")); open24 = _num(ticker.get("open24h"))
    change = ((last / open24) - 1) * 100 if last and open24 else None
    return _row("OKX", "USDT Perpetual", last, change, ticker.get("volCcy24h"), f"OKX public ticker {base}-USDT-SWAP")


PROVIDERS = [_binance_spot, _binance_futures, _coinbase, _kraken, _bybit, _okx]


def _direction(change: float | None) -> str:
    if change is None:
        return "UNCONFIRMED"
    if change >= 0.25:
        return "BULLISH"
    if change <= -0.25:
        return "BEARISH"
    return "SIDEWAYS"


def _build_snapshot(symbol: str) -> dict:
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fn, symbol): fn.__name__ for fn in PROVIDERS}
        for future in as_completed(futures):
            try:
                rows.append(future.result())
            except Exception as exc:
                name = futures[future].replace("_", " ").title()
                rows.append(_row(name, "—", None, None, None, futures[future], "UNAVAILABLE", str(exc)[:160]))
    rows.sort(key=lambda r: (r["exchange"], r["market"]))
    available = [r for r in rows if r["status"] == "OK" and r.get("price") is not None]
    prices = [r["price"] for r in available]
    avg_price = sum(prices) / len(prices) if prices else None
    median_change_values = sorted(r["change_24h_pct"] for r in available if r.get("change_24h_pct") is not None)
    median_change = median_change_values[len(median_change_values)//2] if median_change_values else None
    if median_change_values and len(median_change_values) % 2 == 0:
        median_change = (median_change_values[len(median_change_values)//2-1] + median_change_values[len(median_change_values)//2]) / 2

    divergences = []
    if len(prices) >= 2 and avg_price:
        for r in available:
            deviation = (r["price"] / avg_price - 1) * 100
            if abs(deviation) >= 0.20:
                divergences.append({"exchange": r["exchange"], "market": r["market"], "deviation_pct": round(deviation, 4), "direction": "ABOVE GLOBAL MEAN" if deviation > 0 else "BELOW GLOBAL MEAN"})
    changes = [r["change_24h_pct"] for r in available if r.get("change_24h_pct") is not None]
    consensus = _direction(median_change)
    consensus_ratio = (sum(1 for c in changes if _direction(c) == consensus) / len(changes)) if changes and consensus != "UNCONFIRMED" else None

    # This is a coarse 24h cross-exchange anomaly screen, not a true short-horizon forecast.
    alert_level = "NORMAL"
    alert_title = "No cross-exchange 24h anomaly detected"
    alert_direction = "SIDEWAYS"
    reasons = []
    if len(available) < 2:
        alert_level = "DATA LIMITED"
        alert_title = "Not enough exchanges available to confirm a global move"
        alert_direction = "UNCONFIRMED"
        reasons.append(f"Only {len(available)} of {len(rows)} provider endpoints returned usable prices.")
    else:
        if median_change is not None and abs(median_change) >= 2:
            alert_level = "ELEVATED"
            alert_title = f"Large 24h global move: {median_change:+.2f}% median change"
            alert_direction = _direction(median_change)
            reasons.append("Median 24h change crossed the 2% monitoring threshold.")
        if len(changes) >= 3 and max(changes) - min(changes) >= 1.0:
            alert_level = "ELEVATED"
            alert_title = "Exchange changes diverge materially"
            reasons.append(f"24h change spread is {max(changes) - min(changes):.2f} percentage points.")
        if not reasons:
            reasons.append("No 24h threshold was crossed; this endpoint does not measure second-by-second order flow.")
        alert_direction = _direction(median_change)

    derivatives = [r for r in available if r.get("funding_rate_pct") is not None or r.get("open_interest") is not None]
    oi_values = [r["open_interest"] for r in derivatives if r.get("open_interest") is not None]
    funding_values = [r["funding_rate_pct"] for r in derivatives if r.get("funding_rate_pct") is not None]
    smart = {
        "open_interest": oi_values[0] if oi_values else None,
        "open_interest_source": next((r["exchange"] for r in derivatives if r.get("open_interest") is not None), None),
        "funding_rate_pct": funding_values[0] if funding_values else None,
        "funding_source": next((r["exchange"] for r in derivatives if r.get("funding_rate_pct") is not None), None),
        "order_book_imbalance": None,
        "note": "OI/funding are single-provider snapshots when available; order-book and liquidation feeds are not yet connected.",
    }
    now = datetime.now(timezone.utc).isoformat()
    return {
        "status": "OK" if available else "DATA LIMITED",
        "symbol": symbol,
        "base_asset": "BTC" if symbol.startswith("BTC") else "ETH",
        "updated_at": now,
        "cache_seconds": CACHE_SECONDS,
        "provider_count": len(rows),
        "available_count": len(available),
        "global_mean_price": avg_price,
        "median_change_24h_pct": median_change,
        "consensus": consensus,
        "consensus_ratio": round(consensus_ratio * 100, 1) if consensus_ratio is not None else None,
        "exchanges": rows,
        "divergences": divergences,
        "early_warning": {"level": alert_level, "title": alert_title, "direction": alert_direction, "reasons": reasons,
                          "method": "Cross-exchange 24h ticker thresholds; not a guaranteed sudden-move prediction."},
        "smart_money": smart,
        "liquidation_risk": {"status": "NOT CONNECTED", "long_short_squeeze": "UNCONFIRMED", "note": "No reliable liquidation stream is connected in this version."},
        "probability": {"up_pct": None, "down_pct": None, "status": "NOT CALIBRATED", "note": "Probability is withheld until historical events can be backtested and calibrated."},
    }


@router.get("/snapshot")
def global_snapshot(symbol: str = Query("BTCUSDT"), force: bool = Query(False)):
    # Only BTC and ETH are currently supported by the global public-provider adapters.
    requested = symbol.upper().replace("/", "").replace("-", "")
    aliases = {"BTC": "BTCUSDT", "BTCUSD": "BTCUSDT", "BTCUSDT": "BTCUSDT",
               "ETH": "ETHUSDT", "ETHUSD": "ETHUSDT", "ETHUSDT": "ETHUSDT"}
    if requested not in aliases:
        return {"status": "UNSUPPORTED SYMBOL", "symbol": requested,
                "message": "Global monitor currently supports BTC/USD and ETH/USD only. Select BTC or ETH.",
                "provider_count": 0, "available_count": 0, "exchanges": [],
                "consensus": "UNCONFIRMED", "early_warning": {"level": "DATA LIMITED",
                "title": "Global data unavailable for this symbol", "direction": "UNCONFIRMED",
                "reasons": ["No global provider adapter is configured for this symbol."],
                "method": "No stale BTC/ETH data is reused for unsupported symbols."}}
    normalized = aliases[requested]
    now = time.time()
    with _lock:
        cached = _cache.get(normalized)
        if not force and cached and now - cached["at"] < CACHE_SECONDS:
            return cached["data"]
    data = _build_snapshot(normalized)
    with _lock:
        _cache[normalized] = {"at": time.time(), "data": data}
    return data
