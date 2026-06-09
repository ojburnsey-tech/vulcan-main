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
        response.headers['Access-Control-Allow-Methods']     = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers']     = 'Content-Type, Authorization'
        response.headers['Access-Control-Max-Age']           = '86400'
    return response

# ── Supabase client ───────────────────────────────────────────────────────────────────
# The anon key is sufficient for client-side auth operations (sign up, sign in).
# Read from environment so the key never appears in source — like IConfiguration in C#.
_SB_URL = os.environ.get('SUPABASE_URL', '')
_SB_KEY = os.environ.get('SUPABASE_ANON_KEY', '')
# create_client returns None-safe — we guard every usage with `if not _supabase` below
_supabase = create_client(_SB_URL, _SB_KEY) if (_SB_URL and _SB_KEY) else None


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
    "5.20 Painting and decorating; 5.21 Drainage below ground; "
    "5.23 Windows and external doors; "
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
    "5.28 Floor finishes (tiling, screed, timber flooring); "
    "5.41 Builder's Work in Connection with Services.\n"
    "- External render, tyrolean render, monocouche render, sand and cement render, "
    "polymer render, and all applied render finishes to external masonry walls belong "
    "in section 5.8 Masonry — not 5.20 Painting and Decorating. Render is a structural "
    "finish applied to the building fabric. Never classify render under painting or "
    "decorating sections.\n"
    "5.23 Windows, screens and lights; 5.24 Doors, shutters and hatches; "
    "5.28 Floor finishes (tiling, screed, timber flooring); "
    "5.31 Insulation; "
    "5.41 Builder's work in connection with services.\n"

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
    "roof insulation (between/over rafters, flat roof insulation board) — not in 5.12 Roofing; "
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
)

BOQ_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
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

    for group in groups:                           # iterate each trade section
        if not isinstance(group, dict):            # skip strings or other non-dict entries Claude may have included
            continue
        items = group.get('items') or group.get('line_items') or []
        if not isinstance(items, list):            # guard against items being a scalar or dict
            continue
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


@app.route("/process", methods=["POST"])   # decorator registers this function as POST /process handler — like [HttpPost("process")] in C# Web API
def process_pdf():                         # Flask calls this function when a matching request arrives
    if not _get_bearer_token():            # guard: reject requests with no Authorization: Bearer header
        return jsonify({"error": "Authentication required. Please sign in."}), 401

    if "file" not in request.files:        # request.files is a dict of uploaded files keyed by form field name (like IFormFileCollection in C#)
        return jsonify({"error": "No 'file' field in request. POST multipart/form-data with field name 'file'."}), 400  # 400 Bad Request

    uploaded_file = request.files["file"]  # retrieve the FileStorage object for the field named "file"
    if uploaded_file.filename == "":       # empty filename means the browser sent the field but no file was selected
        return jsonify({"error": "Empty filename — no file was selected."}), 400

    if not uploaded_file.filename.lower().endswith(".pdf"):   # validate extension; .lower() normalises casing so "Drawing.PDF" is accepted
        return jsonify({"error": "Only PDF files are accepted."}), 415            # 415 Unsupported Media Type

    pdf_bytes = uploaded_file.read()       # read the entire upload into bytes in memory — never written to disk (like reading a Stream into byte[] in C#)
    pdf_buffer = io.BytesIO(pdf_bytes)     # wrap bytes in BytesIO so pdfplumber can treat it like a seekable file (like new MemoryStream(bytes) in C#)

    try:                                   # try/except is Python's equivalent of try/catch in C#
        with pdfplumber.open(pdf_buffer) as pdf:          # 'with' guarantees the PDF is closed even on exception — like C# 'using'
            pages_text = [page.extract_text() or "" for page in pdf.pages]  # list comprehension: extract text from every page; replace None with "" (like LINQ Select in C#)
        full_text = "\n\n".join(pages_text)               # join all pages with double newline so Claude sees page breaks (like String.Join in C#)
    except Exception as exc:               # catch any pdfplumber error (corrupt file, password-protected PDF, etc.)
        return jsonify({"error": f"Failed to read PDF: {exc}"}), 422  # 422 Unprocessable Entity; f"..." is Python's interpolated string (like $"..." in C#)

    if not full_text.strip():              # .strip() removes whitespace; empty result means a scanned image PDF with no OCR text layer
        return jsonify({"error": "No text could be extracted. The PDF may be a scanned image without an OCR text layer."}), 422

    api_key = os.environ.get("ANTHROPIC_API_KEY")  # read the key from the environment — never hard-code secrets in source (like Environment.GetEnvironmentVariable in C#)
    if not api_key:                                 # fail fast with a clear message if the variable is missing
        return jsonify({"error": "ANTHROPIC_API_KEY environment variable is not set on the server."}), 500

    client = anthropic.Anthropic(api_key=api_key)  # create the SDK client with the key — like new AnthropicClient(apiKey) in a hypothetical C# SDK

    try:
        app.logger.info(
            "Claude structured output call: model=%s max_tokens=%s "
            "pdf_text_length=%s approximate_word_count=%s",
            "claude-sonnet-4-6",
            12000,
            len(full_text),
            len(full_text.split()),
        )
        response = client.messages.create(         # call the Messages API — a synchronous HTTP POST to the Claude endpoint
            model="claude-sonnet-4-6",             # the specific Claude model to use
            max_tokens=12000,                       # maximum tokens Claude may generate; 4096 is enough for a detailed BoQ
            system=SYSTEM_PROMPT,                  # system prompt is a top-level kwarg in Anthropic SDK (NOT a {"role":"system"} entry — that is the OpenAI convention)
            messages=[                             # messages is a list of conversation turns; here just one user turn with no prior history
                {
                    "role": "user",                # "user" is the caller/human role — equivalent to UserChatMessage in a C# OpenAI SDK
                    "content": full_text,          # the extracted PDF text is the entire user message for Claude to analyse
                }
            ],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": BOQ_OUTPUT_SCHEMA,
                }
            },
        )
    except anthropic.APIStatusError as exc:        # APIStatusError covers 4xx/5xx responses from the Claude API (bad key, rate limit, server error)
        return jsonify({"error": f"Claude API error {exc.status_code}: {exc.message}"}), 502  # 502 Bad Gateway — this server got an error from an upstream service
    except anthropic.APIConnectionError as exc:    # APIConnectionError means the network call to Anthropic failed entirely (DNS failure, timeout, etc.)
        return jsonify({"error": f"Could not reach Claude API: {exc}"}), 503  # 503 Service Unavailable

    raw_text = _extract_claude_text(response)     # join Claude text blocks; strip whitespace/newlines Claude may have emitted before the JSON
    _log_claude_response("structured", response)

    stop_reason = getattr(response, "stop_reason", None)
    if stop_reason == "max_tokens":
        return jsonify({"error": "Claude structured output was truncated before completion."}), 502
    if stop_reason == "refusal":
        return jsonify({"error": "Claude refused to produce the requested structured output."}), 502

    try:
        boq_data = json.loads(raw_text)            # structured output returns JSON text matching BOQ_OUTPUT_SCHEMA
    except json.JSONDecodeError as exc:
        app.logger.exception("Claude structured output was not valid JSON: %s", exc)
        return jsonify({"error": f"Claude structured output was not valid JSON: {exc}"}), 502

    try:
        _validate_boq_output(boq_data)
    except ValueError as exc:
        app.logger.warning("Claude structured output failed schema validation: %s", exc)
        return jsonify({"error": f"Claude structured output failed schema validation: {exc}"}), 502

    boq_data = _enrich_boq(boq_data)               # look up rates in RATES_DB and add material_rate, labour_rate, line_total to every item

    print('BOQ STRUCTURE:', json.dumps(boq_data, indent=2)[:500])

    return jsonify(boq_data), 200                  # serialise the Python dict/list back to a JSON HTTP response — like return Ok(boqData) in C# Web API

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

    try:
        pdf_bytes = generate_boq_pdf(boq_json)   # build the PDF; returns raw bytes
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


if __name__ == "__main__":                         # only runs when executed directly (python app.py), not when imported by a WSGI server — like a Program.Main guard in C#
    app.run(debug=True, port=5001)                 # start the Flask dev server on port 5001; debug=True enables hot-reload (never use in production)
