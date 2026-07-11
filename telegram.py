import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def send_message(message):

    if not TELEGRAM_BOT_TOKEN:
        return {
            "success": False,
            "error": "❌ TELEGRAM_BOT_TOKEN Missing"
        }

    if not TELEGRAM_CHAT_ID:
        return {
            "success": False,
            "error": "❌ TELEGRAM_CHAT_ID Missing"
        }

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    try:

        response = requests.post(
            url,
            json=payload,
            timeout=15
        )

        return response.json()

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }
