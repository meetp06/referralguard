"""
ReferralGuard — Fetch.ai uAgent (ASI:One Agent Challenge entry).

This is the ASI:One-discoverable agent. A user (or another agent) describes a
referral / prior-auth request in plain English inside an ASI:One chat; the agent
extracts the fields (ASI:One LLM), runs the full ReferralGuard pipeline (Claude +
rules + Sentry + Browserbase submission), and replies with the verdict, the reasons
behind each flag, and a submission confirmation — completing the whole workflow in
chat, no custom frontend.

Implements the Agent Chat Protocol (ASI:One compatible) and an agent-to-agent
ReferralRequest/ReferralVerdict model for multi-agent orchestration (see clinic_agent.py).

Run:
    pip install uagents
    export ASI_ONE_API_KEY=...        # optional, improves extraction
    python fetch_agent.py             # prints the agent address — put it in README
Then add the agent on https://agentverse.ai (Mailbox) so ASI:One can discover it.

Agent name: referralguard
"""
import os
from datetime import datetime
from uuid import uuid4

from agent_pipeline import run_pipeline
from asi_client import extract_referral, ASI_ON

FETCH_SEED = os.getenv("FETCH_AGENT_SEED", "referralguard-demo-seed")
FETCH_ON = False


def _build_request(text: str) -> dict:
    """Turn extracted fields + raw text into the pipeline's request shape."""
    ex = extract_referral(text)
    return {
        "id": "REF-ASI-" + uuid4().hex[:6].upper(),
        "chan": "asi1_chat", "clinic": "ASI:One user",
        "patient": {"name": ex.get("patient_name"), "dob": ex.get("dob"), "mrn": None},
        "diagnosis_code": ex.get("diagnosis_code"),
        "requested_cpt": ex.get("requested_cpt"),
        "procedure": ex.get("procedure") or "",
        "insurance": {"payer": ex.get("payer"), "member_id": ex.get("member_id"), "group": None},
        "npi": ex.get("npi"), "raw": text,
    }


def format_verdict(result: dict) -> str:
    """Human-readable chat reply summarizing the pipeline run."""
    icon = {"ok": "✅", "warn": "⚠️", "risk": "🛑"}.get(result["vclass"], "•")
    lines = [f"{icon} **{result['verdict']}** — {result['vsub']}", ""]
    if result["flags"]:
        lines.append("**Flags:**")
        for f in result["flags"]:
            lines.append(f"• {f['ttl']} — {f['rsn']}")
    else:
        lines.append("No issues found — all required fields present and no payer-rule conflicts.")
    sub = result.get("submission")
    if sub and sub.get("confirmation"):
        lines += ["", f"📨 Submitted to the payer portal via Browserbase — confirmation **{sub['confirmation']}**."]
    lines += ["", f"_Audit trail persisted ({len(result['steps'])} steps). Engine: ASI:One extraction "
              f"{'(live)' if ASI_ON else '(heuristic)'} → ReferralGuard pipeline._"]
    return "\n".join(lines)


try:
    # Python 3.12+ removed the implicit event-loop creation that uagents' Agent()
    # relies on; ensure one exists for this thread before building the agent.
    import asyncio
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    from uagents import Agent, Context, Model, Protocol
    from uagents_core.contrib.protocols.chat import (
        ChatAcknowledgement, ChatMessage, EndSessionContent,
        StartSessionContent, TextContent, chat_protocol_spec,
    )

    # ---- agent-to-agent contract (multi-agent orchestration bonus) ----
    class ReferralRequest(Model):
        text: str

    class ReferralVerdict(Model):
        request_id: str
        verdict: str
        flags: list
        confirmation: str | None = None

    agent = Agent(name="referralguard", seed=FETCH_SEED, port=8001, mailbox=True)
    FETCH_ON = True

    chat_proto = Protocol(spec=chat_protocol_spec)

    def _text(text: str) -> ChatMessage:
        return ChatMessage(timestamp=datetime.utcnow(), msg_id=uuid4(),
                           content=[TextContent(type="text", text=text)])

    @chat_proto.on_message(ChatMessage)
    async def handle_chat(ctx: Context, sender: str, msg: ChatMessage):
        # ack first (per spec)
        await ctx.send(sender, ChatAcknowledgement(
            timestamp=datetime.utcnow(), acknowledged_msg_id=msg.msg_id))
        for item in msg.content:
            if isinstance(item, StartSessionContent):
                await ctx.send(sender, _text(
                    "👋 ReferralGuard here. Describe a specialty referral or prior-auth request "
                    "(patient, diagnosis, procedure/CPT, insurance) and I'll tell you if it's ready "
                    "to submit or likely to be denied — and why."))
            elif isinstance(item, TextContent):
                ctx.logger.info(f"Referral text from {sender}: {item.text[:80]}")
                try:
                    result = run_pipeline(_build_request(item.text))
                    await ctx.send(sender, _text(format_verdict(result)))
                except Exception as e:
                    ctx.logger.error(f"pipeline error: {e}")
                    await ctx.send(sender, _text(
                        "I hit an error processing that referral. Please include patient, diagnosis "
                        "code, requested CPT, and insurance, and try again."))
            elif isinstance(item, EndSessionContent):
                ctx.logger.info(f"Session ended with {sender}")

    @chat_proto.on_message(ChatAcknowledgement)
    async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
        ctx.logger.info(f"ack from {sender} for {msg.acknowledged_msg_id}")

    # agent-to-agent handler (used by clinic_agent.py)
    a2a = Protocol(name="referralguard-a2a", version="1.0")

    @a2a.on_message(model=ReferralRequest, replies=ReferralVerdict)
    async def handle_a2a(ctx: Context, sender: str, msg: ReferralRequest):
        result = run_pipeline(_build_request(msg.text))
        sub = result.get("submission") or {}
        await ctx.send(sender, ReferralVerdict(
            request_id=result["session"], verdict=result["verdict"],
            flags=[f["ttl"] for f in result["flags"]], confirmation=sub.get("confirmation")))

    agent.include(chat_proto, publish_manifest=True)
    agent.include(a2a, publish_manifest=True)

    if __name__ == "__main__":
        print("=" * 60)
        print(f"ReferralGuard uAgent address: {agent.address}")
        print("Add this agent on https://agentverse.ai (Mailbox) to make it")
        print("discoverable through ASI:One. Put the address in README.md.")
        print("=" * 60)
        agent.run()

except ImportError:
    if __name__ == "__main__":
        print("uagents not installed. Install with `pip install uagents` to run the "
              "Fetch.ai/ASI:One agent. The same pipeline is also available via REST "
              "(backend/server.py) and the dashboard.")
