# api/classification.py
# Deterministic measurement classification pipeline.
#
#     measurement -> normalisation -> classification (NRM2 section) -> rate key
#
# Phase-1: NO Claude / AI. Classification uses transparent keyword + token rules
# so results are deterministic and explainable. The pipeline is split into small
# stages with stable signatures so an AI-backed classifier can later replace the
# `classify_nrm2` / `assign_rate_key` stages (e.g. method="ai") without changing
# callers or the response shape.
#
# Kept standalone (imports only rates.RATES_DB, no Flask) so it is cheap to import
# and easy to unit-test in isolation.

import re

from rates import RATES_DB


# ── NRM2 section keyword rules ──────────────────────────────────────────────────
# (code, human label, [keywords]). Keywords are matched as substrings against the
# normalised, lower-cased description. Specific multi-word keywords are preferred
# via the scoring in classify_nrm2 (more hits + longer keywords win).
NRM2_SECTIONS = [
    ("5.1",  "Groundworks",                        ["excavat", "earthwork", "dig", "disposal", "trench", "hardcore", "topsoil", "backfill", "muck away", "filling"]),
    ("5.4",  "In-situ concrete",                   ["concrete", "foundation", "rc slab", "reinforcement", "rebar", "formwork", "blinding", "in-situ"]),
    ("5.8",  "Masonry",                            ["brick", "block", "masonry", "mortar", "cavity wall", "render", "wall tie", "dpc", "damp proof course"]),
    ("5.9",  "Structural metalwork",               ["structural steel", "steel beam", "universal beam", "rsj", "steel column", "padstone", "steel lintel"]),
    ("5.11", "Carpentry and joinery",              ["timber", "joist", "stud", "rafter", "plywood", "skirting", "architrave", "carpentry", "noggin", "batten", "wall plate", "studwork"]),
    ("5.12", "Roofing",                            ["roof", "fascia", "soffit", "gutter", "downpipe", "ridge", "verge", "barge", "eaves"]),
    ("5.14", "Mechanical services",                ["radiator", "boiler", "plumb", "sanitary", "soil stack", "ductwork", "ventilation", "heating", "mvhr", "pipework", "waste pipe", "wc", "basin"]),
    ("5.15", "Electrical services",                ["cable", "socket", "switch", "consumer unit", "electric", "luminaire", "lighting", "conduit", "wiring", "downlight", "spotlight"]),
    ("5.17", "Plastering and internal finishes",   ["plaster", "skim", "plasterboard", "dry lining", "bonding", "float and set", "render internal", "scrim"]),
    ("5.18", "Roof coverings",                     ["roof tile", "roof slate", "interlocking tile", "plain tile", "roof sheet", "slate covering"]),
    ("5.21", "Drainage below ground",              ["drain", "manhole", "inspection chamber", "gully", "soakaway", "sewer", "rodding", "below ground drainage"]),
    ("5.23", "Windows and external doors",         ["window", "rooflight", "velux", "glazing", "external door", "patio door", "bifold", "french door"]),
    ("5.24", "Doors",                              ["door", "door lining", "door set", "ironmongery", "door leaf"]),
    ("5.28", "Floor, wall and ceiling finishes",   ["tiling", "floor tile", "wall tile", "vinyl", "carpet", "screed", "floor finish", "ceramic", "laminate", "lvt"]),
    ("5.29", "Decoration",                         ["paint", "emulsion", "decorat", "varnish", "stain", "gloss", "undercoat", "primer", "eggshell"]),
    ("5.31", "Insulation",                         ["insulat", "kingspan", "celotex", "rockwool", "mineral wool", "pir board", "loft insulation"]),
    ("5.35", "External works",                     ["paving", "tarmac", "kerb", "footpath", "landscap", "fence", "gate", "patio", "block paving", "tarmacadam"]),
]

_NRM2_LABEL = {code: label for code, label, _ in NRM2_SECTIONS}


class MeasurementClassificationError(Exception):
    """Raised for malformed classification input; carries an HTTP status."""

    def __init__(self, message, status=422):
        super().__init__(message)
        self.message = message
        self.status = status


# ── Stage 1: normalisation ──────────────────────────────────────────────────────
# Expand common QS abbreviations and canonicalise units so downstream matching is
# stable regardless of how the takeoff was typed.
_ABBREV = [
    (r'\bexc\b',     'excavation'),
    (r'\bconc\b',    'concrete'),
    (r'\bfdn\b',     'foundation'),
    (r'\bfdns\b',    'foundations'),
    (r'\bblk\b',     'block'),
    (r'\bblkwk\b',   'blockwork'),
    (r'\bbwk\b',     'brickwork'),
    (r'\bplstr\b',   'plaster'),
    (r'\binsul\b',   'insulation'),
    (r'\breinf\b',   'reinforced'),
    (r'\bne\b',      'not exceeding'),
    (r'\bg\.?l\.?\b', 'ground level'),
]

_UNIT_CANON = {
    'm2': 'm²', 'm^2': 'm²', 'sqm': 'm²', 'sq m': 'm²', 'sq.m': 'm²', 'm²': 'm²',
    'm3': 'm³', 'm^3': 'm³', 'cum': 'm³', 'cu m': 'm³', 'm³': 'm³',
    'lm': 'm', 'lin m': 'm', 'lin.m': 'm', 'l/m': 'm', 'm': 'm',
    'no': 'nr', 'no.': 'nr', 'nr': 'nr', 'each': 'nr', 'ea': 'nr', 'item': 'item',
}


def normalise(description, unit):
    """Stage 1 — clean a raw measurement into a normalised description + unit."""
    text = re.sub(r'\s+', ' ', (description or '').strip().lower())
    for pattern, repl in _ABBREV:
        text = re.sub(pattern, repl, text)
    text = re.sub(r'\s+', ' ', text).strip()

    raw_u = (unit or '').strip().lower()
    canon_u = _UNIT_CANON.get(raw_u, (unit or '').strip())

    display = (text[:1].upper() + text[1:]) if text else ''
    return {"normalised_description": display, "normalised_unit": canon_u}


# ── Stage 2: NRM2 classification ────────────────────────────────────────────────

def classify_nrm2(normalised_description):
    """Stage 2 — map a normalised description to an NRM2 section by keyword rules.

    Returns the best section with a 0..1 section_score. Swap this function for an
    AI classifier later (same return shape) to upgrade classification.
    """
    text = (normalised_description or '').lower()
    best = None    # (sort_key, code, label, hits)
    for idx, (code, label, keywords) in enumerate(NRM2_SECTIONS):
        hits = [kw for kw in keywords if kw in text]
        if not hits:
            continue
        # More distinct hits win; tie-break on total keyword specificity (length),
        # then on declaration order (earlier section).
        sort_key = (len(hits), sum(len(kw) for kw in hits), -idx)
        if best is None or sort_key > best[0]:
            best = (sort_key, code, label, hits)

    if best is None:
        return {"nrm2_section": None, "nrm2_label": "Unclassified", "section_score": 0.0, "hits": []}
    hits = best[3]
    section_score = 0.85 if len(hits) >= 2 else 0.6
    return {"nrm2_section": best[1], "nrm2_label": best[2], "section_score": section_score, "hits": hits}


# ── Stage 3: rate-key assignment ────────────────────────────────────────────────
# Token-set Jaccard match against RATES_DB keys — the same dependency-free
# technique already used server-side for /process enrichment.
_STOP = frozenset(['to', 'in', 'of', 'the', 'a', 'and', 'for', 'with', 'at', 'on', 'per', 'by', 'or'])


def _tokenise(text):
    clean = re.sub(r'[^a-z0-9\s]', ' ', (text or '').lower())
    return frozenset(w for w in clean.split() if w not in _STOP and len(w) > 1)


_RATE_TOKENS = {key: _tokenise(key.replace('_', ' ')) for key in RATES_DB}


def _infer_section_for_key(rate_key):
    """Best-effort NRM2 section for a rate key, by running the key name through
    the same keyword classifier. Used only to corroborate confidence."""
    if not rate_key:
        return None
    return classify_nrm2(rate_key.replace('_', ' '))['nrm2_section']


def assign_rate_key(normalised_description, nrm2_section=None):
    """Stage 3 — choose the closest RATES_DB key for a normalised description.

    nrm2_section is accepted (and forwarded) so a future implementation can scope
    candidates to the section; the deterministic version matches globally and
    reports the key's own inferred section for confidence corroboration.
    """
    tokens = _tokenise(normalised_description)
    if not tokens:
        return {"rate_key": None, "rate_unit": None, "key_score": 0.0, "inferred_section": None}

    best_key, best_score = None, 0.0
    for key, ktoks in _RATE_TOKENS.items():
        if not ktoks:
            continue
        inter = len(tokens & ktoks)
        if not inter:
            continue
        score = inter / len(tokens | ktoks)
        if score > best_score:
            best_score, best_key = score, key

    if best_score < 0.10 or not best_key:
        return {"rate_key": None, "rate_unit": None, "key_score": 0.0, "inferred_section": None}
    return {
        "rate_key": best_key,
        "rate_unit": RATES_DB[best_key].get('unit'),
        "key_score": round(best_score, 3),
        "inferred_section": _infer_section_for_key(best_key),
    }


# ── Confidence ──────────────────────────────────────────────────────────────────

def _confidence(section_score, key_score, agree):
    """Blend section and rate-key strength into a single 0..1 confidence."""
    if section_score <= 0 and key_score <= 0:
        return 0.0
    base = 0.5 * section_score + 0.5 * min(1.0, key_score)
    if agree:
        base += 0.15
    return round(min(1.0, base), 2)


# ── Orchestration ───────────────────────────────────────────────────────────────

def classify_one(measurement, user_overrides=None):
    """Run the full pipeline for a single measurement dict.

    Resolution order:
      1. user_overrides dict (keyed by lower-cased normalised_description)
      2. Normal keyword + Jaccard rules (existing behaviour)
    """
    raw_desc = (measurement.get('description') or '').strip()
    raw_unit = (measurement.get('unit') or '').strip()

    norm = normalise(raw_desc, raw_unit)

    # ── Resolution step 1: user override ────────────────────────────────────
    if user_overrides:
        ov = user_overrides.get(norm['normalised_description'].lower())
        if ov:
            nrm2_section = ov.get('nrm2_section') or None
            rate_key     = ov.get('rate_key') or None
            return {
                "description":            raw_desc,
                "quantity":               measurement.get('quantity'),
                "unit":                   raw_unit,
                "normalised_description": norm['normalised_description'],
                "normalised_unit":        norm['normalised_unit'],
                "nrm2_section":           nrm2_section,
                "nrm2_label":             _NRM2_LABEL.get(nrm2_section, 'Unclassified') if nrm2_section else 'Unclassified',
                "rate_key":               rate_key,
                "rate_unit":              RATES_DB.get(rate_key, {}).get('unit') if rate_key else None,
                "confidence":             1.0,
                "method":                 "user_override",
                "overridden":             True,
            }

    # ── Resolution step 2: normal rules ─────────────────────────────────────
    section = classify_nrm2(norm['normalised_description'])
    rate = assign_rate_key(norm['normalised_description'], section['nrm2_section'])

    # Backfill: if keyword rules found no section but a rate key matched, adopt the
    # key's inferred section at reduced confidence rather than leaving it blank.
    if section['nrm2_section'] is None and rate['inferred_section']:
        code = rate['inferred_section']
        section = {"nrm2_section": code, "nrm2_label": _NRM2_LABEL.get(code, "Unclassified"),
                   "section_score": 0.5, "hits": ["(from rate key)"]}

    agree = (section['nrm2_section'] is not None
             and rate['inferred_section'] == section['nrm2_section'])
    confidence = _confidence(section['section_score'], rate['key_score'], agree)

    return {
        "description":            raw_desc,
        "quantity":               measurement.get('quantity'),
        "unit":                   raw_unit,
        "normalised_description": norm['normalised_description'],
        "normalised_unit":        norm['normalised_unit'],
        "nrm2_section":           section['nrm2_section'],
        "nrm2_label":             section['nrm2_label'],
        "rate_key":               rate['rate_key'],
        "rate_unit":              rate['rate_unit'],
        "confidence":             confidence,
        "method":                 "deterministic",   # future: "ai"
        "overridden":             False,
    }


def classify_measurements(measurements, user_overrides=None):
    """Classify a list of measurement dicts. Raises MeasurementClassificationError
    on malformed input. user_overrides is propagated to classify_one()."""
    if not isinstance(measurements, list):
        raise MeasurementClassificationError("`measurements` must be a list.", 400)
    out = []
    for m in measurements:
        if not isinstance(m, dict):
            raise MeasurementClassificationError("Each measurement must be an object.", 400)
        out.append(classify_one(m, user_overrides))
    return out


def classification_options():
    """Option lists for the manual-override dropdowns in the UI."""
    return {
        "nrm2_sections": [{"code": code, "label": label} for code, label, _ in NRM2_SECTIONS],
        "rate_keys": sorted(RATES_DB.keys()),
    }
