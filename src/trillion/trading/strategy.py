"""Trading strategies: turn a run of `Candle`s into a `Signal`.

This is a scaffold, not a finished trading system — `MovingAverageCrossStrategy`
below is a placeholder starting point. Add a real one by writing a class
with an `evaluate(candles) -> Signal` method and registering it in
`STRATEGIES`; nothing else (the heartbeat check, config.yaml) needs code
changes to pick it up, only a `strategy:` name in config.
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol

from .data_feed import Candle


class Signal(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class Strategy(Protocol):
    def evaluate(self, candles: list[Candle]) -> Signal: ...


def _sma(values: list[float], period: int) -> list[float | None]:
    """Simple moving average, aligned to `values` (None until there's enough history)."""
    result: list[float | None] = []
    for i in range(len(values)):
        if i + 1 < period:
            result.append(None)
        else:
            result.append(sum(values[i + 1 - period : i + 1]) / period)
    return result


class MovingAverageCrossStrategy:
    """BUY on a fresh cross of the fast SMA above the slow SMA, SELL on the
    reverse cross, HOLD otherwise — including when there isn't yet enough
    history to compute both averages, and while an existing cross persists
    without a new one (so it fires once per crossover, not every tick)."""

    def __init__(self, fast_period: int = 20, slow_period: int = 50) -> None:
        if fast_period >= slow_period:
            raise ValueError("fast_period must be smaller than slow_period")
        self.fast_period = fast_period
        self.slow_period = slow_period

    def evaluate(self, candles: list[Candle]) -> Signal:
        closes = [c.close for c in candles]
        fast = _sma(closes, self.fast_period)
        slow = _sma(closes, self.slow_period)

        if len(closes) < self.slow_period + 1 or fast[-2] is None or slow[-2] is None:
            return Signal.HOLD

        crossed_up = fast[-2] <= slow[-2] and fast[-1] > slow[-1]
        crossed_down = fast[-2] >= slow[-2] and fast[-1] < slow[-1]

        if crossed_up:
            return Signal.BUY
        if crossed_down:
            return Signal.SELL
        return Signal.HOLD


STRATEGIES = {
    "moving_average_cross": MovingAverageCrossStrategy,
}
