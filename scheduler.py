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

        # WAIT par alert nahi
        if current_signal == "WAIT":
            return

        # Same signal repeat nahi
        if current_signal == last_signal:
            return

        last_signal = current_signal

        emoji = "🟢" if current_signal == "BIG BUY" else "🔴"

        message = f"""
🚨 NAKSHATRA BIG MOVE ALERT 🚨

{emoji} {current_signal}

📊 Symbol : BTCUSD
💰 Entry : {signal['price']}

📈 Trend : {signal['trend']}
🔥 Confidence : {signal['confidence']}%

📉 RSI : {signal['rsi']}
📊 EMA9 : {signal['ema9']}
📊 EMA21 : {signal['ema21']}

Reasons
- {'\n- '.join(signal['reasons'])}
"""

        send_message(message)

        print("✅ BIG MOVE ALERT SENT")

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

# Server start hote hi ek scan
market_scan()
