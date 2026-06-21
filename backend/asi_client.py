"""
ASI:One LLM client (Fetch.ai).

ASI:One is OpenAI-compatible. We use it to turn a natural-language referral typed
into an ASI:One chat into the structured fields our pipeline needs — so the whole
prior-auth workflow completes inside an ASI:One conversation with no custom frontend.

  - ASI_ONE_API_KEY set -> real asi1-mini calls
  - otherwise           -> heuristic regex extraction (demo still works)

Get a key at https://asi1.ai (Developer / API keys).
"""
import os, re, json

ASI_ONE_API_KEY = os.getenv("ASI_ONE_API_KEY")
ASI_BASE = os.getenv("ASI_ONE_BASE_URL", "https://api.asi1.ai/v1")
ASI_MODEL = os.getenv("ASI_ONE_MODEL", "asi1-mini")
ASI_ON = bool(ASI_ONE_API_KEY)

EXTRACT_SYS = (
    "You extract structured fields from a clinic referral / prior-auth request typed in plain English. "
    "Return ONLY JSON with keys: patient_name, dob, diagnosis_code, requested_cpt, procedure, payer, "
    "member_id, npi. Use null for anything not stated."
)


def asi_chat(prompt: str, system: str = "You are a helpful prior-auth assistant.") -> str:
    """One-shot ASI:One completion. Returns text (empty string on failure)."""
    if not ASI_ON:
        return ""
    import requests
    try:
        r = requests.post(
            f"{ASI_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {ASI_ONE_API_KEY}", "Content-Type": "application/json"},
            json={"model": ASI_MODEL, "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}]},
            timeout=30)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception:
        return ""


def extract_referral(text: str) -> dict:
    """NL referral -> structured dict. ASI:One if available, else regex heuristics."""
    if ASI_ON:
        raw = asi_chat(text, EXTRACT_SYS)
        i, j = raw.find("{"), raw.rfind("}")
        if i >= 0:
            try:
                return json.loads(raw[i:j + 1])
            except Exception:
                pass
    return _heuristic(text)


def _heuristic(text: str) -> dict:
    t = text or ""
    icd = re.search(r"\b[A-TV-Z]\d{2}(?:\.\d{1,4})?\b", t)              # ICD-10
    cpt = re.search(r"\b(?:[A-Z]\d{4}|\d{5})\b", t)                    # CPT / HCPCS
    mid = re.search(r"\b[A-Z]{2,4}-\d{4}-\d{4}\b", t)                  # member id
    npi = re.search(r"\b\d{10}\b", t)                                  # NPI
    payer = next((p for p in ["UnitedHealthcare", "Aetna", "Cigna", "Humana",
                              "BlueShield", "Blue Cross", "Anthem", "Kaiser"]
                  if p.lower() in t.lower()), None)
    return {"patient_name": None, "dob": None,
            "diagnosis_code": icd.group(0) if icd else None,
            "requested_cpt": cpt.group(0) if cpt else None,
            "procedure": "", "payer": payer,
            "member_id": mid.group(0) if mid else None,
            "npi": npi.group(0) if npi else None}
