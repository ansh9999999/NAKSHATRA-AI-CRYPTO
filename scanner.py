"""Lightweight market scanner used by the NAKSHATRA scheduler and API."""

from history import get_history
from analysis.signal import generate_signal

SYMBOLS = ['BTCUSD', 'ETHUSD']


def scan_symbol(symbol):
    try:
        df = get_history(symbol=symbol)
        if df is None or getattr(df, 'empty', True):
            return {'symbol': symbol, 'signal': 'WAIT', 'strength': 0, 'status': 'NO DATA'}
        result = generate_signal(df)
        signal = str(result.get('signal', 'WAIT')).upper()
        confidence = result.get('confidence', result.get('strength', 0))
        try:
            strength = round(float(confidence), 1)
        except (TypeError, ValueError):
            strength = 0
        return {'symbol': symbol, 'signal': signal, 'strength': strength, 'status': 'OK'}
    except Exception as exc:
        print(f'Scanner error {symbol}: {exc}')
        return {'symbol': symbol, 'signal': 'WAIT', 'strength': 0, 'status': 'ERROR'}


def market_scan():
    results = [scan_symbol(symbol) for symbol in SYMBOLS]
    print('🔎 Market Scan:', results)
    return results
