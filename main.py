
from fastapi import FastAPI
import os

app = FastAPI()

@app.get("/")
def home():
    return {
        "status": "NAKSHATRA AI CRYPTO Running",
        "api_key_found": bool(os.getenv("DELTA_API_KEY")),
        "api_secret_found": bool(os.getenv("DELTA_API_SECRET"))
    }
