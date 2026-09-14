NAKSHATRA AI Crypto
FastAPI + Delta Exchange India crypto analytics dashboard.
Included
BTC/USD and ETH/USD quick selection
Live Delta crypto product search
Technical + MTF analysis
Option intelligence when Delta option data is available
Intraday / volume / reversal context
Astrology and numerology dashboard heuristics
AI BUY / SELL / WAIT decision
SQLite trade history and statistics
Live scanner and scheduler
Responsive dark neon dashboard
Render
Build command:
pip install -r requirements.txt
Start command:
uvicorn main:app --host 0.0.0.0 --port $PORT
Health check: /health
Important
This repository does not contain secrets. Add Delta credentials and other secrets in Render Environment Variables if needed.
trades.db is generated at runtime and is intentionally ignored by Git.
