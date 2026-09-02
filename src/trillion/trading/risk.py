"""Pure risk-control logic for automatic order placement.

Kept broker- and network-free on purpose so the actual money-relevant
decision — is a new order allowed right now — is fully unit-testable
without MT5 installed, and stays in one obvious place to audit.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskLimits:
    lot_size: float
    stop_loss_pips: float
    take_profit_pips: float
    max_open_positions: int
    daily_loss_cap: float


def order_allowed(
    limits: RiskLimits, open_position_count: int, daily_realized_pnl: float
) -> tuple[bool, str | None]:
    """Whether a new order is allowed right now, and if not, why.

    Both caps are hard stops: hitting either blocks every new order —
    win or lose — until the condition clears on its own (a position
    closes, or a new day starts). Neither resets itself mid-streak, and
    neither is bypassable from here.
    """
    if open_position_count >= limits.max_open_positions:
        return False, f"max_open_positions ({limits.max_open_positions}) reached"
    if daily_realized_pnl <= -abs(limits.daily_loss_cap):
        return (
            False,
            f"daily loss cap (${limits.daily_loss_cap:.2f}) reached "
            f"(realized ${daily_realized_pnl:.2f} today)",
        )
    return True, None
