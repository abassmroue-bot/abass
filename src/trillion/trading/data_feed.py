"""Fetches OHLC price candles for a symbol via Yahoo Finance (yfinance).

This is the only place that talks to a market-data provider — strategies
only ever see plain `Candle` objects, so swapping data sources later (a
broker API, a different vendor) means touching this file alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


def fetch_candles(symbol: str, interval: str, lookback: str) -> list[Candle]:
    """Fetch recent OHLC candles for `symbol` (e.g. "XAUUSD=X" for gold/USD).

    `interval` and `lookback` follow yfinance's own interval/period syntax
    (e.g. interval="15m", lookback="5d"). Raises RuntimeError on an empty
    or failed fetch rather than returning silently-wrong data — the
    heartbeat scheduler already catches and logs any check that raises,
    so a bad fetch shows up in the log instead of vanishing.
    """
    import yfinance as yf  # imported lazily: only needed when this check runs

    history = yf.Ticker(symbol).history(period=lookback, interval=interval)
    if history.empty:
        raise RuntimeError(
            f"no price data returned for {symbol!r} (interval={interval!r}, period={lookback!r})"
        )

    return [
        Candle(
            timestamp=timestamp.to_pydatetime(),
            open=float(row.Open),
            high=float(row.High),
            low=float(row.Low),
            close=float(row.Close),
            volume=float(row.Volume),
        )
        for timestamp, row in history.iterrows()
    ]
