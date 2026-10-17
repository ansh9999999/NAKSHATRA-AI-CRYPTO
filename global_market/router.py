"""Public, read-only global crypto monitor. Separate from Delta trading logic."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import math, threading, time, xml.etree.ElementTree as ET
from typing import Any
import requests
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/global-market", tags=["global-market"])
TIMEOUT=(3,5); CACHE_SECONDS=15
_cache: dict[str, dict[str, Any]]={}; _context_cache={}; _lock=threading.Lock()
_session=requests.Session(); _session.headers.update({"User-Agent":"Mozilla/5.0 (compatible; NakshatraAI/5.9; public-market-monitor)","Accept":"application/json,application/xml,text/xml,*/*"})

def _get(url: str, params: dict|None=None, expected=dict):
    r=_session.get(url,params=params,timeout=TIMEOUT); r.raise_for_status(); payload=r.json() if 'json' in r.headers.get('content-type','').lower() or url.endswith('.json') else None
    if payload is None: payload=r.text
    if expected is dict and not isinstance(payload,dict): raise ValueError('Unexpected provider response')
    if expected is list and not isinstance(payload,list): raise ValueError('Unexpected provider response')
    return payload

def _get_json_fallback(urls: list[str], params: dict|None=None, expected=dict):
    errors=[]
    for url in urls:
        try: return _get(url,params,expected=expected)
        except Exception as exc: errors.append(f"{url.split('/')[2]}: {str(exc)[:90]}")
    raise RuntimeError('All endpoint hosts failed: '+'; '.join(errors))

def _num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except (TypeError,ValueError): return None

def _row(name,market,price,change,volume,source,status='OK',note=None):
    return {'exchange':name,'market':market,'price':_num(price),'change_24h_pct':_num(change),'volume_24h':_num(volume),'source':source,'status':status,'note':note,'open_interest':None,'open_interest_change_pct':None,'funding_rate_pct':None,'options_open_interest':None,'order_book_imbalance_pct':None,'large_trade_flow':'Not connected','volume_interpretation':'Volume is participation context; it does not predict direction alone.'}

def _binance_spot(symbol):
    p=_get_json_fallback(['https://api.binance.com/api/v3/ticker/24hr','https://api1.binance.com/api/v3/ticker/24hr','https://api2.binance.com/api/v3/ticker/24hr','https://api3.binance.com/api/v3/ticker/24hr'],{'symbol':symbol})
    return _row('Binance','Spot',p.get('lastPrice'),p.get('priceChangePercent'),p.get('quoteVolume'),'Binance Spot alternate-host fallback')

def _binance_futures(symbol):
    p=_get_json_fallback(['https://fapi.binance.com/fapi/v1/ticker/24hr','https://fapi1.binance.com/fapi/v1/ticker/24hr'],{'symbol':symbol})
    row=_row('Binance','USD-M Futures',p.get('lastPrice'),p.get('priceChangePercent'),p.get('quoteVolume'),'Binance USD-M Futures')
    try:
        oi=_get_json_fallback(['https://fapi.binance.com/fapi/v1/openInterest'],{'symbol':symbol}); row['open_interest']=_num(oi.get('openInterest'))
    except Exception: pass
    try:
        hist=_get_json_fallback(['https://fapi.binance.com/futures/data/openInterestHist','https://fapi1.binance.com/futures/data/openInterestHist'],{'symbol':symbol,'period':'1h','limit':2},expected=list)
        if isinstance(hist,list) and len(hist)>=2:
            old=_num(hist[-2].get('sumOpenInterestValue') or hist[-2].get('sumOpenInterest')); new=_num(hist[-1].get('sumOpenInterestValue') or hist[-1].get('sumOpenInterest'))
            if old and new is not None: row['open_interest_change_pct']=(new/old-1)*100
    except Exception: pass
    try:
        fr=_get_json_fallback(['https://fapi.binance.com/fapi/v1/premiumIndex'],{'symbol':symbol}); row['funding_rate_pct']=(_num(fr.get('lastFundingRate')) or 0)*100
    except Exception: pass
    try:
        book=_get_json_fallback(['https://fapi.binance.com/fapi/v1/depth','https://fapi1.binance.com/fapi/v1/depth'],{'symbol':symbol,'limit':20})
        bids=sum((_num(x[1]) or 0) for x in book.get('bids',[])); asks=sum((_num(x[1]) or 0) for x in book.get('asks',[])); total=bids+asks
        row['order_book_imbalance_pct']=((bids-asks)/total*100) if total else None
    except Exception: pass
    return row

def _coinbase(symbol):
    product='BTC-USD' if symbol.startswith('BTC') else 'ETH-USD'
    ticker=_get(f'https://api.exchange.coinbase.com/products/{product}/ticker'); stats=_get(f'https://api.exchange.coinbase.com/products/{product}/stats')
    last=_num(ticker.get('price')); op=_num(stats.get('open')); change=(last/op-1)*100 if last and op else None
    return _row('Coinbase','Spot',last,change,stats.get('volume'),f'Coinbase Exchange {product}')

def _kraken(symbol):
    pair='XBTUSD' if symbol.startswith('BTC') else 'ETHUSD'; p=_get('https://api.kraken.com/0/public/Ticker',{'pair':pair})
    if p.get('error'): raise ValueError('Kraken: '+', '.join(p['error']))
    t=next(iter((p.get('result') or {}).values()),{}); last=_num((t.get('c') or [None])[0]); op=_num(t.get('o')); ch=(last/op-1)*100 if last and op else None
    return _row('Kraken','Spot',last,ch,_num((t.get('v') or [None,None])[1]),f'Kraken public ticker {pair}')

def _bybit(symbol):
    p=_get('https://api.bybit.com/v5/market/tickers',{'category':'linear','symbol':symbol})
    if p.get('retCode') not in (0,None): raise ValueError(str(p.get('retMsg','Bybit API error')))
    t=((p.get('result') or {}).get('list') or [{}])[0]
    ch=_num(t.get('price24hPcnt')); row=_row('Bybit','USDT Perpetual',t.get('lastPrice'),ch*100 if ch is not None else None,t.get('turnover24h'),f'Bybit V5 linear {symbol}')
    row['open_interest']=_num(t.get('openInterest')); fr=_num(t.get('fundingRate')); row['funding_rate_pct']=fr*100 if fr is not None else None
    try:
        hist=_get('https://api.bybit.com/v5/market/open-interest',{'category':'linear','symbol':symbol,'intervalTime':'1h','limit':2})
        lst=((hist.get('result') or {}).get('list') or [])
        if len(lst)>=2:
            old=_num(lst[-1].get('openInterest')); new=_num(lst[0].get('openInterest'))
            if old and new is not None: row['open_interest_change_pct']=(new/old-1)*100
    except Exception: pass
    try:
        book=_get('https://api.bybit.com/v5/market/orderbook',{'category':'linear','symbol':symbol,'limit':25})
        item=(book.get('result') or {}); bids=sum((_num(x[1]) or 0) for x in item.get('b',[])); asks=sum((_num(x[1]) or 0) for x in item.get('a',[])); total=bids+asks
        row['order_book_imbalance_pct']=((bids-asks)/total*100) if total else None
    except Exception: pass
    return row

def _okx(symbol):
    base='BTC' if symbol.startswith('BTC') else 'ETH'; inst=f'{base}-USDT-SWAP'
    p=_get('https://www.okx.com/api/v5/market/ticker',{'instId':inst})
    if p.get('code') not in ('0',0,None): raise ValueError(str(p.get('msg','OKX API error')))
    t=(p.get('data') or [{}])[0]; last=_num(t.get('last')); op=_num(t.get('open24h')); ch=(last/op-1)*100 if last and op else None
    row=_row('OKX','USDT Perpetual',last,ch,t.get('volCcy24h'),f'OKX public ticker {inst}')
    try:
        oi=_get('https://www.okx.com/api/v5/public/open-interest',{'instType':'SWAP','instId':inst}); item=(oi.get('data') or [{}])[0]; row['open_interest']=_num(item.get('oi'))
    except Exception: pass
    try:
        fr=_get('https://www.okx.com/api/v5/public/funding-rate',{'instId':inst}); item=(fr.get('data') or [{}])[0]; val=_num(item.get('fundingRate')); row['funding_rate_pct']=val*100 if val is not None else None
    except Exception: pass
    try:
        book=_get('https://www.okx.com/api/v5/market/books',{'instId':inst,'sz':20}); item=(book.get('data') or [{}])[0]
        bids=sum((_num(x[1]) or 0) for x in item.get('bids',[])); asks=sum((_num(x[1]) or 0) for x in item.get('asks',[])); total=bids+asks
        row['order_book_imbalance_pct']=((bids-asks)/total*100) if total else None
    except Exception: pass
    return row

PROVIDERS=[_binance_spot,_binance_futures,_coinbase,_kraken,_bybit,_okx]
def _direction(v):
    if v is None:return 'UNCONFIRMED'
    if v>=0.25:return 'BULLISH'
    if v<=-0.25:return 'BEARISH'
    return 'SIDEWAYS'
def _median(vals):
    vals=sorted(vals)
    if not vals:return None
    m=len(vals)//2
    return vals[m] if len(vals)%2 else (vals[m-1]+vals[m])/2

def _build_snapshot(symbol):
    rows=[]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs={pool.submit(fn,symbol):fn.__name__ for fn in PROVIDERS}
        for f in as_completed(futs):
            try: rows.append(f.result())
            except Exception as exc:
                name=futs[f].replace('_',' ').title(); rows.append(_row(name,'—',None,None,None,futs[f],'UNAVAILABLE',str(exc)[:200]))
    rows.sort(key=lambda r:(r['exchange'],r['market']))
    available=[r for r in rows if r['status']=='OK' and r.get('price') is not None]
    prices=[r['price'] for r in available]; avg=sum(prices)/len(prices) if prices else None
    changes=[r['change_24h_pct'] for r in available if r.get('change_24h_pct') is not None]; med=_median(changes)
    divergences=[]
    if len(prices)>=2 and avg:
        for r in available:
            dev=(r['price']/avg-1)*100
            if abs(dev)>=0.20: divergences.append({'exchange':r['exchange'],'market':r['market'],'deviation_pct':round(dev,4),'direction':'ABOVE GLOBAL MEAN' if dev>0 else 'BELOW GLOBAL MEAN','effect':'Premium vs mean; can indicate venue-specific flow or stale/illiquid quote. Confirm volume and order book before acting.'})
    consensus=_direction(med); ratio=(sum(_direction(c)==consensus for c in changes)/len(changes)*100) if changes and consensus!='UNCONFIRMED' else None
    spread=(max(changes)-min(changes)) if len(changes)>=2 else None
    level='NORMAL'; title='No large 24h anomaly detected'; reasons=[]; alertdir=consensus
    if len(available)<3:
        level='DATA LIMITED'; title='Insufficient exchanges for reliable confirmation'; alertdir='UNCONFIRMED'; reasons.append(f'{len(available)}/{len(rows)} endpoints have usable {symbol} prices; wait for more feeds.')
    else:
        if med is not None and abs(med)>=2:
            level='ELEVATED'; title=f'Large {symbol} 24h move: median {med:+.2f}%'; reasons.append('24h median crossed the 2% watch threshold; this is a momentum flag, not a forecast.')
        if spread is not None and spread>=1.0:
            level='ELEVATED'; title='Cross-exchange 24h changes diverge'; reasons.append(f'24h change spread is {spread:.2f} percentage points; verify data timestamps and venue liquidity.')
        if not reasons: reasons.append('No 24h threshold crossed. This endpoint does not measure tick-by-tick order flow.')
    # Heuristic risk score is a monitoring score, NOT a probability.
    risk_score=0
    if len(available)<3: risk_score=0
    else:
        risk_score += min(35,abs(med or 0)*10)
        risk_score += min(35,(spread or 0)*20)
        risk_score += min(30,max(0,(100-(ratio or 0)))*0.3)
    risk_score=int(round(min(100,risk_score)))
    risk_label='HIGH' if risk_score>=65 else 'ELEVATED' if risk_score>=35 else 'LOW'
    deriv=[r for r in rows if r.get('open_interest') is not None or r.get('funding_rate_pct') is not None]
    smart={'open_interest':next((r['open_interest'] for r in deriv if r.get('open_interest') is not None),None),'open_interest_source':next((r['exchange'] for r in deriv if r.get('open_interest') is not None),None),'funding_rate_pct':next((r['funding_rate_pct'] for r in deriv if r.get('funding_rate_pct') is not None),None),'funding_source':next((r['exchange'] for r in deriv if r.get('funding_rate_pct') is not None),None),'order_book_imbalance':_median([r['order_book_imbalance_pct'] for r in rows if r.get('order_book_imbalance_pct') is not None]),'rows':[{k:r.get(k) for k in ('exchange','market','open_interest','open_interest_change_pct','funding_rate_pct','options_open_interest','order_book_imbalance_pct','status','note')} for r in rows if r['market'] in ('USD-M Futures','USDT Perpetual') or r['exchange']=='Binance'],'note':'OI change is shown only where a provider returns comparable snapshots. Rising OI means leverage/positions are building, not automatically bullish; combine with price direction and funding. Option OI is unavailable in these public adapters.'}
    if smart['open_interest_change_pct'] if 'open_interest_change_pct' in smart else False: pass
    # Explain what the observed derivatives combination means without overstating it.
    oi_changes=[r.get('open_interest_change_pct') for r in rows if r.get('open_interest_change_pct') is not None]
    oi_ch=_median(oi_changes)
    if oi_ch is None: deriv_effect='OI change unavailable: cannot confirm fresh leverage build-up.'
    elif oi_ch>1 and (med or 0)>0: deriv_effect='Price and OI both rising: new positions may be joining the move; crowded-long risk still needs funding/liquidation confirmation.'
    elif oi_ch>1 and (med or 0)<0: deriv_effect='Price falling while OI rises: new shorts or trapped longs may be building; squeeze direction remains unconfirmed.'
    elif oi_ch<-1: deriv_effect='OI falling: positions are closing/deleveraging; move may be position unwind rather than fresh conviction.'
    else: deriv_effect='OI is broadly stable; no strong leverage expansion signal from available feeds.'
    smart['median_oi_change_pct']=oi_ch; smart['effect']=deriv_effect
    obi=smart.get('order_book_imbalance')
    smart['order_book_effect']=('Bid depth exceeds ask depth in sampled order book; this is short-term visible liquidity, not guaranteed buying pressure.' if obi is not None and obi>10 else 'Ask depth exceeds bid depth in sampled order book; this is short-term visible liquidity, not guaranteed selling pressure.' if obi is not None and obi<-10 else 'Order-book depth is roughly balanced or too limited to interpret.' if obi is not None else 'Order-book feed unavailable; cannot infer visible bid/ask pressure.')
    # Funding interpretation: positive means longs pay shorts; extreme readings can imply crowded positioning.
    fund=_median([r['funding_rate_pct'] for r in deriv if r.get('funding_rate_pct') is not None])
    smart['median_funding_rate_pct']=fund
    if fund is None: smart['funding_effect']='Funding unavailable.'
    elif fund>0.03: smart['funding_effect']='High positive funding: long positioning may be crowded; downside liquidation risk can rise if price reverses.'
    elif fund<-0.03: smart['funding_effect']='Negative funding: short positioning may be crowded; upside squeeze risk can rise if price reverses.'
    else: smart['funding_effect']='Funding is not extreme by this simple threshold; funding alone is not a direction signal.'
    now=datetime.now(timezone.utc).isoformat()
    return {'status':'OK' if available else 'DATA LIMITED','symbol':symbol,'base_asset':'BTC' if symbol.startswith('BTC') else 'ETH','updated_at':now,'cache_seconds':CACHE_SECONDS,'provider_count':len(rows),'available_count':len(available),'global_mean_price':avg,'median_change_24h_pct':med,'consensus':consensus,'consensus_ratio':round(ratio,1) if ratio is not None else None,'exchanges':rows,'divergences':divergences,'early_warning':{'level':level,'title':title,'direction':alertdir,'reasons':reasons,'method':'24h ticker thresholds + cross-exchange spread; cannot predict second-by-second moves.'},'smart_money':smart,'liquidation_risk':{'status':'UNCONFIRMED','long_short_squeeze':'NO LIVE LIQUIDATION FEED','effect':'A squeeze needs forced liquidations plus price/positioning evidence. Rising OI and funding are context only; without a live liquidation stream, long/short squeeze direction cannot be confirmed.','note':'Liquidation stream is not connected. Treat as unconfirmed, not as zero risk.'},'probability':{'up_pct':None,'down_pct':None,'status':'HEURISTIC RISK SCORE — NOT PROBABILITY','risk_score':risk_score,'risk_label':risk_label,'direction_bias':consensus,'note':f'Monitoring score {risk_score}/100 ({risk_label}) from 24h move, cross-exchange spread and agreement. It is NOT a statistically calibrated probability; direction bias is {consensus}.'},'scenarios':{'upside':'Upside follow-through is better supported if selected-asset price rises with increasing volume, OI builds without extreme positive funding, and multiple exchanges agree.','downside':'Downside follow-through is better supported if price falls with rising sell volume, multiple exchanges confirm, and liquidation/OI evidence agrees.','invalidations':'If exchanges disagree, volume is thin, feeds are stale, or derivatives are unavailable, treat direction as low-confidence.'},'definitions':{'intraday_high':'HIGH means elevated volatility/activity, not bullish. Direction comes from each timeframe signal: green bullish, red bearish, orange sideways/neutral.','divergence':'Price spread between exchanges can reflect liquidity, timing, or venue-specific flow; large spread may increase execution/slippage risk, not prove manipulation.','volume':'Rising volume with price move supports participation; price move on low volume is less confirmed. Volume alone does not tell future direction.','open_interest':'Rising open interest means more outstanding contracts, not automatically bullish; combine with price direction. Falling OI often indicates position closure/deleveraging.','funding':'Positive perpetual funding generally means longs pay shorts; extreme positive funding can signal crowded longs. Negative funding can indicate crowded shorts.','liquidation':'A liquidation/squeeze conclusion requires actual forced-order/liquidation data. Without that stream the state is unconfirmed, not zero risk.','risk_score':'The 0–100 score is a rule-based monitoring score from 24h movement, spread and exchange agreement. It is not a calibrated probability and has no measured historical accuracy yet.'}}

@router.get('/snapshot')
def global_snapshot(symbol:str=Query('BTCUSDT'),force:bool=Query(False)):
    requested=symbol.upper().replace('/','').replace('-','')
    if requested in ('BTCUSD','BTCUSDT','XBTUSD'): normalized='BTCUSDT'
    elif requested in ('ETHUSD','ETHUSDT','ETHUSDTPERP'): normalized='ETHUSDT'
    else: return {'status':'UNSUPPORTED SYMBOL','symbol':requested,'available_count':0,'provider_count':len(PROVIDERS),'exchanges':[],'consensus':'UNCONFIRMED','early_warning':{'level':'DATA LIMITED','title':'Global data unavailable for this symbol','direction':'UNCONFIRMED','reasons':['No global provider adapter is configured for this symbol.'],'method':'No stale BTC/ETH data is reused for unsupported symbols.'}}
    now=time.time()
    with _lock:
        cached=_cache.get(normalized)
        if not force and cached and now-cached['at']<CACHE_SECONDS:return cached['data']
    data=_build_snapshot(normalized)
    with _lock:_cache[normalized]={'at':time.time(),'data':data}
    return data

def _fetch_calendar_events(errors):
    """Fetch a public economic-calendar mirror; gracefully report if unavailable."""
    urls=['https://nfs.faireconomy.media/ff_calendar_thisweek.json']
    for url in urls:
        try:
            items=_get(url,expected=list)
            out=[]
            now=datetime.now(timezone.utc)
            for item in items:
                if str(item.get('country','')).upper() not in ('USD','US','UNITED STATES'):
                    continue
                impact=str(item.get('impact','')).lower()
                if impact not in ('high','medium'):
                    continue
                title=str(item.get('title') or item.get('event') or 'USD economic event')[:180]
                raw_date=str(item.get('date') or item.get('datetime') or '')
                try:
                    dt=datetime.fromisoformat(raw_date.replace('Z','+00:00'))
                    if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
                    dt_ist=dt.astimezone(__import__('datetime').timezone(__import__('datetime').timedelta(hours=5,minutes=30)))
                    if dt < now.replace(year=now.year-1): continue
                    display_time=dt_ist.strftime('%d %b %Y, %I:%M %p IST')
                except Exception: display_time=raw_date or 'Time not supplied'
                actual=str(item.get('actual') or '').strip(); forecast=str(item.get('forecast') or '').strip(); previous=str(item.get('previous') or '').strip()
                out.append({'title':title,'country':'USD','impact':impact.upper(),'date':raw_date,'time_ist':display_time,'actual':actual or None,'forecast':forecast or None,'previous':previous or None,'effect':'Potential volatility catalyst. Direction depends on the event, actual-versus-forecast surprise, and broader macro context; not assigned in advance.'})
            return out[:12]
        except Exception as exc:
            errors.append('Economic calendar unavailable: '+str(exc)[:100])
    return []

@router.get('/context')
def global_context(symbol:str=Query('BTCUSDT'),force:bool=Query(False)):
    """Public Fear & Greed and crypto headlines. Calendar is explicitly not fabricated."""
    normalized='ETHUSDT' if symbol.upper().replace('/','').replace('-','').startswith('ETH') else 'BTCUSDT'; key='context:'+normalized; now=time.time()
    with _lock:
        if not force and key in _context_cache and now-_context_cache[key]['at']<300:return _context_cache[key]['data']
    fng=None; headlines=[]; errors=[]; calendar_events=[]
    try:
        d=_get('https://api.alternative.me/fng/?limit=1&format=json'); item=(d.get('data') or [{}])[0]
        val=_num(item.get('value')); label=item.get('value_classification')
        if val is not None:fng={'value':val,'label':label,'bias':'BULLISH' if val>=55 else 'BEARISH' if val<=25 else 'NEUTRAL','interpretation':'Greed can support risk appetite but may also mean crowded positioning; fear can reflect risk-off conditions or potential capitulation.'}
    except Exception as exc: errors.append('Fear & Greed unavailable: '+str(exc)[:100])
    try:
        feed=_session.get('https://www.coindesk.com/arc/outboundfeeds/rss/',timeout=TIMEOUT,headers={'User-Agent':'Mozilla/5.0'})
        feed.raise_for_status(); root=ET.fromstring(feed.text)
        for item in root.findall('.//item')[:8]:
            title=(item.findtext('title') or '').strip(); link=(item.findtext('link') or '').strip(); pub=(item.findtext('pubDate') or '').strip()
            if title: headlines.append({'title':title[:220],'url':link,'published':pub,'effect':_headline_effect(title)})
    except Exception as exc: errors.append('News RSS unavailable: '+str(exc)[:100])
    calendar_events=_fetch_calendar_events(errors)
    out={'updated_at':datetime.now(timezone.utc).isoformat(),'symbol':normalized,'base_asset':'ETH' if normalized.startswith('ETH') else 'BTC','fear_greed':fng,'headlines':headlines,'calendar_events':calendar_events,'calendar_status':'CONNECTED • PUBLIC USD CALENDAR' if calendar_events else 'UNAVAILABLE','calendar_note':'Public calendar mirror: USD high/medium-impact events only. Times/fields depend on provider; event effects are contextual, not deterministic. Headlines are separate from scheduled events.','errors':errors,'sentiment_method':'Fear & Greed index plus keyword-based CoinDesk headline tags; not a trained social sentiment model. Social sentiment provider is not connected.'}
    with _lock:_context_cache[key]={'at':time.time(),'data':out}
    return out

def _headline_effect(title:str)->str:
    t=title.lower(); positive=('etf inflow','inflows','approval','adoption','surge','record high','bullish','rally','buying','partnership')
    negative=('hack','exploit','lawsuit','outflow','outflows','ban','crackdown','liquidation','sell-off','selloff','bearish','fraud','breach')
    pos=sum(w in t for w in positive); neg=sum(w in t for w in negative)
    if pos>neg:return 'POTENTIALLY POSITIVE — headline keyword match; verify context'
    if neg>pos:return 'POTENTIALLY NEGATIVE — headline keyword match; verify context'
    return 'MIXED / UNCLEAR — read source before assigning direction'
