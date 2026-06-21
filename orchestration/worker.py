"""
Orkes Conductor workers — optional.

Registers each ReferralGuard agent as a Conductor task worker so the workflow in
referralguard_workflow.json runs durably on Orkes (with the HUMAN approval gate
pausing the workflow until an approver acts). Without Orkes creds the demo uses the
in-process pipeline in backend/agent_pipeline.py instead — same logic, same audit trail.

Run (after `pip install conductor-python`):
    export CONDUCTOR_SERVER_URL=https://<your-cluster>.orkesconductor.io/api
    export CONDUCTOR_AUTH_KEY=...      CONDUCTOR_AUTH_SECRET=...
    python worker.py
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import agent_pipeline as ap
import submission_agent as sub_agent


def _steps_collector():
    steps = []
    return steps, (lambda who, badge, act, det: steps.append(
        {"who": who, "badge": badge, "act": act, "det": det}))


try:
    from conductor.client.worker.worker_task import worker_task

    @worker_task(task_definition_name="extraction_agent")
    def extraction_agent(raw: str) -> dict:
        return {"fields": ap.claude_extract(raw) if ap.CLAUDE_ON else {}}

    @worker_task(task_definition_name="denial_risk_agent")
    def denial_risk_agent(fields: dict, raw: str) -> dict:
        cpt = (fields or {}).get("requested_cpt")
        rule = ap.PAYER_RULES.get(cpt)
        if not rule:
            return {"risk": "none"}
        met = ap.requirement_met((raw or "").lower(), rule["keywords"])
        return {"risk": "none" if met else "high", "reason": rule["msg"]}

    @worker_task(task_definition_name="submission_agent")
    def submission_agent(request: dict, approved_by: str = "") -> dict:
        steps, push = _steps_collector()
        return sub_agent.run_submission(request, push)

    if __name__ == "__main__":
        from conductor.client.automator.task_handler import TaskHandler
        from conductor.client.configuration.configuration import Configuration
        TaskHandler(configuration=Configuration()).start_processes()

except ImportError:
    if __name__ == "__main__":
        print("conductor-python not installed. This file is the optional Orkes path; "
              "the hackathon demo runs the same pipeline in-process via backend/agent_pipeline.py.")
