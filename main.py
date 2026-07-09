from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {
        "project": "NAKSHATRA AI",
        "status": "Running",
        "version": "0.1"
    }
