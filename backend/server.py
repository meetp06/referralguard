"""
ReferralGuard API — thin FastAPI wrapper around the agent pipeline.

Run:
    cd backend
    pip install -r requirements.txt
    cp .env.example .env        # add your keys (optional — runs without them)
    uvicorn server:app --reload --port 8000

Endpoints:
    GET  /health   -> which engines are live
    POST /process  -> run the multi-agent pipeline on one request, return the audit trail
"""
import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

import agent_pipeline as ap
import intake_voice as voice
import observability as obs

app = FastAPI(title="ReferralGuard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"ok": True, "claude": ap.CLAUDE_ON, "redis": ap.REDIS_ON, "sentry": ap.SENTRY_ON,
            "deepgram": voice.DEEPGRAM_ON, "phoenix": obs.PHOENIX_ON,
            "browserbase": ap.sub_agent.BROWSERBASE_ON, "orkes": ap.ORKES_ON}


@app.post("/process")
async def process(request: Request):
    req = await request.json()
    return ap.run_pipeline(req)


@app.post("/intake/voice")
async def intake_voice(request: Request):
    """Deepgram voice intake: transcribe a phone referral, then run the pipeline.
    Body (optional): {"audio_path": "/path/to/call.wav", "request_meta": {...}}.
    With no key/audio, a baked medical transcript is used so the demo always runs."""
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    # Default to the bundled sample call so the button gives a real Deepgram transcription
    # (when DEEPGRAM_API_KEY is set) with no path coupling in the frontend.
    default_audio = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "call.wav"))
    audio_path = body.get("audio_path") or (default_audio if os.path.exists(default_audio) else None)
    tr = voice.transcribe(audio_path)
    # Claude turns the free-form transcript into a typed request, then the normal pipeline runs.
    meta = body.get("request_meta") or {
        "id": "REF-VOICE-001", "chan": "deepgram_voice", "clinic": "Northgate Urgent Care",
        "patient": {"name": "James O'Neill", "dob": "1981-11-02", "mrn": None},
        "diagnosis_code": None, "requested_cpt": "45378", "procedure": "Diagnostic colonoscopy",
        "insurance": {"payer": "Aetna", "member_id": "AET-7781-2200", "group": None}, "npi": None,
    }
    meta["raw"] = tr["text"]
    result = ap.run_pipeline(meta)
    result["transcript"] = tr
    result["request"] = meta
    return result


@app.post("/chat")
async def chat(request: Request):
    """Grounded case Q&A. Body: {"context": {...case...}, "messages": [{role,content}...]}.
    Claude answers ONLY from the supplied case context (anti-hallucination)."""
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    reply = ap.claude_chat(body.get("context") or {}, body.get("messages") or [])
    return {"reply": reply, "engine": "claude" if ap.CLAUDE_ON else "mock"}


# convenience: serve the dashboard if you want one process for everything
@app.get("/")
def root():
    return {"service": "ReferralGuard", "dashboard": "open ../dashboard/index.html",
            "engines": {"claude": ap.CLAUDE_ON, "redis": ap.REDIS_ON, "sentry": ap.SENTRY_ON}}
