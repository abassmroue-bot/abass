from datetime import datetime, timedelta

import pytest

from trillion.heartbeat import checks as checks_module
from trillion.heartbeat.checks import gold_signal_check
from trillion.trading.data_feed import Candle
from trillion.trading.strategy import STRATEGIES, MovingAverageCrossStrategy, Signal


def _candles(closes: list[float]) -> list[Candle]:
    start = datetime(2026, 1, 1)
    return [
        Candle(timestamp=start + timedelta(minutes=i), open=c, high=c, low=c, close=c, volume=0)
        for i, c in enumerate(closes)
    ]


# --- strategy.py -------------------------------------------------------


def test_moving_average_cross_holds_without_enough_history():
    strategy = MovingAverageCrossStrategy(fast_period=2, slow_period=4)
    assert strategy.evaluate(_candles([1, 2, 3])) is Signal.HOLD


def test_moving_average_cross_detects_a_fresh_bullish_cross():
    strategy = MovingAverageCrossStrategy(fast_period=2, slow_period=4)
    # fast SMA sits below the slow one through a decline, then a sharp
    # last-bar rally flips it above -- a fresh cross on the final candle.
    closes = [10, 9, 8, 7, 6, 5, 20]
    assert strategy.evaluate(_candles(closes)) is Signal.BUY


def test_moving_average_cross_detects_a_fresh_bearish_cross():
    strategy = MovingAverageCrossStrategy(fast_period=2, slow_period=4)
    closes = [90, 91, 92, 93, 94, 95, 80]
    assert strategy.evaluate(_candles(closes)) is Signal.SELL


def test_moving_average_cross_holds_when_no_new_cross():
    strategy = MovingAverageCrossStrategy(fast_period=2, slow_period=4)
    closes = [1, 2, 3, 4, 5, 6, 7]  # steadily rising -- crossed long ago, nothing new
    assert strategy.evaluate(_candles(closes)) is Signal.HOLD


def test_fast_period_must_be_smaller_than_slow_period():
    with pytest.raises(ValueError):
        MovingAverageCrossStrategy(fast_period=10, slow_period=10)


def test_strategy_registry_contains_the_default():
    assert STRATEGIES["moving_average_cross"] is MovingAverageCrossStrategy


# --- checks.py: gold_signal_check ---------------------------------------


def test_gold_signal_check_notifies_on_a_sell_cross(monkeypatch):
    candles = _candles([90, 91, 92, 93, 94, 95, 80])
    monkeypatch.setattr(checks_module, "fetch_candles", lambda *a, **k: candles)

    result = gold_signal_check({"fast_period": 2, "slow_period": 4})
    assert result is not None
    assert result.level == "interrupt"
    assert "SELL" in result.text
    assert "no trade was placed" in result.text


def test_gold_signal_check_is_quiet_on_hold(monkeypatch):
    candles = _candles([1, 2, 3, 4, 5, 6, 7])
    monkeypatch.setattr(checks_module, "fetch_candles", lambda *a, **k: candles)

    assert gold_signal_check({"fast_period": 2, "slow_period": 4}) is None


def test_gold_signal_check_reports_an_unknown_strategy_without_crashing():
    result = gold_signal_check({"strategy": "not_a_real_strategy"})
    assert result.level == "log"
    assert "not_a_real_strategy" in result.text


def test_gold_signal_check_is_registered():
    assert checks_module.CHECKS["gold_signal"] is gold_signal_check
