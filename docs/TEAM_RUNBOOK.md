# ReferralGuard — Team Runbook (4 people)

Goal: take the project from "runs in mock mode" to **fully live, end-to-end**, ready for 1–3pm Sunday judging.
Each person owns one part. Do **Shared setup** first (everyone), then your section, then the **Integration checklist** together.

Repo: https://github.com/nobuiz/hackathon2026
The app already runs with **zero keys** (mock mode). "Going live" = adding each API key and verifying that engine flips on in `GET /health`.

---

## Shared setup (everyone, 10 min)

```bash
git clone https://github.com/nobuiz/hackathon2026.git
cd hackathon2026/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn server:app --port 8000   # then open ../dashboard/index.html in a browser
```

- Health check: open http://localhost:8000/health — every engine shows `false` until its key is added.
- Branch discipline: each person works on a branch (`git checkout -b yourname-section`), opens a PR, Person D merges.
- Put **all** keys in `backend/.env` (never commit it — it's gitignored). Share keys via Slack DM, not the repo.

---

## Part 1 — Core reasoning: Claude + Redis  (owner: ______)

**You make the agent actually think and remember.**

1. **Claude (Anthropic):** get an API key at https://console.anthropic.com → API Keys.
   - In `.env`: `ANTHROPIC_API_KEY=sk-ant-...`
   - Verify: restart server, `GET /health` shows `"claude": true`. POST a sample to `/process` and confirm the Extraction + Denial-Risk steps now say "Claude (live)".
2. **Redis:** run locally (`brew install redis && redis-server`) or use a free Redis Cloud instance.
   - In `.env`: `REDIS_URL=redis://localhost:6379/0`
   - Verify: `"redis": true` in `/health`; after a run, `redis-cli KEYS 'sess:*'` shows session keys.
3. **Tune the reasoning:** review the prompts in `backend/agent_pipeline.py` (`EXTRACT_PROMPT`, `RISK_PROMPT`) and the `PAYER_RULES`. Add 1–2 more real payer rules if time allows.
4. **Files you own:** `backend/agent_pipeline.py`.

**Done when:** a live Claude call extracts fields and predicts denial risk on all 5 samples, with Redis holding session state.

---

## Part 2 — Action layer: Browserbase + Orkes  (owner: ______)

**You make it submit to a portal and add the human approval gate. This is the most on-thesis part.**

1. **Browserbase:** sign up at https://browserbase.com → get API key + Project ID.
   - In `.env`: `BROWSERBASE_API_KEY=...`, `BROWSERBASE_PROJECT_ID=...`
   - Stand up a target form to submit against (no real payer portal exists): make a simple HTML form (or a free Tally/Google Form) and set `PAYER_PORTAL_URL=` to it.
   - Install the live driver: `pip install playwright && playwright install chromium`, then uncomment `playwright` in `requirements.txt`.
   - Verify: process the **Cardiology** sample (the READY one) → the Submission Agent steps show a real page title and return a confirmation. `"browserbase": true` in `/health`.
2. **Orkes Conductor:** create a free cluster at https://orkes.io → Conductor → get `CONDUCTOR_SERVER_URL` + key/secret.
   - In `.env`: `CONDUCTOR_SERVER_URL=...`, `CONDUCTOR_AUTH_KEY=...`, `CONDUCTOR_AUTH_SECRET=...`
   - Import `orchestration/referralguard_workflow.json` in the Conductor UI; run `python orchestration/worker.py` (after `pip install conductor-python`).
   - Verify: the HUMAN approval task appears in the Conductor inbox and pauses the workflow until approved.
3. **Fetch.ai / ASI:One agent (its own prize — read `FETCH_AI.md`):**
   - `pip install uagents requests`; set `ASI_ONE_API_KEY` (from https://asi1.ai) and `FETCH_AGENT_SEED` in `.env`.
   - `python backend/fetch_agent.py` → copy the printed **agent address** into `README.md` + `FETCH_AI.md`.
   - On https://agentverse.ai add it as a **Mailbox** agent, paste the README (keep the `innovationlab` + `hackathon` badges) → it becomes discoverable in ASI:One.
   - Test in ASI:One with the example prompts in `FETCH_AI.md`; capture the **shared-chat URL** and **agent profile URL** for Devpost.
   - Optional bonus: run `python backend/clinic_agent.py` for the agent-to-agent demo.
4. **Files you own:** `backend/submission_agent.py`, `backend/fetch_agent.py`, `backend/clinic_agent.py`, `backend/asi_client.py`, `orchestration/`, `FETCH_AI.md`.

**Done when:** a READY request triggers a real browser submission with a confirmation number, the human-approval gate is visible in Orkes, and the uAgent answers an agent-to-agent referral.

---

## Part 3 — Observability + voice: Sentry + Phoenix + Deepgram  (owner: ______)

**You make it production-grade and demo the voice intake. Sentry is a prize (Switch 2 + interview).**

1. **Sentry:** create a project at https://sentry.io → get the DSN.
   - In `.env`: `SENTRY_DSN=https://...@...ingest.sentry.io/...`
   - Verify: process the **MRI right knee** sample (bad member ID) → a `MemberIdFormatError` event appears in your Sentry dashboard with breadcrumbs + tags. `"sentry": true` in `/health`. **Screenshot this for judging.**
2. **Arize Phoenix:** run it locally — `pip install arize-phoenix && phoenix serve` (UI at http://localhost:6006).
   - In `.env`: `PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006`
   - Uncomment the two phoenix/otel lines in `requirements.txt` and `pip install -r requirements.txt`.
   - Verify: process a few requests → spans appear in the Phoenix UI. `"phoenix": true` in `/health`.
3. **Deepgram:** get a key at https://console.deepgram.com.
   - In `.env`: `DEEPGRAM_API_KEY=...`
   - Record a 20-sec phone-style referral as a `.wav`, then `POST /intake/voice` with `{"audio_path": "/abs/path/call.wav"}` → confirm it transcribes and runs the pipeline. `"deepgram": true` in `/health`.
4. **Files you own:** `backend/observability.py`, `backend/intake_voice.py`.

**Done when:** Sentry shows a captured agent exception, Phoenix shows live traces, and a real audio file flows through the voice endpoint.

---

## Part 4 — Demo, pitch & submission  (owner: ______)

**You own the thing judges actually see. Also the integration glue.**

1. **Demo polish:** make sure `dashboard/index.html` flips to "live" when the backend is up (header chip). Practice the <30s run on all 5 samples. Pick the 2 best samples for the live demo (suggest: Cardiology = full happy path incl. Browserbase submit; MRI knee = Sentry capture).
2. **Devpost:** open `DEVPOST.md`, fill in **team name** + **table number**, paste the elevator pitch + description into the Devpost form. **Submit the draft before 11am Sunday** (you can edit until 12pm).
3. **One-pager / SkyDeck:** open `one-pager.html` in a browser → Print → Save as PDF. Use for the SkyDeck incubator prize and as the table handout.
4. **Sponsor booths:** `SPONSOR_TALKING_POINTS.md` — assign one booth per teammate (Browserbase, Orkes, Phoenix, Anthropic, Sentry, Deepgram). These are recruiting conversations.
5. **Integration owner:** merge everyone's PRs, keep one shared `.env` working, and run the full **checklist** below before judging.

**Done when:** Devpost submitted, one-pager PDF ready, everyone has booth talking points, and the integrated build passes the checklist.

---

## Integration checklist (all together, before judging)

- [ ] `GET /health` returns `true` for: claude, redis, sentry, deepgram, phoenix, browserbase, orkes
- [ ] All 5 samples produce correct verdicts (READY / NEEDS INFO / HIGH DENIAL RISK)
- [ ] READY request → Orkes approval gate → Browserbase submit → confirmation number shown
- [ ] Bad-member-ID sample → exception visible in Sentry dashboard (screenshot saved)
- [ ] Voice endpoint transcribes a real audio file and runs the pipeline
- [ ] Phoenix shows the decision-trace spans
- [ ] Dashboard runs the full trace in under 30 seconds, "live" chip shown
- [ ] Devpost draft submitted (team name + table number filled)
- [ ] one-pager PDF exported; talking points assigned
- [ ] Final commit pushed to main; no `.env` committed

## Quick owner map

| Part | Sponsors | Prize angle |
|---|---|---|
| 1 | Claude, Redis | core functionality |
| 2 | Browserbase, Orkes, Fetch.ai | most on-thesis; durable + compliant; agent-to-agent |
| 3 | Sentry, Phoenix, Deepgram | Best Use of Sentry API; recruiting |
| 4 | demo + Devpost + one-pager | Best UI/UX; SkyDeck incubator |
