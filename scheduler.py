from apscheduler.schedulers.background import BackgroundScheduler
from scanner import market_scan

scheduler = BackgroundScheduler()


def start_scheduler():
    if scheduler.running:
        return
    scheduler.add_job(
        market_scan,
        'interval',
        minutes=5,
        id='market_scan',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    print('🚀 NAKSHATRA Scheduler Started')


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print('🛑 NAKSHATRA Scheduler Stopped')
