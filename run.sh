#!/usr/bin/env bash
# One-command launcher: sets up Trillion on first run, then starts it.
#
# Usage:
#   ./run.sh            # text chat (default)
#   ./run.sh voice      # push-to-talk voice
#   ./run.sh heartbeat  # the background proactive loop
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -d .venv ]; then
    echo "First run: creating a virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -e ".[dev]"

if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "Created .env from .env.example -- add your ANTHROPIC_API_KEY, then run this again."
    echo "(Get one at https://console.anthropic.com)"
    exit 1
fi

MODE="${1:-text}"
case "$MODE" in
    text)      exec python -m trillion.main ;;
    voice)     exec python -m trillion.voice_main ;;
    heartbeat) exec python -m trillion.heartbeat_main ;;
    *)
        echo "Usage: ./run.sh [text|voice|heartbeat]  (default: text)"
        exit 1
        ;;
esac
