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
from ..trading.data_feed import fetch_candles
from ..trading.strategy import STRATEGIES, Signal


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


CHECKS = {
    "notes_watch": notes_watch,
    "open_reminders_digest": open_reminders_digest,
    "gold_signal": gold_signal_check,
}
