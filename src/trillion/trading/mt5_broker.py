"""Thin seam around a running MetaTrader 5 terminal: price data in,
orders out.

The `MetaTrader5` Python package only works on Windows, talking to an
already-running, already-logged-in MT5 terminal over local IPC — it
can't be installed or exercised in this build environment at all. Every
function below imports it lazily so the rest of the app never needs it
installed, and every one is exercised in tests through monkeypatching
this module's functions directly rather than the real package. Treat
this seam as unverified against a live terminal until you've run it
yourself, on your own machine, against a demo account first.

Pip size: `place_market_order` takes `pip_size` as an explicit argument
rather than guessing it from the symbol's tick size, because gold's pip
convention (0.1 vs 0.01 vs something else) varies by broker — get this
wrong and your stop loss/take profit land at the wrong distance. Check
your broker's XAUUSD contract specification before trusting the default
in config.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time as dt_time

from .data_feed import Candle


@dataclass
class Position:
    ticket: int
    symbol: str
    direction: str  # "buy" | "sell"
    volume: float
    open_price: float
    profit: float


def _mt5():
    import MetaTrader5 as mt5  # only importable on Windows with the terminal installed

    return mt5


def connect() -> None:
    """Attach to the already-running, already-logged-in MT5 terminal.

    Login itself happens in the terminal application (or via
    `mt5.login(...)` if you want this to do it too) — this just opens
    the IPC connection to whichever terminal/account is already open.
    """
    mt5 = _mt5()
    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize() failed: {mt5.last_error()}")


def get_candles(symbol: str, timeframe: str, count: int) -> list[Candle]:
    mt5 = _mt5()
    tf = getattr(mt5, f"TIMEFRAME_{timeframe.upper()}", None)
    if tf is None:
        raise ValueError(f"unknown MT5 timeframe {timeframe!r}")

    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"no MT5 price data for {symbol!r}: {mt5.last_error()}")

    return [
        Candle(
            timestamp=datetime.fromtimestamp(r["time"]),
            open=float(r["open"]),
            high=float(r["high"]),
            low=float(r["low"]),
            close=float(r["close"]),
            volume=float(r["tick_volume"]),
        )
        for r in rates
    ]


def get_open_positions(symbol: str) -> list[Position]:
    mt5 = _mt5()
    positions = mt5.positions_get(symbol=symbol) or []
    return [
        Position(
            ticket=p.ticket,
            symbol=p.symbol,
            direction="buy" if p.type == mt5.POSITION_TYPE_BUY else "sell",
            volume=p.volume,
            open_price=p.price_open,
            profit=p.profit,
        )
        for p in positions
    ]


def get_daily_realized_pnl(symbol: str) -> float:
    """Sum of closed-trade profit on `symbol` since local midnight."""
    mt5 = _mt5()
    today_start = datetime.combine(datetime.now().date(), dt_time.min)
    deals = mt5.history_deals_get(today_start, datetime.now(), group=symbol) or []
    return sum(d.profit for d in deals)


def place_market_order(
    symbol: str,
    direction: str,  # "buy" | "sell"
    volume: float,
    stop_loss_pips: float,
    take_profit_pips: float,
    pip_size: float,
) -> int:
    """Send a market order that always carries a stop loss and take
    profit — no trade this seam sends is ever unprotected. Returns the
    resulting ticket number; raises on any failure or rejection, so a
    failed order can never be mistaken for a placed one."""
    mt5 = _mt5()
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError(f"no MT5 tick data for {symbol!r}: {mt5.last_error()}")

    price = tick.ask if direction == "buy" else tick.bid
    distance_sl = pip_size * stop_loss_pips
    distance_tp = pip_size * take_profit_pips
    sl = price - distance_sl if direction == "buy" else price + distance_sl
    tp = price + distance_tp if direction == "buy" else price - distance_tp

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_BUY if direction == "buy" else mt5.ORDER_TYPE_SELL,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "type_filling": mt5.ORDER_FILLING_IOC,
        "type_time": mt5.ORDER_TIME_GTC,
        "comment": "trillion-autotrade",
    }
    result = mt5.order_send(request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        raise RuntimeError(f"MT5 order_send failed: {result}")
    return result.order
