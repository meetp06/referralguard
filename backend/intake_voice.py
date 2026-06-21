"""
Deepgram voice intake — phone referrals arrive as audio.

transcribe(audio_path) -> text
  - DEEPGRAM_API_KEY set  -> real Deepgram transcription
  - no key                -> returns a baked phone-referral transcript so the demo still runs

The transcript then flows into the SAME pipeline (run_pipeline) as a typed request,
so a spoken referral gets the identical extraction + flagging + audit trail.
"""
import os

DEEPGRAM_KEY = os.getenv("DEEPGRAM_API_KEY")
DEEPGRAM_ON = bool(DEEPGRAM_KEY)

# Fallback transcript used when no key / no audio is provided (mirrors samples/02)
MOCK_TRANSCRIPT = (
    "Hi, this is Northgate Urgent Care calling in a referral to GI. "
    "Patient James O'Neill, date of birth eleven two nineteen eighty-one. "
    "He needs a diagnostic colonoscopy, CPT four five three seven eight. "
    "Insurance is Aetna, member ID A-E-T seven seven eight one two two zero zero. "
    "Symptoms are intermittent rectal bleeding with a family history of colon cancer. "
    "We don't have an ICD-10 code on this one."
)


def transcribe(audio_path: str = None) -> dict:
    """Returns {'text': transcript, 'engine': 'deepgram'|'mock'}."""
    if DEEPGRAM_ON and audio_path and os.path.exists(audio_path):
        try:
            from deepgram import DeepgramClient, PrerecordedOptions
            dg = DeepgramClient(DEEPGRAM_KEY)
            with open(audio_path, "rb") as f:
                source = {"buffer": f.read()}
            opts = PrerecordedOptions(model="nova-2-medical", smart_format=True, punctuate=True)
            resp = dg.listen.prerecorded.v("1").transcribe_file(source, opts)
            text = resp["results"]["channels"][0]["alternatives"][0]["transcript"]
            return {"text": text, "engine": "deepgram"}
        except Exception:
            pass
    return {"text": MOCK_TRANSCRIPT, "engine": "mock"}
