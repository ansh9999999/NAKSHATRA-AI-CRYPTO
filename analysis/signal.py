from analysis.indicators import ema, rsi, macd, atr, trend
from delta import get_option_chain, get_ticker
from history import get_history


def _option_analysis(symbol, spot):
    chain = get_option_chain(symbol)
    rows = chain.get("rows", [])
    if not rows:
        return {**chain, "score": 0, "signal": "NOT_AVAILABLE", "pcr_oi": None, "pcr_volume": None, "atm": None, "support": None, "resistance": None, "max_pain": None, "atm_chain": []}
    calls = [r for r in rows if r["type"] == "CE"]
    puts = [r for r in rows if r["type"] == "PE"]
    strikes = sorted({r["strike"] for r in rows})
    atm = min(strikes, key=lambda x: abs(x-spot))
    call_oi=sum(r["oi"] for r in calls); put_oi=sum(r["oi"] for r in puts)
    call_vol=sum(r["volume"] for r in calls); put_vol=sum(r["volume"] for r in puts)
    pcr = put_oi/call_oi if call_oi else None
    vpcr = put_vol/call_vol if call_vol else None
    support=max(puts,key=lambda r:r["oi"])["strike"] if puts else None
    resistance=max(calls,key=lambda r:r["oi"])["strike"] if calls else None
    # Max pain: total intrinsic value across strikes.
    max_pain=None; min_pain=None
    for k in strikes:
        pain=sum(max(k-r["strike"],0)*r["oi"] for r in calls)+sum(max(r["strike"]-k,0)*r["oi"] for r in puts)
        if min_pain is None or pain<min_pain: min_pain,pain_k=pain,k
    max_pain=pain_k if strikes else None
    score=0
    if pcr is not None:
        if pcr>=1.20: score+=25
        elif pcr>=1.00: score+=10
        elif pcr<=0.75: score-=25
        else: score-=10
    if vpcr is not None:
        if vpcr>=1.10: score+=10
        elif vpcr<=0.80: score-=10
    score=max(-35,min(35,score))
    signal="BUY" if score>=20 else "SELL" if score<=-20 else "NEUTRAL"
    nearby=sorted(strikes,key=lambda x:abs(x-atm))[:11]
    atm_chain=[]
    for k in sorted(nearby):
        ce=next((r for r in calls if r["strike"]==k),None); pe=next((r for r in puts if r["strike"]==k),None)
        atm_chain.append({"strike":k,"atm":k==atm,"call_ltp":ce and ce["ltp"],"call_oi":ce and ce["oi"],"call_volume":ce and ce["volume"],"put_ltp":pe and pe["ltp"],"put_oi":pe and pe["oi"],"put_volume":pe and pe["volume"]})
    return {**chain,"score":score,"signal":signal,"pcr_oi":round(pcr,3) if pcr is not None else None,"pcr_volume":round(vpcr,3) if vpcr is not None else None,"atm":atm,"support":support,"resistance":resistance,"max_pain":max_pain,"call_oi":call_oi,"put_oi":put_oi,"call_volume":call_vol,"put_volume":put_vol,"atm_chain":atm_chain}


def _tf(symbol, resolution):
    df=get_history(symbol,resolution,250)
    if df.empty: return {"timeframe":resolution,"trend":"NO DATA","score":0,"rows":0}
    c=df.close; e9=ema(c,9).iloc[-1]; e50=ema(c,50).iloc[-1]; e200=ema(c,200).iloc[-1]
    s=2 if e9>e50 else -2
    if e50>e200: s+=2
    else: s-=2
    return {"timeframe":resolution,"trend":trend(c),"score":s,"rows":len(df),"ema9":round(float(e9),2),"ema50":round(float(e50),2),"ema200":round(float(e200),2)}


def _intraday(symbol):
    frames=[_tf(symbol,x) for x in ("5m","15m","1h","1d")]
    score=sum(x["score"] for x in frames)
    label="STRONG BULLISH" if score>=8 else "BULLISH" if score>=3 else "STRONG BEARISH" if score<=-8 else "BEARISH" if score<=-3 else "SIDEWAYS"
    return {"overall":label,"score":score,"timeframes":frames}


def generate_signal(df=None, symbol="BTCUSD"):
    symbol=symbol.upper()
    if df is None or df.empty: df=get_history(symbol,"5m",250)
    if df.empty: return {"status":"NO_DATA","symbol":symbol}
    c,h,l,v=df.close,df.high,df.low,df.volume
    price=float(c.iloc[-1]); e9=float(ema(c,9).iloc[-1]); e21=float(ema(c,21).iloc[-1]); e50=float(ema(c,50).iloc[-1]); e200=float(ema(c,200).iloc[-1]); rv=float(rsi(c).iloc[-1]); ml,ms,mh=macd(c)
    score=0; reasons=[]
    if e9>e21>e50: score+=25; reasons.append("EMA stack bullish")
    elif e9<e21<e50: score-=25; reasons.append("EMA stack bearish")
    elif e9>e21: score+=10; reasons.append("Short-term EMA bullish")
    else: score-=10; reasons.append("Short-term EMA bearish")
    if rv>=55 and rv<=70: score+=15; reasons.append("RSI bullish zone")
    elif rv<=45 and rv>=30: score-=15; reasons.append("RSI bearish zone")
    elif rv>75: score-=10; reasons.append("RSI overbought")
    elif rv<25: score+=10; reasons.append("RSI oversold")
    if ml.iloc[-1]>ms.iloc[-1]: score+=20; reasons.append("MACD bullish")
    else: score-=20; reasons.append("MACD bearish")
    avg=v.tail(20).mean()
    if avg>0 and v.iloc[-1]>avg*1.5: score += 10 if c.iloc[-1]>=c.iloc[-2] else -10; reasons.append("Volume spike")
    if price>e200: score+=10; reasons.append("Price above EMA200")
    else: score-=10; reasons.append("Price below EMA200")
    tech=max(-80,min(80,score))
    option=_option_analysis(symbol,price)
    final=max(-100,min(100,tech+option.get("score",0)))
    rec="BUY" if final>=35 else "SELL" if final<=-35 else "WAIT"
    confidence=round(min(99,50+abs(final)*0.5),1)
    return {"status":"OK","symbol":symbol,"price":round(price,2),"trend":trend(c),"signal":rec,"recommendation":rec,"confidence":confidence,"overall_score":final,"technical_score":tech,"option_score":option.get("score",0),"ema9":round(e9,2),"ema21":round(e21,2),"ema50":round(e50,2),"ema200":round(e200,2),"rsi":round(rv,2),"macd":round(float(ml.iloc[-1]),5),"macd_signal":round(float(ms.iloc[-1]),5),"atr":round(float(atr(h,l,c).iloc[-1]),2),"reasons":reasons,"option_chain":option,"intraday_trend":_intraday(symbol)}
