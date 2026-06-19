# api/app.py — Flask backend: PDF upload → pdfplumber → Claude → JSON BoQ

import os                          # os gives access to environment variables (like Environment.GetEnvironmentVariable in C#)
import io                          # io.BytesIO is an in-memory byte buffer — like MemoryStream in C#
import re                          # re is Python's regex module — like System.Text.RegularExpressions in C#
import json                        # json parses/serialises JSON — like System.Text.Json in C#
import pdfplumber                  # third-party library that opens PDFs and extracts text page by page
import anthropic                   # official Anthropic Python SDK — wraps the Claude REST API
from flask import Flask, request, jsonify, send_file, session, send_from_directory, make_response  # session = server-signed cookie dict, like HttpContext.Session in ASP.NET
from jsonschema import Draft202012Validator, ValidationError
from supabase import create_client # supabase-py v2 — wraps the Supabase REST API for auth
from rates import RATES_DB         # our local dict of 2025-2026 UK construction rates (material + labour per unit)
from export_pdf import generate_boq_pdf  # ReportLab PDF generator for the /export endpoint
from export_excel import generate_boq_excel
from totals import _effective_line_total  # canonical line-total — single source of truth
from measurement_import import parse_measurements, MeasurementImportError  # CSV/XLSX measurement parser
from classification import classify_measurements, classification_options, MeasurementClassificationError  # deterministic NRM2/rate classifier
from measurement_hub import build_boq_from_measurements, validate_boq_structure  # measurement → BoQ conversion
from user_overrides import load_overrides, save_override, delete_override  # per-user persistent classification overrides
from mapping_loader import load_mappings_at_startup, get_loader_status  # Bluebeam Term Mapping loader
from measurement_classifier import classify_measurement  # Spreadsheet-based measurement classification
import time, statistics
import copy                         # deep-copy BOQ_OUTPUT_SCHEMA into the tool input_schema without mutating the validator's copy
import threading                  # only used for a stable per-request key in the in-flight tracker below
_processing_times = []
_start_time = time.time()
_ai_status = None

# In-flight request registry, read by the gunicorn worker_abort hook in
# gunicorn.conf.py so a killed/timed-out worker can log WHICH request it was
# serving (gevent worker kills otherwise leave no trace in Railway's logs).
# Keyed by greenlet/thread id (threading.get_ident() returns the greenlet id once
# gunicorn's gevent worker has monkey-patched the process).
_INFLIGHT_REQUESTS: dict = {}

# ── Timeout budget (ONE place; the three layers must stay strictly ordered) ──────
# A /process upload is a single long request: a STREAMING completion toward
# BOQ_MAX_OUTPUT_TOKENS against the ~6,500-token NRM2 SYSTEM_PROMPT routinely takes
# SEVERAL MINUTES even for a tiny PDF (the prompt forces a full 41-section bill).
# The three timeouts below must satisfy  anthropic < frontend < gunicorn  so that
# whichever limit trips, the browser still receives a clean, CORS-decorated reply:
#   • ANTHROPIC ─ per-read/inactivity timeout on the Claude call (we also stream,
#                 so this only fires if tokens genuinely stop arriving).
#   • FRONTEND  ─ vq-pages.jsx AbortController (kept in sync there).
#   • GUNICORN  ─ worker --timeout in api/gunicorn.conf.py (kept in sync there).
# These last two are recorded here only so the startup log can surface all three
# together — a mismatch like the old 120s-anthropic-vs-180s-gunicorn is then
# obvious in Railway logs at boot instead of being discovered via burnt credits.
ANTHROPIC_CLIENT_TIMEOUT_S = 600   # 10 min — inactivity headroom for a full 32k-token bill
FRONTEND_ABORT_TIMEOUT_S   = 650   # mirrors VQ_UPLOAD_TIMEOUT_MS in vq-pages.jsx
GUNICORN_WORKER_TIMEOUT_S  = 660   # mirrors `timeout` in api/gunicorn.conf.py

# ── BoQ output-token budget ──────────────────────────────────────────────────────
# The model writes the ENTIRE NRM2 bill as one JSON object, and the SYSTEM_PROMPT
# demands a lot of it: up to 41 work sections, a mandatory trades checklist, a 5.41
# BWIC section, a risk_schedule and an assumptions_register — and every line item is
# verbose (description, rate_key, quantity, unit, drawing_ref, dimension_string, cdp,
# performance_requirement). A full bill routinely blew past the OLD 16,000-token cap,
# so the stream stopped with stop_reason=="max_tokens" mid-object: the JSON was
# unparseable, /process 502'd, and the (billed) output was wasted.
#
# WHY 32,000 — and pointedly NOT the full ceiling:
#   • The Sonnet 4.x SYNCHRONOUS Messages API ceiling is 64,000 output tokens, so the
#     old 16,000 used only ~25% of the available headroom.
#   • 32,000 roughly DOUBLES the prior headroom while still controlling two real
#     trade-offs: (a) COST — output tokens bill at the higher per-token rate, so we
#     do not reserve 64k we rarely need; and (b) LATENCY — more tokens means a longer
#     stream, and the whole generation must still finish within the timeout budget
#     ABOVE. Streaming makes ANTHROPIC_CLIENT_TIMEOUT_S an INACTIVITY timeout, so a
#     longer-but-healthy stream is fine as long as tokens keep flowing — the
#     "AI CALL IN PROGRESS" heartbeat in _run_boq_pipeline distinguishes a
#     slow-but-alive stream from a genuinely stuck one in Railway logs.
#   • Raise toward 64,000 ONLY if truncation still occurs on the very largest real
#     bills; the salvage path in _run_boq_pipeline now degrades gracefully if it does.
BOQ_MAX_OUTPUT_TOKENS = 32000

app = Flask(__name__)              # create the Flask app instance; __name__ tells Flask the root path (like WebApplication.CreateBuilder in C#)

# Surface the whole timeout budget in one line at import/boot so any future
# layer-mismatch is visible in Railway logs immediately (point 6 of the fix).
app.logger.info(
    "TIMEOUT_BUDGET: anthropic_client=%ss frontend_abort=%ss gunicorn_worker=%ss "
    "(must stay ordered anthropic < frontend < gunicorn)",
    ANTHROPIC_CLIENT_TIMEOUT_S, FRONTEND_ABORT_TIMEOUT_S, GUNICORN_WORKER_TIMEOUT_S,
)

# Flask sessions are signed cookies; SECRET_KEY is the signing key.
# Without it sessions cannot be trusted.  Set this env var in production —
# the urandom fallback regenerates on every restart, invalidating all sessions.
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY') or os.urandom(32)
app.config['SESSION_COOKIE_SECURE']   = os.environ.get('FLASK_ENV') != 'development'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'None'

# Browsers always send the bare host (scheme + host only, never a path) as Origin.
_ALLOWED_ORIGINS = [
    'https://ojburnsey-tech.github.io',
    'https://vulcan-production-d039.up.railway.app',
    'http://localhost:8080',
    'http://localhost:5001',
]


# ── OPTIONS short-circuit ─────────────────────────────────────────────────────
# Routes declared with methods=["POST"] return 405 for OPTIONS before any
# after_request hook fires.  This before_request intercepts OPTIONS first and
# returns an empty 204 — the after_request hook below then adds the CORS headers
# to that response, same as it does for every other response.
@app.before_request
def handle_options():
    if request.method == 'OPTIONS':
        return make_response('', 204)


# ── In-flight request tracking (for worker-kill diagnostics) ──────────────────
# Record what this greenlet is working on so gunicorn's worker_abort hook can name
# the request if the worker is killed (e.g. a /process that outran the timeout).
@app.before_request
def _track_inflight():
    if request.method == 'OPTIONS':
        return
    _INFLIGHT_REQUESTS[threading.get_ident()] = (request.method, request.path, time.time())


# teardown_request runs on success AND on normal exceptions, clearing the entry.
# A hard worker kill (GreenletExit) skips it on purpose — that leaves the entry
# behind precisely so worker_abort can report the request that was still running.
@app.teardown_request
def _untrack_inflight(exc=None):
    _INFLIGHT_REQUESTS.pop(threading.get_ident(), None)


# ── CORS headers on every response ───────────────────────────────────────────
# Single place that sets Access-Control-* headers.  Runs after every request
# including the 204 returned above, so both preflight and real POST responses
# always carry the right headers.
@app.after_request
def add_cors_headers(response):
    origin = request.headers.get('Origin', '')
    if origin in _ALLOWED_ORIGINS:
        response.headers['Access-Control-Allow-Origin']      = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Methods']     = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers']     = 'Content-Type, Authorization'
        response.headers['Access-Control-Max-Age']           = '86400'
        response.headers['Vary']                             = 'Origin'
    return response


# Belt-and-suspenders: if an unhandled exception reaches WSGI before after_request
# fires (e.g. GreenletExit from a gunicorn worker kill), this handler still sets
# CORS headers so the browser can read the error body instead of seeing an opaque
# CORS failure.
@app.errorhandler(Exception)
def handle_unhandled_exception(exc):
    app.logger.exception(
        "UNHANDLED_EXCEPTION in request: method=%s path=%s exception_type=%s exception_message=%s",
        request.method,
        request.path,
        type(exc).__name__,
        str(exc)
    )
    response = jsonify({"error": "An unexpected server error occurred. Please try again."})
    response.status_code = 500
    origin = request.headers.get('Origin', '')
    if origin in _ALLOWED_ORIGINS:
        response.headers['Access-Control-Allow-Origin']      = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Vary']                             = 'Origin'
    return response

@app.route('/api/health', methods=['GET'])
def health_check():
    global _ai_status
    if _ai_status != "online":
        try:
            _api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not _api_key:
                raise RuntimeError("no key")
            _hc_client = anthropic.Anthropic(api_key=_api_key, timeout=10.0)
            _hc_client.messages.create(model="claude-sonnet-4-6", max_tokens=1, messages=[{"role": "user", "content": "ping"}])
            _ai_status = "online"
        except Exception:
            _ai_status = "offline"
    avg = round(statistics.mean(_processing_times[-50:]), 1) if _processing_times else None
    return jsonify({"ai_engine": _ai_status, "uptime_seconds": int(time.time() - _start_time), "avg_processing_seconds": avg}), 200


# ── Supabase client ───────────────────────────────────────────────────────────────────
# The anon key is sufficient for client-side auth operations (sign up, sign in).
# Read from environment so the key never appears in source — like IConfiguration in C#.
_SB_URL = os.environ.get('SUPABASE_URL', '')
_SB_KEY = os.environ.get('SUPABASE_ANON_KEY', '')
# create_client returns None-safe — we guard every usage with `if not _supabase` below
_supabase = create_client(_SB_URL, _SB_KEY) if (_SB_URL and _SB_KEY) else None

# Optional service-role key for table operations. The anon role typically has no
# privileges on application tables (Postgres 42501 "permission denied"), so data
# access must run as either service_role or the authenticated user. Every query in
# this file filters by user_id, so the service client never leaks across users.
_SB_SERVICE_KEY = (os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
                   or os.environ.get('SUPABASE_SERVICE_KEY', ''))
_supabase_admin = create_client(_SB_URL, _SB_SERVICE_KEY) if (_SB_URL and _SB_SERVICE_KEY) else None


# ── Bluebeam Term Mapping Loader ───────────────────────────────────────────────
# Load measurement classification mappings at startup (once, cached in memory).
_mappings_loaded_ok, _mappings_loaded_msg = load_mappings_at_startup()
if _mappings_loaded_ok:
    import logging
    logging.getLogger(__name__).info(f"Mappings: {_mappings_loaded_msg}")
else:
    import logging
    logging.getLogger(__name__).warning(f"Mappings: {_mappings_loaded_msg}")


def _db_client(token=None):
    """Supabase client for table reads/writes.

    Prefers the service-role client when SUPABASE_SERVICE_ROLE_KEY is set.
    Otherwise builds a per-request client that forwards the caller's JWT, so
    PostgREST executes as the `authenticated` role and RLS policies keyed on
    auth.uid() apply. A fresh client per request keeps tokens from leaking
    between concurrent requests.
    """
    if _supabase_admin:
        return _supabase_admin
    if not (_SB_URL and _SB_KEY):
        return None
    client = create_client(_SB_URL, _SB_KEY)
    client.postgrest.auth(token or _get_bearer_token())
    return client


def _auth_error_msg(exc: Exception) -> str:
    """Extract a readable sentence from a supabase-py / gotrue exception.
    gotrue wraps errors as JSON strings; fall back to the raw str() if parsing fails."""
    raw = str(exc)
    try:
        data = json.loads(raw)                         # gotrue may wrap: {"code":..., "message":"..."}
        return data.get('message') or data.get('msg') or raw
    except Exception:
        return raw or "Authentication failed."


def _get_bearer_token() -> str:
    """Return the JWT from 'Authorization: Bearer <token>', or '' if absent."""
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return auth[7:].strip()
    return ''


def _authenticated_user():
    """Resolve the Supabase user from the Bearer token.

    Returns (user, None) on success, or (None, (response, status)) on failure so
    callers can `return error` immediately — like a TryGetUser out-pattern in C#.
    """
    if not _supabase:
        return None, (jsonify({"error": "Auth not configured — set SUPABASE_URL and SUPABASE_ANON_KEY."}), 503)
    token = _get_bearer_token()
    if not token:
        return None, (jsonify({"error": "Authentication required. Please sign in."}), 401)
    try:
        # get_user validates the JWT against Supabase and returns the owning user
        res  = _supabase.auth.get_user(token)
        user = getattr(res, "user", None)
    except Exception as exc:
        return None, (jsonify({"error": _auth_error_msg(exc)}), 401)
    if not user:
        return None, (jsonify({"error": "Authentication required. Please sign in."}), 401)
    return user, None


# Optional project columns accepted from the client on create/update.
_PROJECT_EXTRA_FIELDS = {"client_name", "contract_type", "location_factor",
                         "notes_for_ai", "auto_delete_days", "description"}

# Statuses the app understands — kept in sync with the projects_status_check
# constraint in supabase_schema.sql. Anything else is dropped so the column
# default decides, rather than letting an unknown value hit the constraint.
_PROJECT_STATUSES = {"draft", "processing", "completed", "archived", "in_review", "signed_off"}


def _insert_project(db, user_id, name, page_count, estimated_value, boq_data, status, extra=None):
    """Insert a single project row owned by user_id and return the created row dict.

    Shared by POST /projects and the auto-save step in /process so both write the
    same shape. Raises on failure — callers decide whether that is fatal.
    `extra` may carry the optional setup fields (client, contract type, etc.).
    """
    row = {
        "user_id":         user_id,
        "name":            name,
        "page_count":      page_count,
        "estimated_value": estimated_value,
        "boq_data":        boq_data,
    }
    if status in _PROJECT_STATUSES:
        row["status"] = status
    if extra:
        row.update({k: v for k, v in extra.items() if k in _PROJECT_EXTRA_FIELDS})

    # Live databases have drifted: some carry a stricter projects_status_check
    # constraint that rejects 'draft' (Postgres error 23514). Until the schema
    # script is re-run, fall back through values every known constraint accepts
    # rather than failing the create outright.
    attempts = [row]
    if "status" in row:
        attempts.append({k: v for k, v in row.items() if k != "status"})  # column default
    attempts.append({**row, "status": "processing"})
    attempts.append({**row, "status": "completed"})

    last_exc = None
    for attempt in attempts:
        try:
            res = db.table("projects").insert(attempt).execute()
            # supabase-py returns the inserted rows in res.data (a list) when returning='representation'
            return res.data[0] if getattr(res, "data", None) else None
        except Exception as exc:
            if "projects_status_check" not in str(exc):
                raise
            last_exc = exc
    raise last_exc


def _sum_line_totals(boq_data) -> float:
    """Sum every item's line_total across all trade groups in an enriched BoQ.

    Mirrors the outer-shape normalisation in _enrich_boq so it works whether the
    BoQ is a list of groups, a {bill_of_quantities: [...]} wrapper, or {trades: [...]}.
    """
    if isinstance(boq_data, dict):
        groups = boq_data.get('bill_of_quantities') or boq_data.get('trades') or []
    elif isinstance(boq_data, list):
        groups = boq_data
    else:
        return 0.0

    total = 0.0
    for group in groups:
        if not isinstance(group, dict):
            continue
        for item in (group.get('items') or group.get('line_items') or []):
            if isinstance(item, dict):
                total += _effective_line_total(item, {})
    return round(total, 2)


def _extract_claude_text(response) -> str:
    """Join all text blocks returned by Claude into one response string."""
    return "".join(
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
    ).strip()


def _extract_tool_use_input(response):
    """Return the .input dict from the first tool_use block in a Message, or None.

    Under forced tool_choice the model answers with a tool_use block whose .input the
    SDK has already parsed into a dict (accumulated across the stream with jiter
    partial_mode, so even a max_tokens truncation yields the valid-so-far portion).
    Reading .input here is the definitive fix for the two Railway-logged 502 bugs:
      Bug 1 — no text block means no ```json markdown fence to trip json.loads;
      Bug 2 — the dict shape is schema-driven, not free-text-guessed.
    """
    for block in getattr(response, "content", None) or []:
        if getattr(block, "type", None) == "tool_use":
            inp = getattr(block, "input", None)
            if isinstance(inp, dict):
                return inp
    return None


def _strip_code_fence(text: str) -> str:
    """Strip a markdown code fence Claude may wrap JSON in despite being told not to.

    Railway logs (POST /process → 502) showed raw_text starting with ```json then a
    newline, so `json.loads` failed at 'line 1 column 1 (char 0)'. Prose instructions
    do NOT reliably suppress fences, so the text path must defend against them:
      • removes a leading ``` or ```json (any language tag), tolerating surrounding
        whitespace and the newline after the opening fence;
      • removes a trailing ```;
      • returns the text unchanged when there is no fence (always safe to call).
    Only fence-stripping happens here; the riskier first-'{'/last-'}' extraction is a
    separate helper applied by the pipeline ONLY after the de-fenced text still fails
    to parse, so it can never corrupt valid JSON whose strings contain braces.
    """
    if not text:
        return text
    s = text.strip()
    if s.startswith("```"):
        nl = s.find("\n")                  # drop the opening fence line (``` plus optional lang tag)
        s = s[nl + 1:] if nl != -1 else s[3:]
        s = s.rstrip()
        if s.endswith("```"):              # drop the trailing closing fence
            s = s[:-3]
    return s.strip()


def _extract_first_json_object(text):
    """Last-resort parse of the substring from the first '{' to the last '}'.

    Used ONLY after fence-stripping still fails to parse, so it cannot corrupt
    otherwise-valid JSON; it strips any leading/trailing prose the model added around
    the object. Returns a dict or None.
    """
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        obj = json.loads(text[start:end + 1])
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _log_claude_response(attempt: str, response) -> None:
    usage = getattr(response, "usage", None)
    app.logger.info(
        "Claude response diagnostics: attempt=%s stop_reason=%s "
        "usage.input_tokens=%s usage.output_tokens=%s",
        attempt,
        getattr(response, "stop_reason", None),
        getattr(usage, "input_tokens", None),
        getattr(usage, "output_tokens", None),
    )


SYSTEM_PROMPT = (
    "You are a United Kingdom and Northern Ireland quantity surveyor. Analyse the construction specification and "
    "produce a professional Bill of Quantities for a UK residential construction project. "
    "For each line item, set the rate_key field to the single most appropriate key from "
    "this exact list — do not invent keys, do not modify keys, copy them exactly as shown:\n\n"
    + "\n".join(f"- {k}" for k in RATES_DB.keys())
    + "\n\nRules:\n"
    "- Every item MUST have a rate_key from the list above.\n"

    # ── Groundworks ──────────────────────────────────────────────────────────
    "- CRITICAL GROUNDWORKS RULE: Excavation and disposal items must always be measured in m³ "
    "(volume), never m² (area). Calculate excavation volume as: plan area (m²) × excavation "
    "depth (m). For a standard domestic extension floor slab, assume 0.15m depth unless the "
    "specification states otherwise. Apply a 30% bulking factor to net excavation volume for "
    "disposal quantities. Example: 45m² plan area → 45 × 0.15 = 6.75m³ excavation → "
    "6.75 × 1.30 = 8.78m³ disposal off site.\n"

    # ── Wetroom tanking ───────────────────────────────────────────────────────
    "- Wetroom tanking (rate_key: wetroom_tanking_system) is measured in m². "
    "Measure the floor area plus wall area up to 1800mm height for all wetroom/shower "
    "enclosure areas. Do not use qty: 1 for this item.\n"
    "- WETROOM TANKING RULE: Wetroom tanking (rate_key: wetroom_tanking_system) is "
    "measured in m². Measure the floor area plus wall area up to 1800mm height for "
    "all wetroom and shower enclosure areas. Never set quantity to 1 for this item.\n"

    # ── Double-counting prevention ────────────────────────────────────────────
    "- DOUBLE-COUNTING RULE: Never measure the same physical work in both a composite item "
    "and a constituent item. For cavity walls: choose either a single composite item covering "
    "the full wall build-up (both leaves, insulation, ties) OR separate items for each "
    "component — never both. If you use a composite cavity wall item, do not add separate "
    "items for the outer leaf, inner leaf, or wall ties.\n"

    # ── Plasterboard double-counting prevention ───────────────────────────────
    "- Plasterboard double-counting prevention:\n"
    "  * Stud partitions: the composite stud partition rate already includes "
    "plasterboard to both faces. Never add separate plasterboard line items "
    "for the faces of stud partitions. If a stud partition item exists, "
    "plasterboard to that partition is already priced.\n"
    "  * Dot-and-dab plasterboard to masonry: measure to one face only — the "
    "masonry face receiving the board. Do not measure the reverse face.\n"
    "  * Internal partitions of any construction type: never measure plasterboard "
    "to both faces. One face only, always.\n"
    "  * Ceiling plasterboard and plasterboard to external walls or soffits are "
    "measured independently and are not affected by this rule.\n"

    # ── Missing trades checklist ──────────────────────────────────────────────
    "- MANDATORY TRADES CHECKLIST: For any residential extension or new build, you MUST "
    "include or explicitly exclude every item in this list. If the input drawings or "
    "specification do not provide enough information to measure an item, insert a clearly "
    "labelled Provisional Sum with a note stating what information is missing. The trades "
    "to check are: (1) first fix electrical — consumer unit, cabling, back boxes; "
    "(2) second fix electrical — sockets, switches, luminaires; "
    "(3) plumbing first fix — pipework, soil stack connections; "
    "(4) plumbing second fix — sanitaryware, taps, shower fittings; "
    "(5) structural steelwork — if the input references any SE or structural drawing; "
    "(6) internal door leaves — supply and hang, separate from door linings; "
    "(7) floor finishes — screed, tiling, or timber flooring.\n"
    "- Always include a 5.41 Builder's Work in Connection with Services section. "
    "This section covers all building work carried out solely to accommodate M&E "
    "installations — not the M&E installation itself. "
    "Classify items into 5.41 using the following categories:\n"
    "  Penetrations — holes formed through walls, floors or ceilings for services to pass through:\n"
    "    * Through masonry walls (nr) — rate_key: bwic_service_penetration_masonry\n"
    "    * Through concrete floors or walls (nr) — rate_key: bwic_service_penetration_concrete\n"
    "  Sleeves — cast-in or post-fixed service sleeves lining or protecting penetrations:\n"
    "    * 100mm diameter duct sleeve (nr) — rate_key: bwic_duct_sleeve_100mm\n"
    "    * 150mm diameter duct sleeve (nr) — rate_key: bwic_duct_sleeve_150mm\n"
    "  Boxing-in — enclosing service risers, exposed ducts or pipe casings in timber and board:\n"
    "    * Pipework boxed in timber framing and plasterboard (m) — rate_key: bwic_boxing_in_pipework_timber\n"
    "  Fire stopping — sealing service penetrations through fire-rated compartment walls or floors:\n"
    "    * Fire stopping to service penetration through compartment (nr) — rate_key: bwic_fire_stopping_penetration\n"
    "  Making good — reinstating finishes around completed service installations:\n"
    "    * Plaster or plasterboard around services (nr) — rate_key: bwic_making_good_plaster\n"
    "    * Masonry around services (nr) — rate_key: bwic_making_good_masonry\n"
    "  Chases — cutting service routes through masonry, including making good:\n"
    "    * Chase in masonry for conduit or pipework (m) — rate_key: bwic_chase_masonry_small\n"
    "BWIC NEGATIVE RULE: Do NOT classify MEP equipment installation itself as BWIC. "
    "Boilers, radiators, pipework runs, ductwork, cable containment, luminaires, "
    "distribution boards, consumer units, and all M&E equipment and wiring belong in "
    "5.14 Mechanical services or 5.15 Electrical services. Only the associated building "
    "work — the hole, sleeve, boxing-in, fire stop, or reinstatement around the service "
    "— belongs in 5.41. Never duplicate a service item in both a services section and 5.41.\n"
    "Scale quantities to the size of the project and complexity of M&E installations "
    "described in the drawings. Never omit this section.\n"

    # ── UPVC surfaces ─────────────────────────────────────────────────────────
    # ── MEP measurement rule ──────────────────────────────────────────────────
    "- MEP MEASUREMENT RULE: Electrical and mechanical services items with "
    "unit 'item' must always have quantity 1. These are per-installation "
    "rates for one complete installation, not per-square-metre rates. "
    "Never use the floor area as the quantity for an 'item' rate key. "
    "If the rate_key unit is 'item', set quantity to 1.\n"
    "- UPVC RULE: Never include a paint or decoration line item for UPVC surfaces. UPVC "
    "windows, fascias, soffits, gutters, and downpipes are factory-finished and do not "
    "receive paint. Delete any such item before producing output.\n"

    # ── NRM2 section numbering ────────────────────────────────────────────────
    "- NRM2 SECTION NUMBERING: Prefix every trade heading with its NRM2 work section "
    "number. Every section must have a unique number — never reuse the same number for "
    "two different trade headings. Use these exact mappings and no others: "
    "1 Preliminaries and general conditions; "
    "5.1 Groundworks; 5.4 In-situ concrete; 5.8 Masonry; "
    "5.9 Structural metalwork; 5.11 Carpentry and joinery; 5.12 Roofing; "
    "5.14 Mechanical services; 5.15 Electrical services; "
    "5.17 Plastering and internal finishes; "
    "5.18 Roof Coverings; 5.19 Waterproof Coverings; 5.20 Proprietary Linings; "
    "5.21 Drainage below ground; "
    "5.23 Windows and external doors; "
    "5.28 Floor, Wall and Ceiling Finishes; 5.29 Decoration.\n"
    "5.28 Floor finishes (tiling, screed, timber flooring); "
    "5.31 Insulation; "
    "5.35 External works — hard landscaping and site paving; "
    "5.36 Fencing and gates; "
    "5.37 Soft landscaping and planting; "
    "5.41 Builder's Work in Connection with Services.\n"
    "- PRELIMINARIES RULE: Preliminaries items (site establishment, supervision, welfare, "
    "temporary services, insurance, health and safety, cleaning) belong in Section 1 "
    "Preliminaries. Never include these items in the Measured Works sections (5.x). "
    "If the input describes contractor overhead or site running cost items, do not measure "
    "them — the Preliminaries section is a fixed structure in the PDF and is handled "
    "separately from the measured works you are generating.\n"
    "5.28 Floor, Wall and Ceiling Finishes; "
    "5.41 Builder's Work in Connection with Services.\n"
    "- External render, tyrolean render, monocouche render, sand and cement render, "
    "polymer render, and all applied render finishes to external masonry walls belong "
    "in section 5.8 Masonry — not 5.29 Decoration. Render is a structural "
    "finish applied to the building fabric. Never classify render under painting or "
    "decorating sections.\n"
    "5.23 Windows, screens and lights; 5.24 Doors, shutters and hatches; "
    "5.28 Floor, Wall and Ceiling Finishes; 5.29 Decoration; "
    "5.31 Insulation; "
    "5.41 Builder's work in connection with services.\n"

    # ── NRM2 section detail mappings ─────────────────────────────────────────
    "- NRM2 SECTION DETAIL MAPPINGS: Use the following guidance to distinguish between "
    "sections with overlapping scope:\n"
    "5.18 Roof Coverings: roof tiles, slates, ridge tiles, hip tiles, roof sheets, "
    "profiled metal roof systems. Use for all pitched and flat roof coverings made of "
    "discrete units or sheet materials.\n"
    "5.19 Waterproof Coverings: single-ply membrane, felt roofing, liquid waterproofing, "
    "flat roof membranes, roof waterproofing systems. Use for continuous membrane and "
    "liquid-applied waterproofing systems. "
    "Do not place roof waterproofing in 5.18.\n"
    "5.20 Proprietary Linings: dry lining systems, proprietary wall systems, proprietary "
    "ceiling systems, specialist lining systems. "
    "Do not place proprietary lining systems in 5.28.\n"
    "5.28 Floor, Wall and Ceiling Finishes: screeds, floor finishes, wall finishes, "
    "ceiling finishes, tiling. "
    "Do not place decorative coatings in 5.28. "
    "Do not place proprietary lining systems in 5.28.\n"
    "5.29 Decoration: painting, decorating, stains, varnishes, coatings.\n"
    "Do not place insulation in the serving trade section — all insulation belongs in 5.31.\n"

    # ── Windows and doors rule ────────────────────────────────────────────────
    "- WINDOWS AND DOORS RULE: Always create separate trade sections for windows and doors. "
    "Never combine them in a single section. "
    "Window items include: window frames, glazing units, glazing beads, window boards, "
    "ironmongery to windows, manifestation film. "
    "Door items include: door sets, door leaves, door frames and linings, ironmongery to doors, "
    "door closers, access control to doors. "
    "If glazing is separately described as a standalone element (structural glazing, frameless glass, "
    "glass balustrades), measure it under 5.23.\n"

    # ── Insulation rule ───────────────────────────────────────────────────────
    "- INSULATION RULE: All insulation items must be grouped together in a dedicated "
    "5.31 Insulation section. Do not attach insulation items to the trade they serve. "
    "The following all belong in 5.31, not in other sections: "
    "cavity wall insulation (partial fill or full fill) — not in 5.8 Masonry; "
    "roof insulation (between/over rafters, flat roof insulation board) — not in 5.12 Roofing, 5.18 Roof Coverings, or 5.19 Waterproof Coverings; "
    "floor insulation (rigid insulation board below screed or slab) — not in 5.1 Groundworks; "
    "acoustic insulation (between floors, party walls) — not in 5.8 or 5.11; "
    "pipe and duct insulation lagging — not in 5.14 Mechanical services; "
    "fire-rated insulation to structural elements — not in 5.9. "
    "Always create a 5.31 Insulation section. If the specification does not describe insulation "
    "types or thicknesses, insert a Provisional Sum under 5.31 labelled "
    "'Thermal and acoustic insulation — specification not issued at tender stage; "
    "contractor to include own allowance'.\n"

    # ── External works rule ───────────────────────────────────────────────────
    "- EXTERNAL WORKS RULE: Where external works are present, group all external "
    "works items together in their own dedicated sections rather than scattering "
    "them across unrelated building trades. "
    "External works include: paving (block paving, tarmac, concrete slabs), "
    "kerbs, roadways, car parks, footpaths, fencing, gates, landscaping, "
    "planting, external drainage runs (above-ground surface water routes and "
    "connections), retaining structures, external steps, hard landscaping, "
    "soft landscaping, and reinstatement works.\n"
    "Use these NRM2 section allocations for external works:\n"
    "  5.35 External works — hard landscaping and site paving: block paving, "
    "tarmac, concrete paving slabs, kerbs, roadways, car parks, footpaths, "
    "retaining structures, external steps, hard landscaping, reinstatement.\n"
    "  5.36 Fencing and gates: all fencing types, gates and barriers.\n"
    "  5.37 Soft landscaping and planting: turf, seeding, planting, topsoil, "
    "mulching, tree and shrub planting, soft landscaping.\n"
    "External works sections must appear after all building works sections "
    "(5.1 to 5.41) and before any provisional sums.\n"
    "EXTERNAL DRAINAGE NOTE: External below-ground drainage (foul and surface "
    "water drain runs, inspection chambers, manholes, rodding eyes, connections "
    "to sewer) remains in 5.21 Drainage below ground. Do not move below-ground "
    "drainage to 5.35.\n"
    "EXTERNAL WORKS NEGATIVE RULE: Do not classify internal building elements "
    "as external works. Internal floor finishes, internal staircases, internal "
    "drainage, and internal paving (e.g. tiled floors) belong in their correct "
    "building trade sections — not in 5.35, 5.36, or 5.37.\n"

    # ── Structural engineer references ────────────────────────────────────────
    "- STRUCTURAL ENGINEER RULE: If the input references a structural engineer's drawing "
    "or calculation sheet (any reference beginning SE-, S-, or described as structural), "
    "you MUST include a structural steelwork section or a Provisional Sum labelled "
    "'Structural steelwork — refer to SE drawings Ref: [X] — measure on receipt of "
    "fabrication drawings'. Never silently omit structural elements. "
    "Structural steel beams must be measured in linear metres (m) "
    "with the quantity being the beam span plus 300mm minimum "
    "end bearing each side. Never measure a beam as 1 nr.\n"

    # ── Description format ────────────────────────────────────────────────────
    "- DESCRIPTION FORMAT: Write every item description in this pattern: "
    "[Element]; [specification detail including material standard or mix]; "
    "[dimension or thickness where applicable]; [drawing or spec reference if provided]. "
    "Examples: "
    "'Excavation to reduced level; by machine; maximum depth not exceeding 0.25m; Ref Drawing PL-02' "
    "— "
    "'External cavity wall; facing brick 102mm outer leaf gauged mortar (1:1:6); 100mm clear "
    "cavity with 60mm partial fill mineral wool insulation (lambda 0.035); stainless steel "
    "wall ties type 4 at 2.5/m²; 100mm dense blockwork inner leaf; Ref Drawing PL-03' "
    "— "
    "'Provisional Sum: Electrical installation first and second fix — electrical drawings "
    "not issued at tender stage; contractor to include own allowance'. "
    "Where proprietary product names are referenced in "
    "descriptions (for example Catnic, Hyload, Velux, Rockwool, "
    "Kingspan, Celotex, or any other manufacturer or brand name), "
    "always append 'or equal approved' immediately after the brand "
    "name. Example: 'Hyload or equal approved; 150mm wide DPC'. "
    "Never omit this qualifier when a brand name appears in a "
    "bill description.\n"

    # ── Provisional sum classification ────────────────────────────────────────
    "- PROVISIONAL SUM CLASSIFICATION: Every provisional sum you generate must be "
    "classified as either Defined or Undefined in accordance with NRM2:\n"
    "DEFINED provisional sum: Use when the scope, location, and timing of the work "
    "is known but the precise cost cannot be determined at tender. The contractor "
    "is expected to include allowances in their programme and method statement. "
    "Examples: specialist supplier installations, known future fit-out works, "
    "named subcontractor packages where scope is described. "
    "Output format: include a field 'ps_type': 'Defined'\n"
    "UNDEFINED provisional sum: Use when the nature and extent of the work cannot "
    "be foreseen at tender stage. The contractor makes no programme or preliminary "
    "allowance. "
    "Examples: archaeological investigations, unknown service diversions, "
    "contingency allowances, unforeseen ground conditions. "
    "Output format: include a field 'ps_type': 'Undefined'\n"
    "Never output a provisional sum without a ps_type classification. If uncertain, "
    "classify as Undefined.\n"

    # ── Contractor Designed Portions ─────────────────────────────────────────
    "- CONTRACTOR DESIGNED PORTION (CDP) RULE: Flag cdp=true where the contractor "
    "is likely to carry design responsibility for the element. Typical examples include: "
    "boilers, heating systems, underfloor heating, MVHR, ventilation systems, "
    "fire alarm systems, electrical design packages, specialist glazing, solar PV systems, "
    "and specialist building systems. "
    "Where cdp=true, include a concise performance_requirement. "
    "Examples: "
    "'Provide system to achieve design flow rates.' — "
    "'Provide system to manufacturer's performance criteria.' — "
    "'Provide installation to achieve specified thermal performance.' "
    "Do not mark ordinary measured building elements as CDP. "
    "Omit cdp and performance_requirement entirely from items that are not CDP.\n"
    # OUTPUT-BLOAT EVALUATION (point 5 of the truncation fix): performance_requirement
    # — one of the two heaviest free-text per-item fields — is ALREADY conditional. The
    # rule above generates it ONLY where cdp=true and explicitly OMITS it (and cdp) from
    # every non-CDP item, so it is produced only where it adds value. There is no
    # per-item bloat to cut here; left exactly as-is.
    # ── Tender Query and Assumptions Register ────────────────────────────────
    "- TENDER QUERY AND ASSUMPTIONS RULE: Whenever information is incomplete, "
    "inferred, or excluded, you MUST populate the top-level assumptions_register "
    "array. Each entry must contain three fields: category (a short trade or topic "
    "label, e.g. 'Roofing', 'Drainage', 'Structural'), description (a clear "
    "statement of the assumption, query, or exclusion), and status (one of the "
    "three values below).\n"
    "  * Assumption — use when you have inferred information not explicitly stated "
    "in the input. Example: category 'Roofing', description 'Roof structure assumed "
    "timber trussed rafter construction', status 'Assumption'.\n"
    "  * Clarification Required — use when information is missing and a decision "
    "is needed before the BoQ can be finalised. Example: category 'Drainage', "
    "description 'Drainage route not shown on drawings — confirm connection point "
    "to existing sewer', status 'Clarification Required'.\n"
    "  * Exclusion — use when an item is deliberately omitted from the priced works. "
    "Example: category 'Specialist Surveys', description 'Specialist surveys "
    "excluded from this tender — client to procure direct', status 'Exclusion'.\n"
    "Do not generate entries where all information is fully confirmed by the input. "
    "If no assumptions, clarifications, or exclusions apply, output an empty array "
    "for assumptions_register.\n"

    # ── Standard fields ───────────────────────────────────────────────────────
    "- description is a human-readable label for the PDF output — write it clearly.\n"
    "- quantity is your professional QS estimate based on the specification.\n"
    "- unit must match the unit for that rate_key as listed.\n"
    "- drawing_ref: If the input PDF contains drawing numbers, specification "
    "references, or document revision codes, record the reference(s) this "
    "item was measured from. Format as: 'Drawing [ref] Rev [rev]' or "
    "'[ref1] / [ref2]' for multiple sources. If no drawing references are "
    "visible in the input, omit this field entirely — do not invent references.\n"
    "- dimension_string: Show the arithmetic used to derive the quantity. "
    "Format as a readable calculation string. Examples: "
    "'4.200m × 3.600m = 15.12m²' — "
    "'(12.400m + 8.600m) × 2 = 42.000m perimeter' — "
    "'45.0m² plan × 0.150m depth = 6.75m³ × 1.30 bulking = 8.78m³ disposal' — "
    "'27.0m perimeter × 5.400m height = 145.8m² gross − 10.8m² openings = 135.0m² net'. "
    "Always include this field. If a quantity is a single dimension with no "
    "calculation (e.g. a single door counted as 1nr), write: '1 nr — single "
    "item'. This field is mandatory for every line item.\n"
    # ── OUTPUT-BLOAT TODO (point 5, DEFERRED — do not change without QS sign-off) ──
    # dimension_string is the OTHER heavy free-text per-item field and, unlike
    # performance_requirement above, it is MANDATORY on every line item. It is the
    # single biggest lever left for cutting output tokens (and therefore truncation
    # risk + per-bill cost), but it is also the measurement AUDIT TRAIL.
    #   SPECIFIC OPPORTUNITY: make dimension_string OPTIONAL for trivial enumerated
    #   items — those counted as a plain "1 nr" / "n nr" with NO arithmetic to show
    #   (single door, single fitting). Today the prompt forces the boilerplate string
    #   "1 nr — single item" onto each of those rows; omitting it would save ~5–8
    #   output tokens per simple item with zero loss of derivable information, and
    #   _enrich_boq already setdefault()s dimension_string to '' so downstream
    #   export/render is unaffected.
    #   TRADEOFF / WHY DEFERRED: some QS reviewers expect EVERY priced row to carry a
    #   value in the dimension column for a uniform, defensible audit trail; an empty
    #   cell on count items is a presentation/compliance judgement call, not a clear
    #   win. Per the brief we do NOT guess on anything touching NRM2/audit value —
    #   the BOQ_MAX_OUTPUT_TOKENS=32000 raise + truncation salvage are the safe fix.
    #   Revisit with a QS to confirm before relaxing the "mandatory" wording above.

    # ── Risk schedule ─────────────────────────────────────────────────────────
    "- RISK SCHEDULE RULE: Generate a risk_schedule whenever the project contains "
    "significant uncertainty. Risks must be construction-related only — do not "
    "provide contractual or legal advice. Classify each risk as either Defined or "
    "Undefined using the same NRM2 definitions as provisional sums. "
    "For each risk include: description (what the risk is), risk_type (Defined or "
    "Undefined), impact (consequence if the risk materialises, e.g. cost overrun, "
    "programme delay), likelihood (Low / Medium / High), and mitigation (recommended "
    "action to reduce or manage the risk). "
    "Typical risks warranting inclusion: unknown ground conditions; unverified "
    "drainage routes; existing services not confirmed on drawings; restricted "
    "site access; partial or incomplete design information at tender stage; "
    "unconfirmed structural elements. "
    "Omit risk_schedule entirely if the specification is complete and no material "
    "uncertainties are present.\n"
    # ── NRM2 annexes ─────────────────────────────────────────────────────────
    "- NRM2 ANNEXES RULE: Only populate the annexes object where supporting "
    "information exists in the input. Do not invent quotations, utility "
    "information, statutory undertaker requirements, or specialist "
    "specifications. If none of the annex categories can be populated from "
    "the available information, omit the annexes field entirely — do not "
    "output an empty annexes object. Where applicable:\n"
    "  * risk_notes may reference risks identified during measurement "
    "(e.g. unknown ground conditions, existing service routes, structural "
    "elements requiring specialist input).\n"
    "  * contractor_designed_scope may reference any CDP (Contractor Designed "
    "Portion) items identified in the drawings or specification.\n"
    "  * schedules should list any supporting schedules or measurement "
    "appendices derived from the input (e.g. door schedule, window schedule, "
    "finishes schedule) only where the input contains that information.\n"
    "  * performance_specifications should list performance-based requirements "
    "only where the input explicitly states them.\n"
    "  * quotations and statutory_undertaker_information must never be "
    "invented; include only if the input contains actual quotation references "
    "or named statutory undertaker requirements.\n"
    # ── Document control ──────────────────────────────────────────────────────
    "- DOCUMENT CONTROL RULE: When document-control information is known, populate "
    "the following top-level fields in your output (all optional — omit only if "
    "genuinely unknown):\n"
    "  * revision: document revision letter, e.g. 'A'\n"
    "  * issue_status: e.g. 'Tender Issue'\n"
    "  * prepared_by: e.g. 'Vulcan Quanta'\n"
    "  * checked_by: e.g. 'Professional Review Required'\n"
    "  * intended_use: e.g. 'Tender Pricing'\n"
    "Use the typical values above unless the input document states otherwise. "
    "Do not invent project-specific revision information that is not in the input.\n"
    # OUTPUT MECHANISM: the API FORCES a tool call (tool_choice=record_bill_of_quantities),
    # so the model answers by populating that tool's input — NOT by writing JSON text.
    # The old "respond with a single raw JSON object" wording produced the two bugs the
    # Railway logs caught (a ```json markdown fence, and bill_of_quantities returned as an
    # object), because prose can't enforce shape. We now state the shape AND the mechanism.
    "Provide your completed Bill of Quantities by calling the record_bill_of_quantities "
    "tool. Populate bill_of_quantities as an ARRAY of trade groups — each an object with a "
    "'trade' string and an 'items' array — and place document-control fields (revision, "
    "issue_status, prepared_by, checked_by, intended_use) at the TOP LEVEL of the tool "
    "input, never nested inside bill_of_quantities. Do not add keys that are not in the "
    "tool schema."
)

BOQ_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "revision":      {"type": "string", "description": "Document revision letter, e.g. 'A'."},
        "issue_status":  {"type": "string", "description": "Issue status, e.g. 'Tender Issue'."},
        "prepared_by":   {"type": "string", "description": "Name of the party that prepared this BoQ."},
        "checked_by":    {"type": "string", "description": "Name of the party that checked this BoQ."},
        "intended_use":  {"type": "string", "description": "Intended use of this document, e.g. 'Tender Pricing'."},
        "bill_of_quantities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "trade": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "rate_key": {
                                    "type": "string",
                                    "enum": list(RATES_DB.keys()),
                                },
                                "quantity": {"type": "number"},
                                "unit": {"type": "string"},
                                "drawing_ref": {
                                    "type": "string",
                                    "description": "Drawing and specification references this item was measured from, e.g. 'A02 Rev P03 / SP Rev 04'",
                                },
                                "dimension_string": {
                                    "type": "string",
                                    "description": "Quantity derivation showing the measurement calculation, e.g. '27m × 5.4m = 145.8m² gross - 10.8m² openings = 135.0m² net'",
                                },
                                "cdp": {
                                    "type": "boolean",
                                    "description": "True where the contractor carries design responsibility for this element.",
                                },
                                "performance_requirement": {
                                    "type": "string",
                                    "description": "Concise performance specification for CDP items, e.g. 'Provide system to achieve design flow rates.'",
                                },
                                # This internal item_code is the future integration key for external QS software exporters.
                                "item_code": {
                                    "type": "string",
                                    "description": "Internal codification key in {NRM2-section}/{sequence} format, e.g. '5.8/001'. Generated during enrichment.",
                                },
                            },
                            "required": ["description", "rate_key", "quantity", "unit"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["trade", "items"],
                "additionalProperties": False,
            },
        },
        "risk_schedule": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "risk_type": {
                        "type": "string",
                        "enum": ["Defined", "Undefined"],
                    },
                    "impact": {"type": "string"},
                    "likelihood": {"type": "string"},
                    "mitigation": {"type": "string"},
                },
            },
        },
        "annexes": {
            "type": "object",
            "properties": {
                "schedules": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "performance_specifications": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "quotations": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "risk_notes": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "contractor_designed_scope": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "statutory_undertaker_information": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "additionalProperties": False,
        },
        "assumptions_register": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "risk_type": {
                        "type": "string",
                        "enum": ["Defined", "Undefined"],
                    },
                    "impact": {"type": "string"},
                    "likelihood": {"type": "string"},
                    "mitigation": {"type": "string"},
                    "category":    {"type": "string"},
                    "description": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["Assumption", "Clarification Required", "Exclusion"],
                    },
                },
            },
        },
    },
    "required": ["bill_of_quantities"],
    "additionalProperties": False,
}

_BOQ_OUTPUT_VALIDATOR = Draft202012Validator(BOQ_OUTPUT_SCHEMA)


# ── Forced structured output via tool use (THE definitive fix for shape drift) ──────
# Railway logs proved prose schema instructions are NOT reliably obeyed: the model
# wrapped its JSON in a ```json fence (Bug 1) AND returned bill_of_quantities as an
# OBJECT of metadata instead of the required ARRAY of trade groups (Bug 2). The robust
# fix is tool use: we hand Claude a tool whose input_schema IS the BoQ schema and FORCE
# it (tool_choice) to answer by emitting a tool_use block whose .input is already a dict
# in the right shape — no text, no fence, no json.loads, no shape guessing.
BOQ_TOOL_NAME = "record_bill_of_quantities"


def _build_boq_tool_input_schema():
    """BOQ_OUTPUT_SCHEMA adapted as an Anthropic tool input_schema.

    Identical to BOQ_OUTPUT_SCHEMA except the enrichment-only item_code property is
    removed (the model must not generate it; _enrich_boq assigns it and won't overwrite
    a model-supplied value). Every keyword used here — type/properties/required/items/
    enum/additionalProperties — is supported by Anthropic tool input_schema; there are
    no $ref/oneOf/allOf/pattern/format constructs that would need rewriting.
    """
    schema = copy.deepcopy(BOQ_OUTPUT_SCHEMA)
    try:
        schema["properties"]["bill_of_quantities"]["items"]["properties"]["items"]["items"]["properties"].pop("item_code", None)
    except (KeyError, TypeError):
        pass
    return schema


BOQ_TOOL = {
    "name": BOQ_TOOL_NAME,
    "description": (
        "Record the completed NRM2 Bill of Quantities. Call this exactly once with the "
        "full bill. bill_of_quantities MUST be an ARRAY of trade groups, each an object "
        "with a 'trade' string and an 'items' array of line items. Put document-control "
        "fields (revision, issue_status, prepared_by, checked_by, intended_use) at the "
        "TOP LEVEL — never nested inside bill_of_quantities."
    ),
    "input_schema": _build_boq_tool_input_schema(),
}


def _validate_boq_output(boq_data):
    """Validate Claude's structured output before pricing enrichment."""
    try:
        _BOQ_OUTPUT_VALIDATOR.validate(boq_data)
    except ValidationError as exc:
        path = ".".join(str(p) for p in exc.absolute_path) or "<root>"
        raise ValueError(f"{path}: {exc.message}") from exc


# Top-level keys BOQ_OUTPUT_SCHEMA permits. Anything else (the project/client/
# currency/notes the model invented in the Railway logs) trips additionalProperties:
# false at the root, so normalization drops it rather than letting validation 502.
_BOQ_ALLOWED_TOP_KEYS = {
    "revision", "issue_status", "prepared_by", "checked_by", "intended_use",
    "bill_of_quantities", "risk_schedule", "annexes", "assumptions_register",
}
_BOQ_METADATA_KEYS = ("revision", "issue_status", "prepared_by", "checked_by", "intended_use")
# Line-item fields the model may legitimately supply. item_code is intentionally
# EXCLUDED: it is generated during enrichment and _enrich_boq does not overwrite a
# model-supplied one, so we strip any model value here to guarantee a clean code.
_BOQ_ITEM_FIELDS = (
    "description", "rate_key", "quantity", "unit",
    "drawing_ref", "dimension_string", "cdp", "performance_requirement",
)
_BOQ_ALLOWED_ANNEX_KEYS = {
    "schedules", "performance_specifications", "quotations",
    "risk_notes", "contractor_designed_scope", "statutory_undertaker_information",
}


def _looks_like_trade_groups(value) -> bool:
    """True if value is a non-empty list whose entries look like {trade, items} groups."""
    if not isinstance(value, list) or not value:
        return False
    hits = sum(
        1 for v in value
        if isinstance(v, dict) and ("items" in v or "line_items" in v) and ("trade" in v or "name" in v)
    )
    return hits >= max(1, len(value) // 2)


def _clean_boq_item(item):
    """Return a schema-clean copy of a line item, or None if it lacks required fields.

    Keeps only allowed item fields (drops item_code + any invented keys that would
    trip additionalProperties:false), coerces quantity to a float (the schema requires
    a number), and rejects truncation-tail items missing description/rate_key/unit/qty.
    """
    if not isinstance(item, dict):
        return None
    desc = item.get("description") or item.get("desc")
    rate_key = str(item.get("rate_key") or "").strip()
    unit = item.get("unit")
    if not desc or not rate_key or not unit:
        return None
    try:
        qty = float(item.get("quantity"))
    except (TypeError, ValueError):
        return None                                  # missing/half-written number (e.g. truncated mid-value)
    clean = {k: item[k] for k in _BOQ_ITEM_FIELDS if k in item}
    clean["description"] = desc
    clean["rate_key"] = rate_key
    clean["quantity"] = qty
    if "cdp" in clean and not isinstance(clean["cdp"], bool):
        clean.pop("cdp", None)                       # cdp is optional + boolean-typed; drop a non-bool rather than 502
    return clean


def _normalize_boq_shape(data):
    """Coerce a near-miss Claude BoQ back into BOQ_OUTPUT_SCHEMA shape (defense-in-depth).

    Even with forced tool use we keep this as a safety net for the EXACT drift the
    Railway logs showed (Bug 2) and for truncation tails:
      • bill_of_quantities arriving as an OBJECT (metadata + a nested trade array)
        instead of the required ARRAY → lift metadata to top level, dig out the array;
      • a 'trades' key or a trade-name→items mapping → convert to the array shape;
      • invented top-level keys (project/client/currency/notes) and unknown annex keys
        → dropped so additionalProperties:false does not hard-fail validation;
      • trailing incomplete line items / now-empty trade groups (truncation) → dropped.
    Best-effort and never raises; returns the input unchanged if it is unrecognisable.
    """
    if isinstance(data, list):
        data = {"bill_of_quantities": data}          # a bare list of trade groups is acceptable drift
    if not isinstance(data, dict):
        return data

    out = dict(data)                                 # shallow copy; we rebuild bill_of_quantities below
    boq = out.get("bill_of_quantities")

    # Bug 2 core case: bill_of_quantities is an OBJECT, not an array.
    if isinstance(boq, dict):
        nested = boq
        trade_array = next((v for v in nested.values() if _looks_like_trade_groups(v)), None)
        if trade_array is None:                      # fall back to any list value inside the object
            lists = [v for v in nested.values() if isinstance(v, list)]
            trade_array = lists[0] if lists else []
        for mk in _BOQ_METADATA_KEYS:                # lift recognised metadata up to the top level
            if mk in nested and not out.get(mk):
                out[mk] = nested[mk]
        boq = trade_array

    # Other wrapper shapes seen historically.
    if not isinstance(boq, list):
        if isinstance(out.get("trades"), list):
            boq = out["trades"]
        else:
            boq = [
                {"trade": k, "items": v} for k, v in out.items()
                if isinstance(v, list) and k not in ("risk_schedule", "assumptions_register")
            ]

    # Rebuild clean trade groups: exactly {trade, items}, items cleaned + tail-dropped.
    clean_groups = []
    for g in boq if isinstance(boq, list) else []:
        if not isinstance(g, dict):
            continue
        raw_items = g.get("items") or g.get("line_items") or []
        if not isinstance(raw_items, list):
            continue
        good = [ci for ci in (_clean_boq_item(it) for it in raw_items) if ci]
        if good:
            clean_groups.append({"trade": str(g.get("trade") or g.get("name") or "General"), "items": good})
    out["bill_of_quantities"] = clean_groups

    # Strip unknown top-level keys, and unknown annex keys (annexes also has
    # additionalProperties:false), so legitimate drift degrades instead of 502-ing.
    for k in list(out.keys()):
        if k not in _BOQ_ALLOWED_TOP_KEYS:
            out.pop(k, None)
    if isinstance(out.get("annexes"), dict):
        out["annexes"] = {k: v for k, v in out["annexes"].items() if k in _BOQ_ALLOWED_ANNEX_KEYS}

    return out


def _salvage_truncated_boq(raw_text):
    """Best-effort repair of a JSON BoQ that was cut off at the output-token ceiling.

    When the model hits BOQ_MAX_OUTPUT_TOKENS the stream stops with
    stop_reason=="max_tokens" PART-WAY through writing the JSON — almost always an
    unterminated string / half-written final line item at the very end, with every
    earlier section intact. Rather than throw that paid-for, mostly-complete bill
    away with a 502, we try to REPAIR it:

      1. Scan the accumulated text once, tracking string-escape state and a stack of
         every still-open '{' / '['. JSON structure characters inside string values
         (e.g. a literal '}' in a description) are ignored because we only act when
         NOT inside a string.
      2. Remember the index just AFTER the last container that closed CLEANLY while
         still nested inside the bill (stack non-empty) — that is a safe cut point
         sitting right after a complete line item or a complete trade section.
      3. Truncate there (dropping the final incomplete item) and append the closing
         brackets the stack says are still open, in reverse order.
      4. json.loads the repaired text.

    Returns the parsed dict on success, or None if it still cannot be parsed (in
    which case the caller falls back to an accurate 502). The caller re-runs
    _validate_boq_output on the result, so a structurally invalid salvage is rejected.
    """
    if not raw_text or "{" not in raw_text:
        return None

    in_string = False
    escape = False
    stack = []                 # every still-open container, in nesting order
    safe_cut = None            # index just AFTER the last cleanly-closed nested element
    safe_stack = None          # the open-container stack to re-close at that cut point

    for i, ch in enumerate(raw_text):
        if escape:                         # previous char was a backslash inside a string
            escape = False
            continue
        if in_string:
            if ch == "\\":
                escape = True              # next char is escaped — don't treat it as a quote
            elif ch == '"':
                in_string = False          # closing quote
            continue
        if ch == '"':
            in_string = True               # opening quote
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if not stack:
                return None                # unbalanced — json.loads would fail anyway
            stack.pop()
            # A container just closed outside any string. While we are still nested
            # inside the outer bill object/array, this is the safest place to cut:
            # everything up to here parses, and the partial tail can be discarded.
            if stack:
                safe_cut = i + 1
                safe_stack = list(stack)

    if safe_cut is None or not safe_stack:
        return None                        # nothing closed cleanly inside the bill → unsalvageable

    head = raw_text[:safe_cut]             # ends right after a complete '}' or ']' (no dangling comma)
    closers = "".join("}" if b == "{" else "]" for b in reversed(safe_stack))
    repaired = head + closers

    try:
        parsed = json.loads(repaired)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None

# ── Rate-matching helpers ─────────────────────────────────────────────────────────────
# These run once at module load time — like a static constructor in C#.
# We pre-compute token sets for every RATES_DB key so we don't repeat the work
# on every incoming request.

_STOP = frozenset([                # words too common to be useful for matching
    'to', 'in', 'of', 'the', 'a', 'and', 'for', 'with', 'at', 'on', 'per', 'by', 'or',
])

def _tokenise(text):
    """Lower-case, strip punctuation, remove stop words → frozenset of tokens."""
    clean = re.sub(r'[^a-z0-9\s]', ' ', text.lower())   # keep only alphanumeric + spaces
    return frozenset(w for w in clean.split() if w not in _STOP and len(w) > 1)

# Dict[key → frozenset of tokens] — computed once, reused on every request
_RATES_TOKENS = {key: _tokenise(key.replace('_', ' ')) for key in RATES_DB}


def _match_rate(description):
    """
    Find the closest RATES_DB entry for a free-text description.
    Uses Jaccard similarity on normalised token sets — no extra dependencies.
    Returns (matched_key, rate_dict) or (None, None) if no confident match found.

    Jaccard similarity = |intersection| / |union|  — ranges 0.0 (no overlap) to 1.0 (identical).
    C# equivalent: intersect.Count() / (double)union.Count()
    """
    desc_toks = _tokenise(description)
    if not desc_toks:                    # guard: empty description after normalisation
        return None, None

    best_key   = None
    best_score = 0.0

    for key, key_toks in _RATES_TOKENS.items():
        if not key_toks:
            continue
        intersection = len(desc_toks & key_toks)   # & on frozensets = set intersection
        if intersection == 0:
            continue                                # skip if no common tokens at all
        union = len(desc_toks | key_toks)          # | on frozensets = set union
        score = intersection / union               # Jaccard coefficient
        if score > best_score:
            best_score = score
            best_key   = key

    # Require Jaccard ≥ 0.10 — at least ~1-in-9 tokens must overlap.
    # Lower than 0.15 to handle verbose descriptions like "common brickwork in stretcher bond"
    # whose extra tokens (stretcher, bond) dilute the score against the shorter RATES_DB key.
    if best_score >= 0.10 and best_key:
        return best_key, RATES_DB[best_key]
    return None, None


# Canonical NRM2 ordering improves consistency across projects and export formats.
_NRM2_SECTION_ORDER: dict[str, int] = {
    "5.1":  10,  "5.2":  20,  "5.4":  30,  "5.8":  40,
    "5.9":  50,  "5.11": 60,  "5.12": 70,  "5.14": 80,
    "5.15": 90,  "5.18": 100, "5.19": 110, "5.20": 120,
    "5.21": 130, "5.23": 140, "5.24": 150, "5.28": 160,
    "5.29": 170, "5.31": 180, "5.35": 190, "5.36": 200,
    "5.37": 210, "5.41": 220,
}

_RE_NRM2_PREFIX = re.compile(r'^\s*(\d+(?:\.\d+)*)')


def _nrm2_sort_key(group: dict) -> int:
    """Return the canonical NRM2 sort position for a trade group; unknowns sort last."""
    if not isinstance(group, dict):
        return 9999
    m = _RE_NRM2_PREFIX.match(group.get('trade') or '')
    return _NRM2_SECTION_ORDER.get(m.group(1), 9999) if m else 9999


def _enrich_boq(boq_data):
    """
    Walk the Claude JSON (regardless of its outer shape) and apply RATES_DB rates to
    every line item in place.  Adds material_rate, labour_rate, rate, line_total,
    and rate_source to each item dict.  Returns the same object (mutated).
    """
    # Normalise the outer structure to a flat list of trade-group dicts.
    # Claude may return [{trade, items}], {groundworks:[...]}, {bill_of_quantities:[...]}, etc.
    # isinstance() checks the runtime type — like 'is' / 'as' in C#.
    if isinstance(boq_data, list):
        groups = boq_data                          # already [{trade, items}]
    elif isinstance(boq_data, dict):
        if 'bill_of_quantities' in boq_data:       # wrapper key used by some Claude outputs
            groups = boq_data['bill_of_quantities']
        elif 'trades' in boq_data:
            groups = boq_data['trades']
        else:
            # Keys are trade names, values are item lists — convert to uniform list
            groups = [{'trade': k, 'items': v}
                      for k, v in boq_data.items() if isinstance(v, list)]
    else:
        return boq_data                            # unexpected shape — pass through untouched

    # This internal item_code is the future integration key for external QS software exporters.
    section_counters = {}  # separate sequence counter per NRM2 section, e.g. {"5.8": 3, "5.1": 1}

    for group in groups:                           # iterate each trade section
        if not isinstance(group, dict):            # skip strings or other non-dict entries Claude may have included
            continue
        items = group.get('items') or group.get('line_items') or []
        if not isinstance(items, list):            # guard against items being a scalar or dict
            continue

        # Extract the NRM2 section prefix from the trade heading (e.g. "5.8 Masonry" → "5.8")
        trade_str = group.get('trade', '')
        _section_match = re.match(r'^[\d.]+', trade_str.strip())
        _section = _section_match.group() if _section_match else (trade_str.strip() or 'X')

        for item in items:                         # iterate each line item within the trade
            desc = item.get('description') or item.get('desc') or ''
            qty  = float(item.get('quantity') or item.get('qty') or 0)
            item.setdefault('drawing_ref', '')
            item.setdefault('dimension_string', '')

            # Prefer the rate_key Claude was instructed to output — direct O(1) lookup
            rate_key_direct = item.get('rate_key', '').strip()
            if rate_key_direct and rate_key_direct in RATES_DB:
                matched_key  = rate_key_direct
                rate_entry   = RATES_DB[rate_key_direct]
            else:
                # Fallback: Jaccard fuzzy match on description for legacy or malformed output
                matched_key, rate_entry = _match_rate(desc)
                if rate_entry:
                    best_key = matched_key
                    app.logger.warning(
                        "RATE_KEY_FUZZY_MATCH: item description=%r requested rate_key=%r "
                        "resolved to fuzzy_key=%r — consider adding %r to RATES_DB",
                        item.get("description", ""),
                        item.get("rate_key", ""),
                        best_key,
                        item.get("rate_key", ""),
                    )
                else:
                    app.logger.warning(
                        "RATE_KEY_UNRESOLVED: item description=%r rate_key=%r — "
                        "no direct or fuzzy match in RATES_DB, item will have zero rate",
                        item.get("description", ""),
                        item.get("rate_key", ""),
                    )

            if rate_entry:
                mat   = rate_entry['material_rate']
                lab   = rate_entry['labour_rate']
                plant = rate_entry.get('plant_rate', 0.0)
                waste = rate_entry.get('waste_disposal_rate', 0.0)
                item['material_rate']       = mat
                item['labour_rate']         = lab
                item['plant_rate']          = plant
                item['waste_disposal_rate'] = waste
                item['rate']                = round(mat + lab + plant + waste, 2)
                item['line_total']          = round(item['rate'] * qty, 2)
                item['total']               = item['line_total']
                item['rate_source']         = matched_key
            else:
                # No match found — leave rates at zero so the QS can fill them in manually
                item['material_rate']       = 0.00
                item['labour_rate']         = 0.00
                item['plant_rate']          = 0.00
                item['waste_disposal_rate'] = 0.00
                item['rate']                = 0.00
                item['line_total']          = 0.00
                item['total']               = 0.00
                item['rate_source']         = None

            # Assign item_code in {section}/{sequence} format; do not overwrite if already set.
            # This internal item_code is the future integration key for external QS software exporters.
            if not item.get('item_code'):
                section_counters[_section] = section_counters.get(_section, 0) + 1
                item['item_code'] = f"{_section}/{section_counters[_section]:03d}"

    # Sort trade groups into canonical NRM2 section order.
    groups.sort(key=_nrm2_sort_key)

    return boq_data   # return the same object so callers can chain: data = _enrich_boq(data)


# ── Auth routes ──────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET"])      # GET /login serves the standalone HTML login page
def login_page():
    # send_from_directory serves a file from a directory — like PhysicalFileResult in C# MVC.
    # os.path.abspath(__file__) gives the absolute path to app.py; dirname gives its folder.
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'login.html')


@app.route("/login", methods=["POST"])     # POST /login authenticates and writes the JWT to the session
def login():
    if not _supabase:                      # guard: fail clearly if env vars are missing
        return jsonify({"error": "Auth not configured — set SUPABASE_URL and SUPABASE_ANON_KEY."}), 503

    body     = request.get_json(force=True, silent=True) or {}   # parse JSON body; {} if empty
    email    = (body.get('email')    or '').strip()               # .strip() removes accidental whitespace
    password =  body.get('password') or ''
    if not email or not password:          # validate before hitting Supabase to save a round-trip
        return jsonify({"error": "email and password are required."}), 400

    try:
        # sign_in_with_password is synchronous in supabase-py; it POSTs to Supabase's /auth/v1/token
        res = _supabase.auth.sign_in_with_password({"email": email, "password": password})

        # Store tokens in the Flask session cookie (signed with SECRET_KEY, not encrypted).
        # This is equivalent to writing to HttpContext.Session in ASP.NET Core.
        session['access_token']  = res.session.access_token   # JWT; expires in ~1 h by default
        session['refresh_token'] = res.session.refresh_token  # long-lived; used to renew the JWT
        session['user_id']       = res.user.id                # Supabase user UUID
        session['user_email']    = res.user.email

        return jsonify({"message": "Logged in.", "email": res.user.email}), 200

    except Exception as exc:
        return jsonify({"error": _auth_error_msg(exc)}), 401   # 401 Unauthorized on bad credentials


@app.route("/signup", methods=["POST"])    # POST /signup registers a new Supabase user
def signup():
    if not _supabase:
        return jsonify({"error": "Auth not configured — set SUPABASE_URL and SUPABASE_ANON_KEY."}), 503

    body     = request.get_json(force=True, silent=True) or {}
    email    = (body.get('email')    or '').strip()
    password =  body.get('password') or ''
    if not email or not password:
        return jsonify({"error": "email and password are required."}), 400
    if len(password) < 6:                 # Supabase enforces 6-char minimum; check here for a clear message
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    try:
        res = _supabase.auth.sign_up({"email": email, "password": password})

        # res.session is set immediately if Supabase email confirmation is disabled.
        # If confirmation is required, res.session is None — user must verify first.
        if res.session:
            session['access_token']  = res.session.access_token
            session['refresh_token'] = res.session.refresh_token
            session['user_id']       = res.user.id
            session['user_email']    = res.user.email
            return jsonify({"message": "Account created. You are now signed in."}), 201

        return jsonify({"message": "Account created. Check your email to confirm, then sign in."}), 201

    except Exception as exc:
        return jsonify({"error": _auth_error_msg(exc)}), 400   # 400 Bad Request (e.g. email already in use)


@app.route("/logout", methods=["POST"])    # POST /logout clears the Flask session
def logout():
    # session.clear() removes all keys from the signed cookie — like Session.Clear() in ASP.NET.
    # The Supabase JWT expires on its own (default 3600 s); we do not call supabase.auth.sign_out()
    # here because that would require setting the per-request session on the shared client.
    session.clear()
    return jsonify({"message": "Logged out."}), 200


@app.route("/me", methods=["GET"])         # lightweight session-check endpoint for the frontend
def me():
    if not session.get('access_token'):    # no session → 401 so the SPA knows to redirect to /login
        return jsonify({"error": "Not authenticated."}), 401
    return jsonify({"email": session.get('user_email'), "user_id": session.get('user_id')}), 200


# ── Project CRUD routes ───────────────────────────────────────────────────────────────

@app.route("/projects", methods=["GET"])   # GET /projects lists the signed-in user's saved BoQs
def get_projects():
    user, err = _authenticated_user()       # verify the Bearer token and resolve the owning user
    if err:
        return err

    db = _db_client()

    # Auto-delete expired projects
    try:
        db.rpc("delete_expired_projects", {"uid": user.id}).execute()
    except Exception:
        pass  # non-fatal — list still returns normally

    try:
        # Select every column except boq_data — the BoQ JSON is too large for a list view.
        # order(..., desc=True) gives newest-first, like .OrderByDescending(p => p.CreatedAt) in C#.
        res = (
            db.table("projects")
            .select("id, user_id, name, page_count, estimated_value, status, created_at")
            .eq("user_id", user.id)
            .order("created_at", desc=True)
            .execute()
        )
    except Exception as exc:
        return jsonify({"error": f"Failed to load projects: {exc}"}), 500

    return jsonify(res.data or []), 200


@app.route("/projects", methods=["POST"])   # POST /projects saves a new BoQ project for the user
def create_project():
    user, err = _authenticated_user()
    if err:
        return err

    body = request.get_json(force=True, silent=True) or {}

    try:
        row = _insert_project(
            _db_client(),
            user_id=user.id,                                  # force ownership to the authenticated user
            name=body.get("name"),
            page_count=body.get("page_count"),
            estimated_value=body.get("estimated_value"),
            boq_data=body.get("boq_data"),
            status=body.get("status"),
            extra=body,
        )
    except Exception as exc:
        # postgrest.APIError carries a clean .message — prefer it over the raw
        # repr (a Python dict dump) so the UI toast stays human-readable.
        detail = getattr(exc, "message", None) or str(exc)
        return jsonify({"error": f"Failed to create project: {detail}"}), 500

    return jsonify(row), 201


@app.route("/projects/<project_id>", methods=["DELETE"])   # DELETE /projects/<id> removes one project
def delete_project(project_id):
    user, err = _authenticated_user()
    if err:
        return err

    try:
        # The user_id filter guarantees a user can only delete their own project —
        # a row owned by someone else simply matches nothing and yields a 404 below.
        res = (
            _db_client().table("projects")
            .delete()
            .eq("id", project_id)
            .eq("user_id", user.id)
            .execute()
        )
    except Exception as exc:
        return jsonify({"error": f"Failed to delete project: {exc}"}), 500

    if not getattr(res, "data", None):       # no rows deleted → nothing matched id + owner
        return jsonify({"error": "Project not found."}), 404

    return "", 204                           # 204 No Content — deletion succeeded, no body


@app.route("/projects/<project_id>", methods=["GET"])
def get_project(project_id):
    user, err = _authenticated_user()
    if err:
        return err
    try:
        res = (
            _db_client().table("projects")
            .select("*")
            .eq("id", project_id)
            .eq("user_id", user.id)
            .single()
            .execute()
        )
    except Exception as exc:
        return jsonify({"error": f"Failed to load project: {exc}"}), 500
    if not getattr(res, "data", None):
        return jsonify({"error": "Project not found."}), 404
    return jsonify(res.data), 200


@app.route("/projects/<project_id>", methods=["PUT"])
def update_project(project_id):
    user, err = _authenticated_user()
    if err:
        return err
    body = request.get_json(force=True, silent=True) or {}
    allowed = {"name", "description", "client_name", "contract_type",
               "location_factor", "notes_for_ai", "auto_delete_days"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        return jsonify({"error": "No valid fields to update."}), 400
    try:
        res = (
            _db_client().table("projects")
            .update(updates)
            .eq("id", project_id)
            .eq("user_id", user.id)
            .execute()
        )
    except Exception as exc:
        return jsonify({"error": f"Failed to update project: {exc}"}), 500
    return jsonify(res.data[0] if res.data else {}), 200


@app.route("/projects/<project_id>/chat", methods=["GET"])
def get_chat(project_id):
    user, err = _authenticated_user()
    if err:
        return err
    try:
        res = (
            _db_client().table("chat_messages")
            .select("id, role, content, created_at")
            .eq("project_id", project_id)
            .eq("user_id", user.id)
            .order("created_at", desc=False)
            .execute()
        )
    except Exception as exc:
        return jsonify({"error": f"Failed to load chat: {exc}"}), 500
    return jsonify(res.data or []), 200


@app.route("/projects/<project_id>/chat", methods=["POST"])
def post_chat(project_id):
    user, err = _authenticated_user()
    if err:
        return err

    body = request.get_json(force=True, silent=True) or {}
    user_message = (body.get("message") or "").strip()
    if not user_message:
        return jsonify({"error": "Message is required."}), 400

    # Load project for boq_data and notes_for_ai
    try:
        proj_res = (
            _db_client().table("projects")
            .select("boq_data, notes_for_ai, name, client_name, contract_type, location_factor")
            .eq("id", project_id)
            .eq("user_id", user.id)
            .single()
            .execute()
        )
    except Exception as exc:
        return jsonify({"error": "Project not found."}), 404

    project = proj_res.data or {}

    # Load last 20 messages for context
    try:
        hist_res = (
            _db_client().table("chat_messages")
            .select("role, content")
            .eq("project_id", project_id)
            .eq("user_id", user.id)
            .order("created_at", desc=False)
            .limit(20)
            .execute()
        )
        history = hist_res.data or []
    except Exception:
        history = []

    # Build system prompt
    boq_summary = json.dumps(project["boq_data"], indent=None)[:6000] if project.get("boq_data") else ""

    system = f"""You are a professional quantity surveyor assistant for the project '{project.get("name", "Unnamed")}' \
(client: {project.get("client_name") or "not specified"}, contract: {project.get("contract_type") or "not specified"}, \
location: {project.get("location_factor") or "Belfast"}).

The following is the Bill of Quantities data for this project (NRM2-structured JSON):
{boq_summary if boq_summary else "No BoQ has been generated yet for this project."}

Answer questions about quantities, rates, costs, scope, and NRM2 structure. \
Be concise and professional. Give specific figures from the BoQ where relevant.
{("Additional instructions: " + project["notes_for_ai"]) if project.get("notes_for_ai") else ""}"""

    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": user_message})

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY environment variable is not set on the server."}), 500

    try:
        # max_retries=1: chat replies are short (max_tokens=1024) so a single
        # retry on a transient blip stays well under both the 60s client timeout
        # and the gunicorn worker timeout — unlike the /process call, this can't
        # cause a runaway retry-storm.
        chat_client = anthropic.Anthropic(api_key=api_key, timeout=60.0, max_retries=1)
        response = chat_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system,
            messages=messages,
        )
        # _extract_claude_text joins all text blocks safely; response.content[0]
        # would IndexError if Claude returned no text block.
        assistant_reply = _extract_claude_text(response)
    except Exception as exc:
        return jsonify({"error": f"AI error: {exc}"}), 500

    # Persist both turns — non-fatal if this fails
    try:
        _db_client().table("chat_messages").insert([
            {"project_id": project_id, "user_id": user.id, "role": "user",      "content": user_message},
            {"project_id": project_id, "user_id": user.id, "role": "assistant", "content": assistant_reply},
        ]).execute()
    except Exception:
        pass

    return jsonify({"reply": assistant_reply}), 200


# ── QS Review & Sign-off workspace ──────────────────────────────────────────


def _append_audit_event(project_id: str, user_id: str, action: str, **kwargs) -> None:
    """Append one row to boq_audit_events.  Best-effort — never raises.

    Called after every review action so the audit trail stays consistent even
    when the table doesn't exist yet (pre-migration databases): the except block
    logs a WARNING but lets the main response succeed.
    """
    try:
        row = {"project_id": project_id, "user_id": user_id, "action": action}
        for key, val in kwargs.items():
            if val is not None:
                row[key] = val
        result = _db_client().table("boq_audit_events").insert(row).execute()
        rows = getattr(result, "data", None) or []
        return rows[0] if rows else None
    except Exception as exc:
        app.logger.warning("_append_audit_event failed (non-fatal): %s", exc)
        return None


def _assign_item_ids(boq_data: dict) -> dict:
    """Return a deep copy of boq_data with a stable 'id' field on every item.

    The synthetic key  g{group_index}_i{item_index}  is only assigned when
    the item carries no existing 'id' or 'item_code'.  Both the API and the
    frontend apply this same derivation so review_states keys always match.
    """
    import copy
    data = copy.deepcopy(boq_data)
    groups = data.get("bill_of_quantities") or data.get("trades") or (data if isinstance(data, list) else [])
    for gi, group in enumerate(groups):
        if not isinstance(group, dict):
            continue
        items = group.get("items") or group.get("line_items") or []
        for ii, item in enumerate(items):
            if isinstance(item, dict) and not item.get("id"):
                item["id"] = item.get("item_code") or f"g{gi}_i{ii}"
    return data


def _review_counts(boq_data: dict, review_states: dict) -> dict:
    """Count items per review state across the full bill.

    Soft-deleted items (removed: true) are tallied in the 'removed' key and
    excluded from all other counts including 'total', so the review progress
    percentage and sign-off gate only consider the live working bill.
    """
    counts: dict = {"pending": 0, "approved": 0, "modified": 0, "rejected": 0, "removed": 0, "total": 0}
    groups = boq_data.get("bill_of_quantities") or boq_data.get("trades") or []
    for gi, group in enumerate(groups):
        if not isinstance(group, dict):
            continue
        for ii, item in enumerate(group.get("items") or group.get("line_items") or []):
            if not isinstance(item, dict):
                continue
            if item.get("removed"):
                counts["removed"] += 1
                continue
            key = item.get("id") or item.get("item_code") or f"g{gi}_i{ii}"
            state = (review_states.get(key) or {}).get("state", "pending")
            counts[state] = counts.get(state, 0) + 1
            counts["total"] += 1
    return counts


def _review_grand_total(boq_data: dict, review_states: dict) -> float:
    """Grand total; rejected and soft-deleted lines contribute £0."""
    total = 0.0
    groups = boq_data.get("bill_of_quantities") or boq_data.get("trades") or []
    for gi, group in enumerate(groups):
        if not isinstance(group, dict):
            continue
        for ii, item in enumerate(group.get("items") or group.get("line_items") or []):
            if not isinstance(item, dict):
                continue
            if item.get("removed"):
                continue
            key = item.get("id") or item.get("item_code") or f"g{gi}_i{ii}"
            rs = review_states.get(key) or {}
            if rs.get("state") == "rejected":
                continue
            total += _effective_line_total(item, rs)
    return round(total, 2)


def _signoff_hash(boq_data: dict, review_states: dict) -> str:
    """SHA-256 fingerprint of the effective reviewed bill.

    Operates on working_boq (passed by the caller) so the hash covers the
    live, edited bill — not the original AI draft.  Rejected and soft-deleted
    lines are excluded; they don't appear in the signed document.
    The hash is over (trade, description, effective_qty, unit, effective_total)
    sorted-key JSON so dict ordering never affects the value.
    """
    import hashlib
    lines = []
    groups = boq_data.get("bill_of_quantities") or boq_data.get("trades") or []
    for gi, group in enumerate(groups):
        if not isinstance(group, dict):
            continue
        trade = group.get("trade") or group.get("name") or "General"
        for ii, item in enumerate(group.get("items") or group.get("line_items") or []):
            if not isinstance(item, dict):
                continue
            if item.get("removed"):
                continue
            key   = item.get("id") or item.get("item_code") or f"g{gi}_i{ii}"
            rs    = review_states.get(key) or {}
            state = rs.get("state", "pending")
            if state == "rejected":
                continue
            lines.append({
                "trade":  trade,
                "desc":   item.get("description") or item.get("desc") or "",
                "qty":    float(rs["qty"]) if rs.get("qty") is not None else float(item.get("quantity") or item.get("qty") or 0),
                "unit":   item.get("unit") or "",
                "total":  _effective_line_total(item, rs),
                "state":  state,
            })
    canonical = json.dumps(lines, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _fetch_review_project(project_id: str, user_id: str):
    """Fetch the project row for review endpoints; returns (row, error_response)."""
    try:
        res = (
            _db_client()
            .table("projects")
            .select(
                "id, name, client_name, status, boq_data, working_boq, review_states, "
                "signed_off_at, signed_off_by, signoff_title, signoff_hash"
            )
            .eq("id", project_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        rows = getattr(res, "data", None) or []
        if not rows:
            return None, (jsonify({"error": "Project not found."}), 404)
        return rows[0], None
    except Exception as exc:
        return None, (jsonify({"error": f"Database error: {exc}"}), 500)


@app.route("/projects/<project_id>/review", methods=["GET"])
def review_get(project_id):
    """Return the full review workspace payload for a project.

    On first open (working_boq is null), bootstraps working_boq as a deep copy
    of boq_data with stable UUIDs injected, persists it, and returns it.
    Subsequent opens return working_boq as-is — it is never re-derived from
    boq_data again so QS edits are never overwritten.

    Response shape:
    {
      "project":       { id, name, client_name, status, signed_off_at, ... },
      "boq_data":      { ... },   // working_boq (or bootstrapped copy) — the live bill
      "review_states": { item_id: {state, reason?}, ... },
      "counts":        { pending, approved, modified, rejected, removed, total },
      "grand_total":   float,
      "audit_events":  [ ... ]    // newest first, up to 100 rows
    }
    """
    user, err = _authenticated_user()
    if err:
        return err

    project, err = _fetch_review_project(project_id, user.id)
    if err:
        return err

    boq_data = project.get("boq_data")
    if not boq_data:
        return jsonify({"error": "No Bill of Quantities has been generated for this project yet."}), 422

    working_boq = project.get("working_boq")
    if not working_boq:
        # First open: bootstrap working_boq from boq_data with stable IDs assigned.
        working_boq = _assign_item_ids(boq_data)
        try:
            _db_client().table("projects").update({
                "working_boq": working_boq,
            }).eq("id", project_id).eq("user_id", user.id).execute()
        except Exception as exc:
            app.logger.warning("Could not persist working_boq bootstrap for %s: %s", project_id, exc)

    # Audit trail — newest first, limit 100
    audit_events: list = []
    try:
        ae_res = (
            _db_client()
            .table("boq_audit_events")
            .select("id, action, item_id, section, prev_state, new_state, reason, created_at")
            .eq("project_id", project_id)
            .order("created_at", desc=True)
            .limit(100)
            .execute()
        )
        audit_events = getattr(ae_res, "data", None) or []
    except Exception as exc:
        app.logger.warning("Could not load audit events for project %s: %s", project_id, exc)

    review_states = project.get("review_states") or {}
    return jsonify({
        "project": {
            "id":           project["id"],
            "name":         project.get("name") or "",
            "client_name":  project.get("client_name") or "",
            "status":       project.get("status") or "draft",
            "signed_off_at":   project.get("signed_off_at"),
            "signed_off_by":   project.get("signed_off_by"),
            "signoff_title":   project.get("signoff_title"),
            "signoff_hash":    project.get("signoff_hash"),
        },
        "boq_data":      working_boq,   # key kept as boq_data for frontend compatibility
        "review_states": review_states,
        "counts":        _review_counts(working_boq, review_states),
        "grand_total":   _review_grand_total(working_boq, review_states),
        "audit_events":  audit_events,
    }), 200


_EDITABLE_LINE_FIELDS = frozenset({
    "description", "trade", "unit", "quantity", "rate",
    "material_rate", "labour_rate", "plant_rate", "waste_disposal_rate",
    "drawing_ref", "dimension_string", "rate_key",
})


@app.route("/projects/<project_id>/review/line/<item_id>", methods=["PATCH"])
def review_line_update(project_id, item_id):
    """Update one line: field edits and/or review-state action.

    Body: {
      field_edits?: { description?, trade?, unit?, quantity?, rate?,
                      material_rate?, labour_rate?, plant_rate?,
                      waste_disposal_rate?, drawing_ref?, dimension_string?,
                      rate_key? },
      action?: "approve"|"reject"|"reopen",
      reason?:  str  (required when action=reject)
    }

    Backward compat: action="modify" with qty/rate is translated to field_edits
    so old clients and tests continue to work.

    Returns: { item_id, item, state, grand_total, counts, audit_events }
    """
    user, err = _authenticated_user()
    if err:
        return err

    body        = request.get_json(force=True, silent=True) or {}
    action      = (body.get("action") or "").strip()
    field_edits = dict(body.get("field_edits") or {})
    reason      = (body.get("reason") or "").strip()

    # Backward compat: old action="modify" with qty/rate → field_edits
    if action == "modify":
        if body.get("qty") is not None:
            field_edits.setdefault("quantity", float(body["qty"]))
        if body.get("rate") is not None:
            field_edits.setdefault("rate", float(body["rate"]))
        action = ""

    if action and action not in ("approve", "reject", "reopen"):
        return jsonify({"error": "action must be one of: approve, reject, reopen"}), 400
    if action == "reject" and not reason:
        return jsonify({"error": "reason is required when rejecting a line."}), 400
    if not field_edits and not action:
        return jsonify({"error": "Provide field_edits and/or action."}), 400

    project, err = _fetch_review_project(project_id, user.id)
    if err:
        return err

    if project.get("signed_off_at"):
        return jsonify({"error": "Bill is signed off. Revoke sign-off before making changes."}), 409

    working_boq   = project.get("working_boq") or _assign_item_ids(project.get("boq_data") or {})
    review_states = dict(project.get("review_states") or {})

    # Locate the line in working_boq
    found_item = None
    for group in (working_boq.get("bill_of_quantities") or working_boq.get("trades") or []):
        if not isinstance(group, dict):
            continue
        for item in (group.get("items") or group.get("line_items") or []):
            if isinstance(item, dict) and item.get("id") == item_id:
                found_item = item
                break
        if found_item is not None:
            break

    if found_item is None:
        return jsonify({"error": f"Line {item_id!r} not found in working bill."}), 404

    audit_rows: list = []

    # ── Apply field edits ────────────────────────────────────────────────────
    if field_edits:
        for field, new_val in field_edits.items():
            if field not in _EDITABLE_LINE_FIELDS:
                continue
            if field in ("quantity", "rate", "material_rate", "labour_rate",
                         "plant_rate", "waste_disposal_rate"):
                new_val = float(new_val) if new_val is not None else 0.0
            old_val = found_item.get(field)
            if old_val == new_val:
                continue
            found_item[field] = new_val
            audit_row = _append_audit_event(
                project_id, user.id, "line_edited",
                item_id=item_id,
                prev_state={"field": field, "old_value": old_val},
                new_state={"field": field, "new_value": new_val},
            )
            if audit_row:
                audit_rows.append(audit_row)

        # Recompute stored total so the item is self-consistent
        rs = review_states.get(item_id) or {}
        found_item["total"] = _effective_line_total(found_item, rs)

        # State transition: approved → pending (edit invalidates prior approval);
        # rejected stays rejected (QS must explicitly Reopen); others → modified.
        current_state = rs.get("state", "pending")
        if current_state == "approved":
            review_states[item_id] = {**rs, "state": "pending"}
        elif current_state != "rejected":
            review_states[item_id] = {**rs, "state": "modified"}

    # ── Apply review action ──────────────────────────────────────────────────
    if action:
        prev_rs = review_states.get(item_id, {})
        if action == "approve":
            new_rs: dict = {"state": "approved"}
        elif action == "reopen":
            new_rs = {"state": "pending"}
        else:  # reject
            new_rs = {"state": "rejected", "reason": reason}
        review_states[item_id] = new_rs

        audit_row = _append_audit_event(
            project_id, user.id,
            {"approve": "line_approved", "reject": "line_rejected", "reopen": "line_reopened"}[action],
            item_id=item_id,
            prev_state=prev_rs if prev_rs else None,
            new_state=new_rs,
            reason=reason or None,
        )
        if audit_row:
            audit_rows.append(audit_row)

    # ── Persist ──────────────────────────────────────────────────────────────
    try:
        _db_client().table("projects").update({
            "working_boq":   working_boq,
            "review_states": review_states,
            "status":        "in_review",
        }).eq("id", project_id).eq("user_id", user.id).execute()
    except Exception as exc:
        return jsonify({"error": f"Failed to save changes: {exc}"}), 500

    final_rs = review_states.get(item_id, {"state": "pending"})
    return jsonify({
        "item_id":      item_id,
        "item":         found_item,
        "state":        final_rs,
        "grand_total":  _review_grand_total(working_boq, review_states),
        "counts":       _review_counts(working_boq, review_states),
        "audit_events": audit_rows,
        # legacy key so old callers that read audit_event (singular) still work
        "audit_event":  audit_rows[0] if audit_rows else None,
    }), 200


@app.route("/projects/<project_id>/review/section", methods=["POST"])
def review_section_approve(project_id):
    """Bulk-approve all pending lines in one NRM2 section.

    Body: { section: "<trade name>" }
    Returns: { approved_count, grand_total, counts, audit_event? }
    """
    user, err = _authenticated_user()
    if err:
        return err

    body    = request.get_json(force=True, silent=True) or {}
    section = (body.get("section") or "").strip()
    if not section:
        return jsonify({"error": "section is required."}), 400

    project, err = _fetch_review_project(project_id, user.id)
    if err:
        return err

    if project.get("signed_off_at"):
        return jsonify({"error": "Bill is signed off. Revoke sign-off before making changes."}), 409

    working_boq   = project.get("working_boq") or _assign_item_ids(project.get("boq_data") or {})
    review_states = dict(project.get("review_states") or {})

    # Walk the matching section and approve every non-removed pending item
    approved_count = 0
    groups = working_boq.get("bill_of_quantities") or working_boq.get("trades") or []
    for gi, group in enumerate(groups):
        if not isinstance(group, dict):
            continue
        trade = group.get("trade") or group.get("name") or "General"
        if trade != section:
            continue
        for ii, item in enumerate(group.get("items") or group.get("line_items") or []):
            if not isinstance(item, dict):
                continue
            if item.get("removed"):
                continue
            key = item.get("id") or item.get("item_code") or f"g{gi}_i{ii}"
            cur_state = (review_states.get(key) or {}).get("state", "pending")
            if cur_state in ("pending", "modified"):
                review_states[key] = {"state": "approved"}
                approved_count += 1

    if approved_count:
        try:
            _db_client().table("projects").update({
                "review_states": review_states,
                "status": "in_review",
            }).eq("id", project_id).eq("user_id", user.id).execute()
        except Exception as exc:
            return jsonify({"error": f"Failed to save section approval: {exc}"}), 500

    audit_row = _append_audit_event(
        project_id, user.id, "section_approved",
        section=section,
        new_state={"approved_count": approved_count},
    )

    return jsonify({
        "approved_count": approved_count,
        "grand_total":    _review_grand_total(working_boq, review_states),
        "counts":         _review_counts(working_boq, review_states),
        "audit_event":    audit_row,
    }), 200


@app.route("/projects/<project_id>/signoff", methods=["POST"])
def review_signoff(project_id):
    """Sign off the bill.

    Body: { name, title, declaration: true }
    Computes a SHA-256 content hash, stamps signed_off_at/by/title/hash, and
    transitions status to 'signed_off'.  Does not enforce that every line is
    reviewed — the modal warns the user but allows sign-off with pending lines.
    """
    user, err = _authenticated_user()
    if err:
        return err

    body = request.get_json(force=True, silent=True) or {}
    name  = (body.get("name")  or "").strip()
    title = (body.get("title") or "").strip()
    declaration = bool(body.get("declaration"))

    if not name:
        return jsonify({"error": "name is required."}), 400
    if not title:
        return jsonify({"error": "title is required."}), 400
    if not declaration:
        return jsonify({"error": "declaration must be accepted."}), 400

    project, err = _fetch_review_project(project_id, user.id)
    if err:
        return err

    if project.get("signed_off_at"):
        return jsonify({"error": "Bill is already signed off."}), 409

    working_boq   = project.get("working_boq") or _assign_item_ids(project.get("boq_data") or {})
    review_states = project.get("review_states") or {}

    # Pending-gate: all lines must be reviewed before sign-off.
    counts = _review_counts(working_boq, review_states)
    if counts.get("pending", 0) > 0:
        return jsonify({
            "error":         f"{counts['pending']} line(s) still pending review.",
            "pending_count": counts["pending"],
        }), 409

    content_hash  = _signoff_hash(working_boq, review_states)

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    update_payload = {
        "signed_off_at":          now,
        "signed_off_by":          name,
        "signoff_title":          title,
        "signoff_declaration":    True,
        "signoff_hash":           content_hash,
        "status":                 "signed_off",
    }
    try:
        _db_client().table("projects").update(update_payload).eq("id", project_id).eq("user_id", user.id).execute()
    except Exception as exc:
        return jsonify({"error": f"Failed to record sign-off: {exc}"}), 500

    audit_row = _append_audit_event(
        project_id, user.id, "signed_off",
        new_state={"signed_off_by": name, "signoff_title": title, "signoff_hash": content_hash},
    )

    return jsonify({
        "signed_off_at":  now,
        "signed_off_by":  name,
        "signoff_title":  title,
        "signoff_hash":   content_hash,
        "audit_event":    audit_row,
    }), 200


@app.route("/projects/<project_id>/signoff", methods=["DELETE"])
def review_signoff_revoke(project_id):
    """Revoke an existing sign-off, returning the bill to 'in_review' status."""
    user, err = _authenticated_user()
    if err:
        return err

    project, err = _fetch_review_project(project_id, user.id)
    if err:
        return err

    if not project.get("signed_off_at"):
        return jsonify({"error": "Bill is not signed off."}), 409

    try:
        _db_client().table("projects").update({
            "signed_off_at":         None,
            "signed_off_by":         None,
            "signoff_title":         None,
            "signoff_declaration":   None,
            "signoff_hash":          None,
            "status":                "in_review",
        }).eq("id", project_id).eq("user_id", user.id).execute()
    except Exception as exc:
        return jsonify({"error": f"Failed to revoke sign-off: {exc}"}), 500

    audit_row = _append_audit_event(
        project_id, user.id, "signoff_revoked",
        prev_state={
            "signed_off_by": project.get("signed_off_by"),
            "signoff_hash":  project.get("signoff_hash"),
        },
    )

    return jsonify({"ok": True, "audit_event": audit_row}), 200


@app.route("/projects/<project_id>/audit", methods=["GET"])
def review_audit(project_id):
    """Return the audit trail for a project (newest first, up to 200 rows)."""
    user, err = _authenticated_user()
    if err:
        return err

    # Verify the user owns this project
    try:
        proj_res = (
            _db_client()
            .table("projects")
            .select("id")
            .eq("id", project_id)
            .eq("user_id", user.id)
            .limit(1)
            .execute()
        )
        if not (getattr(proj_res, "data", None) or []):
            return jsonify({"error": "Project not found."}), 404
    except Exception as exc:
        return jsonify({"error": f"Database error: {exc}"}), 500

    try:
        res = (
            _db_client()
            .table("boq_audit_events")
            .select("id, action, item_id, section, prev_state, new_state, reason, created_at")
            .eq("project_id", project_id)
            .order("created_at", desc=True)
            .limit(200)
            .execute()
        )
        return jsonify({"audit_events": getattr(res, "data", None) or []}), 200
    except Exception as exc:
        return jsonify({"error": f"Could not load audit trail: {exc}"}), 500


@app.route("/projects/<project_id>/review/line", methods=["POST"])
def review_line_create(project_id):
    """Add a new line to an existing section in working_boq.

    Body: {
      section_id: str,          // section UUID or trade name
      line: {
        description: str,       // required
        unit?: str,
        quantity?: float,
        rate? | material_rate?/labour_rate?/plant_rate?/waste_disposal_rate?: float,
        drawing_ref?: str,
        dimension_string?: str,
        rate_key?: str,
      }
    }
    Returns: { line, grand_total, counts, audit_event }
    """
    from uuid import uuid4
    user, err = _authenticated_user()
    if err:
        return err

    body       = request.get_json(force=True, silent=True) or {}
    section_id = (body.get("section_id") or "").strip()
    line_data  = body.get("line") or {}

    if not section_id:
        return jsonify({"error": "section_id is required."}), 400
    if not (line_data.get("description") or "").strip():
        return jsonify({"error": "line.description is required."}), 400

    project, err = _fetch_review_project(project_id, user.id)
    if err:
        return err

    if project.get("signed_off_at"):
        return jsonify({"error": "Bill is signed off. Revoke sign-off before making changes."}), 409

    working_boq   = project.get("working_boq") or _assign_item_ids(project.get("boq_data") or {})
    review_states = dict(project.get("review_states") or {})

    # Locate target section by UUID id or trade/name
    target_group = None
    groups = working_boq.get("bill_of_quantities") or working_boq.get("trades") or []
    for group in groups:
        if not isinstance(group, dict):
            continue
        if group.get("id") == section_id:
            target_group = group
            break
        if group.get("trade") == section_id or group.get("name") == section_id:
            target_group = group
            break

    if target_group is None:
        return jsonify({"error": f"Section {section_id!r} not found."}), 404

    new_id   = str(uuid4())
    new_line: dict = {
        "id":               new_id,
        "description":      (line_data.get("description") or "").strip(),
        "unit":             line_data.get("unit") or "",
        "quantity":         float(line_data.get("quantity") or 0),
        "drawing_ref":      line_data.get("drawing_ref") or "",
        "dimension_string": line_data.get("dimension_string") or "",
        "rate_key":         line_data.get("rate_key") or "",
    }
    for rfield in ("rate", "material_rate", "labour_rate", "plant_rate", "waste_disposal_rate"):
        if line_data.get(rfield) is not None:
            new_line[rfield] = float(line_data[rfield])
    new_line["total"] = _effective_line_total(new_line, {})

    key_name = "items" if "items" in target_group else "line_items"
    if key_name not in target_group:
        target_group["items"] = []
        key_name = "items"
    target_group[key_name].append(new_line)
    review_states[new_id] = {"state": "pending"}

    try:
        _db_client().table("projects").update({
            "working_boq":   working_boq,
            "review_states": review_states,
            "status":        "in_review",
        }).eq("id", project_id).eq("user_id", user.id).execute()
    except Exception as exc:
        return jsonify({"error": f"Failed to save new line: {exc}"}), 500

    trade_name = target_group.get("trade") or target_group.get("name") or ""
    audit_row = _append_audit_event(
        project_id, user.id, "line_added",
        item_id=new_id,
        section=trade_name,
        new_state={"description": new_line["description"], "total": new_line["total"]},
    )

    return jsonify({
        "line":        new_line,
        "grand_total": _review_grand_total(working_boq, review_states),
        "counts":      _review_counts(working_boq, review_states),
        "audit_event": audit_row,
    }), 200


@app.route("/projects/<project_id>/review/add-section", methods=["POST"])
def review_add_section(project_id):
    """Add a new section (trade) to working_boq.

    Body: { trade: str, nrm2_section?: str }
    Returns: { section, audit_event }
    """
    from uuid import uuid4
    user, err = _authenticated_user()
    if err:
        return err

    body  = request.get_json(force=True, silent=True) or {}
    trade = (body.get("trade") or "").strip()
    if not trade:
        return jsonify({"error": "trade is required."}), 400

    project, err = _fetch_review_project(project_id, user.id)
    if err:
        return err

    if project.get("signed_off_at"):
        return jsonify({"error": "Bill is signed off. Revoke sign-off before making changes."}), 409

    working_boq = project.get("working_boq") or _assign_item_ids(project.get("boq_data") or {})
    nrm2        = (body.get("nrm2_section") or "").strip()

    new_section: dict = {"id": str(uuid4()), "trade": trade, "items": []}
    if nrm2:
        new_section["nrm2_section"] = nrm2

    bill_key = "bill_of_quantities" if "bill_of_quantities" in working_boq else "trades"
    if bill_key not in working_boq:
        working_boq[bill_key] = []
    working_boq[bill_key].append(new_section)

    try:
        _db_client().table("projects").update({
            "working_boq": working_boq,
            "status":      "in_review",
        }).eq("id", project_id).eq("user_id", user.id).execute()
    except Exception as exc:
        return jsonify({"error": f"Failed to save new section: {exc}"}), 500

    audit_row = _append_audit_event(
        project_id, user.id, "section_added",
        section=trade,
        new_state={"trade": trade, "nrm2_section": nrm2 or None},
    )

    return jsonify({"section": new_section, "audit_event": audit_row}), 200


@app.route("/projects/<project_id>/review/line/<item_id>", methods=["DELETE"])
def review_line_remove(project_id, item_id):
    """Soft-delete a line (sets removed: true; never erases data).

    Body (optional): { reason: str }
    Returns: { grand_total, counts, audit_event }
    """
    from datetime import datetime, timezone
    user, err = _authenticated_user()
    if err:
        return err

    body   = request.get_json(force=True, silent=True) or {}
    reason = (body.get("reason") or "").strip()

    project, err = _fetch_review_project(project_id, user.id)
    if err:
        return err

    if project.get("signed_off_at"):
        return jsonify({"error": "Bill is signed off. Revoke sign-off before making changes."}), 409

    working_boq   = project.get("working_boq") or _assign_item_ids(project.get("boq_data") or {})
    review_states = dict(project.get("review_states") or {})

    now   = datetime.now(timezone.utc).isoformat()
    found = False
    for group in (working_boq.get("bill_of_quantities") or working_boq.get("trades") or []):
        if not isinstance(group, dict):
            continue
        for item in (group.get("items") or group.get("line_items") or []):
            if isinstance(item, dict) and item.get("id") == item_id:
                item["removed"]        = True
                item["removed_at"]     = now
                item["removed_reason"] = reason or None
                found = True
                break
        if found:
            break

    if not found:
        return jsonify({"error": f"Line {item_id!r} not found."}), 404

    try:
        _db_client().table("projects").update({
            "working_boq":   working_boq,
            "review_states": review_states,
            "status":        "in_review",
        }).eq("id", project_id).eq("user_id", user.id).execute()
    except Exception as exc:
        return jsonify({"error": f"Failed to remove line: {exc}"}), 500

    audit_row = _append_audit_event(
        project_id, user.id, "line_removed",
        item_id=item_id,
        reason=reason or None,
        new_state={"removed": True, "removed_at": now},
    )

    return jsonify({
        "grand_total": _review_grand_total(working_boq, review_states),
        "counts":      _review_counts(working_boq, review_states),
        "audit_event": audit_row,
    }), 200


@app.route("/projects/<project_id>/review/line/<item_id>/restore", methods=["POST"])
def review_line_restore(project_id, item_id):
    """Restore a soft-deleted line (clears removed flag).

    Returns: { grand_total, counts, audit_event }
    """
    user, err = _authenticated_user()
    if err:
        return err

    project, err = _fetch_review_project(project_id, user.id)
    if err:
        return err

    if project.get("signed_off_at"):
        return jsonify({"error": "Bill is signed off. Revoke sign-off before making changes."}), 409

    working_boq   = project.get("working_boq") or _assign_item_ids(project.get("boq_data") or {})
    review_states = dict(project.get("review_states") or {})

    found = False
    for group in (working_boq.get("bill_of_quantities") or working_boq.get("trades") or []):
        if not isinstance(group, dict):
            continue
        for item in (group.get("items") or group.get("line_items") or []):
            if isinstance(item, dict) and item.get("id") == item_id:
                item.pop("removed", None)
                item.pop("removed_at", None)
                item.pop("removed_reason", None)
                found = True
                break
        if found:
            break

    if not found:
        return jsonify({"error": f"Line {item_id!r} not found."}), 404

    try:
        _db_client().table("projects").update({
            "working_boq":   working_boq,
            "review_states": review_states,
            "status":        "in_review",
        }).eq("id", project_id).eq("user_id", user.id).execute()
    except Exception as exc:
        return jsonify({"error": f"Failed to restore line: {exc}"}), 500

    audit_row = _append_audit_event(
        project_id, user.id, "line_restored",
        item_id=item_id,
        new_state={"removed": False},
    )

    return jsonify({
        "grand_total": _review_grand_total(working_boq, review_states),
        "counts":      _review_counts(working_boq, review_states),
        "audit_event": audit_row,
    }), 200


def _build_export_payload(live_boq: dict, review_states: dict, project: dict) -> dict:
    """Build a filtered BoQ dict for export.

    Copies live_boq, removes rejected and soft-deleted lines from each group,
    recomputes every line's total, attaches the signoff block when applicable,
    and drops empty sections.  Does NOT mutate the original live_boq dict.
    """
    payload   = copy.deepcopy(live_boq)
    bill_key  = "bill_of_quantities" if "bill_of_quantities" in payload else "trades"
    groups    = payload.get(bill_key) or []
    for group in groups:
        if not isinstance(group, dict):
            continue
        items_key = "items" if "items" in group else "line_items"
        kept: list = []
        for item in (group.get(items_key) or []):
            if not isinstance(item, dict):
                continue
            if item.get("removed"):
                continue
            key = item.get("id") or item.get("item_code") or ""
            rs  = (review_states or {}).get(key) or {}
            if rs.get("state") == "rejected":
                continue
            item["total"] = _effective_line_total(item, rs)
            kept.append(item)
        group[items_key] = kept
    # Drop sections that have no remaining items after filtering
    payload[bill_key] = [
        g for g in groups
        if isinstance(g, dict) and (g.get("items") or g.get("line_items"))
    ]
    if project.get("signed_off_at"):
        payload["signoff"] = {
            "signed_off_by": project.get("signed_off_by"),
            "signoff_title":  project.get("signoff_title"),
            "signed_off_at":  project.get("signed_off_at"),
            "signoff_hash":   project.get("signoff_hash"),
        }
    return payload


@app.route("/projects/<project_id>/export/pdf", methods=["GET"])
def export_project_pdf(project_id):
    """Export the live, QS-edited working bill as PDF.

    Uses working_boq when present; falls back to boq_data for projects that
    pre-date this column (so old projects still export correctly).
    Excluded: rejected lines, soft-deleted lines.  Attached: signoff block
    when the bill has been signed off.
    """
    user, err = _authenticated_user()
    if err:
        return err

    project, err = _fetch_review_project(project_id, user.id)
    if err:
        return err

    live_boq = project.get("working_boq") or project.get("boq_data")
    if not live_boq:
        return jsonify({"error": "No Bill of Quantities for this project."}), 422

    review_states  = project.get("review_states") or {}
    _exp_watermark = True
    try:
        if _supabase:
            _plan = ((user.user_metadata or {}).get("plan", "free") or "free").lower()
            _exp_watermark = _plan not in ("pro", "studio")
    except Exception as _we:
        app.logger.warning("Watermark check failed: %s", _we)

    branding = _load_user_branding()
    payload  = _build_export_payload(live_boq, review_states, project)
    try:
        pdf_bytes = generate_boq_pdf(payload, watermark=_exp_watermark, branding=branding)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    except Exception as exc:
        return jsonify({"error": f"PDF generation failed: {exc}"}), 500

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name='bill-of-quantities.pdf',
    )


@app.route("/projects/<project_id>/export/excel", methods=["GET"])
def export_project_excel(project_id):
    """Export the live, QS-edited working bill as Excel.  Pro/Studio only."""
    user, err = _authenticated_user()
    if err:
        return err

    try:
        if _supabase:
            _plan = ((user.user_metadata or {}).get("plan", "free") or "free").lower()
            if _plan not in ("pro", "studio"):
                return jsonify({"error": "Excel export is available on Pro and Studio plans."}), 403
    except Exception as _xlge:
        app.logger.warning("Plan gate check failed for Excel export: %s", _xlge)

    project, err = _fetch_review_project(project_id, user.id)
    if err:
        return err

    live_boq = project.get("working_boq") or project.get("boq_data")
    if not live_boq:
        return jsonify({"error": "No Bill of Quantities for this project."}), 422

    review_states = project.get("review_states") or {}
    branding      = _load_user_branding()
    firm_name     = branding.get("company_name", "")
    project_name  = project.get("name") or ""
    payload       = _build_export_payload(live_boq, review_states, project)
    try:
        excel_bytes = generate_boq_excel(payload, firm_name, project_name, branding=branding)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    except Exception as exc:
        return jsonify({"error": f"Excel generation failed: {exc}"}), 500

    return send_file(
        io.BytesIO(excel_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="bill-of-quantities.xlsx",
    )


@app.route("/projects/<project_id>/export/pdf/original", methods=["GET"])
def export_project_pdf_original(project_id):
    """Export the original, untouched AI draft as PDF.

    Reads boq_data only — never working_boq, never review_states.  No sign-off
    block (the original draft is never signed; only the reviewed copy can be).
    The filename makes it unmistakable that this is the pre-review AI output.
    """
    user, err = _authenticated_user()
    if err:
        return err

    project, err = _fetch_review_project(project_id, user.id)
    if err:
        return err

    boq_data = project.get("boq_data")
    if not boq_data:
        return jsonify({"error": "No AI draft exists for this project yet."}), 404

    _exp_watermark = True
    try:
        if _supabase:
            _plan = ((user.user_metadata or {}).get("plan", "free") or "free").lower()
            _exp_watermark = _plan not in ("pro", "studio")
    except Exception as _we:
        app.logger.warning("Watermark check failed: %s", _we)

    branding = _load_user_branding()
    try:
        pdf_bytes = generate_boq_pdf(boq_data, watermark=_exp_watermark, branding=branding)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    except Exception as exc:
        return jsonify({"error": f"PDF generation failed: {exc}"}), 500

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name='bill-of-quantities-AI-DRAFT.pdf',
    )


@app.route("/projects/<project_id>/export/excel/original", methods=["GET"])
def export_project_excel_original(project_id):
    """Export the original, untouched AI draft as Excel.  Pro/Studio only."""
    user, err = _authenticated_user()
    if err:
        return err

    try:
        if _supabase:
            _plan = ((user.user_metadata or {}).get("plan", "free") or "free").lower()
            if _plan not in ("pro", "studio"):
                return jsonify({"error": "Excel export is available on Pro and Studio plans."}), 403
    except Exception as _xlge:
        app.logger.warning("Plan gate check failed for Excel export: %s", _xlge)

    project, err = _fetch_review_project(project_id, user.id)
    if err:
        return err

    boq_data = project.get("boq_data")
    if not boq_data:
        return jsonify({"error": "No AI draft exists for this project yet."}), 404

    branding     = _load_user_branding()
    firm_name    = branding.get("company_name", "")
    project_name = project.get("name") or ""
    try:
        excel_bytes = generate_boq_excel(boq_data, firm_name, project_name, branding=branding)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    except Exception as exc:
        return jsonify({"error": f"Excel generation failed: {exc}"}), 500

    return send_file(
        io.BytesIO(excel_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="bill-of-quantities-AI-DRAFT.xlsx",
    )


def _run_boq_pipeline(user=None):
    """Shared upload → pdfplumber → Claude → validate → enrich pipeline.

    Single home for the BoQ generation business logic, used by both the
    authenticated /process route and the public /demo-process route so the
    pipeline is never duplicated.  Reads the uploaded file from the current
    Flask request context.

    `user` is the already-validated Supabase user resolved by the caller
    (/process passes it; /demo-process passes None for the public path). Passing
    it in means we DON'T re-call _supabase.auth.get_user() three separate times
    inside one request — each of those was a network round trip, and the ones
    after the Claude call widened the window in which a worker-kill could lose a
    BoQ that had already been billed.

    Returns (boq_data, pages_text, uploaded_file, error) where error is a
    (response, status) tuple ready to return from a view, or None on success.
    """
    _fail = (None, None, None)             # prefix for every error return below

    # ── Per-user monthly quota check ─────────────────────────────────────────
    # Free plan: 50,000 tokens/month (~2 small projects).
    # Pro plan:  2,000,000 tokens/month (effectively unlimited for normal use).
    # Studio plan: same as Pro.
    # If Supabase is unavailable we fail open (allow the request) so an infra
    # blip never hard-blocks a paying user.
    _PLAN_MONTHLY_TOKEN_LIMITS = {
        "free":   50_000,
        "pro":    2_000_000,
        "studio": 2_000_000,
    }
    try:
        # Reuse the user the caller already validated — no extra auth round trip.
        # (user is None on the public /demo-process path, which skips the quota.)
        _quota_user = user
        if _supabase and _quota_user:
            _plan = (
                (_quota_user.user_metadata or {}).get("plan", "free") or "free"
            ).lower().strip()
            _limit = _PLAN_MONTHLY_TOKEN_LIMITS.get(_plan, _PLAN_MONTHLY_TOKEN_LIMITS["free"])

            # Sum tokens used this calendar month
            from datetime import datetime, timezone
            _month_start = datetime.now(timezone.utc).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            ).isoformat()
            _usage_rows = (
                _db_client()
                .table("usage_events")
                .select("input_tokens, output_tokens")
                .eq("user_id", _quota_user.id)
                .gte("created_at", _month_start)
                .execute()
            )
            _tokens_used = sum(
                (r.get("input_tokens", 0) or 0) + (r.get("output_tokens", 0) or 0)
                for r in (_usage_rows.data or [])
            )
            if _tokens_used >= _limit:
                return (*_fail, (jsonify({
                    "error": (
                        f"Monthly usage limit reached for your {_plan.title()} plan "
                        f"({_tokens_used:,} of {_limit:,} tokens used). "
                        "Upgrade your plan or wait until next month to continue."
                    )
                }), 429))
    except Exception as _qe:
        app.logger.warning("Quota check failed (failing open): %s", _qe)
    # ── End quota check ──────────────────────────────────────────────────────

    # ── Free-tier project count gate (2 completed projects per calendar month) ─
    try:
        # Reuse the caller-validated user instead of a second auth round trip.
        _pc_user = user
        if _supabase and _pc_user:
            _pc_plan = (
                (_pc_user.user_metadata or {}).get("plan", "free") or "free"
            ).lower().strip()
            if _pc_plan == "free":
                from datetime import datetime, timezone
                _pc_month_start = datetime.now(timezone.utc).replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0
                ).isoformat()
                _pc_rows = (
                    _db_client()
                    .table("projects")
                    .select("id")
                    .eq("user_id", _pc_user.id)
                    .eq("status", "completed")
                    .gte("created_at", _pc_month_start)
                    .execute()
                )
                _pc_count = len(_pc_rows.data or [])
                if _pc_count >= 2:
                    return (*_fail, (jsonify({
                        "error": (
                            "Free plan includes 2 completed projects per month. "
                            f"You have used {_pc_count} this month. "
                            "Upgrade to Pro for unlimited projects."
                        )
                    }), 429))
    except Exception as _pce:
        app.logger.warning("Project count gate failed (failing open): %s", _pce)
    # ── End project count gate ────────────────────────────────────────────────

    if "file" not in request.files:        # request.files is a dict of uploaded files keyed by form field name (like IFormFileCollection in C#)
        return (*_fail, (jsonify({"error": "No 'file' field in request. POST multipart/form-data with field name 'file'."}), 400))  # 400 Bad Request

    uploaded_file = request.files["file"]  # retrieve the FileStorage object for the field named "file"
    if uploaded_file.filename == "":       # empty filename means the browser sent the field but no file was selected
        return (*_fail, (jsonify({"error": "Empty filename — no file was selected."}), 400))

    if not uploaded_file.filename.lower().endswith(".pdf"):   # validate extension; .lower() normalises casing so "Drawing.PDF" is accepted
        return (*_fail, (jsonify({"error": "Only PDF files are accepted."}), 415))            # 415 Unsupported Media Type

    pdf_bytes = uploaded_file.read()       # read the entire upload into bytes in memory — never written to disk (like reading a Stream into byte[] in C#)
    pdf_buffer = io.BytesIO(pdf_bytes)     # wrap bytes in BytesIO so pdfplumber can treat it like a seekable file (like new MemoryStream(bytes) in C#)
    
    app.logger.info("START PDF PARSE: filename=%s file_size_bytes=%d", uploaded_file.filename, len(pdf_bytes))

    try:                                   # try/except is Python's equivalent of try/catch in C#
        with pdfplumber.open(pdf_buffer) as pdf:          # 'with' guarantees the PDF is closed even on exception — like C# 'using'
            app.logger.info("PDF opened: page_count=%d", len(pdf.pages))
            pages_text = [page.extract_text() or "" for page in pdf.pages]  # list comprehension: extract text from every page; replace None with "" (like LINQ Select in C#)
        full_text = "\n\n".join(pages_text)               # join all pages with double newline so Claude sees page breaks (like String.Join in C#)
        app.logger.info("END PDF PARSE: extracted_text_length=%d approx_words=%d", len(full_text), len(full_text.split()))
    except Exception as exc:               # catch any pdfplumber error (corrupt file, password-protected PDF, etc.)
        app.logger.exception("START PDF PARSE FAILED: exception_type=%s exception_message=%s", type(exc).__name__, str(exc))
        return (*_fail, (jsonify({"error": f"Failed to read PDF: {exc}"}), 422))  # 422 Unprocessable Entity; f"..." is Python's interpolated string (like $"..." in C#)

    if not full_text.strip():              # .strip() removes whitespace; empty result means a scanned image PDF with no OCR text layer
        app.logger.warning("PDF_PARSE_EMPTY_TEXT: no text extracted from %d pages", len(pages_text))
        return (*_fail, (jsonify({"error": "No text could be extracted. The PDF may be a scanned image without an OCR text layer."}), 422))

    api_key = os.environ.get("ANTHROPIC_API_KEY")  # read the key from the environment — never hard-code secrets in source (like Environment.GetEnvironmentVariable in C#)
    if not api_key:                                 # fail fast with a clear message if the variable is missing
        return (*_fail, (jsonify({"error": "ANTHROPIC_API_KEY environment variable is not set on the server."}), 500))

    # ROOT-CAUSE FIX (confirmed via Railway logs: httpx.ReadTimeout → APITimeoutError).
    # The old non-streaming client used timeout=120s (later 240s). A full NRM2 bill
    # (max_tokens=BOQ_MAX_OUTPUT_TOKENS against the ~6,500-token SYSTEM_PROMPT, which
    # forces all 41 sections regardless of input) legitimately generates for
    # SEVERAL MINUTES even
    # for a 3KB PDF — so any short *total-request* timeout trips while Claude is still
    # producing billable output: tokens burnt, no usable result.
    #
    # Two-part fix:
    #   (1) timeout = ANTHROPIC_CLIENT_TIMEOUT_S (600s). Combined with STREAMING below
    #       this behaves as an INACTIVITY timeout: it only fires if tokens stop
    #       arriving for 600s, which a healthy generation never does — so the
    #       wall-clock length of a slow-but-successful bill no longer matters.
    #   (2) max_retries=0 — never silently re-bill a long, non-idempotent generation.
    # The gunicorn worker timeout (api/gunicorn.conf.py = GUNICORN_WORKER_TIMEOUT_S,
    # 660s) sits ABOVE this so the worker is never killed mid-stream; the layers are
    # logged together at boot as TIMEOUT_BUDGET. 120s/240s were simply far too
    # aggressive for non-streaming 16k-token output.
    client = anthropic.Anthropic(api_key=api_key, timeout=float(ANTHROPIC_CLIENT_TIMEOUT_S), max_retries=0)

    app.logger.info(
        # Log value is DERIVED from the constant (was a hardcoded "16000") so the log
        # can never drift from the real max_tokens sent on the call below.
        "START AI CALL: model=claude-sonnet-4-6 max_tokens=%d streaming=true "
        "tool=%s tool_choice=forced timeout=%ss pdf_text_length=%d approx_words=%d",
        BOQ_MAX_OUTPUT_TOKENS, BOQ_TOOL_NAME, ANTHROPIC_CLIENT_TIMEOUT_S, len(full_text), len(full_text.split()),
    )
    try:
        _t = time.time()
        _last_log = _t
        _chars = 0
        # STREAM the completion instead of blocking on messages.create(). Two wins:
        #   • the socket stays continuously active, so the read timeout cannot trip
        #     while tokens are flowing (the 120s ReadTimeout failure mode is gone);
        #   • we emit a heartbeat every ~15s so Railway logs PROVE the call is alive
        #     and show progress, instead of a silent multi-minute gap.
        # We FORCE tool use (tools + tool_choice): the BoQ comes back as a tool_use
        # block whose .input is a schema-shaped dict, eliminating the ```json-fence and
        # wrong-shape 502s. stream.get_final_message() still returns the full Message.
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=BOQ_MAX_OUTPUT_TOKENS,      # raised 16000 → 32000 (see BOQ_MAX_OUTPUT_TOKENS): the old cap truncated full NRM2 bills mid-JSON
            system=SYSTEM_PROMPT,                  # system prompt is a top-level kwarg in the Anthropic SDK (NOT a {"role":"system"} entry — that's the OpenAI convention)
            tools=[BOQ_TOOL],                      # hand Claude the BoQ schema AS a tool (input_schema == BOQ_OUTPUT_SCHEMA)
            tool_choice={"type": "tool", "name": BOQ_TOOL_NAME},   # FORCE the answer into that tool's input — no free-text JSON to mis-shape or fence
            messages=[
                {"role": "user", "content": full_text},   # the extracted PDF text is the entire user turn for Claude to analyse
            ],
        ) as stream:
            # Forced tool use emits NO text deltas — the BoQ streams as input_json_delta
            # events — so iterate the RAW event stream, not stream.text_stream (which
            # would be empty and starve the heartbeat). Counting partial_json bytes keeps
            # "AI CALL IN PROGRESS" meaningful so a stuck stream is still distinguishable
            # from a slow-but-healthy one in Railway logs.
            for _event in stream:
                if getattr(_event, "type", None) == "content_block_delta":
                    _delta = getattr(_event, "delta", None)
                    _piece = getattr(_delta, "partial_json", None) or getattr(_delta, "text", None)
                    if _piece:
                        _chars += len(_piece)
                _now = time.time()
                if _now - _last_log >= 15:          # heartbeat at most every 15s — keeps logs readable
                    app.logger.info("AI CALL IN PROGRESS: elapsed=%.0fs accumulated_chars=%d", _now - _t, _chars)
                    _last_log = _now
            response = stream.get_final_message()   # fully-accumulated Message; tool_use.input is a parsed dict
        _ai_call_time = round(time.time() - _t, 1)
        _processing_times.append(_ai_call_time)
        if len(_processing_times) > 200:
            _processing_times.pop(0)
        app.logger.info("END AI CALL: processing_time_seconds=%s accumulated_chars=%d stop_reason=%s",
                        _ai_call_time, _chars, getattr(response, "stop_reason", None))
    except anthropic.APIStatusError as exc:
        app.logger.exception("AI CALL FAILED (APIStatusError): status_code=%s message=%s", exc.status_code, exc.message)
        return (*_fail, (jsonify({"error": f"Claude API error {exc.status_code}: {exc.message}"}), 502))
    except anthropic.APITimeoutError as exc:
        # ACCURATE message: this is a generation-TIME problem, not a file-SIZE problem.
        # The old text ("the PDF may be too large") was actively misleading — a 3KB PDF
        # triggers it too, because the system prompt forces a full bill regardless of
        # input size. Only mention document size when the extracted text really is large.
        app.logger.exception("AI CALL FAILED (APITimeoutError after %ss inactivity): %s", ANTHROPIC_CLIENT_TIMEOUT_S, str(exc))
        if len(full_text) > 60000:   # ~15k+ tokens of input genuinely adds latency
            _to_msg = ("Claude timed out generating the Bill of Quantities. Your document is "
                       "large, which adds to generation time — try splitting it into smaller "
                       "sections, or try again in a moment.")
        else:
            _to_msg = ("Claude is taking longer than expected to generate the full Bill of "
                       "Quantities. This is usually due to server load, not file size — "
                       "please try again in a moment.")
        return (*_fail, (jsonify({"error": _to_msg}), 504))
    except anthropic.APIConnectionError as exc:
        app.logger.exception("AI CALL FAILED (APIConnectionError): %s", str(exc))
        return (*_fail, (jsonify({"error": f"Could not reach Claude API: {exc}"}), 503))

    # ── Read Claude's answer. PRIMARY: forced tool_use → a schema-shaped dict ────────
    # tool_choice forced the model to answer via the record_bill_of_quantities tool, so
    # the BoQ arrives as tool_use.input — already a parsed dict in the correct shape.
    # This is the definitive fix for the two Railway-logged 502 bugs: Bug 1 (the model
    # wrapped JSON in a ```json fence → json.loads failed at char 0) and Bug 2 (it
    # returned bill_of_quantities as an OBJECT of metadata, not the required ARRAY).
    # tool_use has no text and no fence, and its shape is schema-driven, so both vanish.
    tool_input = _extract_tool_use_input(response)
    raw_text   = _extract_claude_text(response)   # normally "" under forced tool use; kept for the text fallback + logging
    app.logger.info("Claude response read: tool_use=%s raw_text_length=%d", tool_input is not None, len(raw_text))
    _log_claude_response("structured", response)

    # ── COST-SAFETY GUARDRAIL: persist the paid-for Claude output FIRST ──────────
    # This runs immediately after the (billed) Claude call and BEFORE JSON parse,
    # schema validation, enrichment and auto-save. If any of those later steps
    # raises — or the worker is killed before the response reaches the browser —
    # the raw response we already paid for is safely on disk in usage_events, so
    # it can be recovered without calling (and paying) Claude again.
    #   TODO(recovery): a future GET /projects/<id>/recover (out of scope now)
    #   could read the latest usage_events.raw_response for the user, re-run
    #   _enrich_boq on it and return the BoQ — no second Claude call required.
    # Best-effort: a logging/persistence failure must NEVER fail the request.
    # We reuse the caller-validated `user` instead of a 3rd auth.get_user() call.
    try:
        _usage = getattr(response, "usage", None)
        if _supabase and user:
            _usage_row = {
                "user_id":       user.id,
                "input_tokens":  getattr(_usage, "input_tokens",  0) or 0,
                "output_tokens": getattr(_usage, "output_tokens", 0) or 0,
            }
            # Extra recovery columns (raw_response/model/stop_reason) are added by
            # supabase_schema.sql. On a live DB that hasn't run the migration yet,
            # PostgREST rejects unknown columns — so fall back to the minimal row
            # rather than losing the usage event entirely.
            # Under forced tool use raw_text is empty, so persist the tool_use input
            # JSON instead — otherwise the cost-safety recovery would have nothing to
            # recover. The raw_response column is text and holds either form.
            _persist_payload = raw_text
            if not _persist_payload and tool_input is not None:
                try:
                    _persist_payload = json.dumps(tool_input)
                except Exception:
                    _persist_payload = ""
            _recovery_row = {
                **_usage_row,
                "raw_response": _persist_payload,
                "model":        "claude-sonnet-4-6",
                "stop_reason":  getattr(response, "stop_reason", None),
            }
            try:
                _db_client().table("usage_events").insert(_recovery_row).execute()
            except Exception as _re:
                app.logger.warning(
                    "Recovery columns not present (run supabase_schema.sql to enable "
                    "BoQ recovery); persisting usage only: %s", _re)
                _db_client().table("usage_events").insert(_usage_row).execute()
    except Exception as _ue:
        app.logger.warning("Failed to persist usage event: %s", _ue)

    stop_reason = getattr(response, "stop_reason", None)
    truncated   = (stop_reason == "max_tokens")
    if stop_reason == "refusal":
        app.logger.error("AI_OUTPUT_REFUSED: stop_reason=refusal")
        return (*_fail, (jsonify({"error": "Claude refused to produce the requested structured output."}), 502))

    # User-facing 502 messages, defined once (reused on every parse/validate failure path).
    _TRUNC_MSG = ("This was an unusually large and detailed bill, and Claude reached its "
                  "maximum output length before the Bill of Quantities finished. Please try "
                  "generating it again — large bills occasionally complete on a second pass.")
    _SHAPE_MSG = ("The AI returned an unexpected structure for the Bill of Quantities. "
                  "This is usually transient — please try generating again.")

    # ── Obtain boq_data as a dict ────────────────────────────────────────────────
    # PRIMARY: the forced tool_use input — already a dict, schema-shaped (no fence, no
    # json.loads). On a max_tokens truncation the SDK's jiter partial-parse yields the
    # valid-so-far portion, and _normalize_boq_shape below drops any incomplete tail.
    boq_data = None
    if tool_input is not None:
        boq_data = tool_input
        app.logger.info("BOQ_SOURCE=tool_use input_keys=%s", list(tool_input.keys()))
    else:
        # FALLBACK (should not happen under forced tool_choice): the model returned TEXT.
        # Strip any markdown code fence (Bug 1) then parse; on truncation use the
        # bracket-closing salvage; last resort = first-'{'…last-'}' substring (only AFTER
        # fence-strip fails, so valid JSON with braces inside strings is never corrupted).
        cleaned = _strip_code_fence(raw_text)
        app.logger.warning("BOQ_SOURCE=text_fallback cleaned_length=%d fence_stripped=%s",
                           len(cleaned), cleaned != (raw_text or "").strip())
        try:
            boq_data = json.loads(cleaned)
        except Exception as _je:
            app.logger.warning("TEXT_FALLBACK json.loads failed (%s); trying salvage/extraction", _je)
            if truncated:
                boq_data = _salvage_truncated_boq(cleaned)
            if boq_data is None:
                boq_data = _extract_first_json_object(cleaned)
        if boq_data is None:
            app.logger.error("BOQ_UNPARSEABLE (truncated=%s). First 500 chars of raw_text: %s", truncated, (raw_text or "")[:500])
            return (*_fail, (jsonify({"error": _TRUNC_MSG if truncated else _SHAPE_MSG}), 502))

    # ── Normalise shape (defense-in-depth for the Bug 2 drift + truncation tails) ──
    # Fixes the EXACT drift the Railway logs showed — bill_of_quantities returned as an
    # OBJECT with metadata nested inside, plus invented top-level keys (project/client/
    # currency/notes) that would trip additionalProperties:false — and drops incomplete
    # trailing items. A slightly-off response degrades into a valid BoQ instead of a 502.
    try:
        boq_data = _normalize_boq_shape(boq_data)
    except Exception as _ne:
        app.logger.warning("BOQ_NORMALIZE_FAILED (continuing with raw shape): %s", _ne)

    # Nothing usable left (e.g. truncated before the first complete item) → surface an
    # accurate error rather than returning an empty bill (which would pass the schema).
    _trades = boq_data.get("bill_of_quantities") if isinstance(boq_data, dict) else None
    if not _trades:
        app.logger.error("BOQ_EMPTY_AFTER_NORMALIZE: no usable trade sections (truncated=%s)", truncated)
        return (*_fail, (jsonify({"error": _TRUNC_MSG if truncated else _SHAPE_MSG}), 502))

    # ── Validate the (normalised) structure ──────────────────────────────────────
    app.logger.info("START SCHEMA VALIDATION: keys=%s trade_sections=%d", list(boq_data.keys()), len(_trades))
    try:
        _validate_boq_output(boq_data)
        app.logger.info("END SCHEMA VALIDATION: validation_passed=true")
    except ValueError as exc:
        # Log the FULL normalised payload (also persisted to usage_events) so the drift is
        # debuggable from Railway logs without re-running a paid generation.
        app.logger.error("SCHEMA_VALIDATION_FAILED after normalize: %s | payload=%s",
                         exc, json.dumps(boq_data, default=str)[:4000])
        return (*_fail, (jsonify({"error": _TRUNC_MSG if truncated else _SHAPE_MSG}), 502))
    except Exception as exc:
        app.logger.exception("SCHEMA_VALIDATION_FAILED: Unexpected exception_type=%s: %s", type(exc).__name__, str(exc))
        return (*_fail, (jsonify({"error": f"Schema validation error: {exc}"}), 502))

    app.logger.info("START RATE ENRICHMENT")
    try:
        boq_data = _enrich_boq(boq_data)               # look up rates in RATES_DB and add material_rate, labour_rate, line_total to every item
        app.logger.info("END RATE ENRICHMENT: enrichment_complete=true")
    except Exception as exc:
        app.logger.exception("RATE_ENRICHMENT_FAILED: exception_type=%s: %s", type(exc).__name__, str(exc))
        return (*_fail, (jsonify({"error": f"Failed to enrich BoQ with rates: {exc}"}), 502))

    if truncated:
        # NON-BLOCKING truncation flags (the tool/text path + normalize already salvaged a
        # partial-but-valid bill). Added AFTER validation + enrichment so they never trip
        # the schema's additionalProperties:False. The frontend reads _truncated to show a
        # caveat banner while STILL rendering and navigating to the (partial) bill.
        app.logger.warning("AI_OUTPUT_TRUNCATED_SALVAGED: proceeding with partial bill trades=%d", len(_trades))
        boq_data["_truncated"] = True
        boq_data["_truncation_notice"] = (
            "This bill was very large and may be missing its final sections — "
            "please review and regenerate if needed."
        )

    app.logger.info("PIPELINE_SUCCESS: returning_to_process_pdf truncated=%s trades=%d", truncated, len(_trades))
    return boq_data, pages_text, uploaded_file, None


@app.route("/process", methods=["POST"])   # decorator registers this function as POST /process handler — like [HttpPost("process")] in C# Web API
def process_pdf():                         # Flask calls this function when a matching request arrives
    app.logger.info("PROCESS_PDF_START: method=POST path=/process")

    # Validate the JWT up front — NOT just "is a token present?". The old guard
    # only checked _get_bearer_token() was non-empty, so an EXPIRED/invalid token
    # sailed past it and still triggered a paid Claude call (the quota/auto-save
    # blocks fail open on a bad token). Resolving the user here means an expired
    # mid-upload session returns a clean 401 BEFORE any billing, and the frontend
    # can redirect to sign-in instead of showing a fake-progress hang.
    user, err = _authenticated_user()
    if err:
        app.logger.warning("PROCESS_PDF_AUTH_FAILED: token missing/invalid/expired")
        return err

    app.logger.info("PROCESS_PDF_AUTH_OK: calling _run_boq_pipeline user_id=%s", user.id)
    # Pass the validated user down so the pipeline reuses it for the quota gate,
    # project gate and usage persistence instead of re-validating 3 more times.
    boq_data, pages_text, uploaded_file, err = _run_boq_pipeline(user=user)
    if err:
        app.logger.error("PROCESS_PDF_PIPELINE_ERROR: pipeline_returned_error")
        return err

    app.logger.info("PROCESS_PDF_PIPELINE_SUCCESS: pages=%d boq_trades=%d", 
                   len(pages_text), 
                   len(boq_data.get("bill_of_quantities", [])) if isinstance(boq_data, dict) else 0)
    
    print('BOQ STRUCTURE:', json.dumps(boq_data, indent=2)[:500])

    # Auto-save the completed BoQ as a project for the authenticated user.
    # This is best-effort: any failure is logged but never surfaced to the caller,
    # so a save problem can't turn a successful BoQ generation into an error response.
    app.logger.info("START AUTO-SAVE")
    try:
        # Reuse the user validated at the top of this route — this used to be a
        # 4th _supabase.auth.get_user() round trip AFTER the Claude call, which is
        # exactly the kind of post-billing latency that widened the worker-kill
        # window described in the timeout fix above.
        if user:
            app.logger.info("AUTO_SAVE: authenticated user_id=%s", user.id)
            db = _db_client()
            project_id = (request.form.get("project_id") or "").strip()
            if project_id:
                # The upload belongs to an existing project (workspace flow) —
                # attach the BoQ to that row instead of creating a duplicate.
                app.logger.info("AUTO_SAVE: updating existing project_id=%s", project_id)
                db.table("projects").update({
                    "page_count":      len(pages_text),
                    "estimated_value": _sum_line_totals(boq_data),
                    "boq_data":        boq_data,
                    "status":          "completed",
                }).eq("id", project_id).eq("user_id", user.id).execute()
                app.logger.info("AUTO_SAVE: project update completed for project_id=%s", project_id)
            else:
                project_name = re.sub(r'\.pdf$', '', uploaded_file.filename, flags=re.IGNORECASE)  # filename without the .pdf extension
                app.logger.info("AUTO_SAVE: creating new project name=%s pages=%d", project_name, len(pages_text))
                _insert_project(
                    db,
                    user_id=user.id,
                    name=project_name,
                    page_count=len(pages_text),                # one entry in pages_text per PDF page
                    estimated_value=_sum_line_totals(boq_data),  # total of every line_total in the enriched BoQ
                    boq_data=boq_data,
                    status='completed',
                )
                app.logger.info("AUTO_SAVE: new project created successfully")
        else:
            app.logger.warning("AUTO_SAVE: no authenticated user, skipping save")
    except Exception as exc:
        app.logger.exception("AUTO_SAVE_FAILED: exception_type=%s message=%s (continuing to return response)", type(exc).__name__, str(exc))

    app.logger.info("START RESPONSE BUILD: serializing boq_data to JSON")
    try:
        response_obj = jsonify(boq_data)
        response_obj.status_code = 200
        app.logger.info("END RESPONSE BUILD: jsonify successful status_code=200")
        app.logger.info("PROCESS_PDF_SUCCESS: returning response to client")
        return response_obj
    except Exception as exc:
        app.logger.exception("RESPONSE_BUILD_FAILED: exception_type=%s message=%s", type(exc).__name__, str(exc))
        error_response = jsonify({"error": f"Failed to serialize response: {exc}"})
        error_response.status_code = 502
        return error_response


# ── Public demo (no account required) ───────────────────────────────────────────────
# Lightweight in-memory rate limiting: one demo generation per IP per 30 minutes.
# A plain timestamp dict is deliberate — no Redis, no extra dependencies. State is
# per-process and resets on restart, which is acceptable for a marketing demo.
_DEMO_RATE_WINDOW_SECONDS = 30 * 60
_demo_last_request_at: dict[str, float] = {}   # client IP → unix timestamp of last demo run
_DEMO_MAX_SECTIONS = 3

_RE_MEASURED_SECTION = re.compile(r'^\s*5\.\d')   # measured works trades are numbered 5.x


def _demo_client_ip() -> str:
    """Resolve the caller's IP, honouring the proxy chain Railway puts in front of Flask."""
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()   # first hop is the original client
    return request.remote_addr or 'unknown'


def _trim_boq_for_demo(boq_data):
    """Restrict a full enriched BoQ to the public demo preview.

    Keeps only the first 3 measured work sections (5.x trades), drops
    provisional sum line items, and strips every other top-level section
    (risk schedule, assumptions register, annexes, document control) so the
    demo never returns the full NRM2 output. Grand Summary and Dayworks only
    exist in the PDF/Excel exports, which are disabled for the demo.
    """
    if isinstance(boq_data, dict):
        groups = boq_data.get('bill_of_quantities') or boq_data.get('trades') or []
    elif isinstance(boq_data, list):
        groups = boq_data
    else:
        groups = []

    def _demo_items(group):
        return [
            item for item in (group.get('items') or group.get('line_items') or [])
            if isinstance(item, dict)
            and 'provisional sum' not in (item.get('description') or '').lower()
        ]

    trimmed = []
    for group in groups:
        if len(trimmed) >= _DEMO_MAX_SECTIONS:
            break
        if not isinstance(group, dict):
            continue
        trade = (group.get('trade') or '').strip()
        if not _RE_MEASURED_SECTION.match(trade):
            continue                              # measured works only — no prelims etc.
        items = _demo_items(group)
        if items:
            trimmed.append({'trade': trade, 'items': items})

    if not trimmed:
        # Fallback for outputs with non-standard trade numbering: take the first
        # sections that have any non-provisional items rather than returning nothing.
        for group in groups:
            if len(trimmed) >= _DEMO_MAX_SECTIONS:
                break
            if not isinstance(group, dict):
                continue
            items = _demo_items(group)
            if items:
                trimmed.append({'trade': (group.get('trade') or 'Measured works').strip(), 'items': items})

    return {'demo': True, 'bill_of_quantities': trimmed}


@app.route("/demo-process", methods=["POST"])
def demo_process():
    """Public, unauthenticated demo endpoint.

    Runs exactly the same pipeline as /process (PDF → Claude → validation →
    rates enrichment) but never saves anything, and trims the response to the
    first 3 measured work sections before returning it.
    """
    global _demo_last_request_at
    ip  = _demo_client_ip()
    now = time.time()

    last = _demo_last_request_at.get(ip)
    if last and (now - last) < _DEMO_RATE_WINDOW_SECONDS:
        app.logger.info("Demo blocked by rate limit: ip=%s", ip)
        return jsonify({"error": "Demo limit reached. Please create a free account to continue."}), 429

    # Stamp before the Claude call so a second request from the same IP can't
    # run concurrently; the stamp is refunded below if generation fails.
    _demo_last_request_at[ip] = now
    if len(_demo_last_request_at) > 1000:          # keep the dict from growing unbounded
        cutoff = now - _DEMO_RATE_WINDOW_SECONDS
        _demo_last_request_at = {k: v for k, v in _demo_last_request_at.items() if v >= cutoff}

    app.logger.info("Demo started: ip=%s", ip)

    boq_data, _pages_text, _uploaded_file, err = _run_boq_pipeline()
    if err:
        _demo_last_request_at.pop(ip, None)        # don't burn the visitor's slot on a failed upload
        return err

    demo_boq = _trim_boq_for_demo(boq_data)
    app.logger.info("Demo completed: ip=%s sections=%s", ip, len(demo_boq["bill_of_quantities"]))
    return jsonify(demo_boq), 200


def _load_user_branding():
    """Best-effort load of the signed-in user's white-label branding.

    Returns a branding dict for the PDF pipeline, or {} when the caller is
    unauthenticated, has no branding row, or anything goes wrong. Never raises —
    a branding lookup must never break PDF export, so every failure path falls
    back to an empty dict (which reproduces the default Vulcan Quanta output).
    """
    try:
        token = _get_bearer_token()
        if not token or not _supabase:
            return {}
        user_res = _supabase.auth.get_user(token)
        user     = getattr(user_res, "user", None)
        if not user:
            return {}
        db = _db_client(token)
        if not db:
            return {}
        res = (
            db.table("branding")
            .select("company_name, company_address, company_phone, company_email, logo")
            .eq("user_id", user.id)
            .limit(1)
            .execute()
        )
        rows = getattr(res, "data", None) or []
        row  = rows[0] if rows else {}
        if not row:
            return {}
        # Map the DB `logo` column (a data URL) onto the pipeline's logo_url key.
        return {
            "company_name":    row.get("company_name")    or "",
            "company_address": row.get("company_address") or "",
            "company_phone":   row.get("company_phone")   or "",
            "company_email":   row.get("company_email")   or "",
            "logo_url":        row.get("logo")            or "",
        }
    except Exception as exc:
        app.logger.warning("Branding load failed (continuing without branding): %s", exc)
        return {}


@app.route("/export",   methods=["POST"])   # original route kept for backward compatibility
@app.route("/download", methods=["POST"])   # new route used by the frontend Download PDF button
def export_pdf():                           # Flask calls this for both URLs; stacking decorators is supported and idiomatic
    if not _get_bearer_token():            # guard: same auth requirement as /process
        return jsonify({"error": "Authentication required. Please sign in."}), 401

    # request.get_json() parses the JSON body — like JsonSerializer.Deserialize in C#
    # force=True accepts the body even if Content-Type is not application/json
    # silent=True returns None instead of raising an exception on parse failure
    boq_json = request.get_json(force=True, silent=True)
    if not boq_json:                       # guard: body was empty or not valid JSON
        return jsonify({"error": "Request body must be a JSON BoQ object."}), 400

    # Resolve plan for watermark decision
    _exp_watermark = True  # default to watermarked (safe fallback)
    try:
        if _supabase:
            _exp_user_res = _supabase.auth.get_user(_get_bearer_token())
            _exp_user     = getattr(_exp_user_res, "user", None) if _exp_user_res else None
            if _exp_user:
                _exp_plan = (
                    (_exp_user.user_metadata or {}).get("plan", "free") or "free"
                ).lower().strip()
                _exp_watermark = _exp_plan not in ("pro", "studio")
    except Exception as _we:
        app.logger.warning("Could not resolve plan for watermark check: %s", _we)

    branding = _load_user_branding()        # best-effort; {} when none configured

    try:
        pdf_bytes = generate_boq_pdf(
            boq_json,
            watermark=_exp_watermark,
            branding=branding,
        )   # build the PDF; returns raw bytes
    except ValueError as exc:             # raised by generate_boq_pdf if JSON has no trade groups
        return jsonify({"error": str(exc)}), 422
    except Exception as exc:              # catch any unexpected ReportLab error
        return jsonify({"error": f"PDF generation failed: {exc}"}), 500

    # Wrap the bytes in a BytesIO so send_file can stream it as a download.
    # send_file is equivalent to File(bytes, "application/pdf", "filename.pdf") in C# MVC.
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,                # triggers "Save As" in the browser (Content-Disposition: attachment)
        download_name='bill-of-quantities.pdf',
    )


@app.route("/export-excel", methods=["POST"])
def export_excel():
    if not _get_bearer_token():
        return jsonify({"error": "Authentication required. Please sign in."}), 401

    # ── Plan gate: Excel export is Pro and Studio only ────────────────────────
    try:
        if _supabase:
            _xl_user_res = _supabase.auth.get_user(_get_bearer_token())
            _xl_user     = getattr(_xl_user_res, "user", None) if _xl_user_res else None
            if _xl_user:
                _xl_plan = (
                    (_xl_user.user_metadata or {}).get("plan", "free") or "free"
                ).lower().strip()
                if _xl_plan not in ("pro", "studio"):
                    return jsonify({
                        "error": "Excel export is available on Pro and Studio plans. Upgrade to download in Excel format."
                    }), 403
    except Exception as _xlge:
        app.logger.warning("Plan gate check failed for Excel export: %s", _xlge)
    # ── End plan gate ─────────────────────────────────────────────────────────

    boq_json = request.get_json(force=True, silent=True)
    if not boq_json:
        return jsonify({"error": "Request body must be a JSON BoQ object."}), 400

    # Branding comes from the signed-in user's Settings → Branding row, same as
    # the PDF export. Query params remain as an explicit override / fallback.
    branding     = _load_user_branding()
    firm_name    = request.args.get("firm", "") or branding.get("company_name", "")
    project_name = request.args.get("project", "")

    try:
        excel_bytes = generate_boq_excel(boq_json, firm_name, project_name, branding=branding)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    except Exception as exc:
        return jsonify({"error": f"Excel generation failed: {exc}"}), 500

    return send_file(
        io.BytesIO(excel_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="bill-of-quantities.xlsx",
    )


# Reject measurement uploads larger than this before reading them into memory.
_MEASUREMENT_MAX_BYTES = 10 * 1024 * 1024   # 10 MB


@app.route("/measurement/import", methods=["POST"])
def measurement_import():
    """Parse an uploaded CSV/XLSX of measurements into rows.

    Phase-1 infrastructure: reads description/quantity/unit from the file and
    returns them as-is. No AI, no pricing, no NRM2, no persistence. Completely
    separate from /process — that route and its pipeline are untouched.
    """
    if "file" not in request.files:        # request.files keyed by form field name
        return jsonify({"error": "No 'file' field in request. POST multipart/form-data with field name 'file'."}), 400

    uploaded = request.files["file"]
    if uploaded.filename == "":
        return jsonify({"error": "Empty filename — no file was selected."}), 400

    name = uploaded.filename.lower()
    if not (name.endswith(".csv") or name.endswith(".xlsx")):
        return jsonify({"error": "Unsupported file type. Upload a .csv or .xlsx file."}), 415

    file_bytes = uploaded.read()
    if len(file_bytes) > _MEASUREMENT_MAX_BYTES:
        return jsonify({"error": "File too large. Maximum size is 10 MB."}), 413

    try:
        measurements = parse_measurements(uploaded.filename, file_bytes)
    except MeasurementImportError as exc:          # expected, user-facing failures
        return jsonify({"error": exc.message}), exc.status
    except Exception as exc:                        # never leak a stack trace to the client
        app.logger.exception("Measurement import failed unexpectedly")
        return jsonify({"error": f"Could not parse the file: {exc}"}), 422

    return jsonify({"measurements": measurements}), 200


# ── Spreadsheet-Based Measurement Classification ────────────────────────────────
# Lookup a measurement description in the Bluebeam Term Mapping spreadsheet.
# Returns trade code, trade group, CSI division, unit, and takeoff type — or
# {matched: false} if not found. No AI fallback.

@app.route("/measurement/lookup-mapping", methods=["POST"])
def measurement_lookup_mapping():
    """Classify a measurement using the Bluebeam Term Mapping spreadsheet.

    Input:
    {
        "description": "Wall Area"
    }

    Output (match found):
    {
        "matched": true,
        "description": "Wall Area",
        "trade_code": "TILE-CERAMIC",
        "trade_group": "Finishes",
        "csi_division": "09 3000",
        "unit": "m²",
        "takeoff_type": "Flooring"
    }

    Output (no match):
    {
        "matched": false,
        "description": "Wall Area"
    }

    Mapping priority:
    1. Exact match (case-sensitive)
    2. Case-insensitive match
    3. No match — returns {matched: false}

    No AI classification is used. Only spreadsheet mappings.
    """
    body = request.get_json(force=True, silent=True) or {}
    description = body.get("description")

    if not description or not isinstance(description, str):
        return jsonify({"matched": False, "description": description}), 200

    result = classify_measurement(description)
    return jsonify(result), 200


_CLASSIFY_MAX_ROWS = 5000


@app.route("/measurement/classify", methods=["POST"])
def measurement_classify():
    """Classify parsed measurements through the deterministic pipeline.

    measurement -> normalisation -> NRM2 section -> rate key, with a confidence
    score per row. No AI, no pricing — classification only. Separate from
    /process and /measurement/import; neither is affected.

    When a valid Bearer token is supplied the route loads the user's saved
    classification overrides and applies them before the keyword rules
    (resolution order: user override → normal rules).  Requests without a
    token continue to work unchanged.
    """
    body = request.get_json(force=True, silent=True) or {}
    measurements = body.get("measurements")
    if not isinstance(measurements, list):
        return jsonify({"error": "Request body must be {\"measurements\": [...]}."}), 400
    if len(measurements) > _CLASSIFY_MAX_ROWS:
        return jsonify({"error": f"Too many measurements; {_CLASSIFY_MAX_ROWS} max per request."}), 413

    # Load user overrides when authenticated (fail-open: skip on any error).
    user_overrides = {}
    token = _get_bearer_token()
    if token and _supabase:
        try:
            res  = _supabase.auth.get_user(token)
            user = getattr(res, "user", None)
            if user:
                user_overrides = load_overrides(_db_client(), user.id)
                app.logger.info(
                    "Classification: loaded %d override(s) for user %s",
                    len(user_overrides), user.id,
                )
        except Exception as exc:
            app.logger.warning("Could not load user overrides (failing open): %s", exc)

    try:
        classified = classify_measurements(measurements, user_overrides)
    except MeasurementClassificationError as exc:
        return jsonify({"error": exc.message}), exc.status
    except Exception as exc:
        app.logger.exception("Measurement classification failed unexpectedly")
        return jsonify({"error": f"Classification failed: {exc}"}), 422

    return jsonify({"classified": classified, "options": classification_options()}), 200


@app.route("/measurement/overrides", methods=["GET"])
def measurement_get_overrides():
    """Return all saved classification overrides for the authenticated user."""
    user, err = _authenticated_user()
    if err:
        return err
    overrides = load_overrides(_db_client(), user.id)
    return jsonify({"overrides": overrides}), 200


@app.route("/measurement/overrides", methods=["PUT"])
def measurement_save_override():
    """Upsert one classification override for the authenticated user.

    Body: {source_term, nrm2_section (nullable), rate_key (nullable)}
    source_term is the normalised_description returned by /measurement/classify.
    """
    user, err = _authenticated_user()
    if err:
        return err
    body        = request.get_json(force=True, silent=True) or {}
    source_term = (body.get("source_term") or "").strip()
    nrm2_section = body.get("nrm2_section") or None
    rate_key     = body.get("rate_key") or None
    if not source_term:
        return jsonify({"error": "source_term is required."}), 400
    try:
        save_override(_db_client(), user.id, source_term, nrm2_section, rate_key)
    except Exception as exc:
        app.logger.error("Failed to save classification override: %s", exc)
        return jsonify({"error": "Failed to save override."}), 500
    return jsonify({"ok": True}), 200


@app.route("/measurement/overrides", methods=["DELETE"])
def measurement_delete_override():
    """Delete one classification override for the authenticated user.

    Body: {source_term}
    """
    user, err = _authenticated_user()
    if err:
        return err
    body        = request.get_json(force=True, silent=True) or {}
    source_term = (body.get("source_term") or "").strip()
    if not source_term:
        return jsonify({"error": "source_term is required."}), 400
    try:
        delete_override(_db_client(), user.id, source_term)
    except Exception as exc:
        app.logger.error("Failed to delete classification override: %s", exc)
        return jsonify({"error": "Failed to delete override."}), 500
    return jsonify({"ok": True}), 200


@app.route("/measurement/generate-boq", methods=["POST"])
def measurement_generate_boq():
    """Generate a BoQ from classified measurements.

    This endpoint converts the output of /measurement/classify into a full
    BoQ JSON structure, applies rates via _enrich_boq(), and returns a
    preview-ready BoQ ready for export or project storage.

    Input:
    {
        "classified_measurements": [...],  # output from /measurement/classify
        "project_name": "string (optional)"
    }

    Output:
    {
        "boq_data": {...},  # enriched BoQ matching BOQ_OUTPUT_SCHEMA
        "item_count": 42,
        "total_value": 12345.67
    }

    Uses existing:
    - _enrich_boq() to apply rates
    - _validate_boq_output() to validate schema
    - rate engine (RATES_DB)
    """
    if not _get_bearer_token():
        return jsonify({"error": "Authentication required. Please sign in."}), 401

    body = request.get_json(force=True, silent=True) or {}
    classified_meas = body.get("classified_measurements")
    project_name = body.get("project_name", "Draft BoQ from Measurements")

    if not isinstance(classified_meas, list):
        return jsonify({"error": "Request body must include 'classified_measurements' list."}), 400

    if len(classified_meas) == 0:
        return jsonify({"error": "classified_measurements cannot be empty."}), 400

    try:
        # Convert measurements to BoQ structure
        boq_json = build_boq_from_measurements(classified_meas, project_name)

        # Validate structure before enrichment
        is_valid, error_msg = validate_boq_structure(boq_json)
        if not is_valid:
            app.logger.error(f"Generated BoQ validation failed: {error_msg}")
            return jsonify({"error": f"BoQ generation failed: {error_msg}"}), 422

        # Apply rates and enrichment (reuse existing logic)
        enriched_boq = _enrich_boq(boq_json)

        # Final schema validation
        _validate_boq_output(enriched_boq)

        # Calculate summary
        item_count = sum(len(t['items']) for t in enriched_boq.get('bill_of_quantities', []))
        total_value = _sum_line_totals(enriched_boq)

        return jsonify({
            "boq_data": enriched_boq,
            "item_count": item_count,
            "total_value": total_value
        }), 200

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    except Exception as exc:
        app.logger.exception("BoQ generation failed unexpectedly")
        return jsonify({"error": f"BoQ generation failed: {exc}"}), 500


if __name__ == "__main__":                         # only runs when executed directly (python app.py), not when imported by a WSGI server — like a Program.Main guard in C#
    app.run(debug=True, port=5001)                 # start the Flask dev server on port 5001; debug=True enables hot-reload (never use in production)
