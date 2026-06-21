# Sponsor booth talking points

Short, honest, recruiting-oriented. Lead with the project, connect to their tech, end with a question.

> ⚠️ **Heads-up:** HRT (Hudson River Trading) is **not** on this hackathon's sponsor list. Anthropic,
> Sentry, and Deepgram are. Points for those three below, plus Redis/Arize/SkyDeck as bonus stops you
> can actually use here. If HRT does have a booth, skip the project pitch and talk systems/latency —
> ReferralGuard isn't a finance project, so be upfront that you're there for the conversation.

---

## Browserbase (most on-thesis — lead here)

1. **"Prior auth IS browser automation."** Once a request passes our checks, a Browserbase hosted
   browser logs into the payer portal, fills the PA form, and pulls back a confirmation. Your product
   is the agentic payoff of our entire pipeline, not a bolt-on.
2. **"Headless Chrome as infra."** We treat Browserbase like 'Lambda for Chrome' — spin up a session
   per submission, drive it with Playwright over CDP, tear it down. Stateless, parallelizable, exactly
   the shape of a high-volume submission queue.
3. **Recruiting hook:** "Our submission agent degrades to a mock with no key, so the wiring is clean to
   show. I'd love to talk about session reliability, stealth, and scaling concurrent browser agents —
   and what you look for in engineers."

## Orkes Conductor (core — durable + compliant)

1. **"We need a human in the loop, and Conductor gives us that for free."** Prior auth legally requires
   human sign-off. We model it as a Conductor `HUMAN` task that pauses the workflow until an approver
   acts, then resumes into the Browserbase submission. Durable, auditable, resumable.
2. **"Right tool, right domain."** A multi-step agent pipeline with approval gates and retries is
   exactly Conductor's wheelhouse — and you already serve healthcare workflows (GE Healthcare).
3. **Recruiting hook:** "Here's our workflow JSON with the SWITCH on verdict and the HUMAN gate. How do
   you think about long-running, human-in-the-loop agent orchestration at scale?"

## Arize Phoenix (core + strong resume match)

1. **"Every agent step is an OTEL span in Phoenix."** Our decision trace isn't just UI — it's real
   tracing you can replay and eval. Phoenix made the demo look production-grade.
2. **"Observability is the trust layer for clinical agents."** When a model predicts a denial, we can
   inspect the exact span, inputs, and reason — essential for a regulated workflow.
3. **Recruiting hook:** "My background is quantization / vLLM / SGLang / observability — I wired Phoenix
   in under an hour here. I'd love to talk about eval for agent pipelines and how your team works."

## Anthropic (Claude)

1. **"Claude is the reasoning core, not a wrapper."** We use Claude for two distinct jobs — structured
   extraction from messy referral text, and denial-risk *reasoning* over payer policy. Two different
   prompt patterns, both returning strict JSON we can act on.
2. **"We made Claude's reasoning auditable."** Every Claude call is a timestamped span in a replayable
   audit trail — so a clinician can see *why* the model flagged a denial, not just the verdict. That's
   the trust layer healthcare actually needs.
3. **Recruiting hook:** "We picked Haiku for sub-second live inference and designed around negation
   bugs in clinical text. I'd love to hear how your team thinks about reliability for high-stakes,
   structured-output use cases."

## Sentry (targeting *Best Use of Sentry API* → Switch 2 + guaranteed interview)

1. **"We instrument the agent pipeline itself, not just a web server."** When the member-ID validator
   hits malformed OCR input, we raise a real exception, **capture it to Sentry with breadcrumbs of the
   full agent path** (intake → extract → validate) and tags (request_id, payer), then *recover* —
   the request is routed to human review instead of crashing the run.
2. **"Sentry is our safety net for non-deterministic agents."** Agents fail in weird ways; we treat
   every captured exception as a triage signal with the exact decision context attached.
3. **Recruiting hook:** "Show me the captured event in our demo — breadcrumbs + tags on an agent
   exception. How are you all thinking about observability for LLM agent failures specifically?"

## Deepgram

1. **"Referrals come in by phone — so we transcribe them."** Deepgram (`nova-2-medical`) turns a spoken
   phone referral into text that flows into the *exact same* pipeline as a fax or EHR message. One
   intake abstraction, multiple channels.
2. **"Medical vocab matters."** Drug names, CPT codes, and member IDs spoken aloud are where generic STT
   falls apart — the medical model is the difference between a usable transcript and garbage fields.
3. **Recruiting hook:** "Our voice path is real but optional — degrades to a baked transcript with no key.
   I'd love to talk about streaming + diarization for live call intake, and what you look for in
   engineers."

---

## Bonus stops you can actually make

- **Redis** — "Redis is our inter-agent state bus and audit store; session state moves between six agents
  through it, with TTLs. Simple, fast, exactly right for an agent pipeline."
- **Arize** — "Our decision-trace spans push to Arize for visualization — the audit trail doubles as
  agent observability. How do you handle traces where each span is an LLM decision with a human-readable reason?"
- **Fetch.ai (uAgents / Agentverse / ASI:One)** — "We expose ReferralGuard as a uAgent with the Chat
  Protocol, so a partner clinic's agent can send a referral agent-to-agent and get a verdict back —
  same pipeline, reached over Agentverse instead of HTTP. How do you see multi-agent marketplaces
  working for regulated, human-in-the-loop workflows like healthcare?"
- **SkyDeck (grand prize = Pad-13 incubator)** — "ReferralGuard is a per-seat SaaS wedge into a workflow
  every specialist hits ~40x/week. Pre-submission denial prevention with an auditable trail. Here's the one-pager."
