import os

# Delta Exchange
DELTA_API_KEY = os.getenv("DELTA_API_KEY")
DELTA_API_SECRET = os.getenv("DELTA_API_SECRET")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# API
BASE_URL = "https://api.india.delta.exchange/v2"

# Symbols
BTC_SYMBOL = "BTCUSD"
ETH_SYMBOL = "ETHUSD"

# Timeframes
DEFAULT_TIMEFRAME = "5m"

# Risk Management
DEFAULT_STOPLOSS = 1.0      # %
DEFAULT_TARGET = 2.0        # %

# Project
PROJECT_NAME = "NAKSHATRA AI CRYPTO"
VERSION = "2.0"
