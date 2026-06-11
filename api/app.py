# api/app.py — Flask backend: PDF upload → pdfplumber → Claude → JSON BoQ

import os                          # os gives access to environment variables (like Environment.GetEnvironmentVariable in C#)
import io                          # io.BytesIO is an in-memory byte buffer — like MemoryStream in C#
import re                          # re is Python's regex module — like System.Text.RegularExpressions in C#
import json                        # json parses/serialises JSON — like System.Text.Json in C#
import difflib                     # difflib is a stdlib module for comparing sequences; used for fuzzy string matching
import pdfplumber                  # third-party library that opens PDFs and extracts text page by page
import anthropic                   # official Anthropic Python SDK — wraps the Claude REST API
from flask import Flask, request, jsonify, send_file, session, send_from_directory, make_response  # session = server-signed cookie dict, like HttpContext.Session in ASP.NET
from jsonschema import Draft202012Validator, ValidationError
from supabase import create_client # supabase-py v2 — wraps the Supabase REST API for auth
from rates import RATES_DB         # our local dict of 2025-2026 UK construction rates (material + labour per unit)
from export_pdf import generate_boq_pdf  # ReportLab PDF generator for the /export endpoint
from export_excel import generate_boq_excel
from measurement_import import parse_measurements, MeasurementImportError  # CSV/XLSX measurement parser
from classification import classify_measurements, classification_options, MeasurementClassificationError  # deterministic NRM2/rate classifier
import time, statistics
_processing_times = []
_start_time = time.time()
_ai_status = None

app = Flask(__name__)              # create the Flask app instance; __name__ tells Flask the root path (like WebApplication.CreateBuilder in C#)

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
        "status":          status,
    }
    if extra:
        row.update({k: v for k, v in extra.items() if k in _PROJECT_EXTRA_FIELDS})
    res = db.table("projects").insert(row).execute()
    # supabase-py returns the inserted rows in res.data (a list) when returning='representation'
    return res.data[0] if getattr(res, "data", None) else None


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
                total += float(item.get('line_total') or 0)
    return round(total, 2)


def _extract_claude_text(response) -> str:
    """Join all text blocks returned by Claude into one response string."""
    return "".join(
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
    ).strip()


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
    "Respond with a single raw JSON object only — no markdown, no code fences, "
    "no preamble, no trailing text. The root key must be bill_of_quantities "
    "containing an array of trade groups, each with a trade string and an items array."
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


def _validate_boq_output(boq_data):
    """Validate Claude's structured output before pricing enrichment."""
    try:
        _BOQ_OUTPUT_VALIDATOR.validate(boq_data)
    except ValidationError as exc:
        path = ".".join(str(p) for p in exc.absolute_path) or "<root>"
        raise ValueError(f"{path}: {exc.message}") from exc

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
                item['rate_source']         = matched_key
            else:
                # No match found — leave rates at zero so the QS can fill them in manually
                item['material_rate']       = 0.00
                item['labour_rate']         = 0.00
                item['plant_rate']          = 0.00
                item['waste_disposal_rate'] = 0.00
                item['rate']                = 0.00
                item['line_total']          = 0.00
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
        return jsonify({"error": f"Failed to create project: {exc}"}), 500

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
        chat_client = anthropic.Anthropic(api_key=api_key, timeout=60.0)
        response = chat_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system,
            messages=messages,
        )
        assistant_reply = response.content[0].text
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


def _run_boq_pipeline():
    """Shared upload → pdfplumber → Claude → validate → enrich pipeline.

    Single home for the BoQ generation business logic, used by both the
    authenticated /process route and the public /demo-process route so the
    pipeline is never duplicated.  Reads the uploaded file from the current
    Flask request context.

    Returns (boq_data, pages_text, uploaded_file, error) where error is a
    (response, status) tuple ready to return from a view, or None on success.
    """
    _fail = (None, None, None)             # prefix for every error return below

    if "file" not in request.files:        # request.files is a dict of uploaded files keyed by form field name (like IFormFileCollection in C#)
        return (*_fail, (jsonify({"error": "No 'file' field in request. POST multipart/form-data with field name 'file'."}), 400))  # 400 Bad Request

    uploaded_file = request.files["file"]  # retrieve the FileStorage object for the field named "file"
    if uploaded_file.filename == "":       # empty filename means the browser sent the field but no file was selected
        return (*_fail, (jsonify({"error": "Empty filename — no file was selected."}), 400))

    if not uploaded_file.filename.lower().endswith(".pdf"):   # validate extension; .lower() normalises casing so "Drawing.PDF" is accepted
        return (*_fail, (jsonify({"error": "Only PDF files are accepted."}), 415))            # 415 Unsupported Media Type

    pdf_bytes = uploaded_file.read()       # read the entire upload into bytes in memory — never written to disk (like reading a Stream into byte[] in C#)
    pdf_buffer = io.BytesIO(pdf_bytes)     # wrap bytes in BytesIO so pdfplumber can treat it like a seekable file (like new MemoryStream(bytes) in C#)

    try:                                   # try/except is Python's equivalent of try/catch in C#
        with pdfplumber.open(pdf_buffer) as pdf:          # 'with' guarantees the PDF is closed even on exception — like C# 'using'
            pages_text = [page.extract_text() or "" for page in pdf.pages]  # list comprehension: extract text from every page; replace None with "" (like LINQ Select in C#)
        full_text = "\n\n".join(pages_text)               # join all pages with double newline so Claude sees page breaks (like String.Join in C#)
    except Exception as exc:               # catch any pdfplumber error (corrupt file, password-protected PDF, etc.)
        return (*_fail, (jsonify({"error": f"Failed to read PDF: {exc}"}), 422))  # 422 Unprocessable Entity; f"..." is Python's interpolated string (like $"..." in C#)

    if not full_text.strip():              # .strip() removes whitespace; empty result means a scanned image PDF with no OCR text layer
        return (*_fail, (jsonify({"error": "No text could be extracted. The PDF may be a scanned image without an OCR text layer."}), 422))

    api_key = os.environ.get("ANTHROPIC_API_KEY")  # read the key from the environment — never hard-code secrets in source (like Environment.GetEnvironmentVariable in C#)
    if not api_key:                                 # fail fast with a clear message if the variable is missing
        return (*_fail, (jsonify({"error": "ANTHROPIC_API_KEY environment variable is not set on the server."}), 500))

    client = anthropic.Anthropic(api_key=api_key, timeout=180.0)  # create the SDK client with the key — like new AnthropicClient(apiKey) in a hypothetical C# SDK

    try:
        app.logger.info(
            "Claude structured output call: model=%s max_tokens=%s "
            "pdf_text_length=%s approximate_word_count=%s",
            "claude-sonnet-4-6",
            12000,
            len(full_text),
            len(full_text.split()),
        )
        _t = time.time()
        response = client.messages.create(         # call the Messages API — a synchronous HTTP POST to the Claude endpoint
            model="claude-sonnet-4-6",             # the specific Claude model to use
            max_tokens=16000,                       # maximum tokens Claude may generate; 4096 is enough for a detailed BoQ
            system=SYSTEM_PROMPT,                  # system prompt is a top-level kwarg in Anthropic SDK (NOT a {"role":"system"} entry — that is the OpenAI convention)
            messages=[                             # messages is a list of conversation turns; here just one user turn with no prior history
                {
                    "role": "user",                # "user" is the caller/human role — equivalent to UserChatMessage in a C# OpenAI SDK
                    "content": full_text,          # the extracted PDF text is the entire user message for Claude to analyse
                }
            ],
        )
        _processing_times.append(round(time.time() - _t, 1))
        if len(_processing_times) > 200:
            _processing_times.pop(0)
    except anthropic.APIStatusError as exc:        # APIStatusError covers 4xx/5xx responses from the Claude API (bad key, rate limit, server error)
        return (*_fail, (jsonify({"error": f"Claude API error {exc.status_code}: {exc.message}"}), 502))  # 502 Bad Gateway — this server got an error from an upstream service
    except anthropic.APIConnectionError as exc:    # APIConnectionError means the network call to Anthropic failed entirely (DNS failure, timeout, etc.)
        return (*_fail, (jsonify({"error": f"Could not reach Claude API: {exc}"}), 503))  # 503 Service Unavailable

    raw_text = _extract_claude_text(response)     # join Claude text blocks; strip whitespace/newlines Claude may have emitted before the JSON
    _log_claude_response("structured", response)

    stop_reason = getattr(response, "stop_reason", None)
    if stop_reason == "max_tokens":
        return (*_fail, (jsonify({"error": "Claude structured output was truncated before completion."}), 502))
    if stop_reason == "refusal":
        return (*_fail, (jsonify({"error": "Claude refused to produce the requested structured output."}), 502))

    try:
        boq_data = json.loads(raw_text)            # structured output returns JSON text matching BOQ_OUTPUT_SCHEMA
    except json.JSONDecodeError as exc:
        app.logger.exception("Claude structured output was not valid JSON: %s", exc)
        return (*_fail, (jsonify({"error": f"Claude structured output was not valid JSON: {exc}"}), 502))

    try:
        _validate_boq_output(boq_data)
    except ValueError as exc:
        app.logger.warning("Claude structured output failed schema validation: %s", exc)
        return (*_fail, (jsonify({"error": f"Claude structured output failed schema validation: {exc}"}), 502))

    boq_data = _enrich_boq(boq_data)               # look up rates in RATES_DB and add material_rate, labour_rate, line_total to every item

    return boq_data, pages_text, uploaded_file, None


@app.route("/process", methods=["POST"])   # decorator registers this function as POST /process handler — like [HttpPost("process")] in C# Web API
def process_pdf():                         # Flask calls this function when a matching request arrives
    if not _get_bearer_token():            # guard: reject requests with no Authorization: Bearer header
        return jsonify({"error": "Authentication required. Please sign in."}), 401

    boq_data, pages_text, uploaded_file, err = _run_boq_pipeline()
    if err:
        return err

    print('BOQ STRUCTURE:', json.dumps(boq_data, indent=2)[:500])

    # Auto-save the completed BoQ as a project for the authenticated user.
    # This is best-effort: any failure is logged but never surfaced to the caller,
    # so a save problem can't turn a successful BoQ generation into an error response.
    try:
        user_res = _supabase.auth.get_user(_get_bearer_token()) if _supabase else None
        user     = getattr(user_res, "user", None) if user_res else None
        if user:
            db = _db_client()
            project_id = (request.form.get("project_id") or "").strip()
            if project_id:
                # The upload belongs to an existing project (workspace flow) —
                # attach the BoQ to that row instead of creating a duplicate.
                db.table("projects").update({
                    "page_count":      len(pages_text),
                    "estimated_value": _sum_line_totals(boq_data),
                    "boq_data":        boq_data,
                    "status":          "completed",
                }).eq("id", project_id).eq("user_id", user.id).execute()
            else:
                project_name = re.sub(r'\.pdf$', '', uploaded_file.filename, flags=re.IGNORECASE)  # filename without the .pdf extension
                _insert_project(
                    db,
                    user_id=user.id,
                    name=project_name,
                    page_count=len(pages_text),                # one entry in pages_text per PDF page
                    estimated_value=_sum_line_totals(boq_data),  # total of every line_total in the enriched BoQ
                    boq_data=boq_data,
                    status='completed',
                )
    except Exception as exc:
        app.logger.warning("Failed to auto-save project from /process: %s", exc)

    return jsonify(boq_data), 200                  # serialise the Python dict/list back to a JSON HTTP response — like return Ok(boqData) in C# Web API


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

    branding = _load_user_branding()        # best-effort; {} when none configured

    try:
        pdf_bytes = generate_boq_pdf(boq_json, branding=branding)   # build the PDF; returns raw bytes
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

    boq_json = request.get_json(force=True, silent=True)
    if not boq_json:
        return jsonify({"error": "Request body must be a JSON BoQ object."}), 400

    firm_name    = request.args.get("firm", "")
    project_name = request.args.get("project", "")

    try:
        excel_bytes = generate_boq_excel(boq_json, firm_name, project_name)
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


_CLASSIFY_MAX_ROWS = 5000


@app.route("/measurement/classify", methods=["POST"])
def measurement_classify():
    """Classify parsed measurements through the deterministic pipeline.

    measurement -> normalisation -> NRM2 section -> rate key, with a confidence
    score per row. No AI, no pricing — classification only. Separate from
    /process and /measurement/import; neither is affected.
    """
    body = request.get_json(force=True, silent=True) or {}
    measurements = body.get("measurements")
    if not isinstance(measurements, list):
        return jsonify({"error": "Request body must be {\"measurements\": [...]}."}), 400
    if len(measurements) > _CLASSIFY_MAX_ROWS:
        return jsonify({"error": f"Too many measurements; {_CLASSIFY_MAX_ROWS} max per request."}), 413

    try:
        classified = classify_measurements(measurements)
    except MeasurementClassificationError as exc:
        return jsonify({"error": exc.message}), exc.status
    except Exception as exc:
        app.logger.exception("Measurement classification failed unexpectedly")
        return jsonify({"error": f"Classification failed: {exc}"}), 422

    return jsonify({"classified": classified, "options": classification_options()}), 200


if __name__ == "__main__":                         # only runs when executed directly (python app.py), not when imported by a WSGI server — like a Program.Main guard in C#
    app.run(debug=True, port=5001)                 # start the Flask dev server on port 5001; debug=True enables hot-reload (never use in production)
