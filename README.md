# ReferralGuard

**A multi-agent pre-flight check for specialty referrals & prior authorizations — with a watchable, timestamped audit trail.**

UC Berkeley AI Hackathon 2026.

---

## The problem

Specialty clinics lose patients and revenue because referrals and prior-auth (PA)
requests get stuck in manual, fax-and-phone paperwork. The 2025 AMA Prior Authorization
Physician Survey (fielded December 2025) found physicians complete an **average of ~40
prior authorizations per week**, spend **~13 hours/week** on them, and **94% say PA
contributes to burnout**, with denials rising year over year. Separately, a widely cited
figure puts roughly **half of specialty referrals as never completed**. Most of that pain
is avoidable: requests get denied or returned for missing fields, missing step-therapy
documentation, or unreadable insurance info — things that are knowable *before* submission.

## What ReferralGuard does

It reads an incoming referral / PA request and, in real time:

1. **Extracts** key fields — patient, diagnosis (ICD-10), requested procedure (CPT/HCPCS), insurance.
2. **Flags** what's missing or likely to cause a denial, **with a stated reason for each flag**.
3. **Shows a visible, timestamped audit trail** of exactly what each agent checked and why
   it made each call — replayable in under 30 seconds. **This audit trail is the centerpiece.**

The verdict for each request is one of: `READY TO SUBMIT`, `NEEDS INFO`, or `HIGH DENIAL RISK`.

---

## Demo in 30 seconds

1. Open `dashboard/index.html` in any browser (no build, no server required).
2. Pick a request from the **Incoming queue** (left).
3. Press **Receive & process**. Watch the agent decision trace stream in the center,
   with extracted fields, flags, and the final verdict on the right.

The dashboard runs **fully standalone** (deterministic in-browser pipeline). If the backend
is running on `localhost:8000`, it automatically switches to live mode and calls the real agents.

### Optional: run the live backend

```bash
./run.sh
# or:
cd backend
pip install -r requirements.txt
cp .env.example .env      # add API keys (all optional)
uvicorn server:app --port 8000
```

Then reload the dashboard — the mode chip flips to **live**.

---

## Architecture

```
                ┌────────────────────────────────────────────────────────┐
  referral  →   │  Intake → Extraction → Completeness → Validation →      │
 (fax / EHR /   │          Denial-Risk → Decision                         │  → verdict + audit trail
  phone voice)  └────────────────────────────────────────────────────────┘
                     every step writes a timestamped span to the audit log
```

Cooperating agents, each emitting one timestamped audit entry:

| Agent | Does | Engine |
|---|---|---|
| **Intake** | Opens a session, caches raw payload (fax / EHR / **voice**) | Redis (+ Deepgram for voice) |
| **Extraction** | Parses raw/voice text → typed fields | Claude |
| **Completeness** | Checks the 7 required fields | rules |
| **Validation** | Validates member-ID format; bad input raises a captured exception | Redis + Sentry |
| **Denial-Risk** | Reasons over payer policy (step therapy, conservative-care rules) to predict denials | Claude |
| **Decision** | Combines flags into a final verdict; persists the full trace | rules |
| **Approval Gate** | *(READY only)* pauses for human sign-off — prior auth legally requires it | Orkes (HUMAN task) |
| **Submission** | *(READY only)* hosted browser logs into the payer portal, submits the PA, returns a confirmation | Browserbase |

State flows between steps via Redis; every step is logged as a span (Phoenix + `traces.jsonl`) for replay.
NEEDS INFO / HIGH DENIAL RISK requests skip submission and route to human review instead.

---

## Sponsor integrations — real vs. mocked

Everything runs in **mock mode** with no keys. Add a key in `.env` to flip that engine to **live**.
This is intentional so judges can run the demo instantly, and so each integration is a clean swap.

| Sponsor | Used for | Status | Where |
|---|---|---|---|
| **Browserbase** | Submission agent — hosted headless browser submits the PA to the payer portal + pulls status. The most on-thesis tool: prior auth *is* portal navigation. | **Wired** (live with `BROWSERBASE_API_KEY`+`BROWSERBASE_PROJECT_ID`; mock portal steps otherwise) | `backend/submission_agent.py` |
| **Orkes (Conductor)** | Durable orchestration + the **human-approval gate** prior auth legally requires (HUMAN task pauses the workflow until sign-off) | **Wired** — workflow + workers in `orchestration/` (live with `CONDUCTOR_SERVER_URL`); in-process pipeline is the reference impl | `orchestration/referralguard_workflow.json`, `orchestration/worker.py` |
| **Anthropic (Claude)** | Core reasoning: field extraction + denial-risk analysis | **Wired** (live with `ANTHROPIC_API_KEY`; deterministic mock otherwise) | `backend/agent_pipeline.py` |
| **Arize Phoenix** | OSS OTEL tracing/eval of the agent decision spans | **Wired** (live with `PHOENIX_COLLECTOR_ENDPOINT`; spans always written to `traces.jsonl`) | `backend/observability.py` |
| **Deepgram** | Voice intake — transcribe phone referrals into the pipeline | **Wired** (live with `DEEPGRAM_API_KEY`; baked medical transcript otherwise) | `backend/intake_voice.py`, `POST /intake/voice` |
| **Sentry** | Exception capture in the agent pipeline (member-ID error path), with breadcrumbs + tags | **Wired** (live with `SENTRY_DSN`) — *Best Use of Sentry API* | `backend/agent_pipeline.py` |
| **Redis** | Inter-agent session state + audit persistence | **Wired** (live with `REDIS_URL`; in-memory fallback) | `backend/agent_pipeline.py` |

### What's mocked

- **Payer policy rules** are a small hand-built knowledge base (3 representative rules:
  biologic step therapy, lumbar-MRI conservative-care, knee-MRI conservative-care). In
  production these come from payer policy feeds / a rules service.
- **Incoming requests** are 5 synthetic samples in `samples/` (no real PHI).
- **EHR/fax connectors** are simulated by the sample channel field; the pipeline is the real part.

---

## Repo layout

```
calhack/
├── dashboard/index.html      ← the demo (open this) — standalone, Apple-clean UI
├── backend/
│   ├── server.py             ← FastAPI: /health, /process, /intake/voice
│   ├── agent_pipeline.py     ← the agent pipeline (Claude + Redis + Sentry + gate/submit)
│   ├── submission_agent.py   ← Browserbase payer-portal submission
│   ├── intake_voice.py       ← Deepgram voice intake
│   ├── observability.py      ← Phoenix / JSONL decision-trace logging
│   ├── requirements.txt
│   └── .env.example
├── orchestration/
│   ├── referralguard_workflow.json   ← Orkes Conductor workflow (+ HUMAN approval gate)
│   └── worker.py                     ← Orkes Conductor task workers
├── samples/                  ← 5 referral/PA requests, varying completeness
├── one-pager.html            ← founder/pitch one-pager (print to PDF)
├── DEVPOST.md                ← submission text
├── SPONSOR_TALKING_POINTS.md ← booth/recruiting talking points
└── run.sh
```

The frontend pipeline (`dashboard/index.html`) mirrors the backend (`agent_pipeline.py`)
so the offline demo is faithful to the live system.

---

## Assumptions made (no clarifying questions asked, per the brief)

- **No real PHI / payer APIs.** All requests are synthetic; payer rules are illustrative.
- **Best UI/UX** is also a prize, so the dashboard is intentionally minimal (Apple-style, light).
- **HRT is not a sponsor** at this event — Anthropic, Sentry, and Deepgram are. Booth talking
  points target the actual sponsors (see `SPONSOR_TALKING_POINTS.md`).
- Claude model used: `claude-haiku-4-5` for fast, cheap extraction/reasoning during a live demo.
- The 30-second demo target drives a deterministic, replayable trace rather than long LLM waits.

## Why this could be a company

Every denied or returned PA is lost clinic revenue and a delayed patient. ReferralGuard sits
at the point of submission and turns a reactive, after-the-fact denial into a *pre-submission*
fix — with an audit trail payers and compliance teams can trust. That's a per-seat SaaS wedge
into a workflow ~40 times a week, for every specialist.
