# Trillion

The core of a voice-first AI assistant, built tier by tier. See
[`AGENT.md`](./AGENT.md) for the full spec and the decisions behind it.

## Status

Tier 1 (text conversation loop) is implemented. See `AGENT.md` for the
full tier roadmap and what's next.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # then fill in ANTHROPIC_API_KEY
```

## Run (Tier 1: text)

```bash
python -m trillion.main
```

Type a message and press enter; `/exit` or `/quit` to leave. The
conversation is remembered for the session but not across restarts yet
(that's Tier 4).

## Tests

```bash
pytest
```
