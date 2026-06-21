![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

# ReferralGuard on Fetch.ai — ASI:One Agent Challenge

**Challenge:** *From Intent to Action.* ReferralGuard is an ASI:One-discoverable agent that takes a
plain-English referral / prior-auth request, extracts the clinical + insurance fields, runs a real
multi-step pipeline (completeness, member-ID validation, payer denial-risk reasoning, decision,
human-approval gate, payer-portal submission), and returns a verdict with reasons — the entire
workflow completes **inside an ASI:One conversation, no custom frontend**.

## Agents

| Agent | Name | Address | Role |
|---|---|---|---|
| Primary | `referralguard` | `agent1q...` _(fill in after first run)_ | ASI:One-facing; runs the prior-auth pipeline |
| Secondary | `clinic_intake` | `agent1q...` _(fill in)_ | Referring-clinic agent that forwards referrals (agent-to-agent demo) |

> Run `python backend/fetch_agent.py` — it prints the address. Paste it above and in the repo README.

## Mandatory requirements — how we meet them

- **Registered on Agentverse** — the agent runs with `mailbox=True`; add it at https://agentverse.ai.
- **Agent Chat Protocol** — implemented in `backend/fetch_agent.py` (`chat_protocol_spec`: ChatMessage,
  ChatAcknowledgement, Start/Text/End content), manifest published.
- **Discoverable + usable through ASI:One** — natural-language in, verdict out; no frontend needed.
- **Meaningful tool execution + agent-to-agent** — runs the full pipeline (Claude reasoning, payer
  rules, Sentry-guarded validation, Browserbase submission); `clinic_agent.py` shows agent-to-agent
  orchestration.
- **Public repo with run instructions** — this repo + `README.md` + `TEAM_RUNBOOK.md`.

## Bonus targeted

- **Multi-agent collaboration** — `clinic_intake` → `referralguard` round trip.
- **Reliability / error recovery** — bad member IDs raise a captured exception and recover to human
  review instead of crashing (Sentry); the chat handler catches pipeline errors and asks for missing fields.
- **Real-world impact** — prior auth is ~40/physician/week; this prevents denials pre-submission.
- **Payment Protocol** — scaffold/notes only (see “Next steps”); not funded for the demo.

## Run it

```bash
cd backend
pip install uagents requests
export ASI_ONE_API_KEY=...                 # optional; improves field extraction (asi1-mini)
python fetch_agent.py                       # prints the agent address
# (optional, second terminal) agent-to-agent demo:
export REFERRALGUARD_AGENT_ADDRESS=agent1q...   # from the line above
python clinic_agent.py
```

Then on https://agentverse.ai → add a **Mailbox** agent using the printed address, give it the README
(with the badges above), and it becomes discoverable in ASI:One.

## Try it in ASI:One (example prompts)

- "Prior auth for a lumbar MRI, CPT 72148, low back pain M54.50, Humana Medicare Advantage member
  HUM-9921-3304, NPI 1902847711, onset 10 days, no conservative therapy yet." → **HIGH DENIAL RISK**
- "Cardiology referral + stress echo CPT 93350, unstable angina I20.0, BlueShield PPO member
  BSC-4471-9920, NPI 1295847362, conservative tx started." → **READY TO SUBMIT** (+ Browserbase confirmation)
- "Colonoscopy CPT 45378, Aetna member AET-7781-2200, rectal bleeding — no ICD-10 yet." → **NEEDS INFO**

## Devpost deliverables checklist (Fetch.ai)

- [ ] Public **ASI:One shared-chat URL** showing the full workflow
- [ ] **Agentverse agent profile URL** (both agents)
- [ ] Public **GitHub repo** (this one) with agent name + address in README
- [ ] **Demo video** (3–5 min)
- [ ] README carries the `innovationlab` + `hackathon` badges (top of this file)

## Next steps (Payment Protocol bonus)

To add monetization, wire the FET or Skyfire payment protocol around `handle_chat` (charge per
verdict / per submission). Reference: Fetch.ai Innovation Lab docs → “Enable Payment Protocol”.
Left as a scaffold to avoid shipping an unfunded wallet in the demo.
