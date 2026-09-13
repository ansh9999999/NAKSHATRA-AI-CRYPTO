from apscheduler.schedulers.background import BackgroundScheduler
from analysis.signal import generate_signal
from history import get_history
from telegram import send_message

scheduler=BackgroundScheduler()
last_alert={}

def market_scan():
    for symbol in ("BTCUSD","ETHUSD"):
        try:
            result=generate_signal(get_history(symbol,"5m",250),symbol)
            sig=result.get("signal")
            if sig not in ("BUY","SELL"): continue
            key=f"{symbol}:{sig}"
            if last_alert.get(symbol)==sig: continue
            last_alert[symbol]=sig
            msg=(f"🚨 NAKSHATRA CRYPTO SIGNAL\n\n{symbol} • {sig}\nPrice: {result.get('price')}\n"
                 f"Confidence: {result.get('confidence')}%\nScore: {result.get('overall_score')}\nTrend: {result.get('trend')}\n\n"
                 + "\n".join(f"• {x}" for x in result.get("reasons",[])[:6]))
            send_message(msg)
            print(f"Signal sent: {key}")
        except Exception as e: print(f"Scheduler {symbol}: {e}")

scheduler.add_job(market_scan,"interval",minutes=5,max_instances=1)
scheduler.start()
