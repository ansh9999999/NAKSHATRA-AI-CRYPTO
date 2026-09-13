from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

from delta import get_ticker
from history import get_history
from analysis.indicators import indicator_summary
from analysis.signal import generate_signal

app=FastAPI(title="NAKSHATRA AI CRYPTO",version="3.0")
app.mount("/static",StaticFiles(directory="static"),name="static")
templates=Jinja2Templates(directory="templates")
SYMBOLS=("BTCUSD","ETHUSD")

@app.get("/",response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={}
    )

@app.get("/health")
def health(): return {"status":"healthy","project":"NAKSHATRA AI CRYPTO","version":"3.0"}

@app.get("/api/live")
def live(symbol: str=Query("BTCUSD")):
    s=symbol.upper()
    if s not in SYMBOLS: return {"status":"ERROR","error":"Unsupported symbol"}
    try:
        ticker=get_ticker(s)
        analysis=generate_signal(get_history(s,"5m",250),s)
        return {"status":"OK","symbol":s,"ticker":ticker,"analysis":analysis}
    except Exception as e: return {"status":"ERROR","symbol":s,"error":str(e)}

@app.get("/api/analysis")
def analysis(symbol: str=Query("BTCUSD")):
    s=symbol.upper(); df=get_history(s,"5m",250)
    if df.empty: return {"status":"ERROR","error":"No market data"}
    return {"status":"OK","symbol":s,"indicators":indicator_summary(df),"analysis":generate_signal(df,s)}

@app.get("/api/history")
def history(symbol: str=Query("BTCUSD"), resolution: str=Query("5m"), limit:int=Query(250,ge=50,le=500)):
    df=get_history(symbol.upper(),resolution,limit)
    return {"status":"OK","symbol":symbol.upper(),"resolution":resolution,"rows":df.to_dict(orient="records")}

@app.get("/api/option-chain")
def option_chain(symbol: str=Query("BTCUSD")):
    from delta import get_option_chain
    return get_option_chain(symbol.upper())

@app.get("/api/scanner")
def scanner():
    out=[]
    for s in SYMBOLS:
        try: out.append(generate_signal(get_history(s,"5m",250),s))
        except Exception as e: out.append({"status":"ERROR","symbol":s,"error":str(e)})
    return {"status":"OK","markets":out}

# Backward-compatible endpoints
@app.get("/btc")
def btc(): return get_ticker("BTCUSD")
@app.get("/eth")
def eth(): return get_ticker("ETHUSD")
@app.get("/signal")
def signal(): return generate_signal(get_history("BTCUSD","5m",250),"BTCUSD")
@app.get("/analysis")
def legacy_analysis():
    df=get_history("BTCUSD","5m",250); return {"success":True,"indicators":indicator_summary(df),"signal":generate_signal(df,"BTCUSD")}
