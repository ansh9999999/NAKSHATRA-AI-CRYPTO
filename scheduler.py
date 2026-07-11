from apscheduler.schedulers.background import BackgroundScheduler
from main import send_telegram

scheduler = BackgroundScheduler()

def market_scan():
    try:
        send_telegram("🤖 NAKSHATRA AI Scheduler Running")
        print("Scheduler OK")
    except Exception as e:
        print(e)

scheduler.add_job(
    market_scan,
    "interval",
    minutes=5
)

scheduler.start()
