"""
NAKSHATRA AI v4.0 - Fast dashboard API

Drop-in replacement for main.py.

The trading/analysis engine is not changed. This file:
- avoids JSONResponse around analysis objects,
- adds a lightweight analysis cache,
- prevents duplicate dashboard/scanner analysis calls,
- exposes /api/live and /api/debug-data for the dashboard,
- returns explicit errors instead of leaving the UI stuck on Loading.
"""

from contextlib import asynccontextmanager
import time
import math

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from scheduler import start_scheduler
from logger import logger
from database.database import initialize_database
from database.models import get_all_trades, get_open_trades
from history import get_multi_timeframe_history
from analysis.signal import generate_signal
from scanner import market_scan
from delta import get_ticker, BASE_URL, session

CACHE_TTL = 8
PRODUCTS_TTL = 300
_analysis_cache = {}
_products_cache = {"time": 0, "items": []}


def _json_safe(value):
    """Convert common pandas/numpy scalar values without changing the engine."""
    if value is None or isinstance(value, (str, bool, int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return value

    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except Exception:
            pass

    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]

    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass

    return str(value)



def _product_row(row):
    """Normalize one Delta product row for the dashboard/search API."""
    symbol = str(row.get("symbol") or "").upper().strip()
    contract_type = str(row.get("contract_type") or "").lower().strip()
    state = str(row.get("state") or "").lower().strip()
    trading_status = str(row.get("trading_status") or "").lower().strip()
    return {
        "symbol": symbol,
        "description": row.get("description") or symbol,
        "contract_type": contract_type,
        "underlying": (
            (row.get("underlying_asset") or {}).get("symbol")
            if isinstance(row.get("underlying_asset"), dict)
            else row.get("underlying_asset_symbol")
        ),
        "state": state,
        "trading_status": trading_status,
    }


def get_product(symbol):
    """Fetch and validate one product directly from Delta.

    Direct /products/{symbol} lookup is deliberately used for validation instead
    of trusting a paginated product-list cache.  This avoids false DATA RISK when
    the list endpoint changes ordering/pagination while the product itself is live.
    """
    symbol = str(symbol or "").upper().strip()
    if not symbol:
        return None
    try:
        response = session.get(f"{BASE_URL}/products/{symbol}", timeout=10)
        response.raise_for_status()
        payload = response.json()
        row = payload.get("result") or {}
        if isinstance(row, list):
            row = next((x for x in row if str(x.get("symbol", "")).upper() == symbol), {})
        if not isinstance(row, dict) or not row.get("symbol"):
            return None
        item = _product_row(row)
        if item["state"] and item["state"] != "live":
            return None
        if item["trading_status"] and item["trading_status"] not in {"operational", "active"}:
            return None
        if item["contract_type"] in {"call_options", "put_options"} or "option" in item["contract_type"]:
            return None
        return item
    except Exception as exc:
        logger.warning("Delta product lookup failed %s: %s", symbol, exc)
        return None


def get_live_products():
    """Return live non-option Delta trading products for crypto search."""
    now = time.time()
    if _products_cache["items"] and now - _products_cache["time"] < PRODUCTS_TTL:
        return _products_cache["items"]

    try:
        rows = []
        after = None
        for _ in range(20):
            params = {
                "states": "live",
                "contract_types": "perpetual_futures,futures",
                "page_size": 100,
            }
            if after:
                params["after"] = after
            response = session.get(f"{BASE_URL}/products", params=params, timeout=10)
            response.raise_for_status()
            payload = response.json()
            result = payload.get("result") or []
            if isinstance(result, dict):
                result = [result]
            rows.extend(result)
            after = (payload.get("meta") or {}).get("after")
            if not after:
                break

        items = []
        seen = set()
        for row in rows:
            item = _product_row(row)
            symbol = item["symbol"]
            if not symbol or symbol in seen:
                continue
            if item["state"] not in {"", "live"}:
                continue
            if item["trading_status"] and item["trading_status"] not in {"operational", "active"}:
                continue
            if item["contract_type"] not in {"perpetual_futures", "futures"}:
                continue
            seen.add(symbol)
            items.append(item)

        # Always verify the two dashboard quick buttons directly. This is also a
        # fallback if the paginated product list is temporarily incomplete.
        for quick in ("BTCUSD", "ETHUSD"):
            if quick not in seen:
                item = get_product(quick)
                if item and item["symbol"] not in seen:
                    items.append(item)
                    seen.add(item["symbol"])

        items.sort(key=lambda x: (x["symbol"] not in {"BTCUSD", "ETHUSD"}, x["symbol"]))
        _products_cache.update({"time": now, "items": items})
        return items
    except Exception as exc:
        logger.warning("Delta products failed: %s", exc)
        # Keep the dashboard usable even if the paginated search endpoint fails.
        fallback = []
        for quick in ("BTCUSD", "ETHUSD"):
            item = get_product(quick)
            if item:
                fallback.append(item)
        if fallback:
            _products_cache.update({"time": now, "items": fallback})
        return _products_cache["items"]

def run_analysis(symbol: str, force=False):
    symbol = symbol.upper()
    now = time.time()

    if not force:
        cached = _analysis_cache.get(symbol)
        if cached and now - cached["time"] < CACHE_TTL:
            return cached["result"]

    started = time.time()

    try:
        data = get_multi_timeframe_history(symbol, limit=200)

        entry = data.get("5m")
        if entry is None or entry.empty:
            result = {
                "status": "NO DATA",
                "symbol": symbol,
                "message": "Delta 5m candle data unavailable",
                "server_time": time.time(),
            }
            _analysis_cache[symbol] = {"time": time.time(), "result": result}
            return result

        # Preserve the existing signal engine exactly.
        entry = data.get("5m") if isinstance(data, dict) else data
        if entry is None or getattr(entry, "empty", True):
            result = {
                "status": "NO DATA",
                "symbol": symbol,
                "message": "Delta 5m candle data unavailable",
                "server_time": time.time(),
            }
            _analysis_cache[symbol] = {"time": time.time(), "result": result}
            return result

        result = generate_signal(entry, symbol=symbol)
        result = _json_safe(result)

        if isinstance(result, dict):
            result["status"] = "OK"
            result["server_ms"] = round((time.time() - started) * 1000)

        _analysis_cache[symbol] = {"time": time.time(), "result": result}
        return result

    except Exception as exc:
        logger.exception("ANALYSIS ERROR %s", symbol)
        result = {
            "status": "ERROR",
            "symbol": symbol,
            "message": str(exc),
            "server_ms": round((time.time() - started) * 1000),
        }
        _analysis_cache[symbol] = {"time": time.time(), "result": result}
        return result


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting NAKSHATRA AI v4.0")
    initialize_database()
    start_scheduler()
    yield
    logger.info("Stopping NAKSHATRA AI v4.0")


app = FastAPI(
    title="NAKSHATRA AI v4.0",
    version="4.0",
    lifespan=lifespan,
)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"request": request},
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"request": request},
    )


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/api")
def api():
    return {
        "project": "NAKSHATRA AI",
        "version": "4.0",
        "status": "RUNNING",
        "supported_symbols": ["BTCUSD", "ETHUSD"],
        "symbol_search": "/api/products",
        "dashboard_api": "/api/live?symbol=BTCUSD",
    }



@app.get("/api/products")
def api_products(q: str = ""):
    query = q.upper().strip()
    items = get_live_products()
    if query:
        items = [
            x for x in items
            if query in x["symbol"]
            or query in str(x.get("description", "")).upper()
            or query in str(x.get("underlying", "")).upper()
        ]
    return {"status": "OK", "count": len(items), "products": items[:50]}

@app.get("/api/live")
def api_live(symbol: str = "BTCUSD", force: bool = False):
    symbol = symbol.upper().strip()
    product = get_product(symbol)
    if product is None:
        valid = {x["symbol"] for x in get_live_products()}
        if symbol not in valid:
            return {
                "status": "NO DATA",
                "symbol": symbol,
                "message": "Symbol is not a live Delta Exchange product",
            }
    analysis = run_analysis(symbol, force=force)

    ticker = None
    try:
        ticker = get_ticker(symbol)
    except Exception as exc:
        logger.warning("Ticker failed %s: %s", symbol, exc)

    return _json_safe({
        "status": analysis.get("status", "UNKNOWN")
            if isinstance(analysis, dict) else "UNKNOWN",
        "symbol": symbol,
        "ticker": ticker,
        "analysis": analysis,
        "server_time": time.time(),
    })


@app.get("/api/debug-data")
def debug_data(symbol: str = "BTCUSD"):
    symbol = symbol.upper()
    data = get_multi_timeframe_history(symbol, limit=20)

    return {
        "symbol": symbol,
        "timeframes": {
            tf: {
                "rows": int(len(df)),
                "empty": bool(df.empty),
                "last_close": (
                    float(df["close"].iloc[-1])
                    if not df.empty and "close" in df.columns
                    else None
                ),
            }
            for tf, df in data.items()
        },
    }


@app.get("/stats")
def stats():
    trades = get_all_trades()
    total = len(trades)
    wins = losses = open_positions = 0
    total_pnl = 0

    for trade in trades:
        try:
            pnl = float(trade[8] or 0)
        except Exception:
            pnl = 0

        result = trade[13]

        total_pnl += pnl

        if result == "WIN":
            wins += 1
        elif result == "LOSS":
            losses += 1
        elif result == "OPEN":
            open_positions += 1

    win_rate = round(wins / (wins + losses) * 100, 2) if wins + losses else 0

    return {
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "open_trades": open_positions,
        "win_rate": win_rate,
        "net_pnl": total_pnl,
    }


@app.get("/trades")
def trades():
    data = get_all_trades()
    return {"count": len(data), "trades": data}


@app.get("/open-trades")
def open_trades():
    data = get_open_trades()
    return {"count": len(data), "trades": data}


@app.get("/api/history")
def api_history():
    trades = get_all_trades()
    history = []

    for t in trades[-100:]:
        history.append({
            "symbol": t[1],
            "side": t[2],
            "entry": t[5],
            "exit": t[6],
            "pnl": t[8],
            "status": t[13],
        })

    return _json_safe(history)


@app.get("/api/scanner")
def api_scanner():
    # Reuse the same cached analysis endpoint instead of running six
    # fresh Delta requests for each scanner refresh.
    results = []

    for symbol in ("BTCUSD", "ETHUSD"):
        result = run_analysis(symbol)
        technical = result.get("technical", {}) if isinstance(result, dict) else {}

        results.append({
            "symbol": symbol,
            "signal": (
                technical.get("signal")
                or result.get("signal")
                or result.get("recommendation")
                or "WAIT"
            ),
            "strength": (
                technical.get("confidence")
                or result.get("overall_confidence")
                or 0
            ),
            "status": result.get("status", "UNKNOWN"),
            "message": result.get("message", ""),
        })

    return results


@app.get("/btc")
def btc():
    return run_analysis("BTCUSD")


@app.get("/eth")
def eth():
    return run_analysis("ETHUSD")


@app.get("/signal")
def signal():
    return run_analysis("BTCUSD")


@app.get("/signal/{symbol}")
def signal_symbol(symbol: str):
    return run_analysis(symbol)


@app.get("/analysis")
def analysis():
    return run_analysis("BTCUSD")


@app.get("/analysis/{symbol}")
def analysis_symbol(symbol: str):
    return run_analysis(symbol)


@app.get("/scan")
def scan():
    try:
        market_scan()
        return {"status": "SUCCESS", "message": "Market Scan Completed"}
    except Exception as exc:
        logger.exception("Manual scan failed")
        return {"status": "ERROR", "message": str(exc)}
