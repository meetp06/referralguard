"""
Clinic Intake Agent — the second agent (multi-agent orchestration bonus).

Simulates a referring clinic's own uAgent that forwards a referral to the
ReferralGuard agent over the **Agent Chat Protocol** and receives the verdict
back — agent-to-agent collaboration on Agentverse, the same protocol ASI:One uses.

Run (ReferralGuard agent must be up first):
    pip install uagents
    python clinic_agent.py
    # then connect its mailbox via the printed inspector URL (Chrome)
"""
import os
from datetime import datetime
from uuid import uuid4

from dotenv import load_dotenv
load_dotenv()

# ReferralGuard's address is deterministic (fixed seed), so default to it.
TARGET = os.getenv("REFERRALGUARD_AGENT_ADDRESS",
                   "agent1qgq4la65vzumw4ec469vk5zdaqycnxfhuxx669r7p2umzf887cylc2egetv")

SAMPLE_REFERRAL = (
    "Prior auth for Humira (adalimumab), CPT J0135, for rheumatoid arthritis, dx M06.9. "
    "Patient Dana Whitfield, DOB 1990-07-22. Insurance UnitedHealthcare, member ID "
    "UHC-3398-1180, NPI 1487720013. No documentation of a methotrexate trial in the note."
)

try:
    # Python 3.12+ removed the implicit event loop uagents relies on.
    import asyncio
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    from uagents import Agent, Context, Protocol
    from uagents_core.contrib.protocols.chat import (
        ChatAcknowledgement, ChatMessage, TextContent, chat_protocol_spec,
    )

    clinic = Agent(name="clinic_intake", seed=os.getenv("CLINIC_AGENT_SEED", "clinic-demo-seed"),
                   port=8002, mailbox=True)

    chat = Protocol(spec=chat_protocol_spec)

    def _text(t: str) -> ChatMessage:
        return ChatMessage(timestamp=datetime.utcnow(), msg_id=uuid4(),
                           content=[TextContent(type="text", text=t)])

    _state = {"sent": 0, "done": False}

    @clinic.on_interval(period=20.0)
    async def send_referral(ctx: Context):
        if _state["done"] or _state["sent"] >= 3:
            return
        _state["sent"] += 1
        ctx.logger.info(f"→ Sending referral to ReferralGuard ({TARGET[:18]}…) via Chat Protocol")
        await ctx.send(TARGET, _text(SAMPLE_REFERRAL))

    @chat.on_message(ChatMessage)
    async def on_message(ctx: Context, sender: str, msg: ChatMessage):
        # ack per spec
        await ctx.send(sender, ChatAcknowledgement(
            timestamp=datetime.utcnow(), acknowledged_msg_id=msg.msg_id))
        for item in msg.content:
            if isinstance(item, TextContent):
                _state["done"] = True
                print("=" * 60)
                print("AGENT-TO-AGENT REPLY from ReferralGuard:")
                print(item.text)
                print("=" * 60)
                ctx.logger.info("✅ Verdict received from ReferralGuard (agent-to-agent)")

    @chat.on_message(ChatAcknowledgement)
    async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
        ctx.logger.info(f"ack from {sender[:18]}…")

    clinic.include(chat, publish_manifest=True)

    if __name__ == "__main__":
        print("=" * 60)
        print(f"Clinic intake agent address: {clinic.address}")
        print(f"Talking to ReferralGuard at: {TARGET}")
        print("Connect this agent's mailbox via the inspector URL below, then")
        print("it sends a referral to ReferralGuard and prints the verdict.")
        print("=" * 60)
        clinic.run()

except ImportError:
    if __name__ == "__main__":
        print("uagents not installed. `pip install uagents` to run the agent-to-agent demo.")
