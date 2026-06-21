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

TARGET = os.getenv("REFERRALGUARD_AGENT_ADDRESS", "")

SAMPLE_REFERRAL = (
    "Prior auth for Humira (adalimumab), CPT J0135, for rheumatoid arthritis, dx M06.9. "
    "Patient Dana Whitfield. Insurance UnitedHealthcare, member ID UHC-3398-1180, NPI 1487720013. "
    "No documentation of a methotrexate trial in the note."
)

try:
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

    @clinic.on_event("startup")
    async def send_referral(ctx: Context):
        if not TARGET:
            ctx.logger.warning("Set REFERRALGUARD_AGENT_ADDRESS to the ReferralGuard agent address.")
            return
        ctx.logger.info("Sending referral to ReferralGuard…")
        await ctx.send(TARGET, ReferralRequest(text=SAMPLE_REFERRAL))

    @clinic.on_message(model=ReferralVerdict)
    async def on_verdict(ctx: Context, sender: str, msg: ReferralVerdict):
        ctx.logger.info(f"Verdict: {msg.verdict} | flags={msg.flags} | conf={msg.confirmation}")

    if __name__ == "__main__":
        print(f"Clinic intake agent address: {clinic.address}")
        clinic.run()

except ImportError:
    if __name__ == "__main__":
        print("uagents not installed. `pip install uagents` to run the agent-to-agent demo.")
