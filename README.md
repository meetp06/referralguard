# ReferralGuard

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

**A multi-agent pre-flight check for specialty referrals & prior authorizations — plain-language for any doctor, with a watchable, timestamped audit trail underneath.**

UC Berkeley AI Hackathon 2026.

> **Try it:** open [`dashboard/index.html`](dashboard/index.html) in any browser — runs standalone, flips to **live** when the backend is up.
>
> **Fetch.ai / ASI:One:** ReferralGuard is also a live **ASI:One-discoverable uAgent** — describe a referral in plain English in ASI:One chat and get the verdict back, no UI. Agent: `referralguard` · address `agent1qgq4la65vzumw4ec469vk5zdaqycnxfhuxx669r7p2umzf887cylc2egetv`. See [Fetch.ai / ASI:One](#fetchai--asione--a-discoverable-referral-agent).

---

## The problem

Specialty clinics lose patients and revenue because referrals and prior-auth (PA)
requests get stuck in manual, fax-and-phone paperwork. The 2025 AMA Prior Authorization
Physician Survey found physicians complete **~40 prior authorizations per week**, spend
**~13 hours/week** on them, and **94% say PA contributes to burnout** — and roughly **half of
specialty referrals are never completed**. Most of that pain is avoidable: requests get
denied or returned for missing fields, missing step-therapy documentation, or unreadable
insurance info — all knowable *before* submission.

## What ReferralGuard does

Drop in a referral (file, sample, or a **spoken** phone call) and, in real time:

1. **Reads & extracts** key fields — patient, diagnosis (ICD-10), procedure (CPT/HCPCS), insurance.
2. **Flags** what's missing or likely to be denied, **with a stated reason for each flag**.
3. **Streams a live, plain-English trace** of what each agent checked and why — replayable in seconds.
4. **Gives a verdict + what to do next:** `READY TO SUBMIT` · `NEEDS INFO` · `HIGH DENIAL RISK`.

Then the doctor can:

- 💬 **Ask the case chatbot** anything — grounded *only* in this referral (won't invent facts).
- 📄 **Prepare a prior-auth form** — auto-filled from the case, blanks highlighted, **download as PDF**.
- 📈 See the **ROI** — time + denial cost saved per referral, per day, per month.

---

## Demo in 30 seconds

1. Open **`dashboard/index.html`** in any browser (no build, no server required).
2. **Drop a referral**, pick a **sample case**, or hit **🎙 Speak a referral** (Deepgram).
3. Watch the agents work live → read the verdict, issues, and what to fix.
4. Ask the **case chatbot**, or **Take this case → prepare prior-auth form** → **Download PDF**.

The dashboard runs **fully standalone** (deterministic in-browser pipeline). With the backend on
`localhost:8000`, it switches to live mode and calls the real agents.

### Run the live backend

```bash
./run.sh
# or:
cd backend
pip install -r requirements.txt
cp .env.example .env      # add API keys (all optional)
uvicorn server:app --port 8000
python selftest.py        # end-to-end: /health + 5 samples + voice
```

Reload the dashboard — the connection chip flips to **live** and the header shows which engines are on.

---

## Architecture

```
                ┌────────────────────────────────────────────────────────┐
  referral  →   │  Intake → Extraction → Completeness → Validation →      │
 (file / EHR /  │          Denial-Risk → Decision → Approval → Submit     │  → verdict + audit trail
  phone voice)  └────────────────────────────────────────────────────────┘
                     every step writes a timestamped span to the audit log
```

| Agent | Does | Engine |
|---|---|---|
| **Intake** | Opens a session, caches raw payload (file / EHR / **voice**) | Redis (+ Deepgram for voice) |
| **Extraction** | Parses raw/voice text → typed fields | Claude |
| **Completeness** | Checks the 7 required fields | rules |
| **Validation** | Validates member-ID format; bad input raises a captured exception | Redis + Sentry |
| **Denial-Risk** | Reasons over payer policy (step therapy, conservative-care) to predict denials | Claude |
| **Decision** | Combines flags into a final verdict; persists the full trace | rules |
| **Approval Gate** | *(READY only)* pauses for human sign-off — prior auth legally requires it | Orkes (HUMAN task) |
| **Submission** | *(READY only)* hosted browser logs into the payer portal, submits, returns a confirmation | Browserbase |

State flows between steps via Redis; every step is logged as a span (Phoenix + `traces.jsonl`).
NEEDS INFO / HIGH DENIAL RISK requests skip submission and route to human review.

---

## Context compression — The Token Company challenge

The **case chatbot** would otherwise resend a bloated context every turn (referral + full note +
all flags + every audit step + history). Before each LLM call, `compress_context()` shrinks it:

- **Drops the verbose audit trail** (biggest waste for Q&A)
- **Extractive note summarization** — keeps only high-signal sentences (clinical terms, case
  keywords, and **negations** — negations drive denial logic)
- **Removes null fields, abbreviates keys, windows chat history** to the last 8 turns
- **Claude guard/verifier** confirms every decision-critical field (Dx, CPT, payer, verdict)
  survived compression and **restores it if not** — no silent quality loss

Token counts use the **model's real tokenizer** (`messages.count_tokens`). The chat panel shows the
live ratio: *"45–65% context compressed · 283 → 156 tokens · N saved this session."*
→ `compress_context()` in `backend/agent_pipeline.py`.

---

## Fetch.ai / ASI:One — a discoverable referral agent

Beyond the dashboard, ReferralGuard runs as a **uAgent on the ASI:One Chat Protocol** — so a
clinician (or another agent) can reach it in plain English, with no frontend at all.

- **NL in, verdict out.** Send "Prior auth for Humira, RA patient, no methotrexate trial, Aetna…"
  → **ASI:One** (`asi_client.py`) extracts the structured fields → the same pipeline runs → it
  replies with the verdict, the per-flag reasons, and (if READY) the Browserbase confirmation.
- **ASI:One-discoverable.** Registered on Agentverse as a **Mailbox** agent so it's reachable
  through ASI:One.
  Address: `agent1qgq4la65vzumw4ec469vk5zdaqycnxfhuxx669r7p2umzf887cylc2egetv`.
- **Agent-to-agent.** `clinic_agent.py` is a second uAgent that messages ReferralGuard over a
  typed `ReferralRequest → ReferralVerdict` contract — a working multi-agent handoff, not just one bot.

```bash
cd backend
python fetch_agent.py     # prints the agent address + Agentverse inspector link
# then add it on https://agentverse.ai (Mailbox) to make it ASI:One-discoverable
```

Files: `backend/fetch_agent.py` (Chat Protocol + a2a), `backend/clinic_agent.py` (peer agent),
`backend/asi_client.py` (ASI:One LLM extraction). Details in [`docs/FETCH_AI.md`](docs/FETCH_AI.md).

---

## Sponsors — used for real (with code proof)

Every integration makes a **real SDK/API call**, not just a feature flag. Add the key in `.env` to flip
it live; `GET /health` shows what's on (mock mode otherwise, so judges can run instantly).

**General track:** Ddoski's **World** (real-world healthcare impact).
**Sponsor prizes targeted:** Best Use of the Agentverse (Fetch.ai) · Best Use of Claude · Redis (Beyond Caching) · Best Use of Sentry API · Best Use of Deepgram · Best Use of Browserbase · Best Use of Arize · Best Use of The Token Company.

The "What it does" column is written to each prize's stated criteria.

| Sponsor | What it does here (mapped to the criteria) | Proof in code |
|---|---|---|
| **Fetch.ai / Agentverse** | An **ASI:One-discoverable agent that takes action**, not a chatbot or thin wrapper: understands a plain-English referral, runs the checks, and (when clean) **submits it** — plus an agent-to-agent handoff. | `fetch_agent.py` (uagents Chat Protocol + a2a), `asi_client.py` (ASI:One LLM) |
| **Anthropic — Claude** | Core reasoning on a **health** problem, built with Claude Code: field extraction, denial-risk analysis, grounded case chat, and the compression guard. | `agent_pipeline.py` — `anthropic.Anthropic().messages.create()` (L100), `.count_tokens()` (L351) |
| **Redis — beyond caching** | **Agent memory / shared state** across the multi-agent pipeline (each step reads + writes session state) and a replayable audit trail — not a cache. | `agent_pipeline.py:63` — `redis.from_url().ping()/.hset()/.expire()` |
| **Sentry** | **Reliability from day one**: captures the real failure path (unreadable member ID) with breadcrumbs + tags so a bad input is logged, not a crash. | `agent_pipeline.py:37-54` — `sentry_sdk.init / add_breadcrumb / capture_exception` |
| **Deepgram** | **Voice is essential, not tacked on** — phone referrals come in as audio and are transcribed live (`nova-3`) to drive the whole pipeline. | `intake_voice.py:41` — `dg.listen.rest.v("1").transcribe_file()` |
| **Browserbase** | **An agent that uses the web**: a real hosted browser logs into the payer portal and submits the prior auth (Playwright over CDP). | `submission_agent.py:31,48` — `api.browserbase.com/v1/sessions` + `playwright.connect_over_cdp()` |
| **Arize** | **Tracing that improved the app**: OTEL spans of every agent decision; we used them to verify and replay the pipeline (and caught the export issue). | `observability.py:25-32` — `OTLPSpanExporter → /v1/traces` |
| **The Token Company** | **Research/ingenuity**: real context compression before every LLM call with a verifier guard + a live before/after token meter (model's own tokenizer). | `agent_pipeline.py:375` — `compress_context()`, `_count_tokens()` (L346) |
| **Orkes Conductor** | Durable workflow + the HUMAN approval gate prior auth requires. *(Note: the Orkes prize targets Agentspan, which we don't use — this is a Conductor integration.)* | `orchestration/worker.py:28-50` — `conductor.client @worker_task / TaskHandler` |

**Mocked (clearly labeled):** payer policy rules (3 representative), 5 synthetic samples (no PHI),
EHR/fax connectors (channel field). The pipeline itself is the real part.

---

## Repo layout

```
calhack/
├── README.md
├── CLAUDE.md                       project context / handoff notes
├── run.sh                          one-command backend start
├── dashboard/
│   ├── index.html                  ★ the demo — doctor-facing UI (standalone, live trace)
│   └── console.html                technical ops console (legacy view)
├── backend/
│   ├── server.py                   FastAPI: /health, /process, /intake/voice, /chat
│   ├── agent_pipeline.py           agent pipeline + case chat + context compression
│   ├── submission_agent.py         Browserbase payer-portal submission
│   ├── intake_voice.py             Deepgram voice intake
│   ├── observability.py            Phoenix / JSONL decision-trace logging
│   ├── fetch_agent.py              Fetch.ai uAgent (ASI:One Chat Protocol)
│   ├── clinic_agent.py             second uAgent (agent-to-agent demo)
│   ├── asi_client.py               ASI:One LLM (NL referral extraction)
│   ├── selftest.py                 end-to-end check
│   ├── requirements.txt
│   └── .env.example
├── orchestration/
│   ├── referralguard_workflow.json Orkes Conductor workflow (+ HUMAN approval gate)
│   └── worker.py                   Orkes task workers
├── samples/                        5 referral/PA requests, varying completeness
├── assets/
│   └── call.wav                    sample phone referral (Deepgram voice intake)
└── docs/
    ├── DEVPOST.md                  submission text
    ├── FETCH_AI.md                 ASI:One submission details
    ├── GO_LIVE.md                  turn each engine live
    ├── TEAM_RUNBOOK.md             4-person split
    ├── SPONSOR_TALKING_POINTS.md   booth / recruiting talking points
    └── one-pager.html              pitch one-pager (print to PDF)
```

The frontend pipeline (`dashboard/index.html`) mirrors the backend (`agent_pipeline.py`)
so the offline demo is faithful to the live system.

---

## Notes & assumptions

- **No real PHI / payer APIs.** All requests are synthetic; payer rules are illustrative.
- Claude model: `claude-haiku-4-5` — fast, cheap extraction/reasoning/chat for a live demo.
- The 30-second demo target drives a deterministic, replayable trace over long LLM waits.

## Why this could be a company

Every denied or returned PA is lost clinic revenue and a delayed patient. ReferralGuard sits at the
point of submission and turns a reactive, after-the-fact denial into a *pre-submission* fix — with an
audit trail payers and compliance teams can trust. A per-seat SaaS wedge into a workflow that happens
~40 times a week, for every specialist.
