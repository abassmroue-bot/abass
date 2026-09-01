# Trillion

The core of a voice-first AI assistant, built tier by tier. See
[`AGENT.md`](./AGENT.md) for the full spec and the decisions behind it.

## Status

Tiers 1–4 are implemented (text brain, tools, push-to-talk voice, durable
memory). See `AGENT.md` for the full tier roadmap, what's verified, and
what's next.

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

## Tests

```bash
pytest
```
