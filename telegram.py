import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def send_message(message):

    if not TELEGRAM_BOT_TOKEN:
        return {
            "success": False,
            "error": "Bot Token Missing"
        }

    if not TELEGRAM_CHAT_ID:
        return {
            "success": False,
            "error": "Chat ID Missing"
        }

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }

    r = requests.post(url, json=payload)

    return r.json()
