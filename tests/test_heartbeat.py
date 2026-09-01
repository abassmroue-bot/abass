from datetime import datetime, time as dt_time

from trillion.heartbeat.checks import CheckResult, notes_watch, open_reminders_digest
from trillion.heartbeat.config import CheckConfig, HeartbeatConfig, QuietHours, load_heartbeat_config
from trillion.heartbeat.notices import add_notice, dismiss_notice, list_notices, surface_pending
from trillion.heartbeat.scheduler import Scheduler
from trillion.tools.reminders import add_reminder


# --- config.py ---------------------------------------------------------


def test_load_heartbeat_config_falls_back_when_file_missing(tmp_path):
    config = load_heartbeat_config(str(tmp_path / "does_not_exist.yaml"))
    assert config.checks == []
    assert config.poll_interval_seconds == 30


def test_load_heartbeat_config_parses_a_real_file(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
heartbeat:
  poll_interval_seconds: 5
  quiet_hours:
    start: "23:00"
    end: "06:30"
  checks:
    - name: notes_watch
      enabled: true
      interval_seconds: 10
      params:
        query: "URGENT"
"""
    )
    config = load_heartbeat_config(str(config_file))
    assert config.poll_interval_seconds == 5
    assert config.quiet_hours.start == dt_time(23, 0)
    assert config.quiet_hours.end == dt_time(6, 30)
    assert len(config.checks) == 1
    assert config.checks[0].name == "notes_watch"
    assert config.checks[0].interval_seconds == 10
    assert config.checks[0].params == {"query": "URGENT"}


# --- notices.py ----------------------------------------------------------


def test_add_list_and_dismiss_notice(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))
    notice = add_notice("some_check", "log", "hello")
    assert notice.text == "hello"

    assert [n.id for n in list_notices()] == [notice.id]
    assert dismiss_notice(notice.id) is True
    assert list_notices() == []
    assert dismiss_notice("nonexistent") is False


def test_log_level_notices_never_surface_as_interruptions(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))
    add_notice("digest", "log", "3 open reminders")
    quiet_hours = QuietHours(start=dt_time(22, 0), end=dt_time(7, 0))

    surfaced = surface_pending(quiet_hours, now=datetime(2026, 1, 1, 10, 0))
    assert surfaced == []
    # still visible in the calm log on demand, though
    assert len(list_notices()) == 1


def test_interrupt_notices_are_held_during_quiet_hours_and_released_after(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))
    add_notice("notes_watch", "interrupt", "found something")
    quiet_hours = QuietHours(start=dt_time(22, 0), end=dt_time(7, 0))

    # 11pm — inside quiet hours (wraps past midnight) — held
    held = surface_pending(quiet_hours, now=datetime(2026, 1, 1, 23, 0))
    assert held == []

    # 8am the next day — quiet hours over — now it surfaces
    surfaced = surface_pending(quiet_hours, now=datetime(2026, 1, 2, 8, 0))
    assert len(surfaced) == 1
    assert surfaced[0].text == "found something"

    # shown once — calling again doesn't re-deliver it
    assert surface_pending(quiet_hours, now=datetime(2026, 1, 2, 8, 5)) == []
    # but it's still in the inbox until dismissed
    assert len(list_notices()) == 1


def test_critical_notices_bypass_quiet_hours(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))
    add_notice("some_check", "critical", "wake up")
    quiet_hours = QuietHours(start=dt_time(22, 0), end=dt_time(7, 0))

    surfaced = surface_pending(quiet_hours, now=datetime(2026, 1, 1, 23, 0))
    assert len(surfaced) == 1


# --- checks.py -------------------------------------------------------------


def test_notes_watch_finds_configured_phrase(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_NOTES_DIR", str(tmp_path))
    (tmp_path / "note.md").write_text("Nothing to see here.\nURGENT: call the bank.\n")

    result = notes_watch({"query": "URGENT"})
    assert isinstance(result, CheckResult)
    assert result.level == "interrupt"
    assert "call the bank" in result.text


def test_notes_watch_returns_none_when_nothing_found(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_NOTES_DIR", str(tmp_path))
    (tmp_path / "note.md").write_text("nothing relevant\n")
    assert notes_watch({"query": "URGENT"}) is None


def test_open_reminders_digest_is_quiet_when_nothing_is_open(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))
    assert open_reminders_digest({}) is None


def test_open_reminders_digest_summarizes_open_reminders(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))
    add_reminder({"text": "buy milk"})

    result = open_reminders_digest({})
    assert result.level == "log"
    assert "buy milk" in result.text


# --- scheduler.py ----------------------------------------------------------


def test_scheduler_runs_a_due_check_and_persists_next_due(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TRILLION_NOTES_DIR", str(tmp_path / "notes"))
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "note.md").write_text("URGENT: renew passport\n")

    config = HeartbeatConfig(
        poll_interval_seconds=1,
        quiet_hours=QuietHours(start=dt_time(22, 0), end=dt_time(7, 0)),
        checks=[CheckConfig(name="notes_watch", interval_seconds=60, params={"query": "URGENT"})],
    )
    scheduler = Scheduler(config)
    now = datetime(2026, 1, 1, 12, 0)
    scheduler.tick(now=now)

    assert len(list_notices()) == 1
    assert "renew passport" in list_notices()[0].text

    # a restart: a fresh Scheduler reloads the same persisted state
    reloaded = Scheduler(config)
    assert "notes_watch" in reloaded.state
    persisted_next_due = datetime.fromisoformat(reloaded.state["notes_watch"]["next_due"])
    assert persisted_next_due == datetime(2026, 1, 1, 12, 1)  # now + 60s interval


def test_scheduler_skips_a_check_that_is_not_due_yet(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TRILLION_NOTES_DIR", str(tmp_path / "notes"))
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "note.md").write_text("URGENT: renew passport\n")

    config = HeartbeatConfig(
        poll_interval_seconds=1,
        quiet_hours=QuietHours(start=dt_time(22, 0), end=dt_time(7, 0)),
        checks=[CheckConfig(name="notes_watch", interval_seconds=3600, params={"query": "URGENT"})],
    )
    scheduler = Scheduler(config)
    scheduler.tick(now=datetime(2026, 1, 1, 12, 0))
    assert len(list_notices()) == 1

    # ticking again a second later shouldn't re-run it (not due for an hour)
    scheduler.tick(now=datetime(2026, 1, 1, 12, 0, 1))
    assert len(list_notices()) == 1


def test_scheduler_does_not_repeat_an_unchanged_finding(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TRILLION_NOTES_DIR", str(tmp_path / "notes"))
    (tmp_path / "notes").mkdir()
    note_path = tmp_path / "notes" / "note.md"
    note_path.write_text("URGENT: renew passport\n")

    config = HeartbeatConfig(
        poll_interval_seconds=1,
        quiet_hours=QuietHours(start=dt_time(22, 0), end=dt_time(7, 0)),
        checks=[CheckConfig(name="notes_watch", interval_seconds=1, params={"query": "URGENT"})],
    )
    scheduler = Scheduler(config)
    scheduler.tick(now=datetime(2026, 1, 1, 12, 0, 0))
    scheduler.tick(now=datetime(2026, 1, 1, 12, 0, 2))
    scheduler.tick(now=datetime(2026, 1, 1, 12, 0, 4))
    assert len(list_notices()) == 1  # still unresolved, but not re-notified

    # the condition changes (new distinct text) -> a new notice does appear
    note_path.write_text("URGENT: renew passport AND visa\n")
    scheduler.tick(now=datetime(2026, 1, 1, 12, 0, 6))
    assert len(list_notices()) == 2

    # and once resolved, a later recurrence notifies again too
    note_path.write_text("nothing relevant\n")
    scheduler.tick(now=datetime(2026, 1, 1, 12, 0, 8))
    note_path.write_text("URGENT: renew passport\n")
    scheduler.tick(now=datetime(2026, 1, 1, 12, 0, 10))
    assert len(list_notices()) == 3


def test_scheduler_survives_a_bad_check_without_crashing(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))

    from trillion.heartbeat import checks as checks_module

    def boom(params):
        raise RuntimeError("check exploded")

    monkeypatch.setitem(checks_module.CHECKS, "boom_check", boom)

    config = HeartbeatConfig(
        poll_interval_seconds=1,
        quiet_hours=QuietHours(start=dt_time(22, 0), end=dt_time(7, 0)),
        checks=[
            CheckConfig(name="boom_check", interval_seconds=1, params={}),
            CheckConfig(name="open_reminders_digest", interval_seconds=1, params={}),
        ],
    )
    scheduler = Scheduler(config)
    add_reminder({"text": "buy milk"})
    scheduler.tick(now=datetime(2026, 1, 1, 12, 0))

    # the bad check's failure didn't stop the good one from running
    assert len(list_notices()) == 1
    assert "check exploded" in capsys.readouterr().out


def test_scheduler_ignores_unknown_check_names_in_config(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))
    config = HeartbeatConfig(
        poll_interval_seconds=1,
        quiet_hours=QuietHours(start=dt_time(22, 0), end=dt_time(7, 0)),
        checks=[CheckConfig(name="does_not_exist", interval_seconds=1, params={})],
    )
    scheduler = Scheduler(config)
    scheduler.tick(now=datetime(2026, 1, 1, 12, 0))  # must not raise
    assert list_notices() == []
