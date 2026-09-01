# Trillion

The core of a voice-first AI assistant, built tier by tier. See
[`AGENT.md`](./AGENT.md) for the full spec and the decisions behind it.

## Status

The full baseline (Tiers 1–6) is implemented: text brain, tools,
push-to-talk voice, durable memory, the proactive heartbeat, and the
safety rails. See `AGENT.md` for the full tier roadmap, what's verified,
and what's next.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # then fill in ANTHROPIC_API_KEY
```

## Run (Tier 1/2: text)

```bash
python -m trillion.main
```

Type a message and press enter; `/exit` or `/quit` to leave. The
conversation is remembered for the session but not across restarts yet
(that's Tier 4).

## Run (Tier 3: voice, push-to-talk)

```bash
python -m trillion.voice_main
```

Needs `ELEVENLABS_API_KEY` and `DEEPGRAM_API_KEY` in `.env`, a
microphone, and a graphical session (the keyboard-hold detection needs
one). Press enter, then hold SPACE and speak; release to send. The
transcript is printed next to the reply so you can tell the ears and the
brain apart while debugging.

## Memory (Tier 4)

Durable facts about you live in `data/memory.md` (created on first use;
git-ignored) — one plain line per fact, e.g. `- [ab12cd34] Prefers
morning meetings.` Open it in any text editor to review, fix, or delete
a fact by hand; Trillion re-reads it every turn, so an edit takes effect
immediately, no restart needed. It's also updated through conversation
via the `remember_fact`, `list_facts`, `update_fact`, and `forget_fact`
tools ("remember that I prefer morning meetings").

## Heartbeat (Tier 5)

```bash
python -m trillion.heartbeat_main
```

Runs independently of the CLIs — leave it running (e.g. as a systemd
service later) whether or not a conversation is open. What to check, how
often, and quiet hours all live in `config.yaml`, not in code. Two
checks ship by default:

- `notes_watch` — surfaces an interruption if a configured phrase (default
  `URGENT`) shows up in your notes. Good for exercising the heartbeat end
  to end: add a matching line to a note and watch it get noticed.
- `open_reminders_digest` — a quiet, log-only summary of open reminders;
  produces nothing when there's nothing open.

Anything surfaced is held until you're back — both CLIs print what's
pending at startup — and stays in the inbox until dismissed, via the
`list_notices`/`dismiss_notice` tools ("what's pending?" / "dismiss
that"). Non-urgent notices wait out quiet hours; nothing is ever fired
and forgotten.

## Safety rails (Tier 6)

- **Confirmation gate.** A tool marked `requires_confirmation=True` (or
  listed under `tools.require_confirmation` in `config.yaml`) never runs
  silently — the harness states plainly what it's about to do and waits
  for an explicit yes, on every conversation surface (text, voice, and
  any future heartbeat-initiated action). No `confirm` callback wired up
  at all (e.g. in tests) means it defaults to declined, never to allowed.
  `forget_fact` is gated this way today, since deleting a memory is on
  the "never without asking" list in `AGENT.md`.
- **Config over hardcoded values.** `config.yaml`'s `model.name` and
  `tools.require_confirmation` join the heartbeat settings already there
  — tunable without a code change. `TRILLION_MODEL` still overrides the
  model name if set. Config can only *widen* the confirmation gate, never
  narrow it below what a tool's own code already requires.
- **Audit trail.** Every tool call and every confirmation decision is
  appended to `data/audit.log` (one JSON object per line) — what ran,
  what was asked, what was granted or declined, and when. `data/usage.json`
  keeps a running token-usage tally so a runaway loop is visible early.
- **Kill switch.** `python -m trillion.kill_switch pause "reason"` stops
  all heartbeat activity immediately without touching anything else —
  the conversation still works normally. `... resume` re-enables it,
  `... status` checks it.
- **Data, not instructions.** The system prompt tells the model that
  anything a tool returns (notes, search results, anything read from
  outside the conversation) is data to observe, never a command to obey.

## Tests

```bash
pytest
```
