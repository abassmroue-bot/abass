from datetime import datetime, timedelta

import pytest

from trillion.heartbeat import checks as checks_module
from trillion.heartbeat.checks import gold_mt5_autotrade_check, gold_signal_check
from trillion.trading import mt5_broker as mt5_broker_module
from trillion.trading.autotrade_switch import disable_autotrade, enable_autotrade, is_autotrade_enabled
from trillion.trading.data_feed import Candle
from trillion.trading.mt5_broker import Position
from trillion.trading.risk import RiskLimits, order_allowed
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


# --- risk.py -------------------------------------------------------------


def _limits(**overrides):
    defaults = dict(
        lot_size=0.01, stop_loss_pips=100, take_profit_pips=150, max_open_positions=1, daily_loss_cap=50
    )
    defaults.update(overrides)
    return RiskLimits(**defaults)


def test_order_allowed_when_under_every_limit():
    allowed, reason = order_allowed(_limits(), open_position_count=0, daily_realized_pnl=0)
    assert allowed is True
    assert reason is None


def test_order_blocked_at_max_open_positions():
    allowed, reason = order_allowed(_limits(max_open_positions=1), open_position_count=1, daily_realized_pnl=0)
    assert allowed is False
    assert "max_open_positions" in reason


def test_order_blocked_at_daily_loss_cap():
    allowed, reason = order_allowed(_limits(daily_loss_cap=50), open_position_count=0, daily_realized_pnl=-50)
    assert allowed is False
    assert "daily loss cap" in reason


def test_order_allowed_just_under_the_daily_loss_cap():
    allowed, _ = order_allowed(_limits(daily_loss_cap=50), open_position_count=0, daily_realized_pnl=-49.99)
    assert allowed is True


# --- autotrade_switch.py ---------------------------------------------------


def test_autotrade_off_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))
    assert is_autotrade_enabled() is False


def test_autotrade_enable_and_disable_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))
    enable_autotrade()
    assert is_autotrade_enabled() is True
    disable_autotrade()
    assert is_autotrade_enabled() is False


# --- checks.py: gold_mt5_autotrade_check ------------------------------------


def test_autotrade_check_is_a_no_op_when_switch_is_off(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))  # real switch, real (absent) flag file

    def boom(*a, **k):
        raise AssertionError("must not touch MT5 while the autotrade switch is off")

    monkeypatch.setattr(mt5_broker_module, "connect", boom)
    assert gold_mt5_autotrade_check({}) is None


def test_autotrade_check_holds_without_placing_an_order(monkeypatch):
    monkeypatch.setattr(checks_module, "is_autotrade_enabled", lambda: True)
    monkeypatch.setattr(mt5_broker_module, "connect", lambda: None)
    monkeypatch.setattr(
        mt5_broker_module, "get_candles", lambda *a, **k: _candles([1, 2, 3, 4, 5, 6, 7])
    )

    def boom(*a, **k):
        raise AssertionError("must not place an order on a HOLD signal")

    monkeypatch.setattr(mt5_broker_module, "place_market_order", boom)

    result = gold_mt5_autotrade_check({"fast_period": 2, "slow_period": 4})
    assert result is None


def test_autotrade_check_skips_a_signal_blocked_by_risk_limits(monkeypatch):
    monkeypatch.setattr(checks_module, "is_autotrade_enabled", lambda: True)
    monkeypatch.setattr(mt5_broker_module, "connect", lambda: None)
    monkeypatch.setattr(
        mt5_broker_module, "get_candles", lambda *a, **k: _candles([90, 91, 92, 93, 94, 95, 80])
    )
    monkeypatch.setattr(
        mt5_broker_module,
        "get_open_positions",
        lambda symbol: [
            Position(ticket=1, symbol=symbol, direction="sell", volume=0.01, open_price=2400.0, profit=0.0)
        ],
    )
    monkeypatch.setattr(mt5_broker_module, "get_daily_realized_pnl", lambda symbol: 0.0)

    def boom(*a, **k):
        raise AssertionError("must not place an order once max_open_positions is reached")

    monkeypatch.setattr(mt5_broker_module, "place_market_order", boom)

    result = gold_mt5_autotrade_check({"fast_period": 2, "slow_period": 4, "max_open_positions": 1})
    assert result is not None
    assert result.level == "log"
    assert "skipped" in result.text
    assert "max_open_positions" in result.text


def test_autotrade_check_places_an_order_on_a_signal(monkeypatch):
    monkeypatch.setattr(checks_module, "is_autotrade_enabled", lambda: True)
    monkeypatch.setattr(mt5_broker_module, "connect", lambda: None)
    monkeypatch.setattr(
        mt5_broker_module, "get_candles", lambda *a, **k: _candles([90, 91, 92, 93, 94, 95, 80])
    )
    monkeypatch.setattr(mt5_broker_module, "get_open_positions", lambda symbol: [])
    monkeypatch.setattr(mt5_broker_module, "get_daily_realized_pnl", lambda symbol: 0.0)

    placed = {}

    def fake_place_market_order(symbol, direction, volume, stop_loss_pips, take_profit_pips, pip_size):
        placed.update(
            symbol=symbol,
            direction=direction,
            volume=volume,
            stop_loss_pips=stop_loss_pips,
            take_profit_pips=take_profit_pips,
            pip_size=pip_size,
        )
        return 12345

    monkeypatch.setattr(mt5_broker_module, "place_market_order", fake_place_market_order)

    result = gold_mt5_autotrade_check(
        {"fast_period": 2, "slow_period": 4, "lot_size": 0.02, "stop_loss_pips": 100, "take_profit_pips": 150}
    )
    assert result is not None
    assert result.level == "interrupt"
    assert "SELL" in result.text
    assert "12345" in result.text
    assert placed == {
        "symbol": "XAUUSD",
        "direction": "sell",
        "volume": 0.02,
        "stop_loss_pips": 100,
        "take_profit_pips": 150,
        "pip_size": 0.1,
    }


def test_autotrade_check_reports_unknown_strategy_without_touching_mt5(monkeypatch):
    monkeypatch.setattr(checks_module, "is_autotrade_enabled", lambda: True)

    def boom(*a, **k):
        raise AssertionError("must not touch MT5 for an unknown strategy")

    monkeypatch.setattr(mt5_broker_module, "connect", boom)

    result = gold_mt5_autotrade_check({"strategy": "not_a_real_strategy"})
    assert result.level == "log"
    assert "not_a_real_strategy" in result.text


def test_autotrade_check_is_registered():
    assert checks_module.CHECKS["gold_mt5_autotrade"] is gold_mt5_autotrade_check
