from apscheduler.schedulers.background import BackgroundScheduler

from history import get_history
from analysis.signal import generate_signal
from telegram import send_message

scheduler = BackgroundScheduler()

last_signal = None


def market_scan():

    global last_signal

    try:

        df = get_history(
            symbol="BTCUSD",
            resolution="5m",
            limit=200
        )

        signal = generate_signal(df)

        current_signal = signal["signal"]

        # WAIT signal par alert mat bhejo
        if current_signal == "WAIT":
            return

        # Same signal repeat mat bhejo
        if current_signal == last_signal:
            return

        last_signal = current_signal

        message = f"""🚀 NAKSHATRA AI CRYPTO

📊 Symbol : BTCUSD
💰 Price : {signal['price']}

📈 Trend : {signal['trend']}
🎯 Signal : {signal['signal']}
✅ Confidence : {signal['confidence']}%

📉 RSI : {signal['rsi']}
📊 EMA9 : {signal['ema9']}
📊 EMA21 : {signal['ema21']}

Reasons:
- {'\n- '.join(signal['reasons'])}
"""

        send_message(message)

        print("✅ Telegram Alert Sent")

    except Exception as e:

        print(f"❌ Scheduler Error: {e}")


scheduler.add_job(
    market_scan,
    trigger="interval",
    minutes=5,
    max_instances=1
)

scheduler.start()

print("🚀 NAKSHATRA Scheduler Started")

market_scan()
