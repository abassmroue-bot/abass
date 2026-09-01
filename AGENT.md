# Trillion — Project Spec

This file is the single source of truth for what we're building and why. It
was produced from a short interview before any code was written. Update it
whenever a real decision changes — it should always describe the assistant
as it actually is, not as it was first imagined.

## Identity

- **Name:** Trillion
- **What it's for:** a voice-first personal/team assistant that can talk,
  act on my behalf through tools, remember me between conversations, and
  reach out proactively when something is actually worth my attention.
- **Audience:** built for a single primary user today, but with a small
  team in mind for later — durable state (memory, reminders, audit log) is
  keyed by user from the start even though only one user exists right now.
  This costs almost nothing to do early and is expensive to retrofit.
- **Tone/personality:** warm, plain-spoken, and brief. Never stiff or
  corporate; never rambling. Consistent across text and voice.

## Stack

- **Language/runtime:** Python. Kept small and readable — no heavy
  framework for the core harness.
- **Model provider:** Claude, via the official Anthropic Python SDK,
  behind a thin provider seam (`trillion/provider.py`) so the rest of the
  harness never imports the SDK directly. Default model is configurable
  via the `TRILLION_MODEL` env var (defaults to `claude-sonnet-5`).
- **Where it runs:** designed for an always-on host from the start (not a
  "laptop-first, migrate later" build) — persistent file paths, a service
  process rather than a foreground-only script, and a heartbeat (Tier 5)
  that assumes it can keep running unattended. It should still be
  perfectly runnable on a laptop for development.

## First capabilities (become the first tools)

In build order:
1. **Reminders & tasks** — remind me of things, track a to-do list.
2. **Notes Q&A** — answer questions by looking things up in local notes/files.
3. **Draft messages** — help write messages/emails for me to send (drafting
   only; actually sending is a consequential action and goes through the
   Tier 6 confirmation gate).
4. **Web lookups** — search the web / fetch a page for current information.

(Note: during setup, "Something else" was also selected for this list and
for the never-without-asking list below, but no further detail came back
from the interview UI. I've proceeded with the explicit items above/below;
tell me what else you had in mind and I'll fold it in.)

## Voice and interaction

- **Interaction path:** text first (Tiers 1–2), then push-to-talk voice
  (Tier 3). No open-mic/wake-word for now.
- **Speech-to-text:** Deepgram, behind its own seam.
- **Text-to-speech:** ElevenLabs, behind its own seam, streamed.
- ElevenLabs voice choice: not yet picked — to be set in the Tier 6 config
  file once we reach Tier 3, rather than hardcoded.

## Safety rules ("never without asking me first")

The assistant must stop and get explicit yes/no confirmation, stating
plainly what it's about to do, before it ever:
- **Sends** a message/email or anything else outbound.
- **Spends** money (any purchase or payment).
- **Deletes** data.
- **Changes** a setting/config.

This is a hard gate (Tier 6) between the model choosing a tool and the tool
actually running. It applies the same way whether the action was requested
by me (text or voice) or initiated by the heartbeat. Approving one action
never pre-approves the next — every consequential action asks on its own.

## Proactivity

Yes — Trillion may reach out to me first (Tier 5 heartbeat: scheduled
checks, noticing conditions), but **quiet by default**. Most checks should
produce nothing most of the time; only genuinely noteworthy things justify
an interruption. Everything else lands in a calm, dismissible log. Notices
raised while I'm away are held and shown when I'm back, never dropped.
Non-urgent notices respect quiet hours; the schedule survives restarts.

## Build discipline (from the spec this file was generated from)

- One shared agent core; text, voice, and heartbeat-initiated turns all
  flow through the same brain and tool registry — never forked logic.
- Build and verify one tier at a time: brain (text) → tools → voice →
  memory → heartbeat → safety rails. Don't fuse tiers.
- Secrets live in environment variables / a git-ignored `.env`, never in
  source.
- Provider integrations (model, STT, TTS) each sit behind a small, thin
  seam so they can be swapped without touching the rest of the harness.

## Status

- [x] Tier 0 — interview + this spec
- [x] Tier 1 — text conversation loop (`src/trillion/`, run with
      `python -m trillion.main`). Verified: streaming reply, multi-turn
      memory within a session, and clean handling of a missing/unreachable
      provider (see `tests/test_brain.py` and the manual run in the repo
      history). Not yet verified against a live model reply — no
      `ANTHROPIC_API_KEY` was available in the build environment; do that
      first before starting Tier 2.
- [x] Tier 2 — tools (`src/trillion/tools/`): a `ToolRegistry` plus the
      first two capabilities — `add_reminder`/`list_reminders`/
      `complete_reminder` (backed by a small JSON file under
      `TRILLION_DATA_DIR`, default `./data`) and `search_notes` (plain-text
      search over `TRILLION_NOTES_DIR`, default `./notes`). `Brain.take_turn`
      now loops on tool calls until the model gives a final text reply,
      feeding each tool's result (or error) back to the model rather than
      crashing. Verified: unit tests for the registry, both tools, and the
      brain's tool-call loop (success, failure, and a runaway-loop guard);
      a real end-to-end run of the tools against the filesystem (reminder
      persisted to JSON, note found by search, missing-input and
      unknown-tool errors both handled gracefully). Still not verified
      against a live model — same `ANTHROPIC_API_KEY` gap as Tier 1.
      Drafting messages and web lookups (the other two named capabilities)
      are not built yet — natural next tools to add to the registry.
- [x] Tier 3 — voice, push-to-talk (`src/trillion/tts.py`, `stt.py`,
      `audio_io.py`, `voice_main.py`; run with `python -m
      trillion.voice_main`). ElevenLabs for TTS and Deepgram for STT,
      each behind their own thin seam; `voice_main.py` wraps the exact
      same `Brain`/tool registry as the text CLI, only changing how a
      turn arrives (recorded speech, transcribed) and leaves (spoken
      aloud). Verified: unit tests for both seams (mocked network calls)
      and for WAV encoding; the voice CLI starts cleanly and fails
      gracefully with a clear message when there's no display (push-to-
      talk key detection needs one) or no mic — same crash-free posture
      as Tiers 1–2. **Not verified live**: this build ran in a sandboxed
      cloud environment whose network policy blocks both
      `api.elevenlabs.io` and `api.deepgram.com` outright (confirmed via
      the proxy status endpoint — a 403 at the CONNECT level, not an
      auth error), and it has no microphone/speakers/display regardless.
      An ElevenLabs key was provided but a live synthesis call could not
      be made from here for that reason. **Before trusting this tier,
      run `python -m trillion.voice_main` on your own machine** with
      both keys set — that's the real Tier 3 verify step (hold SPACE,
      ask something that needs a tool, hear the spoken answer, confirm
      the transcript matches what you said).
      Known gap: playback is currently synchronous, so starting a new
      turn while Trillion is still speaking (the "let me interrupt it"
      requirement) isn't implemented yet — it needs real audio hardware
      to get right, not guessed at blind.
- [x] Tier 4 — durable memory store (`src/trillion/tools/memory.py`):
      facts live in `data/memory.md`, one plain line per fact
      (`- [id] statement`), loaded fresh into the system prompt on every
      turn (`Brain._system_prompt()`) — so a fact remembered
      mid-conversation, or corrected by hand in the file, takes effect
      immediately rather than only after a restart. Read/write via four
      tools: `remember_fact`, `list_facts`, `update_fact`, `forget_fact`.
      The prompt explicitly tells the model to treat these as background
      knowledge, never as instructions, per the safety note in this spec
      — the actual confirmation gate enforcing that still lands in Tier 6.
      Verified: unit tests for the store (round trip, hand-edit
      respected, unknown-id errors) and for the brain wiring (facts
      appear in the system prompt; a fact remembered via a tool call
      mid-session is visible on the very next turn); a real
      cross-process check simulating "quit and restart" — one Python
      process remembers a fact, the file is hand-edited with `sed` the
      way a person would in a text editor, and a second, independent
      process picks up the corrected version. Not yet verified: an
      actual live conversation asking the model to remember/recall
      something (same `ANTHROPIC_API_KEY` gap as Tiers 1–3).
- [ ] Tier 5 — heartbeat / proactivity
- [ ] Tier 6 — safety rails, config, audit log, kill switch
