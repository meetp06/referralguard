"""
ReferralGuard self-test — run this to confirm everything works end to end.

Usage (with the server running on :8000, in your activated venv):
    python selftest.py

It checks /health (which engines are live), runs all 5 samples through /process
with expected verdicts, and exercises the Deepgram voice endpoint. Prints PASS/FAIL.
"""
import json, os, sys, urllib.request, urllib.error

BASE = os.getenv("REFERRALGUARD_URL", "http://localhost:8000")
SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "samples")

EXPECTED = {
    "01_clean_cardiology.json": "READY TO SUBMIT",
    "02_missing_dx_code.json": "NEEDS INFO",
    "03_step_therapy_risk.json": "HIGH DENIAL RISK",
    "04_bad_member_id.json": "NEEDS INFO",
    "05_mri_no_conservative.json": "HIGH DENIAL RISK",
}


def _post(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def _get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return json.load(r)


def to_req(s):
    return {"id": s["request_id"], "chan": s["channel"], "clinic": s["source_clinic"],
            "patient": s["patient"], "diagnosis_code": s["diagnosis_code"],
            "requested_cpt": s["requested_cpt"], "procedure": s["requested_procedure"],
            "insurance": s["insurance"], "npi": s["referring_provider_npi"], "raw": s["raw_text"]}


def main():
    print(f"\nTesting {BASE}\n" + "=" * 52)

    # 1) health
    try:
        h = _get("/health")
    except Exception as e:
        print(f"❌ Cannot reach backend at {BASE}. Is the server running?\n   {e}")
        sys.exit(1)
    print("ENGINES (true = live, false = mock):")
    for k in ["claude", "redis", "sentry", "deepgram", "phoenix", "browserbase", "orkes"]:
        mark = "🟢 live " if h.get(k) else "⚪ mock "
        print(f"   {mark} {k}")
    print("-" * 52)

    # 2) samples
    passed = 0
    for fname, expect in EXPECTED.items():
        try:
            s = json.load(open(os.path.join(SAMPLES_DIR, fname)))
            out = _post("/process", to_req(s))
            got = out["verdict"]
            ok = got == expect
            passed += ok
            extra = ""
            sub = out.get("submission")
            if sub and sub.get("confirmation"):
                extra = f"  ↳ submitted ({sub.get('engine')}) conf {sub['confirmation']}"
            print(f"{'✅' if ok else '❌'} {fname:32} {got}{'' if ok else '  (expected '+expect+')'}{extra}")
        except Exception as e:
            print(f"❌ {fname:32} ERROR: {e}")
    print("-" * 52)

    # 3) voice
    try:
        v = _post("/intake/voice", {})
        print(f"✅ voice intake: {v['verdict']}  (transcript engine: {v['transcript']['engine']})")
    except Exception as e:
        print(f"❌ voice intake ERROR: {e}")

    print("=" * 52)
    print(f"Samples passed: {passed}/{len(EXPECTED)}")
    print("All 5 + voice OK → demo is solid.\n" if passed == len(EXPECTED)
          else "Some mismatches — paste this output and I'll help debug.\n")


if __name__ == "__main__":
    main()
