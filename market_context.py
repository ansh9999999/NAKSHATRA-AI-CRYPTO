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


def _scheduled_events_2026():
    """Known scheduled macro events shown in IST.

    Times are converted from the official source calendars to Asia/Kolkata.
    Events without a fixed release time are explicitly marked as variable.
    """
    return [
        {
            'name': 'FOMC statement / rate decision',
            'impact': 'EXTREME',
            'effect': 'Fed decision can sharply change yields, USD and crypto volatility.',
            'dt': datetime(2026, 9, 16, 23, 30, tzinfo=IST),
            'source_type': 'scheduled',
        },
        {
            'name': 'FOMC press conference',
            'impact': 'EXTREME',
            'effect': 'Fed guidance can rapidly reprice rates, USD and crypto risk.',
            'dt': datetime(2026, 9, 17, 0, 0, tzinfo=IST),
            'source_type': 'scheduled',
        },
        {
            'name': 'US Jobless Claims',
            'impact': 'MEDIUM',
            'effect': 'Weekly labour data can affect rate expectations and risk appetite.',
            'dt': datetime(2026, 9, 17, 18, 0, tzinfo=IST),
            'source_type': 'scheduled',
        },
        {
            'name': 'US Employment Situation / NFP',
            'impact': 'HIGH',
            'effect': 'Payrolls and unemployment data can move USD, yields and crypto.',
            'dt': datetime(2026, 10, 2, 18, 0, tzinfo=IST),
            'source_type': 'scheduled',
        },
        {
            'name': 'US CPI',
            'impact': 'HIGH',
            'effect': 'Inflation data can change rate expectations and crypto risk appetite.',
            'dt': datetime(2026, 10, 14, 18, 0, tzinfo=IST),
            'source_type': 'scheduled',
        },
        {
            'name': 'US PPI',
            'impact': 'HIGH',
            'effect': 'Producer inflation can influence rate expectations and USD.',
            'dt': datetime(2026, 10, 15, 18, 0, tzinfo=IST),
            'source_type': 'scheduled',
        },
    ]


def event_context(now_utc: datetime | None = None):
    now_utc = now_utc or datetime.now(UTC)
    now = now_utc.astimezone(IST)

    scheduled = [e for e in _scheduled_events_2026() if e['dt'] >= now]
    scheduled.sort(key=lambda e: e['dt'])

    upcoming = []
    for e in scheduled[:6]:
        dt = e['dt']
        delta = (dt - now).total_seconds()
        if delta <= 3600:
            status = 'NEXT • <1H'
        elif delta <= 86400:
            status = 'NEXT • TODAY'
        else:
            status = 'UPCOMING'
        upcoming.append({
            'name': e['name'],
            'impact': e['impact'],
            'effect': e['effect'],
            'date_ist': dt.strftime('%d %b %Y'),
            'time_ist': dt.strftime('%I:%M %p IST').lstrip('0'),
            'datetime_ist': dt.isoformat(),
            'status': status,
            'source_type': e['source_type'],
        })

    # Events without a fixed timestamp remain visible, but are never given a fake time.
    variable = [
        {'name': 'Bitcoin ETF flows / regulatory headlines', 'impact': 'HIGH',
         'effect': 'Can directly alter crypto demand, liquidity and sentiment.',
         'date_ist': 'Daily', 'time_ist': 'Time varies (IST)', 'datetime_ist': None,
         'status': 'VARIABLE', 'source_type': 'variable'},
        {'name': 'Major exchange / protocol / security news', 'impact': 'HIGH',
         'effect': 'Can create idiosyncratic BTC/ETH or sector-wide moves.',
         'date_ist': 'As published', 'time_ist': 'Time varies (IST)', 'datetime_ist': None,
         'status': 'VARIABLE', 'source_type': 'variable'},
    ]

    next_event = upcoming[0] if upcoming else (variable[0] if variable else None)
    next_delta = None
    if next_event and next_event.get('datetime_ist'):
        next_delta = (datetime.fromisoformat(next_event['datetime_ist']) - now).total_seconds()

    if next_delta is not None and next_delta <= 86400:
        risk = 'EXTREME' if next_event['impact'] == 'EXTREME' else 'HIGH'
    else:
        risk = 'NORMAL'

    watchlist = upcoming[:4] + variable[:1]

    return {
        'risk': risk,
        'next_event': next_event,
        'upcoming': upcoming,
        'watchlist': watchlist,
        'timezone': 'Asia/Kolkata',
        'timezone_label': 'IST',
        'disclaimer': 'Scheduled times are displayed in IST. Live surprise headlines and unscheduled events require a connected news/calendar feed.',
    }
