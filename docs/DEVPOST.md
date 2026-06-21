# ReferralGuard — Devpost submission

> **Team name:** _[FILL IN]_
> **Table number:** _[FILL IN]_
> **Built at:** UC Berkeley AI Hackathon 2026

---

## Elevator pitch (2–3 sentences)

ReferralGuard is a multi-agent system that reads an incoming specialty referral or prior-auth
request, extracts the key fields, flags everything missing or likely to cause a denial — each with
a stated reason — pauses for human approval, then drives a hosted browser to submit it to the payer
portal, all behind a timestamped, replayable audit trail of exactly what each agent checked and why.
It turns the reactive, after-the-fact denial that costs clinics revenue and delays patients into a
fix made *before* the request is ever submitted. Built on Claude (reasoning), Browserbase (portal
submission), Orkes Conductor (orchestration + human-approval gate), Phoenix, Deepgram, Sentry, and Redis.

---

## Inspiration

Specialty clinics bleed patients and revenue to paperwork. The 2025 AMA Prior Authorization
Physician Survey found physicians do **~40 prior authorizations a week** and spend **~13 hours/week**
on them, with **94%** saying it drives burnout and denials rising every year — and roughly **half of
specialty referrals are never completed**. The maddening part: most denials are for *knowable*
reasons — a missing diagnosis code, undocumented step therapy, an unreadable member ID. Those are
catchable before submission. Nobody is watching the request at the moment it matters.

## What it does

ReferralGuard runs an incoming referral/PA request through a chain of cooperating agents:

1. **Intake** — opens a session, caches the raw request (fax, EHR, or **voice via Deepgram**).
2. **Extraction (Claude)** — parses unstructured text into typed fields.
3. **Completeness** — checks the seven required fields, names each gap.
4. **Validation** — validates the insurance member ID; malformed input raises an exception that's
   **captured by Sentry** and recovered from instead of crashing the pipeline.
5. **Denial-Risk (Claude)** — reasons over payer policy (step therapy, conservative-care rules) to
   predict denials *with a written reason*.
6. **Decision** — combines the flags into a verdict: `READY TO SUBMIT`, `NEEDS INFO`, or `HIGH DENIAL RISK`.
7. **Approval Gate (Orkes)** — for READY requests, a Conductor HUMAN task pauses the workflow for the
   human sign-off prior auth legally requires.
8. **Submission (Browserbase)** — a hosted headless browser logs into the payer portal, fills the PA
   form, and returns a confirmation number. (Other verdicts route to human review instead.)

Every step writes a **timestamped audit span**, rendered as a live decision trace you can watch in
under 30 seconds — the trail a clinic ops lead or auditor can replay.

## How we built it

- **Browserbase** is the agentic payoff — once a request is READY, a hosted headless browser logs into the payer portal, fills the PA form, and returns a confirmation. Prior auth *is* portal navigation, so this is the most on-thesis piece.
- **Orkes Conductor** orchestrates the agent DAG and provides the **human-approval gate** (a HUMAN task that pauses the workflow until sign-off) that prior auth legally requires.
- **Claude (Anthropic)** is the reasoning core — extraction and denial-risk analysis (`claude-haiku-4-5` for fast, cheap live inference).
- **Sentry** is wired into the pipeline for exception capture with breadcrumbs and tags — our *Best Use of Sentry API* entry. The "unreadable member ID" sample deliberately triggers the captured-and-recovered path.
- **Arize Phoenix** receives the decision-trace spans (OTEL) for tracing/eval (also written locally to `traces.jsonl`).
- **Deepgram** powers voice intake — phone referrals are transcribed (`nova-2-medical`) straight into the same pipeline.
- **Redis** holds inter-agent session state and persists the audit trail.
- **Frontend** — a single, dependency-free, Apple-clean HTML/JS dashboard. It runs the pipeline in-browser for an always-works demo and auto-upgrades to the live backend when present.

Every API key is optional: the whole system runs in mock mode so judges can open one HTML file and
see it work, then flip any engine to live by adding a key.

## Challenges we ran into

The denial-risk check had a subtle bug: a note saying *"No documentation of methotrexate trial"*
naively matched the keyword "methotrexate" and marked the requirement satisfied. We added
negation-aware detection so the agent reads "no/without/absent" near a term correctly — the
difference between approving and denying a request.

## What's next

Real payer-policy feeds, EHR/fax connectors (the intake layer is already abstracted), a write-back
that auto-drafts the missing documentation request, and per-payer denial analytics.

## Why this could be a company

ReferralGuard sits at the point of submission and converts after-the-fact denials into
pre-submission fixes, with an audit trail payers and compliance teams can trust. That's a
per-seat SaaS wedge into a workflow every specialist hits ~40 times a week.

## Built with

`claude` · `anthropic-api` · `browserbase` · `orkes-conductor` · `fetch-ai` · `uagents` · `arize-phoenix` · `deepgram` · `sentry` · `redis` · `fastapi` · `python` · `html` · `javascript`
