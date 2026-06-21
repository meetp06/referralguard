# GO LIVE — turn on every engine, one at a time

Work top to bottom. Each engine = **get key → paste in `backend/.env` → restart server → verify**.
Order is easiest-and-highest-impact first. You can stop at any point; the demo works at every stage.

> The pattern for **all** of them:
> 1. paste the key into `~/Downloads/calhack/backend/.env`
> 2. restart the server (Ctrl+C in the server tab, then `uvicorn server:app --port 8000`)
> 3. verify: `curl -s http://localhost:8000/health` → that engine shows `true`

Reload the dashboard after a restart so it re-checks the backend.

---

## 0. Already done ✅
- **Claude** — `ANTHROPIC_API_KEY` set. Extraction + denial-risk are live.

## 1. Sentry  (prize target — do this next)
- Key: https://sentry.io → create a **Python/FastAPI** project → copy the **DSN**.
- `.env`: `SENTRY_DSN=https://...ingest.sentry.io/...`
- Verify: `"sentry":true` in `/health`. Then in the dashboard run the **MRI right knee** sample → a `MemberIdFormatError` event appears in your Sentry dashboard. **Screenshot it for judging.**

## 2. Redis  (real session state)
- Install + run locally: `brew install redis && redis-server` (leave it running in its own tab).
- `.env`: `REDIS_URL=redis://localhost:6379/0`
- Verify: `"redis":true` in `/health`. After a run: `redis-cli KEYS 'sess:*'` lists sessions.

## 3. Browserbase  (live payer-portal submission — most impressive)
- Keys: https://browserbase.com → API key + Project ID.
- Make a target form to submit to (no real payer portal exists): a Google Form / Tally form, or any page. Copy its URL.
- `.env`:
  ```
  BROWSERBASE_API_KEY=...
  BROWSERBASE_PROJECT_ID=...
  PAYER_PORTAL_URL=https://your-form-url
  ```
- Install the driver: `pip install playwright && playwright install chromium`, then in `requirements.txt` uncomment the `playwright` line.
- Verify: `"browserbase":true` in `/health`. Run the **Cardiology** sample (READY) → Submission Agent shows a real page title + confirmation number.

## 4. Deepgram  (voice intake)
- Key: https://console.deepgram.com → API key.
- `.env`: `DEEPGRAM_API_KEY=...`
- Verify: `"deepgram":true`. Record a short `.wav` referral, then:
  ```
  curl -s -X POST http://localhost:8000/intake/voice -H "Content-Type: application/json" \
    -d '{"audio_path":"/absolute/path/to/call.wav"}'
  ```
  → returns a transcript + verdict.

## 5. Arize Phoenix  (agent tracing)
- Run it locally: `pip install arize-phoenix && phoenix serve` (UI at http://localhost:6006). Leave it running.
- In `requirements.txt` uncomment the two `phoenix`/`opentelemetry` lines, then `pip install -r requirements.txt`.
- `.env`: `PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006`
- Verify: `"phoenix":true`. Process a few requests → spans appear in the Phoenix UI.

## 6. Fetch.ai / ASI:One  (separate prize — see FETCH_AI.md)
- `pip install uagents`
- Key: https://asi1.ai → `ASI_ONE_API_KEY` in `.env` (improves extraction).
- Run the agent (its own process, not uvicorn): `python fetch_agent.py` → copy the printed **agent address** into `README.md` + `FETCH_AI.md`.
- Register it as a **Mailbox** agent on https://agentverse.ai so ASI:One can discover it.
- Test in ASI:One with the example prompts in `FETCH_AI.md`; save the **shared-chat URL** + **agent profile URL** for Devpost.
- Agent-to-agent bonus: second tab → `export REFERRALGUARD_AGENT_ADDRESS=agent1q...` then `python clinic_agent.py`.

## 7. Orkes Conductor  (orchestration + human gate)
- Free cluster: https://orkes.io → Conductor → `CONDUCTOR_SERVER_URL` + auth key/secret in `.env`.
- `pip install conductor-python`, import `orchestration/referralguard_workflow.json` in the Conductor UI, run `python orchestration/worker.py`.
- Verify: `"orkes":true`. The HUMAN approval task appears in the Conductor inbox and pauses the workflow until approved.

---

## Final "everything live" check
```bash
curl -s http://localhost:8000/health
```
All of these `true`: `claude, sentry, redis, browserbase, deepgram, phoenix, orkes`.
(Fetch.ai runs as its own agent process — confirm it via Agentverse/ASI:One, not /health.)

## Cost note
Claude, Browserbase, Deepgram, ASI:One may need a small billing/credit on the account.
Sentry, Redis (local), Phoenix (local), Orkes (free tier) cost nothing to start.
Keep `.env` private — it's gitignored; never commit it.
