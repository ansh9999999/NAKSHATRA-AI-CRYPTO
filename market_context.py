from __future__ import annotations
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo('Asia/Kolkata')
UTC = timezone.utc


def _window(name, start, end, level, effect):
    return {'name': name, 'start_ist': start, 'end_ist': end, 'activity': level, 'effect': effect}


def session_context(now_utc: datetime | None = None):
    now_utc = now_utc or datetime.now(UTC)
    now = now_utc.astimezone(IST)
    # DST-aware windows are represented in UTC and converted to IST.
    # London 08:00-16:30 local; New York 09:30-16:00 local.
    london = now.astimezone(ZoneInfo('Europe/London'))
    ny = now.astimezone(ZoneInfo('America/New_York'))

    def active_local(t, start_h, start_m, end_h, end_m):
        mins = t.hour * 60 + t.minute
        return start_h * 60 + start_m <= mins < end_h * 60 + end_m

    windows = []
    if active_local(london, 8, 0, 16, 30):
        windows.append('EUROPE SESSION')
    if active_local(ny, 9, 30, 16, 0):
        windows.append('US SESSION')
    if active_local(london, 13, 30, 16, 30) and active_local(ny, 9, 30, 13, 0):
        windows.append('EU-US OVERLAP')

    # General liquidity regime; direction is deliberately not inferred.
    hour = now.hour + now.minute / 60
    if 18 <= hour < 24:
        activity, effect = 'HIGH', 'Higher liquidity/volatility; moves can accelerate.'
    elif 13 <= hour < 18:
        activity, effect = 'HIGH', 'Europe/US transition; breakout and reversal risk rises.'
    elif 4 <= hour < 11:
        activity, effect = 'LOW', 'Thinner liquidity; fake breakouts and wider execution risk.'
    else:
        activity, effect = 'MEDIUM', 'Normal global crypto activity.'

    return {
        'timezone': 'Asia/Kolkata',
        'current_ist': now.isoformat(),
        'active_sessions': windows,
        'activity': activity,
        'effect': effect,
        'note': 'Crypto trades 24/7; session labels indicate liquidity/volatility regime, not price direction.'
    }


def event_context(now_utc: datetime | None = None):
    now_utc = now_utc or datetime.now(UTC)
    watchlist = [
        {'name': 'FOMC / Fed communication', 'impact': 'EXTREME', 'effect': 'Can shift yields and USD; BTC/ETH volatility and volume can jump sharply.'},
        {'name': 'US CPI / PPI / inflation', 'impact': 'HIGH', 'effect': 'Inflation surprise can change rate expectations and risk appetite.'},
        {'name': 'US jobs / payrolls', 'impact': 'HIGH', 'effect': 'Employment surprise can reprice rates, USD and crypto risk.'},
        {'name': 'ETF flows / regulatory headlines', 'impact': 'HIGH', 'effect': 'Can directly alter crypto demand, liquidity and sentiment.'},
        {'name': 'Major exchange / protocol / security news', 'impact': 'HIGH', 'effect': 'Can create idiosyncratic BTC/ETH or sector-wide moves.'},
    ]
    return {
        'risk': 'NORMAL',
        'next_event': None,
        'upcoming': [],
        'watchlist': watchlist,
        'disclaimer': 'Live event timestamps require an official economic-calendar/news feed; the dashboard exposes the impact model until that feed is connected.'
    }
