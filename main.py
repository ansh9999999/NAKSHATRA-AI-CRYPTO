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
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal, InvalidOperation
import requests

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from scheduler import start_scheduler
from logger import logger
from database.database import initialize_database
from database.models import get_all_trades, get_open_trades
from history import get_multi_timeframe_history, get_history
from analysis.signal import generate_signal
from scanner import market_scan
from delta import get_ticker, BASE_URL, session
from global_market.router import router as global_market_router

CACHE_TTL = 8
PRODUCTS_TTL = 300
_analysis_cache = {}
_products_cache = {"time": 0, "items": []}
_product_price_cache = {}
PRODUCT_PRICE_TTL = 10
_calendar_cache = {"time": 0, "payload": None}
CALENDAR_TTL = 300


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



def _delta_display_price(symbol: str):
    """Return Delta's ticker price as an exact decimal string for search results.

    Parse JSON decimal tokens as Decimal so the browser receives the full precision
    provided by Delta instead of a rounded JavaScript/Python float.
    """
    symbol = str(symbol or "").upper().strip()
    if not symbol:
        return None
    now = time.time()
    cached = _product_price_cache.get(symbol)
    if cached and now - cached[0] < PRODUCT_PRICE_TTL:
        return cached[1]
    try:
        response = session.get(f"{BASE_URL}/tickers/{symbol}", timeout=5)
        if response.ok:
            payload = json.loads(response.text, parse_float=Decimal, parse_int=Decimal)
            row = payload.get("result") or {}
            if isinstance(row, list):
                row = next((x for x in row if isinstance(x, dict) and str(x.get("symbol", "")).upper() == symbol), {})
            if not isinstance(row, dict) or (row.get("symbol") and str(row.get("symbol")).upper() != symbol):
                row = {}
            raw = row.get("close") or row.get("mark_price") or row.get("spot_price")
            if raw not in (None, "", 0, "0"):
                price = format(raw, "f") if isinstance(raw, Decimal) else str(raw).strip()
                _product_price_cache[symbol] = (now, price)
                return price
        # Use the same exact-symbol ticker fallback as the live market endpoint.
        ticker = get_ticker(symbol)
        raw = ticker.get("price_exact") if ticker else None
        if raw not in (None, "", "0", "0.0"):
            _product_price_cache[symbol] = (now, str(raw))
            return str(raw)
        return None
    except Exception as exc:
        logger.debug("Delta search price unavailable for %s: %s", symbol, exc)
        return None

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
app.include_router(global_market_router)


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
        # If the paginated list/search cache omitted an exact product, resolve the
        # entered ticker directly (DOGEUSD, DOGEUSDT, etc.) before returning empty.
        direct_candidates = [query]
        if query.endswith("USDT"):
            direct_candidates.append(query[:-1])
        elif query.endswith("USD"):
            direct_candidates.append(query + "T")
        elif query.isalpha() and 2 <= len(query) <= 12:
            direct_candidates.extend([query + "USD", query + "USDT", query + "USDTM"])
        known = {x["symbol"] for x in items}
        for candidate in direct_candidates:
            if candidate in known:
                continue
            item = get_product(candidate)
            if item and item["symbol"] not in known:
                items.append(item)
                known.add(item["symbol"])
                # Directly resolved symbol is the strongest search match.
                if candidate == query or item["symbol"] == query:
                    break
    # Attach live prices to only the first eight visible search results. Prices are
    # cached briefly to avoid hammering Delta while the user types.
    visible = []
    for item in items[:8]:
        row = dict(item)
        row["price"] = _delta_display_price(row["symbol"])
        visible.append(row)
    return {"status": "OK", "count": len(items), "products": visible}

@app.get("/api/ticker")
def api_ticker(symbol: str = "BTCUSD"):
    """Fast, exact-symbol ticker endpoint so the market card updates before analytics."""
    symbol = str(symbol or "BTCUSD").upper().strip()
    try:
        ticker = get_ticker(symbol)
    except Exception as exc:
        logger.warning("Fast ticker failed %s: %s", symbol, exc)
        ticker = None
    if ticker is None:
        return {"status": "NO TICKER DATA", "symbol": symbol, "ticker": None,
                "message": f"No exact live ticker returned for {symbol}; no other coin's data was substituted."}
    return _json_safe({"status": "OK", "symbol": symbol, "ticker": ticker, "server_time": time.time()})


@app.get("/api/live")
def api_live(symbol: str = "BTCUSD", force: bool = False):
    symbol = symbol.upper().strip()
    # Fetch exact ticker first. A live ticker is sufficient to show the market
    # card even if the product-list endpoint is temporarily incomplete.
    ticker = None
    try:
        ticker = get_ticker(symbol)
    except Exception as exc:
        logger.warning("Ticker failed %s: %s", symbol, exc)
    if ticker is None:
        valid = {x["symbol"] for x in get_live_products()}
        if symbol not in valid and get_product(symbol) is None:
            return {"status": "NO DATA", "symbol": symbol, "message": "No live Delta ticker/product found for this exact symbol"}
    analysis = run_analysis(symbol, force=force)

    # Live ticker and candle-analysis availability are separate. For searchable
    # Delta contracts without candle history, still return the real ticker so the
    # UI can show its exact price and mark analysis fields unavailable.
    response_status = "OK" if ticker is not None else "NO TICKER DATA"
    return _json_safe({
        "status": response_status,
        "symbol": symbol,
        "ticker": ticker,
        "analysis": analysis,
        "server_time": time.time(),
        "message": None if ticker is not None else f"Delta listed {symbol}, but its live ticker is unavailable from direct and collection endpoints. Check contract status/symbol on Delta Exchange.",
    })


@app.get("/api/calendar")
def api_calendar(days: int = 7):
    """Fetch upcoming economic calendar events from TradingView's public calendar feed.

    The feed is an external public endpoint and may occasionally be rate-limited or
    changed upstream. Never fabricate calendar events when the feed is unavailable.
    """
    now = time.time()
    cached = _calendar_cache.get("payload")
    if cached and now - _calendar_cache.get("time", 0) < CALENDAR_TTL:
        return cached

    days = max(1, min(int(days or 7), 14))
    start = datetime.now(timezone.utc)
    end = start + timedelta(days=days)
    url = "https://economic-calendar.tradingview.com/events"
    params = {
        "from": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "to": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "countries": "US,IN,EU,GB,JP,CN",
    }
    headers = {
        "Origin": "https://in.tradingview.com",
        "Referer": "https://in.tradingview.com/economic-calendar/",
        "User-Agent": "Mozilla/5.0 (compatible; NakshatraDashboard/7.1)",
        "Accept": "application/json, text/plain, */*",
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=8)
        response.raise_for_status()
        body = response.json()
        raw_events = body.get("result", []) if isinstance(body, dict) else []
        if not isinstance(raw_events, list):
            raw_events = []
        ist = ZoneInfo("Asia/Kolkata")
        events = []
        for item in raw_events:
            if not isinstance(item, dict):
                continue
            raw_date = item.get("date") or item.get("datetime") or item.get("time")
            event_dt = None
            if isinstance(raw_date, (int, float)):
                event_dt = datetime.fromtimestamp(raw_date, tz=timezone.utc)
            elif raw_date:
                try:
                    event_dt = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
                    if event_dt.tzinfo is None:
                        event_dt = event_dt.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    event_dt = None
            if event_dt is None or event_dt < start - timedelta(minutes=2) or event_dt > end:
                continue
            event_ist = event_dt.astimezone(ist)
            imp_raw = item.get("importance", item.get("impact", 0))
            try:
                imp_num = int(imp_raw)
            except (ValueError, TypeError):
                imp_num = 3 if "high" in str(imp_raw).lower() else 2 if "medium" in str(imp_raw).lower() else 1 if "low" in str(imp_raw).lower() else 0
            imp = "HIGH" if imp_num >= 3 else "MEDIUM" if imp_num == 2 else "LOW" if imp_num == 1 else "UNRATED"
            country = str(item.get("country") or item.get("currency") or "Global")
            title = str(item.get("title") or item.get("indicator") or "Economic event")
            actual = item.get("actual")
            forecast = item.get("forecast")
            previous = item.get("previous")
            is_us = country.upper() in {"US", "USA", "USD", "UNITED STATES"}
            effect = ("Potentially high volatility for BTC/ETH. For US releases, compare actual vs forecast and watch USD/yields; direction is not guaranteed."
                      if imp == "HIGH" and is_us else
                      "Potential volatility for BTC/ETH; check the released value against forecast before assigning bullish or bearish direction."
                      if imp in {"HIGH", "MEDIUM"} else
                      "Usually lower scheduled impact; monitor only if the result surprises expectations.")
            events.append({
                "name": title,
                "country": country,
                "datetime_ist": event_ist.strftime("%a, %d %b • %I:%M %p IST"),
                "timestamp": int(event_dt.timestamp()),
                "importance": imp,
                "impact": imp,
                "actual": actual,
                "forecast": forecast,
                "previous": previous,
                "effect": effect,
                "status": "Upcoming • verify release on source",
                "source": "TradingView Economic Calendar",
            })
        events.sort(key=lambda e: e["timestamp"])
        next_day = start + timedelta(hours=24)
        high_soon = any(e["importance"] == "HIGH" and e["timestamp"] <= next_day.timestamp() for e in events)
        payload = {
            "status": "OK" if events else "EMPTY",
            "source": "TradingView Economic Calendar",
            "source_url": "https://in.tradingview.com/economic-calendar/",
            "updated_ist": datetime.now(ist).strftime("%d %b %Y, %I:%M:%S %p IST"),
            "risk": "ELEVATED" if high_soon else "NORMAL",
            "events": events[:20],
            "disclaimer": "Calendar times are converted to IST. Event effects are conditional, not predictions; actual/forecast may be blank until release.",
            "message": None if events else "TradingView returned no upcoming events for the selected window.",
        }
    except Exception as exc:
        logger.warning("TradingView calendar fetch failed: %s", str(exc)[:180])
        payload = {
            "status": "UNAVAILABLE", "source": "TradingView Economic Calendar",
            "source_url": "https://in.tradingview.com/economic-calendar/",
            "updated_ist": None, "risk": "UNCONFIRMED", "events": [],
            "disclaimer": "Live calendar feed could not be reached. No events are invented; open TradingView calendar to verify schedules.",
            "message": "TradingView calendar feed unavailable from this server.",
        }
    _calendar_cache["time"] = now
    _calendar_cache["payload"] = payload
    return payload


@app.get("/api/chart")
def api_chart(symbol: str = "BTCUSD", resolution: str = "15m", limit: int = 80):
    try:
        limit = max(20, min(int(limit), 200))
        df = get_history(symbol.upper().strip(), resolution, limit)
        if df is None or df.empty:
            return {"status": "NO_DATA", "symbol": symbol, "rows": []}
        rows = []
        for _, r in df.tail(limit).iterrows():
            rows.append({
                "time": r.get("time"),
                "open": float(r.get("open", 0)),
                "high": float(r.get("high", 0)),
                "low": float(r.get("low", 0)),
                "close": float(r.get("close", 0)),
                "volume": float(r.get("volume", 0)),
            })
        return {"status": "OK", "symbol": symbol.upper(), "resolution": resolution, "rows": rows}
    except Exception as exc:
        logger.warning("Chart failed %s: %s", symbol, exc)
        return {"status": "ERROR", "symbol": symbol, "rows": [], "message": str(exc)}


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


@app.get("/api/market-history")
def api_market_history(symbol: str = "BTCUSD", resolution: str = "5m", limit: int = 100):
    """Return Delta candle history for dashboard indicators such as Stochastic RSI."""
    safe_symbol = str(symbol or "BTCUSD").upper().strip()
    if safe_symbol not in ("BTCUSD", "ETHUSD"):
        return {"status": "UNAVAILABLE", "rows": [], "message": "Unsupported Delta crypto symbol"}
    safe_resolution = str(resolution or "5m").lower().strip()
    if safe_resolution not in ("1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d", "1w"):
        return {"status": "UNAVAILABLE", "rows": [], "message": "Unsupported candle resolution"}
    safe_limit = max(20, min(int(limit or 100), 500))
    try:
        frame = get_history(safe_symbol, safe_resolution, safe_limit)
        if frame is None or frame.empty:
            return {"status": "UNAVAILABLE", "symbol": safe_symbol, "rows": [], "message": "No candles returned by Delta history provider"}
        rows = frame.to_dict(orient="records")
        return {"status": "OK", "symbol": safe_symbol, "resolution": safe_resolution, "rows": _json_safe(rows)}
    except Exception as exc:
        return {"status": "UNAVAILABLE", "symbol": safe_symbol, "rows": [], "message": str(exc)[:160]}


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
