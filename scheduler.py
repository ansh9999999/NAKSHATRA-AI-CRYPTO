"""
NAKSHATRA AI
Scheduler
"""

from apscheduler.schedulers.background import BackgroundScheduler

from scanner import market_scan
from monitor.trade_monitor import monitor_open_trades

from logger import logger


scheduler = BackgroundScheduler()


def start_scheduler():

    if scheduler.running:
        logger.info("Scheduler already running")
        return

    # Run market scanner every 5 minutes
    scheduler.add_job(
        market_scan,
        "interval",
        minutes=5,
        id="market_scan",
        replace_existing=True
    )

    # Monitor open trades every 1 minute
    scheduler.add_job(
        monitor_open_trades,
        "interval",
        minutes=1,
        id="trade_monitor",
        replace_existing=True
    )

    scheduler.start()

    logger.info("===================================")
    logger.info("NAKSHATRA AI Scheduler Started")
    logger.info("Market Scan : Every 5 Minutes")
    logger.info("Trade Monitor : Every 1 Minute")
    logger.info("===================================")


def stop_scheduler():

    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler Stopped")
