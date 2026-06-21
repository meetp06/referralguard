"""
Clinic Intake Agent — the second agent (multi-agent orchestration bonus).

Simulates a referring clinic's own uAgent that forwards a referral to the
ReferralGuard agent and receives the verdict back — demonstrating agent-to-agent
collaboration on Agentverse, not just a single chatbot.

Run (after the ReferralGuard agent is up and you have its address):
    pip install uagents
    export REFERRALGUARD_AGENT_ADDRESS=agent1q...   # printed by fetch_agent.py
    python clinic_agent.py
"""
import os
from uuid import uuid4

from dotenv import load_dotenv
load_dotenv()

# ReferralGuard's address is deterministic (fixed seed), so default to it.
TARGET = os.getenv("REFERRALGUARD_AGENT_ADDRESS",
                   "agent1qgq4la65vzumw4ec469vk5zdaqycnxfhuxx669r7p2umzf887cylc2egetv")

SAMPLE_REFERRAL = (
    "Prior auth for Humira (adalimumab), CPT J0135, for rheumatoid arthritis, dx M06.9. "
    "Patient Dana Whitfield. Insurance UnitedHealthcare, member ID UHC-3398-1180, NPI 1487720013. "
    "No documentation of a methotrexate trial in the note."
)

try:
    # Python 3.12+ removed the implicit event loop uagents relies on.
    import asyncio
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    from uagents import Agent, Context, Model

    class ReferralRequest(Model):
        text: str

    class ReferralVerdict(Model):
        request_id: str
        verdict: str
        flags: list
        confirmation: str | None = None

    clinic = Agent(name="clinic_intake", seed=os.getenv("CLINIC_AGENT_SEED", "clinic-demo-seed"),
                   port=8002, mailbox=True)

    _sent = {"n": 0}

    @clinic.on_interval(period=20.0)
    async def send_referral(ctx: Context):
        if _sent["n"] >= 3:
            return  # send a few times (covers mailbox connecting), then stop
        _sent["n"] += 1
        ctx.logger.info(f"→ Sending referral to ReferralGuard ({TARGET[:18]}…)")
        await ctx.send(TARGET, ReferralRequest(text=SAMPLE_REFERRAL))

    @clinic.on_message(model=ReferralVerdict)
    async def on_verdict(ctx: Context, sender: str, msg: ReferralVerdict):
        _sent["n"] = 99  # got a reply, stop sending
        print("=" * 60)
        print("AGENT-TO-AGENT REPLY from ReferralGuard:")
        print(f"  verdict      : {msg.verdict}")
        print(f"  flags        : {msg.flags}")
        print(f"  confirmation : {msg.confirmation}")
        print("=" * 60)
        ctx.logger.info(f"✅ Verdict received: {msg.verdict} | flags={msg.flags}")

    if __name__ == "__main__":
        print(f"Clinic intake agent address: {clinic.address}")
        clinic.run()

except ImportError:
    if __name__ == "__main__":
        print("uagents not installed. `pip install uagents` to run the agent-to-agent demo.")
