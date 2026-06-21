# CLAUDE.md — project context for Claude Code

Read this first. It's the handoff from the build session.

## What this is
**ReferralGuard** — a multi-agent pre-flight check for specialty referrals & prior-auth requests,
built for the UC Berkeley AI Hackathon 2026. It reads an incoming referral, extracts fields, flags
what's missing or likely to be denied (with a stated reason per flag), and shows a timestamped,
replayable **audit trail** (the centerpiece). Verdicts: `READY TO SUBMIT` / `NEEDS INFO` / `HIGH DENIAL RISK`.

Repo: https://github.com/nobuiz/hackathon2026 (branch `main`).

## How to run
```bash
cd backend
source .venv/bin/activate                 # IMPORTANT: prompt must show (.venv)
uvicorn server:app --port 8000            # backend API
# dashboard: open ../dashboard/index.html in a browser (auto-detects the backend)
python selftest.py                        # end-to-end check: /health + 5 samples + voice
```
Everything runs in mock mode with no keys; each key in `backend/.env` flips one engine to live.
`GET /health` shows which engines are live.

## Current status (live engines)
As of handoff: **claude ✅, redis ✅, deepgram ✅, phoenix ✅, browserbase ✅, orkes ✅** — and
**sentry ⚠️ pending**. All 5 samples pass; Deepgram confirmed transcribing real audio.

### Immediate next task: finish Sentry
DSN is correct in `backend/.env` (single valid line). The blocker was that `sentry-sdk` wasn't
importable in the Python running the server (venv not active). Fix:
```bash
cd backend && source .venv/bin/activate
python -c "import sentry_sdk; print(sentry_sdk.VERSION)"   # if ModuleNotFoundError:
pip install sentry-sdk==2.20.0
uvicorn server:app --port 8000             # restart INSIDE the venv
curl -s http://localhost:8000/health       # expect "sentry":true
```
Then trigger the captured-error path (the **MRI right knee** sample / bad member ID) and confirm a
`MemberIdFormatError` event appears in the Sentry dashboard — screenshot for judging.

## Architecture / file map
- `backend/server.py` — FastAPI: `/health`, `/process`, `/intake/voice`, `/chat`
- `backend/agent_pipeline.py` — agent pipeline (Claude extraction + denial-risk, rules, Redis state, Sentry capture, approval gate + submission for READY) **+ grounded case chat (`claude_chat`) + context compression (`compress_context`) for the Token Company challenge**
- `backend/submission_agent.py` — Browserbase payer-portal submission (READY only)
- `backend/intake_voice.py` — Deepgram voice intake (SDK v3 REST: `listen.rest.v("1")`)
- `backend/observability.py` — Arize Phoenix OTEL spans + `traces.jsonl` (BatchSpanProcessor; silent if Phoenix down)
- `backend/fetch_agent.py` — Fetch.ai uAgent (ASI:One Chat Protocol) — its own challenge
- `backend/clinic_agent.py` — 2nd uAgent (agent-to-agent demo); `backend/asi_client.py` — ASI:One LLM
- `backend/selftest.py` — end-to-end test
- `dashboard/index.html` — **primary doctor-facing UI**: live trace, voice intake, grounded chat, prior-auth form (PDF), ROI panel, token-compression meter (mirrors the pipeline; works offline)
- `dashboard/console.html` — legacy 3-pane ops console (was `index.html`)
- `assets/call.wav` — sample phone referral; `/intake/voice` defaults to it for real Deepgram
- `orchestration/` — Orkes Conductor workflow (+ HUMAN approval gate) and workers
- `samples/` — 5 referral JSONs (expected verdicts in `selftest.py`)
- `docs/` — `README.md` (at root), plus `GO_LIVE.md`, `TEAM_RUNBOOK.md`, `FETCH_AI.md`, `DEVPOST.md`, `SPONSOR_TALKING_POINTS.md`, `one-pager.html`

## Conventions / gotchas
- **Never commit `backend/.env`** (gitignored). Keys are private.
- The frontend pipeline in `dashboard/index.html` mirrors `agent_pipeline.py` — keep them in sync.
- Denial-risk uses **negation-aware** matching (e.g. "no methotrexate" must NOT count as documented).
- The dashboard talks to `http://localhost:8000`; the chip flips to "live" when the backend is up.
- `arize-phoenix` pulls in a `strawberry` that breaks sentry's auto Strawberry integration → it's disabled in `agent_pipeline.py` sentry init. Keep that.
- Commit author email for pushes: `meetp06@users.noreply.github.com` (GitHub email-privacy block).

## What's left (nice-to-have)
- Finish Sentry (above). Optionally make `/intake/voice` extract fields from the transcript so spoken
  content drives the verdict (currently uses a fixed scenario + transcript as `raw`).
- Register the Fetch.ai agent on Agentverse and capture the ASI:One shared-chat URL (see FETCH_AI.md).
- Fill team name + table number in `DEVPOST.md`; export `one-pager.html` to PDF.
