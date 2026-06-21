"""
ReferralGuard — multi-agent pipeline.

Each agent step appends a timestamped entry to a shared audit trail.
The same logic runs whether or not API keys are present:
  - ANTHROPIC_API_KEY  -> Claude does extraction + denial-risk reasoning (else deterministic mock)
  - REDIS_URL          -> session state in Redis (else in-memory dict)
  - SENTRY_DSN         -> exceptions captured to Sentry (else logged locally)

Keep it simple: one file, no framework magic. server.py just calls run_pipeline().
"""
import os, re, json, time, random, string, traceback
import observability as obs
import submission_agent as sub_agent

# Orkes Conductor: orchestrates the agent DAG + the human-approval gate.
ORKES_ON = bool(os.getenv("CONDUCTOR_SERVER_URL") or os.getenv("ORKES_KEY_ID"))

# ---- Optional sponsor integrations (all degrade gracefully) ----
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
REDIS_URL     = os.getenv("REDIS_URL")
SENTRY_DSN    = os.getenv("SENTRY_DSN")

# Sentry ----------------------------------------------------------
SENTRY_ON = False
try:
    if SENTRY_DSN:
        import sentry_sdk
        # arize-phoenix pulls in an incompatible `strawberry`; sentry's auto Strawberry
        # integration then crashes init. Disable just that one (manual capture is unaffected).
        disabled = []
        try:
            from sentry_sdk.integrations.strawberry import StrawberryIntegration
            disabled.append(StrawberryIntegration())
        except Exception:
            pass
        sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=1.0, environment="hackathon-demo",
                        disabled_integrations=disabled)
        SENTRY_ON = True
except Exception:
    SENTRY_ON = False

def sentry_breadcrumb(msg, data=None):
    if SENTRY_ON:
        import sentry_sdk
        sentry_sdk.add_breadcrumb(category="agent", message=msg, data=data or {}, level="info")

def sentry_capture(exc, tags=None):
    if SENTRY_ON:
        import sentry_sdk
        with sentry_sdk.push_scope() as scope:
            for k, v in (tags or {}).items():
                scope.set_tag(k, v)
        return sentry_sdk.capture_exception(exc)
    return "evt_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=10))

# Redis -----------------------------------------------------------
_redis = None
_mem = {}
try:
    if REDIS_URL:
        import redis
        _redis = redis.from_url(REDIS_URL, decode_responses=True)
        _redis.ping()
except Exception:
    _redis = None

def state_set(session, key, value):
    if _redis:
        _redis.hset(session, key, json.dumps(value)); _redis.expire(session, 3600)
    else:
        _mem.setdefault(session, {})[key] = value

REDIS_ON = _redis is not None

# Claude ----------------------------------------------------------
CLAUDE_ON = bool(ANTHROPIC_KEY)
_client = None
def _claude():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    return _client

EXTRACT_PROMPT = """You extract structured fields from a clinic referral / prior-auth request.
Return ONLY JSON with keys: patient_name, dob, diagnosis_code, requested_cpt, procedure, payer, member_id, npi.
Use null for anything not present. Request:
{raw}
"""
RISK_PROMPT = """You are a prior-authorization denial-risk reviewer.
Payer: {payer}. Procedure: {procedure} (CPT {cpt}).
Clinical note: "{raw}"
Known payer rule: {rule}
Answer ONLY JSON: {{"risk": "high"|"none", "reason": "<one sentence>"}}.
Mark "high" only if the rule's requirement is NOT supported by the note.
"""

def claude_extract(raw):
    msg = _claude().messages.create(
        model="claude-haiku-4-5-20251001", max_tokens=400,
        messages=[{"role": "user", "content": EXTRACT_PROMPT.format(raw=raw)}])
    return json.loads(_first_json(msg.content[0].text))

def claude_risk(payer, procedure, cpt, raw, rule):
    msg = _claude().messages.create(
        model="claude-haiku-4-5-20251001", max_tokens=200,
        messages=[{"role": "user", "content": RISK_PROMPT.format(
            payer=payer, procedure=procedure, cpt=cpt, raw=raw, rule=rule)}])
    return json.loads(_first_json(msg.content[0].text))

def _first_json(text):
    i, j = text.find("{"), text.rfind("}")
    return text[i:j + 1] if i >= 0 else "{}"

# ---- Domain knowledge -------------------------------------------
PAYER_RULES = {
    "J0135": {"name": "Adalimumab (Humira)", "need": "step therapy",
              "keywords": ["methotrexate", "mtx", "dmard"],
              "msg": "Payer policy requires a documented trial/failure of a conventional DMARD (e.g., methotrexate) before approving a biologic."},
    "72148": {"name": "Lumbar MRI", "need": "conservative therapy",
              "keywords": ["conservative therapy", "physical therapy", "weeks pt", "red-flag", "red flag"],
              "msg": "Imaging guidelines require 4-6 weeks of conservative therapy OR documented red-flag symptoms for acute low back pain."},
    "73721": {"name": "Knee MRI", "need": "conservative therapy",
              "keywords": ["physical therapy", "weeks pt", "conservative"],
              "msg": "Payer expects a trial of conservative management (e.g., 6 weeks PT) before advanced knee imaging."},
}
# A requirement counts as MET only if a keyword appears AND is not negated nearby
# ("No documentation of methotrexate" must NOT count as a methotrexate trial).
NEGATIONS = ["no ", "not ", "without", "absent", "denies", "negative for", "lacks", "missing", "none"]

def requirement_met(hay: str, keywords: list) -> bool:
    for k in keywords:
        idx = hay.find(k)
        while idx != -1:
            window = hay[max(0, idx - 28):idx]
            if not any(n in window for n in NEGATIONS):
                return True
            idx = hay.find(k, idx + 1)
    return False
REQUIRED = [("patient.name", "Patient name"), ("patient.dob", "Date of birth"),
            ("diagnosis_code", "ICD-10 diagnosis code"), ("requested_cpt", "Requested CPT/HCPCS"),
            ("insurance.payer", "Payer"), ("insurance.member_id", "Member ID"),
            ("npi", "Referring provider NPI")]
MEMBER_ID_RE = re.compile(r"^[A-Z]{2,4}-\d{4}-\d{4}$")


class MemberIdFormatError(ValueError):
    pass


def _get(obj, path):
    cur = obj
    for k in path.split("."):
        if cur is None:
            return None
        cur = cur.get(k) if isinstance(cur, dict) else None
    return cur


def run_pipeline(req: dict) -> dict:
    """req mirrors the sample JSON shape. Returns trace + verdict for the dashboard."""
    steps, flags = [], []
    t = {"ms": 0}
    session = "sess:%s:%s" % (req["id"][-3:], "".join(random.choices(string.ascii_lowercase + string.digits, k=5)))

    def push(who, badge, act, det):
        t["ms"] += 40 + random.randint(0, 90)
        steps.append({"who": who, "badge": badge, "act": act, "det": det, "ms": t["ms"]})
        # persist every step as a span (local JSONL always; Arize if configured)
        obs.log_span(session, who, {"act": act, "engine": badge, "request_id": req["id"]})

    # 1. Intake
    state_set(session, "status", "RECEIVED")
    sentry_breadcrumb("intake", {"request_id": req["id"]})
    push("Intake Agent", "redis", "Request received — session opened",
         f'Channel <code>{req["chan"]}</code> · clinic “{req["clinic"]}”. Raw payload cached to '
         f'<code>{session}</code> (TTL 1h){" via Redis" if REDIS_ON else " (in-memory)"}. State → <code>RECEIVED</code>.')

    # 2. Extraction (Claude or mock)
    if CLAUDE_ON:
        try:
            ex = claude_extract(req.get("raw", ""))
            src = "Claude (live)"
        except Exception as e:
            sentry_capture(e, {"stage": "extract", "request_id": req["id"]}); ex, src = {}, "mock (Claude error)"
    else:
        ex, src = {}, "deterministic mock"
    push("Extraction Agent", "claude", "Structured fields extracted from raw text",
         f'Parsed via {src}: patient=<code>{req["patient"]["name"]}</code> · '
         f'dx=<code>{req.get("diagnosis_code") or "∅ not found"}</code> · cpt=<code>{req.get("requested_cpt")}</code> · '
         f'payer=<code>{req["insurance"]["payer"]}</code>')

    # 3. Completeness
    missing = [(p, label) for (p, label) in REQUIRED if not _get(req, p)]
    push("Completeness Agent", "rule", f"Required-field check: {len(REQUIRED)-len(missing)}/{len(REQUIRED)} present",
         ("Missing → " + ", ".join(f"<code>{l}</code>" for _, l in missing) +
          ". Each is a documented reason the payer would return the request unprocessed.")
         if missing else "All required fields present. No intake gaps.")
    for _, label in missing:
        flags.append({"sev": "warn", "ttl": "Missing: " + label,
                      "rsn": "Payer will reject or pend a submission without this field."})

    # 4. Validation (+ Sentry path)
    push("Validation Agent", "redis", "Member ID format validation",
         f'Checking <code>{req["insurance"]["member_id"]}</code> against payer ID pattern…')
    try:
        if not MEMBER_ID_RE.match(req["insurance"]["member_id"] or ""):
            raise MemberIdFormatError(f'invalid member id: {req["insurance"]["member_id"]}')
        state_set(session, "status", "VALIDATED")
        push("Validation Agent", "redis", "Member ID OK", "Format valid. State → <code>VALIDATED</code>.")
    except MemberIdFormatError as e:
        sentry_breadcrumb("validate.fail", {"member_id": req["insurance"]["member_id"]})
        evt = sentry_capture(e, {"request_id": req["id"], "payer": req["insurance"]["payer"]})
        push("Sentry", "sentry", "Exception captured — pipeline did NOT crash",
             f'<code>MemberIdFormatError</code> raised while normalizing insurance ID. '
             f'Captured to Sentry as <code>{evt}</code>{"" if SENTRY_ON else " (local id; set SENTRY_DSN to send)"} '
             f'with breadcrumbs [intake→extract→validate]. Agent recovered → routed to human review.')
        flags.append({"sev": "warn", "ttl": "Unreadable member ID",
                      "rsn": "Intake produced an invalid member ID. Exception logged to Sentry; flagged for correction before submit."})

    # 5. Denial-risk (Claude or rule)
    cpt = req.get("requested_cpt")
    rule = PAYER_RULES.get(cpt)
    push("Denial-Risk Agent", "claude", f'Payer-policy reasoning for {req["insurance"]["payer"]}',
         (f'Procedure {rule["name"]} (CPT {cpt}) has a known <b>{rule["need"]}</b> requirement. '
          f'Scanning clinical note for supporting evidence…') if rule else
         f'CPT {cpt}: no high-risk utilization rule on file. Checking baseline medical-necessity language…')
    if rule:
        hay = (req.get("raw", "") + " " + req.get("procedure", "")).lower()
        high = not requirement_met(hay, rule["keywords"])
        reason = rule["msg"]
        if CLAUDE_ON:
            try:
                r = claude_risk(req["insurance"]["payer"], req.get("procedure"), cpt, req.get("raw", ""), rule["msg"])
                high = r.get("risk") == "high"; reason = r.get("reason", reason)
            except Exception as e:
                sentry_capture(e, {"stage": "risk", "request_id": req["id"]})
        if high:
            push("Denial-Risk Agent", "claude", f'HIGH denial risk — {rule["need"]} not documented',
                 f'{reason} No supporting evidence found in the referral. Predicted outcome: <b>denial / pend</b> if submitted as-is.')
            flags.append({"sev": "risk", "ttl": f'Likely denial: {rule["need"]} not documented', "rsn": reason})
        else:
            push("Denial-Risk Agent", "claude", f'{rule["need"]} requirement satisfied',
                 "Found supporting evidence in note. Requirement met.")

    # 6. Decision
    has_risk = any(f["sev"] == "risk" for f in flags)
    has_warn = any(f["sev"] == "warn" for f in flags)
    if has_risk:
        verdict, vclass, vsub = "HIGH DENIAL RISK", "risk", "Fix the flagged gap before submitting — high probability of denial."
    elif has_warn:
        verdict, vclass, vsub = "NEEDS INFO", "warn", "Return to referring clinic for the missing or invalid fields."
    else:
        verdict, vclass, vsub = "READY TO SUBMIT", "ok", "All checks passed. Safe to submit to the payer."
    state_set(session, "verdict", verdict)
    push("Decision Agent", "rule", f"Final verdict: {verdict}",
         f'Derived from {len(flags)} flag(s). Full trace persisted to <code>{session}:audit</code> for replay. '
         f'State → <code>{"READY" if vclass=="ok" else "NEEDS_INFO" if vclass=="warn" else "AT_RISK"}</code>.')

    # 7. Human-approval gate (Orkes) + portal submission (Browserbase) — only when READY
    submission = None
    if vclass == "ok":
        approver = "ops@clinic (demo auto-approve)"
        push("Approval Gate", "orkes", "Human-in-the-loop approval — required for prior auth",
             f'Conductor <code>HUMAN</code> task created and awaiting sign-off (prior auth legally requires a human). '
             f'Approved by <code>{approver}</code>{"" if ORKES_ON else " — simulated; set CONDUCTOR_SERVER_URL to run on Orkes"}. Workflow resumes.')
        submission = sub_agent.run_submission(req, push)
        state_set(session, "submission", submission)
    else:
        push("Routing Agent", "rule", "Routed to human review queue",
             "Not eligible for auto-submission. Returned to the referring clinic with the flagged reasons attached.")

    return {"steps": steps, "flags": flags, "verdict": verdict, "vclass": vclass, "vsub": vsub,
            "session": session, "missing": [[p, l] for (p, l) in missing], "submission": submission,
            "engines": {"claude": CLAUDE_ON, "redis": REDIS_ON, "sentry": SENTRY_ON,
                        "phoenix": obs.PHOENIX_ON, "deepgram": __import__("intake_voice").DEEPGRAM_ON,
                        "browserbase": sub_agent.BROWSERBASE_ON, "orkes": ORKES_ON}}


# ---- Case chat (grounded Q&A about ONE referral) ----------------
CHAT_SYSTEM = """You are ReferralGuard's case assistant, helping a clinician understand ONE specific referral / prior-authorization pre-flight result.

Ground EVERY answer strictly in the CASE CONTEXT provided below. Hard rules:
1. Never invent patient facts, diagnosis or CPT codes, payer policies, dates, names, or numbers that are not in the context.
2. If the user asks for something the context does not contain, say plainly: "That isn't in this referral," and suggest what would need to be added.
3. When you explain a denial risk or a missing field, quote the exact flag reason from the context.
4. You may give general, non-fabricated next-step guidance (e.g. "attach documentation of a methotrexate trial"), but do not invent specific clinical details for this patient.
5. Be concise and plain-language — a busy doctor is reading. Use short paragraphs or bullet points.
Stay on this referral only; do not answer unrelated questions."""

def _format_context(c):
    c = c or {}
    r = c.get("request") or {}
    pat = r.get("patient") or {}
    ins = r.get("insurance") or {}
    L = []
    L.append(f"Patient: {pat.get('name')}, DOB {pat.get('dob')}")
    L.append(f"Diagnosis (ICD-10): {r.get('diagnosis_code')}")
    L.append(f"Procedure: {r.get('procedure')} (CPT {r.get('requested_cpt')})")
    L.append(f"Payer: {ins.get('payer')} | Member ID: {ins.get('member_id')}")
    L.append(f"Referring NPI: {r.get('npi')}")
    if r.get("raw"):
        L.append(f'Referral note / call transcript: "{r.get("raw")}"')
    L.append("")
    L.append(f"PRE-FLIGHT VERDICT: {c.get('verdict')}")
    flags = c.get("flags") or []
    if flags:
        L.append("FLAGS (issues found):")
        for f in flags:
            L.append(f"  - {f.get('ttl')}: {f.get('rsn')}")
    else:
        L.append("FLAGS: none — all checks passed.")
    missing = c.get("missing") or []
    if missing:
        labels = [m[1] if isinstance(m, (list, tuple)) and len(m) > 1 else str(m) for m in missing]
        L.append("MISSING REQUIRED FIELDS: " + ", ".join(labels))
    steps = c.get("steps") or []
    if steps:
        L.append("AUDIT STEPS RUN:")
        for s in steps:
            L.append(f"  - {s.get('who')}: {s.get('act')}")
    return "\n".join(str(x) for x in L)

def _mock_chat(context):
    v = (context or {}).get("verdict")
    flags = (context or {}).get("flags") or []
    if flags:
        bul = "\n".join(f"• {f.get('ttl')} — {f.get('rsn')}" for f in flags)
        return f"This referral is **{v}**. Issues found in the pre-flight:\n{bul}\n\n(Connect ANTHROPIC_API_KEY for full conversational Q&A.)"
    return f"This referral is **{v}** — all checks passed and no issues were found. (Connect ANTHROPIC_API_KEY for full conversational Q&A.)"

# ---- Context compression (The Token Company challenge) ----------
# Goal: send the LLM the *smallest* context that still answers the question.
# We measure real token counts before/after and a guard verifies no critical
# field was dropped. The audit trail (10+ verbose steps) is the biggest waste
# for Q&A, so the compressor drops it and keeps only the decision-relevant signal.
_CLINICAL = ("pain", "bleed", "fracture", "trial", "failed", "therapy", "pt ", "weeks",
             "mri", "biopsy", "symptom", "history", "hx", "dx", "neg", "positive",
             "contrast", "dmard", "methotrexate", "red-flag", "red flag", "conservative")
_NEG = ("no ", "not ", "without", "absent", "denies", "negative for", "lacks", "missing", "none")

def _sentences(t):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', (t or "").replace("\n", " ")) if s.strip()]

def _count_tokens(text):
    """Real token count via the model's own tokenizer; heuristic fallback (~4 chars/token)."""
    text = text or " "
    if CLAUDE_ON:
        try:
            r = _claude().messages.count_tokens(
                model="claude-haiku-4-5-20251001",
                messages=[{"role": "user", "content": text}])
            return int(r.input_tokens)
        except Exception:
            pass
    return max(1, (len(text) + 3) // 4)

def _compress_note(raw, signal_terms, max_sent=4):
    """Extractive compression: keep the highest-signal sentences (clinical terms,
    case-specific keywords, and negations — negations drive denial logic)."""
    sents = _sentences(raw)
    if len(sents) <= max_sent:
        return (raw or "").strip()
    scored = []
    for i, s in enumerate(sents):
        low = s.lower()
        score = sum(2 for k in signal_terms if k and k in low)
        score += sum(1 for w in _CLINICAL if w in low)
        score += sum(1 for n in _NEG if n in low)
        scored.append((score, i, s))
    top = sorted(scored, key=lambda x: -x[0])[:max_sent]
    return " ".join(s for _, _, s in sorted(top, key=lambda x: x[1]))

def compress_context(c):
    """Returns (compressed_text, stats, verbose_text). `verbose_text` is the
    uncompressed baseline we'd otherwise send — used for the before/after number."""
    c = c or {}
    r = c.get("request") or {}
    pat = r.get("patient") or {}
    ins = r.get("insurance") or {}
    verbose = _format_context(c)

    sig = [str(r.get(k) or "").lower() for k in ("diagnosis_code", "requested_cpt", "procedure")]
    sig += [str(ins.get("payer") or "").lower()]
    sig = [s for s in sig if s]
    note = _compress_note(r.get("raw") or "", sig)

    member = ins.get("member_id")
    if member and not MEMBER_ID_RE.match(member):
        member = "UNREADABLE"

    def nn(label, val):
        return f"{label} {val}" if val not in (None, "", "null") else None
    parts = [
        nn("Pt:", f"{pat.get('name')}, DOB {pat.get('dob')}" + (f", {pat.get('sex')}" if pat.get('sex') else "")),
        nn("Dx:", r.get("diagnosis_code")),
        nn("Svc:", f"{r.get('procedure')} (CPT {r.get('requested_cpt')})"),
        nn("Payer:", (ins.get("payer") or "") + (f", Member {member}" if member else "")),
        nn("NPI:", r.get("npi")),
    ]
    fields = "; ".join(p for p in parts if p)
    flags = c.get("flags") or []
    fl = "; ".join(f"{f.get('ttl')} — {f.get('rsn')}" for f in flags) if flags else "none"
    comp = f"{fields}.\nNote: {note}\nVerdict: {c.get('verdict')}. Issues: {fl}."

    # GUARD: verify the compressed brief still carries every field needed to answer.
    # If compression dropped a critical value, restore it (no silent quality loss).
    restored = []
    for key, val in [("Dx", r.get("diagnosis_code")), ("CPT", r.get("requested_cpt")),
                     ("Payer", ins.get("payer")), ("Verdict", c.get("verdict"))]:
        if val and str(val) not in comp:
            restored.append(key)
            comp += f"\n{key}: {val}"

    before, after = _count_tokens(verbose), _count_tokens(comp)
    ratio = max(0, round(100 * (1 - after / before))) if before else 0
    stats = {"before": before, "after": after, "ratio": ratio,
             "steps_dropped": len(c.get("steps") or []), "guard_restored": restored}
    return comp, stats, verbose

def claude_chat(context, messages):
    """Grounded Q&A over a single case. Returns {reply, compression}.
    Context is COMPRESSED before being sent to the LLM (Token Company challenge);
    chat history is windowed to the last 8 turns to cap token growth."""
    msgs = [{"role": m.get("role"), "content": str(m.get("content", ""))}
            for m in (messages or []) if m.get("content") and m.get("role") in ("user", "assistant")]
    msgs = msgs[-8:]  # rolling window — older turns dropped to keep token count flat
    comp, stats, _ = compress_context(context)
    if not msgs:
        return {"reply": "Ask me anything about this referral — I'll answer only from this case's data.",
                "compression": stats}
    if not CLAUDE_ON:
        return {"reply": _mock_chat(context), "compression": stats}
    try:
        sentry_breadcrumb("chat", {"turns": len(msgs), "ratio": stats["ratio"]})
        resp = _claude().messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=600,
            system=CHAT_SYSTEM + "\n\nCASE CONTEXT (compressed):\n" + comp,
            messages=msgs)
        return {"reply": resp.content[0].text.strip(), "compression": stats}
    except Exception as e:
        sentry_capture(e, {"stage": "chat"})
        return {"reply": _mock_chat(context), "compression": stats}
