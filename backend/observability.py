"""
Decision-trace observability — Arize Phoenix.

Every agent step is logged as a structured span:
  - always       -> appended to traces.jsonl (a real, replayable audit log)
  - if Phoenix   -> also emitted as an OpenTelemetry span to Phoenix for tracing/eval

Phoenix is OSS and Berkeley-based. Run it locally with `phoenix serve` (default
http://localhost:6006) or set PHOENIX_COLLECTOR_ENDPOINT, then watch agent traces live.
No endpoint configured -> JSONL only, demo still runs.
"""
import os, json, time

_TRACE_FILE = os.path.join(os.path.dirname(__file__), "traces.jsonl")
PHOENIX_ENDPOINT = os.getenv("PHOENIX_COLLECTOR_ENDPOINT")

_tracer = None
PHOENIX_ON = False
try:
    if PHOENIX_ENDPOINT:
        import logging
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        # Export off the request path and in batches, so a span never blocks /process
        # and an unreachable Phoenix degrades quietly (traces.jsonl is still the audit log).
        logging.getLogger("opentelemetry.exporter.otlp.proto.http.trace_exporter").setLevel(logging.CRITICAL)
        logging.getLogger("opentelemetry.sdk.trace.export").setLevel(logging.CRITICAL)
        provider = TracerProvider()
        provider.add_span_processor(BatchSpanProcessor(
            OTLPSpanExporter(endpoint=PHOENIX_ENDPOINT.rstrip("/") + "/v1/traces")))
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer("referralguard")
        PHOENIX_ON = True
except Exception:
    PHOENIX_ON = False

# kept as an alias so older references keep working
ARIZE_ON = PHOENIX_ON


def log_span(session: str, name: str, attributes: dict):
    """Append one span to the local trace log (+ Phoenix if configured)."""
    span = {"ts": time.time(), "session": session, "span": name, "attributes": attributes}
    try:
        with open(_TRACE_FILE, "a") as f:
            f.write(json.dumps(span) + "\n")
    except Exception:
        pass
    if _tracer:
        try:
            with _tracer.start_as_current_span(name) as s:
                s.set_attribute("session.id", session)
                for k, v in attributes.items():
                    s.set_attribute(str(k), str(v))
        except Exception:
            pass
    return span
