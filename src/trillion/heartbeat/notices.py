"""The heartbeat's inbox: proactive notices that are held until they're
worth showing, never silently dropped, and always dismissible.

A "log"-level notice never interrupts — it just accumulates here for
`list_notices`/`dismiss_notice` to find on demand (the calm log). An
"interrupt"-level notice is held back during quiet hours and delivered
the next time `surface_pending()` is called after they end — nothing
generated while you were away is lost, it's just waiting. "critical"
always surfaces immediately, quiet hours or not.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, time as dt_time, timezone
from pathlib import Path

from .config import QuietHours

LEVELS = ("log", "interrupt", "critical")


@dataclass
class Notice:
    id: str
    created_at: str  # UTC ISO 8601
    check_name: str
    level: str
    text: str
    dismissed: bool = False
    shown: bool = False


def _data_dir() -> Path:
    path = Path(os.environ.get("TRILLION_DATA_DIR", "./data"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _store_path() -> Path:
    return _data_dir() / "notices.json"


def _load() -> list[Notice]:
    path = _store_path()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError:
        return []
    return [Notice(**item) for item in raw]


def _save(notices: list[Notice]) -> None:
    _store_path().write_text(json.dumps([asdict(n) for n in notices], indent=2))


def add_notice(check_name: str, level: str, text: str) -> Notice:
    if level not in LEVELS:
        raise ValueError(f"unknown notice level {level!r}, expected one of {LEVELS}")
    notice = Notice(
        id=uuid.uuid4().hex[:8],
        created_at=datetime.now(timezone.utc).isoformat(),
        check_name=check_name,
        level=level,
        text=text,
    )
    notices = _load()
    notices.append(notice)
    _save(notices)
    return notice


def list_notices(include_dismissed: bool = False) -> list[Notice]:
    notices = _load()
    if include_dismissed:
        return notices
    return [n for n in notices if not n.dismissed]


def dismiss_notice(notice_id: str) -> bool:
    notices = _load()
    for notice in notices:
        if notice.id == notice_id:
            notice.dismissed = True
            _save(notices)
            return True
    return False


def _in_quiet_hours(now_local: dt_time, quiet_hours: QuietHours) -> bool:
    start, end = quiet_hours.start, quiet_hours.end
    if start <= end:
        return start <= now_local < end
    return now_local >= start or now_local < end  # wraps past midnight


def surface_pending(quiet_hours: QuietHours, now: datetime | None = None) -> list[Notice]:
    """Return notices worth showing right now, and mark them shown.

    Call this whenever you open the conversation (CLI startup) — it's
    the "catch up on what happened while I was away" step. A notice is
    only ever marked shown here, so nothing is missed: an interrupt held
    during quiet hours simply comes back on the next call once they end.
    """
    now = now or datetime.now()
    notices = _load()
    to_show = []
    changed = False

    for notice in notices:
        if notice.dismissed or notice.shown or notice.level == "log":
            continue
        if notice.level == "interrupt" and _in_quiet_hours(now.time(), quiet_hours):
            continue
        notice.shown = True
        to_show.append(notice)
        changed = True

    if changed:
        _save(notices)
    return to_show
