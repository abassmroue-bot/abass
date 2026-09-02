"""Built-in heartbeat checks.

Each check is a small function `(params: dict) -> CheckResult | None`.
Returning `None` — "nothing worth surfacing" — is the expected outcome
most of the time; that's what "quiet by default" means in practice. Add
a new capability by writing one function here, adding it to `CHECKS`,
then turning it on in `config.yaml` — nothing else needs to change.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..tools.notes import search_notes
from ..tools.reminders import load_reminders
from ..trading import mt5_broker
from ..trading.autotrade_switch import is_autotrade_enabled
from ..trading.data_feed import fetch_candles
from ..trading.risk import RiskLimits, order_allowed
from ..trading.strategy import STRATEGIES, Signal

_AUTOTRADE_NON_STRATEGY_PARAMS = {
    "symbol",
    "timeframe",
    "lookback_candles",
    "strategy",
    "lot_size",
    "stop_loss_pips",
    "take_profit_pips",
    "pip_size",
    "max_open_positions",
    "daily_loss_cap",
}


@dataclass
class CheckResult:
    level: str  # "log" | "interrupt" | "critical"
    text: str


def notes_watch(params: dict) -> CheckResult | None:
    """Surface an interruption if a configured phrase shows up in notes.

    This is the check meant for exercising the heartbeat end to end: add
    a line containing `params["query"]` to a note and the next due tick
    should surface it.
    """
    query = (params.get("query") or "").strip()
    if not query:
        return None
    result = search_notes({"query": query})
    if result.startswith("No matches") or result.startswith("error:"):
        return None
    return CheckResult(level="interrupt", text=f"Found {query!r} in your notes:\n{result}")


def open_reminders_digest(params: dict) -> CheckResult | None:
    """A quiet, log-only digest of open reminders.

    Produces nothing when there's nothing open, so it stays out of the
    way — it only ever shows up in the calm log, never as an
    interruption, per AGENT.md's "most checks produce nothing" rule.
    """
    open_reminders = [r for r in load_reminders() if not r.get("done")]
    if not open_reminders:
        return None
    lines = "\n".join(f"- {r['text']}" for r in open_reminders)
    return CheckResult(level="log", text=f"{len(open_reminders)} open reminder(s):\n{lines}")


def gold_signal_check(params: dict) -> CheckResult | None:
    """Fetches recent gold/USD candles and runs a swappable strategy over
    them, surfacing an interrupt-level notice on a fresh BUY/SELL signal.

    HOLD — including "not enough history yet" — produces nothing, the
    same "quiet by default" rule every other check follows. This only
    ever notices and reports a signal; it never places a trade. Needs
    network access to Yahoo Finance — a fetch failure raises, which the
    scheduler already catches and logs without taking the loop down.
    """
    symbol = params.get("symbol", "XAUUSD=X")
    interval = params.get("interval", "15m")
    lookback = params.get("lookback", "5d")
    strategy_name = params.get("strategy", "moving_average_cross")

    strategy_cls = STRATEGIES.get(strategy_name)
    if strategy_cls is None:
        return CheckResult(level="log", text=f"gold_signal: unknown strategy {strategy_name!r}")

    strategy_kwargs = {
        k: v for k, v in params.items() if k not in {"symbol", "interval", "lookback", "strategy"}
    }
    strategy_instance = strategy_cls(**strategy_kwargs)

    candles = fetch_candles(symbol, interval, lookback)
    signal = strategy_instance.evaluate(candles)
    if signal is Signal.HOLD:
        return None

    last = candles[-1]
    return CheckResult(
        level="interrupt",
        text=(
            f"Gold/USD ({symbol}) signal: {signal.value.upper()} — {strategy_name}, "
            f"last close {last.close:.2f} at {last.timestamp.isoformat()}. "
            f"Signal only, no trade was placed."
        ),
    )


def gold_mt5_autotrade_check(params: dict) -> CheckResult | None:
    """Automatic, unattended MT5 gold/USD trading — this is the one path
    in Trillion that spends real money without a per-trade confirmation
    prompt, and it exists only because of that: see the AGENT.md
    amendment and `autotrade_switch.py` for why this is allowed at all.

    Does nothing at all — not even connecting to MT5 — unless
    `autotrade_switch.is_autotrade_enabled()` is true, which requires a
    deliberate, one-time `python -m trillion.trading.autotrade_switch on`
    run outside of any conversation. With it off (the default), this
    check is a complete no-op, same as an unconfigured `notes_watch`.

    With it on: fetches live MT5 candles, runs the configured strategy,
    and on a BUY/SELL signal checks `risk.order_allowed()` (max open
    positions, daily loss cap) before sending a market order that always
    carries a stop loss and take profit. A HOLD signal, or an order
    blocked by a risk limit, produces no order and either nothing (HOLD)
    or a quiet log entry (blocked) — never a silent failure and never a
    retry that could double an order.
    """
    if not is_autotrade_enabled():
        return None

    symbol = params.get("symbol", "XAUUSD")
    timeframe = params.get("timeframe", "M15")
    lookback_candles = params.get("lookback_candles", 200)
    strategy_name = params.get("strategy", "moving_average_cross")

    strategy_cls = STRATEGIES.get(strategy_name)
    if strategy_cls is None:
        return CheckResult(
            level="log", text=f"gold_mt5_autotrade: unknown strategy {strategy_name!r}"
        )
    strategy_kwargs = {
        k: v for k, v in params.items() if k not in _AUTOTRADE_NON_STRATEGY_PARAMS
    }
    strategy_instance = strategy_cls(**strategy_kwargs)

    limits = RiskLimits(
        lot_size=params.get("lot_size", 0.01),
        stop_loss_pips=params.get("stop_loss_pips", 100),
        take_profit_pips=params.get("take_profit_pips", 150),
        max_open_positions=params.get("max_open_positions", 1),
        daily_loss_cap=params.get("daily_loss_cap", 50),
    )
    pip_size = params.get("pip_size", 0.1)

    mt5_broker.connect()
    candles = mt5_broker.get_candles(symbol, timeframe, lookback_candles)
    signal = strategy_instance.evaluate(candles)
    if signal is Signal.HOLD:
        return None

    open_positions = mt5_broker.get_open_positions(symbol)
    daily_pnl = mt5_broker.get_daily_realized_pnl(symbol)
    allowed, reason = order_allowed(limits, len(open_positions), daily_pnl)
    if not allowed:
        return CheckResult(
            level="log",
            text=f"gold_mt5_autotrade: {signal.value.upper()} signal skipped — {reason}",
        )

    direction = "buy" if signal is Signal.BUY else "sell"
    ticket = mt5_broker.place_market_order(
        symbol, direction, limits.lot_size, limits.stop_loss_pips, limits.take_profit_pips, pip_size
    )
    return CheckResult(
        level="interrupt",
        text=(
            f"MT5 autotrade: placed a {direction.upper()} order on {symbol} "
            f"(ticket {ticket}, {limits.lot_size} lots, SL {limits.stop_loss_pips}p / "
            f"TP {limits.take_profit_pips}p, {strategy_name})."
        ),
    )


CHECKS = {
    "notes_watch": notes_watch,
    "open_reminders_digest": open_reminders_digest,
    "gold_signal": gold_signal_check,
    "gold_mt5_autotrade": gold_mt5_autotrade_check,
}
