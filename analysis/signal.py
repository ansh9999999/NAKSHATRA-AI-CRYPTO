from __future__ import annotations

from datetime import datetime, timezone
from math import floor, sin, pi

from analysis.indicators import ema, rsi, macd, atr, trend
from delta import get_option_chain
from history import get_history
from market_context import session_context, event_context


def _num(v, default=0.0):
    try:
        x = float(v)
        return x if x == x else default
    except Exception:
        return default


def _candle_datetime(df):
    """Return the latest candle timestamp as an aware UTC datetime."""
    if df is None or df.empty or "time" not in df.columns:
        return datetime.now(timezone.utc)
    value = df["time"].iloc[-1]
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _digit_sum(n):
    n = abs(int(n))
    while n > 9:
        n = sum(int(ch) for ch in str(n))
    return n


def _numerology(dt, symbol):
    digits = [int(c) for c in dt.strftime("%Y%m%d")]
    life_path = _digit_sum(sum(digits))
    expression = _digit_sum(sum(ord(c) for c in symbol if c.isalpha()))
    day_vibration = _digit_sum(dt.day)
    market_number = _digit_sum(sum(ord(c) for c in symbol if c.isalpha()) + dt.day)

    # Market-facing numerology score: bounded, deterministic and transparent.
    raw = ((life_path + expression + day_vibration + market_number) % 9) - 4
    score = int(raw)
    bias = "BULLISH" if score >= 2 else "BEARISH" if score <= -2 else "NEUTRAL"
    return {
        "bias": bias,
        "score": score,
        "life_path": life_path,
        "expression": expression,
        "day_vibration": day_vibration,
        "market_number": market_number,
        "reasons": [f"Numerology score {score:+d} from date/symbol vibration"],
    }


def _astrology(dt):
    """Lightweight lunar-cycle dashboard heuristic; not a natal chart."""
    # Synodic-month approximation. Reference new moon: 2000-01-06 18:14 UTC.
    ref = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    age = ((dt - ref).total_seconds() / 86400.0) % 29.530588853
    phase = (age / 29.530588853) * 360.0
    illum = (1 - __import__("math").cos(phase * pi / 180.0)) / 2

    if age < 1.85 or age >= 27.68:
        moon_phase = "NEW MOON"
    elif age < 7.38:
        moon_phase = "WAXING CRESCENT"
    elif age < 9.23:
        moon_phase = "FIRST QUARTER"
    elif age < 14.77:
        moon_phase = "WAXING GIBBOUS"
    elif age < 16.61:
        moon_phase = "FULL MOON"
    elif age < 22.15:
        moon_phase = "WANING GIBBOUS"
    elif age < 24.00:
        moon_phase = "LAST QUARTER"
    else:
        moon_phase = "WANING CRESCENT"

    # Stable dashboard bias buckets. This is intentionally presented as a
    # heuristic rather than a scientific market predictor.
    phase_bias = {
        "NEW MOON": -1,
        "WAXING CRESCENT": 1,
        "FIRST QUARTER": 2,
        "WAXING GIBBOUS": 1,
        "FULL MOON": -1,
        "WANING GIBBOUS": -2,
        "LAST QUARTER": -2,
        "WANING CRESCENT": -1,
    }[moon_phase]
    weekday_bias = {0: 1, 1: -1, 2: 1, 3: 0, 4: -1, 5: 0, 6: 1}[dt.weekday()]
    score = max(-4, min(4, phase_bias + weekday_bias))
    bias = "BULLISH" if score >= 2 else "BEARISH" if score <= -2 else "NEUTRAL"

    # Display fields requested by the legacy Nakshatra UI. The values are
    # deterministic dashboard descriptors, not a claim of astronomical
    # precision for Vedic ephemeris calculations.
    nakshatras = [
        "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
        "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
        "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
        "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta",
        "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
    ]
    nak = nakshatras[int((phase / 360.0) * 27) % 27]
    tithi = int(age / 29.530588853 * 30) + 1
    yoga = "Supportive" if (tithi + dt.weekday()) % 3 == 0 else "Neutral"
    karana = "Bearish" if (tithi + dt.day) % 4 == 0 else "Neutral"

    return {
        "bias": bias,
        "score": score,
        "moon_phase": moon_phase,
        "illumination": round(illum * 100, 1),
        "nakshatra": nak,
        "tithi": tithi,
        "yoga": yoga,
        "karana": karana,
        "rashi_trend": bias,
        "nakshatra_influence": bias,
        "tithi_impact": bias,
        "planetary_alignment": "Bearish" if score < 0 else "Bullish" if score > 0 else "Neutral",
        "reasons": [f"Moon phase: {moon_phase}", f"Nakshatra: {nak}", f"Tithi: {tithi}"],
    }


def _option_analysis(symbol, spot):
    try:
        chain = get_option_chain(symbol)
    except Exception as exc:
        return {"status": "ERROR", "signal": "NEUTRAL", "confidence": 0, "reason": str(exc), "rows": []}

    # Accept both the current mapping response and a legacy raw-list response.
    if isinstance(chain, list):
        chain = {"status": "OK", "symbol": symbol, "rows": chain}
    elif not isinstance(chain, dict):
        chain = {"status": "ERROR", "symbol": symbol, "rows": [], "reason": "Invalid option-chain response"}
    rows = chain.get("rows", []) or []
    if not rows:
        return {**chain, "score": 0, "signal": "NEUTRAL", "confidence": 0,
                "pcr_oi": None, "pcr_volume": None, "atm": None, "support": None,
                "resistance": None, "max_pain": None, "atm_chain": []}

    # Normalize both the current CE/PE schema and legacy Delta field names.
    normalized_rows = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        rr = dict(r)
        ctype = str(rr.get("type") or rr.get("contract_type") or "").lower()
        if ctype in ("call_options", "call", "ce"):
            rr["type"] = "CE"
        elif ctype in ("put_options", "put", "pe"):
            rr["type"] = "PE"
        strike = rr.get("strike")
        if strike is None:
            strike = rr.get("strike_price")
        rr["strike"] = _num(strike, None) if strike is not None else None
        if rr.get("ltp") is None:
            rr["ltp"] = rr.get("close") or rr.get("mark_price")
        normalized_rows.append(rr)

    rows = normalized_rows
    calls = [r for r in rows if r.get("type") == "CE"]
    puts = [r for r in rows if r.get("type") == "PE"]
    strikes = sorted({r["strike"] for r in rows if r.get("strike") is not None})
    if not calls or not puts or not strikes:
        return {**chain, "score": 0, "signal": "NEUTRAL", "confidence": 0,
                "pcr_oi": None, "pcr_volume": None, "atm": None, "support": None,
                "resistance": None, "max_pain": None, "atm_chain": []}

    atm = min(strikes, key=lambda x: abs(x - spot))
    call_oi = sum(_num(r.get("oi")) for r in calls)
    put_oi = sum(_num(r.get("oi")) for r in puts)
    call_vol = sum(_num(r.get("volume")) for r in calls)
    put_vol = sum(_num(r.get("volume")) for r in puts)
    pcr = put_oi / call_oi if call_oi else None
    vpcr = put_vol / call_vol if call_vol else None
    support = max(puts, key=lambda r: _num(r.get("oi")))["strike"] if puts else None
    resistance = max(calls, key=lambda r: _num(r.get("oi")))["strike"] if calls else None

    max_pain = None
    min_pain = None
    for k in strikes:
        pain = sum(max(k - r["strike"], 0) * _num(r.get("oi")) for r in calls)
        pain += sum(max(r["strike"] - k, 0) * _num(r.get("oi")) for r in puts)
        if min_pain is None or pain < min_pain:
            min_pain, max_pain = pain, k

    score = 0
    reasons = []
    if pcr is not None:
        if pcr >= 1.20: score += 25; reasons.append(f"PCR {pcr:.2f} is bullish")
        elif pcr >= 1.00: score += 10; reasons.append(f"PCR {pcr:.2f} mildly bullish")
        elif pcr <= 0.75: score -= 25; reasons.append(f"PCR {pcr:.2f} is bearish")
        else: score -= 10; reasons.append(f"PCR {pcr:.2f} mildly bearish")
    if vpcr is not None:
        if vpcr >= 1.10: score += 10; reasons.append("Volume PCR supports buyers")
        elif vpcr <= 0.80: score -= 10; reasons.append("Volume PCR supports sellers")
    score = max(-35, min(35, score))
    signal = "BUY" if score >= 20 else "SELL" if score <= -20 else "NEUTRAL"
    confidence = int(round(abs(score) / 35 * 100))

    nearby = sorted(strikes, key=lambda x: abs(x - atm))[:11]
    atm_chain = []
    for k in sorted(nearby):
        ce = next((r for r in calls if r["strike"] == k), None)
        pe = next((r for r in puts if r["strike"] == k), None)
        atm_chain.append({
            "strike": k, "atm": k == atm,
            "call_ltp": ce and ce.get("ltp"), "call_oi": ce and ce.get("oi"),
            "call_volume": ce and ce.get("volume"), "put_ltp": pe and pe.get("ltp"),
            "put_oi": pe and pe.get("oi"), "put_volume": pe and pe.get("volume"),
        })

    return {
        **chain, "score": score, "signal": signal, "confidence": confidence,
        "reason": " • ".join(reasons[:4]) or "Live Delta option-chain data",
        "pcr_oi": round(pcr, 3) if pcr is not None else None,
        "pcr_volume": round(vpcr, 3) if vpcr is not None else None,
        "atm": atm, "support": support, "resistance": resistance, "max_pain": max_pain,
        # Delta `oi` is open interest in contracts. Keep contract OI
        # separate from `oi_value`, which is the notional/base-currency value.
        "oi_unit": "contracts",
        "call_oi": round(call_oi, 3), "put_oi": round(put_oi, 3),
        "call_oi_contracts": round(call_oi, 3),
        "put_oi_contracts": round(put_oi, 3),
        "call_oi_value": round(sum(_num(r.get("oi_value")) for r in calls), 3),
        "put_oi_value": round(sum(_num(r.get("oi_value")) for r in puts), 3),
        "oi_value_symbol": next((str(r.get("oi_value_symbol")) for r in rows if r.get("oi_value_symbol")), "USD"),
        "call_volume": round(call_vol, 3), "put_volume": round(put_vol, 3),
        "atm_chain": atm_chain,
        "top_call_oi": [{"strike": r["strike"], "oi": r.get("oi", 0)} for r in sorted(calls, key=lambda r: _num(r.get("oi")), reverse=True)[:5]],
        "top_put_oi": [{"strike": r["strike"], "oi": r.get("oi", 0)} for r in sorted(puts, key=lambda r: _num(r.get("oi")), reverse=True)[:5]],
    }


def _tf(symbol, resolution):
    df = get_history(symbol, resolution, 250)
    if df.empty:
        return {"timeframe": resolution, "trend": "NO DATA", "score": 0, "rows": 0}
    c = df.close
    e9 = ema(c, 9).iloc[-1]; e50 = ema(c, 50).iloc[-1]; e200 = ema(c, 200).iloc[-1]
    s = 2 if e9 > e50 else -2
    s += 2 if e50 > e200 else -2
    return {"timeframe": resolution, "trend": trend(c), "score": s, "rows": len(df),
            "ema9": round(float(e9), 2), "ema50": round(float(e50), 2), "ema200": round(float(e200), 2)}


def _intraday(symbol):
    frames = [_tf(symbol, x) for x in ("5m", "15m", "1h", "1d")]
    score = sum(x["score"] for x in frames)
    label = "STRONG BULLISH" if score >= 8 else "BULLISH" if score >= 3 else "STRONG BEARISH" if score <= -8 else "BEARISH" if score <= -3 else "SIDEWAYS"
    return {"overall": label, "score": score, "timeframes": frames}


def generate_signal(df=None, symbol="BTCUSD"):
    symbol = symbol.upper()
    if df is None or df.empty:
        df = get_history(symbol, "5m", 250)
    if df.empty:
        return {"status": "NO_DATA", "symbol": symbol}

    c, h, l, v = df.close, df.high, df.low, df.volume
    price = float(c.iloc[-1]); e9 = float(ema(c, 9).iloc[-1]); e21 = float(ema(c, 21).iloc[-1])
    e50 = float(ema(c, 50).iloc[-1]); e200 = float(ema(c, 200).iloc[-1]); rv = float(rsi(c).iloc[-1])
    ml, ms, _ = macd(c)
    score = 0; reasons = []
    if e9 > e21 > e50: score += 25; reasons.append("EMA stack bullish")
    elif e9 < e21 < e50: score -= 25; reasons.append("EMA stack bearish")
    elif e9 > e21: score += 10; reasons.append("Short-term EMA bullish")
    else: score -= 10; reasons.append("Short-term EMA bearish")
    if 55 <= rv <= 70: score += 15; reasons.append("RSI bullish zone")
    elif 30 <= rv <= 45: score -= 15; reasons.append("RSI bearish zone")
    elif rv > 75: score -= 10; reasons.append("RSI overbought")
    elif rv < 25: score += 10; reasons.append("RSI oversold")
    if ml.iloc[-1] > ms.iloc[-1]: score += 20; reasons.append("MACD bullish")
    else: score -= 20; reasons.append("MACD bearish")
    avg = v.tail(20).mean()
    if avg > 0 and v.iloc[-1] > avg * 1.5:
        score += 10 if c.iloc[-1] >= c.iloc[-2] else -10; reasons.append("Volume spike")
    if price > e200: score += 10; reasons.append("Price above EMA200")
    else: score -= 10; reasons.append("Price below EMA200")

    tech = max(-80, min(80, score))
    option = _option_analysis(symbol, price)
    session = session_context()
    events = event_context()

    # Relative volume: compare the latest 5m bar with the previous 20 bars.
    vol_avg = float(v.iloc[-21:-1].mean()) if len(v) > 21 else float(v.mean())
    rvol = (float(v.iloc[-1]) / vol_avg) if vol_avg > 0 else 1.0
    if rvol >= 2.0:
        volume_regime = 'EXTREME'
    elif rvol >= 1.5:
        volume_regime = 'HIGH'
    elif rvol >= 1.15:
        volume_regime = 'ELEVATED'
    elif rvol < 0.70:
        volume_regime = 'LOW'
    else:
        volume_regime = 'NORMAL'

    # Price reversal levels are volatility-derived, not guaranteed predictions.
    atr_value = float(atr(h, l, c).iloc[-1])
    resistance_level = round(price + 1.5 * atr_value, 2)
    support_level = round(price - 1.5 * atr_value, 2)
    trend_bias = 'BULLISH' if tech > 10 else 'BEARISH' if tech < -10 else 'NEUTRAL'
    reversal_level = resistance_level if trend_bias == 'BEARISH' else support_level if trend_bias == 'BULLISH' else price
    confirmation_level = round(reversal_level + (0.5 * atr_value if trend_bias == 'BEARISH' else -0.5 * atr_value), 2)

    # Use historical time-of-day volume concentration to estimate a window, not an exact reversal time.
    hour = _candle_datetime(df).astimezone(timezone.utc).hour
    if 13 <= hour <= 15:
        reversal_window = 'US / Europe overlap — elevated reversal risk'
    elif 8 <= hour <= 10:
        reversal_window = 'Europe activity window — elevated reversal risk'
    elif 0 <= hour <= 3:
        reversal_window = 'Asia activity window — moderate reversal risk'
    else:
        reversal_window = 'Next high-liquidity session window'
    intraday_intelligence = {
        'current_trend': trend(c),
        'trend_strength': min(100, int(abs(tech) + abs(option.get('score', 0)))),
        'relative_volume': round(rvol, 2),
        'volume_regime': volume_regime,
        'support_level': support_level,
        'reversal_level': reversal_level,
        'confirmation_level': confirmation_level,
        'probable_reversal_window': reversal_window,
        'reversal_probability': min(85, max(15, int(35 + abs(tech) * 0.25 + (15 if volume_regime in ('HIGH','EXTREME') else 0)))),
        'session': session,
        'events': events,
        'event_effect': events.get('next_event', {}).get('effect') if events.get('next_event') else None,
        'risk_note': 'A reversal window is probabilistic; do not treat it as an exact forecast.'
    }
    astrology = _astrology(_candle_datetime(df))
    numerology = _numerology(_candle_datetime(df), symbol)

    # Preserve the old technical + option score behavior, then expose the
    # two additional modules for the comprehensive dashboard.
    final = max(-100, min(100, tech + option.get("score", 0)))
    rec = "BUY" if final >= 35 else "SELL" if final <= -35 else "WAIT"
    confidence = round(min(99, 50 + abs(final) * 0.5), 1)

    technical_bias = "BULLISH" if tech >= 20 else "BEARISH" if tech <= -20 else "NEUTRAL"
    bullish = sum([
        technical_bias == "BULLISH", astrology["bias"] == "BULLISH", numerology["bias"] in ("BULLISH", "POSITIVE"), option.get("signal") == "BUY"
    ])
    bearish = sum([
        technical_bias == "BEARISH", astrology["bias"] == "BEARISH", numerology["bias"] in ("BEARISH", "NEGATIVE"), option.get("signal") == "SELL"
    ])
    if bullish >= 3: agreement = "BULLISH"
    elif bearish >= 3: agreement = "BEARISH"
    elif bullish > bearish: agreement = "BULLISH BIAS"
    elif bearish > bullish: agreement = "BEARISH BIAS"
    else: agreement = "MIXED"

    reasons += astrology.get("reasons", [])[:2] + numerology.get("reasons", [])[:1]
    return {
        "status": "OK", "symbol": symbol, "price": round(price, 2), "trend": trend(c),
        "signal": rec, "recommendation": rec, "confidence": confidence,
        "overall_score": final, "technical_score": tech, "option_score": option.get("score", 0),
        "ema9": round(e9, 2), "ema21": round(e21, 2), "ema50": round(e50, 2), "ema200": round(e200, 2),
        "rsi": round(rv, 2), "macd": round(float(ml.iloc[-1]), 5), "macd_signal": round(float(ms.iloc[-1]), 5),
        "atr": round(float(atr(h, l, c).iloc[-1]), 2), "reasons": reasons,
        "technical": {"signal": technical_bias, "confidence": min(99, abs(tech)), "score": tech, "reasons": reasons[:8]},
        "astrology": astrology, "numerology": numerology, "option_chain": option,
        "intraday_trend": _intraday(symbol),
        "intraday_intelligence": intraday_intelligence,
        "agreement": agreement,
        "agreement_detail": {"technical": technical_bias, "astrology": astrology["bias"], "numerology": numerology["bias"], "option_chain": option.get("signal", "NEUTRAL"), "final": agreement, "bullish": bullish, "bearish": bearish},
        "timestamp": _candle_datetime(df).isoformat(),
    }
