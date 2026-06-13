# api/export_pdf.py
# Generates a professional NRM2-compliant A4 Bill of Quantities PDF using ReportLab Platypus.

import base64
import html
import io
import re
import unicodedata
import urllib.parse
import urllib.request
from datetime import date

from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    HRFlowable,
    PageBreak,
    Image,
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT

# ── Page geometry ──────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
LEFT_M  = RIGHT_M = 20 * mm
TOP_M   = 30 * mm
BOT_M   = 18 * mm
CONTENT_W = PAGE_W - LEFT_M - RIGHT_M

# Measured Works column widths — Description | Qty | Unit | Mat Rate | Lab Rate | Total
_C_QTY   = 38
_C_UNIT  = 34
_C_MAT   = 58
_C_LAB   = 58
_C_TOTAL = 64
_C_DESC  = CONTENT_W - _C_QTY - _C_UNIT - _C_MAT - _C_LAB - _C_TOTAL
_C_RATE = _C_MAT + _C_LAB
COL_WIDTHS = [_C_DESC, _C_QTY, _C_UNIT, _C_RATE, _C_TOTAL]

_I_DESC, _I_QTY, _I_UNIT, _I_RATE, _I_TOTAL = range(5)

# ── Static section content (module-level constants — edit these to update documents) ──

PREAMBLE_ITEMS = [
    ("1.",  "This Bill of Quantities is a Firm Bill. Quantities have been prepared "
            "from information provided and are not subject to remeasurement unless "
            "otherwise instructed in writing by the Contract Administrator. The "
            "Contractor shall be deemed to have satisfied themselves as to the "
            "accuracy of quantities before submitting their tender."),
    ("2.",  "Measurement Method: Quantities have been measured on a net basis unless "
            "otherwise stated. No allowance for waste, laps, bulking, cutting, or working "
            "space has been included unless specifically described. All descriptions are to "
            "be read in conjunction with the drawings, specifications, schedules, and other "
            "tender documents."),
    ("3.",  "This Bill of Quantities has been prepared in accordance with the RICS "
            "New Rules of Measurement: Detailed Measurement for Building Works (NRM2), "
            "Second Edition. Work sections are numbered and ordered in accordance with "
            "NRM2 Section 5."),
    ("4.",  "All quantities are net as fixed and measured in accordance with NRM2 "
            "measurement rules. No allowance has been made for waste, bulking, shrinkage, "
            "or settlement. Contractors must apply their own waste factors when pricing "
            "materials."),
    ("5.",  "Rates inserted by the contractor are deemed to include all labour, materials, "
            "plant, equipment, tools, fixings, fastenings, consumables, and all other costs "
            "necessary to complete each item fully in accordance with the contract drawings "
            "and specification."),
    ("6.",  "Unless stated otherwise, all work is measured in accordance with NRM2 and "
            "descriptions are abbreviated for brevity. Full details of materials, standards, "
            "and workmanship are contained in the project specification and drawings listed "
            "in the Form of Tender, which take precedence over these descriptions in all "
            "cases."),
    ("7.",  "Provisional Sums are included where insufficient information was available at "
            "the time of preparation to enable accurate measurement. Defined Provisional "
            "Sums are those where the nature and construction of the work is known but the "
            "exact quantity is not. Undefined Provisional Sums are those where the work "
            "cannot be fully described. Both are subject to remeasurement and adjustment "
            "by the Contract Administrator."),
    ("8.",  "Prime Cost (PC) Sums are included for materials or goods to be supplied by "
            "nominated or selected suppliers. The contractor shall allow in their rates for "
            "all costs of unloading, storing, handling, fixing, and waste in connection with "
            "PC Sum items. Profit and attendance on PC Sums shall be stated separately."),
    ("9.",  "The following drawings and documents govern measurement and are listed in the "
            "Form of Tender. Where dimensions on drawings conflict with written dimensions, "
            "the written dimension shall take precedence. Where the specification conflicts "
            "with the drawings, the matter shall be referred to the Contract Administrator "
            "before work proceeds."),
    ("10.", "Where information was incomplete or absent at the time of preparation, "
            "assumptions have been made on the basis of normal construction practice for "
            "the building type and location. All such assumptions are noted in the relevant "
            "item descriptions. The quantity surveyor accepts no liability for costs arising "
            "from assumptions that prove incorrect where the relevant information was not "
            "provided."),
    ("11.", "Rounding: linear quantities are rounded to the nearest whole metre; area "
            "quantities to the nearest whole square metre; volume quantities to the nearest "
            "whole cubic metre. Items fewer than one unit in quantity are given as one. "
            "Monetary amounts are rounded to the nearest penny."),
    ("12.", "This document is an AI-generated draft prepared by Vulcan Quanta. All "
            "quantities, descriptions, and rates must be reviewed and verified by a "
            "chartered quantity surveyor before issue for tender or contract. The preparing "
            "party accepts no liability for errors or omissions in this draft."),
]

# (description, qty, unit, rate_per_unit)
PRELIM_ITEMS = [
    ("Scaffold erection, hire (8 weeks), and strike to full perimeter",  1,  "item", 4800.00),
    ("Skip hire for duration of works (10 skips estimated)",             10, "nr",    280.00),
    ("Temporary site hoarding and security fencing",                      1,  "item",  850.00),
    ("Temporary welfare facilities and site WC hire (8 weeks)",           8,  "wk",     95.00),
    ("Site insurance and all-risks policy allowance",                     1,  "item",  600.00),
    ("Project management and site supervision",                           8,  "wk",    750.00),
]

# (description, allowance_amount)
PROVISIONAL_SUMS = [
    ("Connection to existing sewer; nature and extent subject "
     "to NI Water survey; remeasurable on instruction", 1500.00),
    ("External landscaping and reinstatement; extent and "
     "specification to be confirmed", 2000.00),
]

PC_SUMS = [
    ("Client's fixtures and fittings; PC Sum for supply only; "
     "contractor to add fixing, profit and attendance separately", 3500.00),
]

STATUTORY_FEES = [
    ("Planning application fee — Belfast City Council", 327.00),
    ("Building Control Full Plans fee — Belfast City Council "
     "(40–60m² bracket)", 291.60),
    ("NI Water sewer connection application and inspection fee "
     "(Article 163)", 229.20),
]

# (resource, grade_description, unit_string, guidance_range)
DAYWORKS_ROWS = [
    ("Labour",          "Ganger / working foreman",                                              "/hr", "£26–£32/hr"),
    ("Labour",          "Skilled tradesperson (bricklayer, carpenter, plumber, electrician)",    "/hr", "£22–£28/hr"),
    ("Labour",          "Semi-skilled operative",                                                "/hr", "£18–£22/hr"),
    ("Labour",          "General labourer",                                                      "/hr", "£18–£22/hr"),
    ("Plant",           "Small plant (mixer, compactor, generator)",                             "/hr", "£8–£15/hr"),
    ("Plant",           "Medium plant (mini-excavator, tracked dumper)",                         "/hr", "£25–£45/hr"),
    ("Plant",           "Large plant (excavator, crane — if applicable)",                   "/hr", "£55–£120/hr"),
    ("Materials",       "Percentage addition on net invoiced cost of materials",                 "%",   "Net cost + 15%"),
    ("Sub-contractors", "Percentage addition on net sub-contract price",                         "%",   "Net cost + 15%"),
]

DAYWORKS_NOTE = (
    "Notes on Dayworks Rates:<br/>"
    "(a) Labour rates are all-in rates inclusive of PAYE, employer's National Insurance "
    "contributions, holiday pay, and tool allowance. Rates are based on CIJC Working Rule "
    "Agreement Northern Ireland 2026.<br/>"
    "(b) Plant rates are exclusive of fuel and operator unless otherwise stated.<br/>"
    "(c) Materials are to be charged at net cost (invoiced price) plus the percentage addition "
    "stated above to cover handling, storage, and waste.<br/>"
    "(d) Sub-contractor work is to be charged at the net sub-contract price plus the percentage "
    "addition stated above.<br/>"
    "(e) Dayworks are only to be used where expressly instructed by the Contract Administrator. "
    "All daywork sheets must be submitted for signature within 24 hours of the work being carried out."
)

# Substring replacements applied to item descriptions before rendering
NRM2_SUBSTITUTIONS = [
    (
        "Concrete C25 strip foundations",
        "Concrete C25 (20mm aggregate) poured into structural foundation trenches "
        "not exceeding 2.0m deep",
    ),
    (
        "External cavity wall 300mm",
        "External cavity wall comprising 102mm facing brick outer leaf, 100mm clear cavity "
        "with partial fill mineral wool insulation batts, stainless steel wall ties at "
        "2.5/m², 100mm dense aggregate concrete block inner leaf",
    ),
    (
        "Timber roof structure",
        "Pitched timber roof structure comprising C24 treated softwood rafters, ceiling "
        "joists, purlins, ridge board and wall plates, all at centres to engineer's details",
    ),
    (
        "UPVC fascia",
        "112mm UPVC half-round eaves gutter fixed to fascia boards with brackets at "
        "maximum 1.0m centres",
    ),
]

VALID_UNITS = {"nr", "m", "m2", "m3", "item", "wk", "kg"}

_UNIT_ALIASES = {
    "no": "nr", "no.": "nr", "each": "nr", "ea": "nr",
    "lin m": "m", "lm": "m", "lin.m": "m",
    "sqm": "m2", "sq.m": "m2", "sq m": "m2",
    "m²": "m2", "m^2": "m2",
    "cum": "m3", "cub m": "m3", "m³": "m3", "m^3": "m3",
    "week": "wk", "weeks": "wk",
    "sum": "item", "ls": "item", "l.s": "item",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fmt(n) -> str:
    """Format a number as UK sterling: £1,234.56"""
    return f"£{float(n):,.2f}"


def _sanitise_unit(raw: str) -> str:
    """Normalise any unit string to an ASCII-only NRM2-valid unit; default 'nr'."""
    if not raw:
        return "nr"
    s = unicodedata.normalize("NFKC", str(raw).strip())
    s = s.replace("²", "2").replace("³", "3").lower()
    if s in VALID_UNITS:
        return s
    return _UNIT_ALIASES.get(s, "nr")


def _apply_nrm2_desc(desc: str) -> str:
    """Upgrade abbreviated descriptions to NRM2-standard wording via substring replacement."""
    for old, new in NRM2_SUBSTITUTIONS:
        if old in desc:
            desc = desc.replace(old, new)
    return desc


def _normalise_boq(boq_json):
    """Convert any Claude JSON shape to a list of (trade_name, [item_dict]) tuples.
    Mirrors normaliseBoq() in the React front end and _enrich_boq() in app.py."""
    if not boq_json or not isinstance(boq_json, (list, dict)):
        return []

    if isinstance(boq_json, list):
        groups = boq_json
    else:
        if isinstance(boq_json.get('bill_of_quantities'), list):
            groups = boq_json['bill_of_quantities']
        elif isinstance(boq_json.get('trades'), list):
            groups = boq_json['trades']
        else:
            groups = [{'trade': k, 'items': v}
                      for k, v in boq_json.items() if isinstance(v, list)]

    if not isinstance(groups, list):
        return []

    result = []
    for g in groups:
        if not isinstance(g, dict):
            continue
        trade = g.get('trade') or g.get('name') or 'General'
        items = g.get('items') or g.get('line_items') or []
        if not isinstance(items, list):
            items = []
        result.append((trade, items))
    return result


# ── Paragraph style factory ────────────────────────────────────────────────────
_BASE = getSampleStyleSheet()


def _style(name, *, parent='Normal', font='Helvetica', size=8.5, leading=12,
           align=TA_LEFT, color=colors.black, bold=False):
    return ParagraphStyle(
        name,
        parent=_BASE[parent],
        fontName='Helvetica-Bold' if bold else font,
        fontSize=size,
        leading=leading,
        alignment=align,
        textColor=color,
    )


S_NORMAL        = _style('BoqNormal')
S_BOLD          = _style('BoqBold',       bold=True)
S_RIGHT         = _style('BoqRight',      align=TA_RIGHT)
S_RIGHT_BOLD    = _style('BoqRightBold',  align=TA_RIGHT, bold=True)
S_CENTER        = _style('BoqCenter',     align=TA_CENTER)
S_COL_HDR       = _style('BoqColHdr',     bold=True, color=colors.white)
S_COL_HDR_R     = _style('BoqColHdrR',    bold=True, color=colors.white, align=TA_RIGHT)
S_COL_HDR_C     = _style('BoqColHdrC',    bold=True, color=colors.white, align=TA_CENTER)
S_TRADE         = _style('BoqTrade',      bold=True, size=9.5, leading=14)
S_DISCLAIMER    = _style('BoqDisc',       font='Helvetica-Oblique', size=7,
                          color=colors.Color(0.4, 0.4, 0.4))
S_GUIDANCE_C    = _style('BoqGuidanceC', font='Helvetica-Oblique', size=8,
                          color=colors.Color(0.4, 0.4, 0.4), align=TA_CENTER)
S_TITLE         = _style('BoqTitle',      bold=True, size=14, leading=18)
S_SECTION       = _style('BoqSection',    bold=True, size=11, leading=14)
S_BODY          = _style('BoqBody',       size=9, leading=13)
S_BODY_BOLD     = _style('BoqBodyBold',   bold=True, size=9, leading=13)
S_TENDER_AMT    = _style('BoqTenderAmt',  bold=True, size=11, leading=16)

_GREY_TRADE = colors.Color(0.91, 0.91, 0.91)
_GREY_ALT   = colors.Color(0.97, 0.97, 0.97)
_GREY_LINE  = colors.Color(0.75, 0.75, 0.75)


# ── Shared table style base ────────────────────────────────────────────────────

def _base_table_cmds():
    """Return the standard TableStyle commands applied to all BoQ tables."""
    return [
        ('FONT',          (0, 0), (-1, -1), 'Helvetica', 8.5),
        ('LEADING',       (0, 0), (-1, -1), 12),
        ('BOX',           (0, 0), (-1, -1), 0.8, colors.black),
        ('INNERGRID',     (0, 0), (-1, -1), 0.25, _GREY_LINE),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 5),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 5),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]


def _col_header_cmds():
    """Return TableStyle commands for a black-background column header at row 0."""
    return [
        ('BACKGROUND',    (0, 0), (-1, 0), colors.black),
        ('TOPPADDING',    (0, 0), (-1, 0), 6),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
    ]


# ── Section-heading helper ────────────────────────────────────────────────────

def _section_heading(title: str) -> list:
    """Return flowables for a standard bold section heading with rule."""
    return [
        Spacer(1, 4 * mm),
        Paragraph(title, S_SECTION),
        Spacer(1, 2 * mm),
        HRFlowable(width=CONTENT_W, thickness=1.2, color=colors.black),
        Spacer(1, 4 * mm),
    ]


# ── White-label branding ────────────────────────────────────────────────────────
# Branding is supplied by the caller (the export route loads it for the signed-in
# user). It flows through generate_boq_pdf as an argument — never a global, never
# hardcoded. A missing/empty branding dict reproduces the default Vulcan Quanta
# output exactly.

DEFAULT_DOCUMENT_TITLE = 'Vulcan Quanta'   # used when no company_name is configured

_BRANDING_FIELDS = ('company_name', 'company_address', 'company_phone', 'company_email', 'logo_url')

# Letterhead styles — kept local to branding so they never affect existing sections.
S_BRAND_NAME = _style('BoqBrandName', bold=True, size=13, leading=16)
S_BRAND_LINE = _style('BoqBrandLine', size=8.5, leading=12,
                      color=colors.Color(0.25, 0.25, 0.25))

_LOGO_MAX_H = 18 * mm   # max logo height in the letterhead (within the 15-20mm spec)
_LOGO_MAX_W = 55 * mm   # cap width so a wide logo can't crowd the company details


def _normalise_branding(branding) -> dict:
    """Return a branding dict with all expected keys present as plain strings.

    Accepts None or a partial dict and never raises, so callers can pass whatever
    they loaded (or nothing) and the pipeline degrades cleanly to the default
    Vulcan Quanta presentation.
    """
    src = branding if isinstance(branding, dict) else {}
    out = {}
    for key in _BRANDING_FIELDS:
        val = src.get(key)
        out[key] = str(val).strip() if val else ''
    return out


def _logo_image_bytes(logo_url: str):
    """Fetch the raw bytes for a branding logo, or None on any problem.

    Supports data: URLs (base64 or percent-encoded), http(s) URLs (short timeout),
    and local filesystem paths. Every failure mode returns None so logo issues can
    never crash PDF generation.
    """
    if not logo_url or not isinstance(logo_url, str):
        return None
    src = logo_url.strip()
    try:
        if src.startswith('data:'):
            header, _, payload = src.partition(',')
            if not payload:
                return None
            if 'base64' in header:
                return base64.b64decode(payload)
            return urllib.parse.unquote_to_bytes(payload)
        if src.startswith('http://') or src.startswith('https://'):
            # Bounded fetch — guarded so a slow/broken URL never blocks the export.
            with urllib.request.urlopen(src, timeout=5) as resp:
                return resp.read()
        with open(src, 'rb') as fh:        # treat anything else as a local path
            return fh.read()
    except Exception:
        return None


def _build_logo_flowable(logo_url: str):
    """Return a ReportLab Image flowable for the logo (aspect-ratio preserved,
    height capped to _LOGO_MAX_H), or None if there is no usable image."""
    raw = _logo_image_bytes(logo_url)
    if not raw:
        return None
    try:
        iw, ih = ImageReader(io.BytesIO(raw)).getSize()
        if not iw or not ih:
            return None
        scale = min(_LOGO_MAX_H / ih, _LOGO_MAX_W / iw)
        return Image(io.BytesIO(raw), width=iw * scale, height=ih * scale)
    except Exception:
        return None


def _build_branding_header(branding: dict) -> list:
    """Page-1 letterhead built from configured branding.

    Renders the logo (if any) alongside the company name and only those contact
    lines that are populated — no blank rows. Returns [] when nothing is
    configured, so the default document is byte-for-byte unchanged.
    """
    name = branding.get('company_name', '')
    detail_lines = [branding.get(k, '') for k in ('company_address', 'company_phone', 'company_email')]
    detail_lines = [ln for ln in detail_lines if ln]
    logo = _build_logo_flowable(branding.get('logo_url', ''))

    if not name and not detail_lines and logo is None:
        return []                          # no branding → no letterhead at all

    text_flow = []
    if name:
        text_flow.append(Paragraph(html.escape(name), S_BRAND_NAME))
    for line in detail_lines:
        text_flow.append(Paragraph(html.escape(line), S_BRAND_LINE))

    story = [Spacer(1, 2 * mm)]
    if logo is not None:
        # Logo left, company details right — a balanced letterhead band. The two
        # cells sit in their own columns so the logo can never overlap the text.
        logo_w = min(_LOGO_MAX_W, getattr(logo, 'drawWidth', _LOGO_MAX_W))
        header = Table(
            [[logo, text_flow or '']],
            colWidths=[logo_w + 4 * mm, CONTENT_W - logo_w - 4 * mm],
        )
        header.setStyle(TableStyle([
            ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN',        (0, 0), (0, 0), 'LEFT'),
            ('ALIGN',        (1, 0), (1, 0), 'RIGHT'),
            ('LEFTPADDING',  (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING',   (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 0),
        ]))
        story.append(header)
    else:
        story.extend(text_flow)

    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width=CONTENT_W, thickness=0.5, color=colors.black))
    return story


# ── Section builders ──────────────────────────────────────────────────────────

def _build_doc_control_panel(boq_json, today_str: str) -> list:
    """Compact 2-column document-control panel for the title page."""
    if isinstance(boq_json, dict):
        revision     = boq_json.get('revision',     'A')                              or 'A'
        issue_status = boq_json.get('issue_status', 'Draft')                          or 'Draft'
        prepared_by  = boq_json.get('prepared_by',  'Vulcan Quanta')                  or 'Vulcan Quanta'
        checked_by   = boq_json.get('checked_by',   'Professional Review Required')   or 'Professional Review Required'
        intended_use = boq_json.get('intended_use', 'Tender Pricing')                 or 'Tender Pricing'
    else:
        revision     = 'A'
        issue_status = 'Draft'
        prepared_by  = 'Vulcan Quanta'
        checked_by   = 'Professional Review Required'
        intended_use = 'Tender Pricing'

    lbl_w = 48 * mm
    val_w = CONTENT_W - lbl_w

    rows = [
        [Paragraph("Revision",     S_BOLD), Paragraph(revision,     S_NORMAL)],
        [Paragraph("Issue Status", S_BOLD), Paragraph(issue_status, S_NORMAL)],
        [Paragraph("Prepared By",  S_BOLD), Paragraph(prepared_by,  S_NORMAL)],
        [Paragraph("Checked By",   S_BOLD), Paragraph(checked_by,   S_NORMAL)],
        [Paragraph("Intended Use", S_BOLD), Paragraph(intended_use, S_NORMAL)],
        [Paragraph("Issue Date",   S_BOLD), Paragraph(today_str,    S_NORMAL)],
    ]

    cmds = _base_table_cmds()
    for i in range(len(rows)):
        cmds.append(('BACKGROUND', (0, i), (0, i), _GREY_TRADE))

    tbl = Table(rows, colWidths=[lbl_w, val_w], hAlign='LEFT')
    tbl.setStyle(TableStyle(cmds))
    return [tbl]


def _build_form_of_tender(boq_json, today_str: str) -> list:
    """Page 1 — Form of Tender."""
    if isinstance(boq_json, dict):
        project  = boq_json.get('project_title', 'Residential Extension')
        location = boq_json.get('location', '—')
    else:
        project  = 'Residential Extension'
        location = '—'

    story = []
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("FORM OF TENDER", S_TITLE))
    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width=CONTENT_W, thickness=1.5, color=colors.black))
    story.append(Spacer(1, 6 * mm))

    label_w = 38 * mm
    value_w = CONTENT_W - label_w

    def _field_row(label, text):
        return [Paragraph(label, S_BODY_BOLD), Paragraph(text, S_BODY)]

    fields = Table(
        [
            _field_row("Project:",
                       project),
            _field_row("Location:",
                       location),
            _field_row("Drawing Refs:",
                       "Measured from Architect's Drawings Ref: PL-01 through PL-10 and "
                       "Structural Engineer's Calculation Sheet Ref: SE-04"),
            _field_row("Date:",        today_str),
            _field_row("Prepared by:", "Vulcan Quanta (AI-assisted draft)"),
        ],
        colWidths=[label_w, value_w],
    )
    fields.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
    ]))
    story.append(fields)
    story.append(Spacer(1, 8 * mm))
    story.append(HRFlowable(width=CONTENT_W, thickness=0.5, color=colors.black))
    story.append(Spacer(1, 5 * mm))
    story += _build_doc_control_panel(boq_json, today_str)
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph(
        "We the undersigned offer to carry out and complete the works described herein "
        "in accordance with the Contract Conditions for the sum of:",
        S_BODY,
    ))
    story.append(Spacer(1, 7 * mm))
    story.append(Paragraph(
        "£ ____________________________________________ (excluding VAT)",
        S_TENDER_AMT,
    ))
    story.append(Spacer(1, 12 * mm))

    col1 = 28 * mm
    col2 = 75 * mm
    col3 = 20 * mm
    col4 = CONTENT_W - col1 - col2 - col3
    sign_table = Table(
        [
            [Paragraph("Signed:",  S_BODY_BOLD),
             Paragraph("_________________________", S_BODY),
             Paragraph("Date:",    S_BODY_BOLD),
             Paragraph("_____________", S_BODY)],
            [Paragraph("Company:", S_BODY_BOLD),
             Paragraph("_________________________", S_BODY),
             Paragraph("", S_BODY),
             Paragraph("", S_BODY)],
        ],
        colWidths=[col1, col2, col3, col4],
    )
    sign_table.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
    ]))
    story.append(sign_table)
    return story


def _build_preambles() -> list:
    """Page 2 — Preambles & General Notes."""
    story = []
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("PREAMBLES AND GENERAL NOTES", S_TITLE))
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width=CONTENT_W, thickness=1.5, color=colors.black))
    story.append(Spacer(1, 6 * mm))

    num_w  = 12 * mm
    text_w = CONTENT_W - num_w
    for num, text in PREAMBLE_ITEMS:
        row = Table(
            [[Paragraph(num, S_BODY_BOLD), Paragraph(text, S_BODY)]],
            colWidths=[num_w, text_w],
        )
        row.setStyle(TableStyle([
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING',    (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('LEFTPADDING',   (0, 0), (-1, -1), 0),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
        ]))
        story.append(row)
    return story


def _build_preliminaries() -> tuple:
    """Section 01 — Preliminaries. Returns (flowables, prelim_total)."""
    story = _section_heading("SECTION 01 — PRELIMINARIES")

    lbl_w = 80 * mm
    val_w = CONTENT_W - lbl_w

    _plain_style = TableStyle([
        ('TOPPADDING',    (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING',   (0, 0), (-1, -1), 10),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
    ])

    def _info_block(pairs):
        rows = [[Paragraph(lbl, S_NORMAL), Paragraph(val, S_NORMAL)] for lbl, val in pairs]
        tbl = Table(rows, colWidths=[lbl_w, val_w], hAlign='LEFT')
        tbl.setStyle(_plain_style)
        return tbl

    def _sub_heading(letter, title):
        return [Spacer(1, 5 * mm), Paragraph(f'{letter}.  {title}', S_BODY_BOLD), Spacer(1, 2 * mm)]

    # ── A. PROJECT PARTICULARS ──────────────────────────────────────────────────
    story += _sub_heading('A', 'PROJECT PARTICULARS')
    story.append(_info_block([
        ("Project title:",                      "[To be inserted]"),
        ("Project address:",                    "[To be inserted]"),
        ("Employer:",                           "[To be inserted]"),
        ("Architect / Contract Administrator:", "[To be inserted]"),
        ("Quantity Surveyor:",                  "[To be inserted]"),
        ("Structural Engineer:",                "[To be inserted]"),
    ]))

    # ── B. CONTRACT PARTICULARS ────────────────────────────────────────────────
    story += _sub_heading('B', 'CONTRACT PARTICULARS')
    story.append(_info_block([
        ("Form of contract:",         "JCT Minor Works Building Contract 2016 (or as stated)"),
        ("Contract administrator:",   "[To be inserted]"),
        ("Liquidated damages:",        "[To be inserted] per week"),
        ("Defects liability period:",  "[To be inserted] weeks from practical completion"),
        ("Retention percentage:",     "[To be inserted]%"),
        ("Interim valuations:",        "Monthly"),
    ]))

    # ── C. SITE INFORMATION AND CONSTRAINTS ───────────────────────────────────
    story += _sub_heading('C', 'SITE INFORMATION AND CONSTRAINTS')
    story.append(_info_block([
        ("Site access:",           "[To be inserted]"),
        ("Working hours:",
         "Monday to Friday 08:00–17:30; Saturday 08:00–13:00 by agreement"),
        ("Existing services:",
         "Contractor to locate and protect all existing services"),
        ("Welfare facilities:",
         "Contractor to provide and maintain adequate welfare facilities throughout"),
        ("Hoarding and security:", "Contractor to provide as necessary"),
    ]))

    # ── D. QUALITY AND HANDOVER REQUIREMENTS ──────────────────────────────────
    story += _sub_heading('D', 'QUALITY AND HANDOVER REQUIREMENTS')
    bul_w  = 5 * mm
    txt_w  = CONTENT_W - bul_w
    d_rows = [
        [Paragraph('•', S_NORMAL),
         Paragraph("All work to be carried out in accordance with the specification "
                   "and drawings issued with these documents", S_NORMAL)],
        [Paragraph('•', S_NORMAL),
         Paragraph("Operation and maintenance manuals to be provided at practical completion",
                   S_NORMAL)],
        [Paragraph('•', S_NORMAL),
         Paragraph("As-built drawings to be provided at practical completion", S_NORMAL)],
        [Paragraph('•', S_NORMAL),
         Paragraph("All warranties and guarantees to be assigned to the Employer", S_NORMAL)],
    ]
    d_tbl = Table(d_rows, colWidths=[bul_w, txt_w], hAlign='LEFT')
    d_tbl.setStyle(TableStyle([
        ('TOPPADDING',    (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING',   (0, 0), (0, -1), 10),
        ('LEFTPADDING',   (1, 0), (1, -1), 4),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(d_tbl)

    # ── E. PRICING SCHEDULE — PRELIMINARY ITEMS ───────────────────────────────
    story += _sub_heading('E', 'PRICING SCHEDULE — PRELIMINARY ITEMS')

    itm_w    = 20
    fixed_w  = 70
    time_w   = 90
    tot_w    = _C_TOTAL
    p_desc_w = CONTENT_W - itm_w - fixed_w - time_w - tot_w

    p_rows = [[
        Paragraph("Item",                         S_COL_HDR),
        Paragraph("Description",                  S_COL_HDR),
        Paragraph("Fixed Charge (£)",             S_COL_HDR_R),
        Paragraph("Time-Related Charge (£/week)", S_COL_HDR_R),
        Paragraph("Total (£)",                    S_COL_HDR_R),
    ]]
    p_cmds = list(_col_header_cmds())

    prelim_schedule = [
        "Site establishment and mobilisation",
        "Site management and supervision",
        "Temporary site offices and welfare",
        "Temporary power supply",
        "Temporary water supply",
        "Site security and hoarding",
        "Cleaning and rubbish disposal during works",
        "Final clean on completion",
        "Insurance — works, employer's liability, public liability",
        "Health and safety — CDM compliance, method statements, risk assessments",
    ]
    for i, desc in enumerate(prelim_schedule, 1):
        ir = len(p_rows)
        p_rows.append([
            Paragraph(f'{i}.', S_CENTER),
            Paragraph(desc,    S_NORMAL),
            Paragraph("",      S_RIGHT),
            Paragraph("",      S_RIGHT),
            Paragraph("",      S_RIGHT),
        ])
        if ir % 2 == 0:
            p_cmds.append(('BACKGROUND', (0, ir), (-1, ir), _GREY_ALT))

    p_base = _base_table_cmds() + [('ALIGN', (2, 0), (-1, -1), 'RIGHT')]
    p_tbl  = Table(p_rows, colWidths=[itm_w, p_desc_w, fixed_w, time_w, tot_w],
                   repeatRows=1, hAlign='LEFT')
    p_tbl.setStyle(TableStyle(p_base + p_cmds))
    story.append(p_tbl)
    story.append(Spacer(1, 4 * mm))

    # Prelim total for Grand Summary — QS estimate carried from PRELIM_ITEMS
    prelim_total = sum(round(qty * rate, 2) for _, qty, _, rate in PRELIM_ITEMS)

    return story, prelim_total


def _build_measured_works(trade_groups) -> tuple:
    """Section 02 — Measured Works. Returns (flowables, measured_works_total).

    Column order is fixed throughout: Description | Qty | Unit | Rate | Total.
    One Table per trade so column headers repeat correctly on page splits.
    """
    story = _section_heading("SECTION 02 — MEASURED WORKS")
    trade_summaries = []

    for trade_idx, (trade_name, items) in enumerate(trade_groups, start=1):
        _m = re.match(r'^(\d+(?:\.\d+)*)', trade_name.strip())
        section_prefix = _m.group(1) if _m else str(trade_idx)

        rows = [[
            Paragraph('Description', S_COL_HDR),
            Paragraph('Qty',         S_COL_HDR_R),
            Paragraph('Unit',        S_COL_HDR_C),
            Paragraph('Rate',        S_COL_HDR_R),
            Paragraph('Total',       S_COL_HDR_R),
        ]]
        cmds = list(_col_header_cmds())

        # Trade name spanning all columns
        tr = len(rows)
        rows.append([Paragraph(trade_name.upper(), S_TRADE), '', '', '', ''])
        cmds += [
            ('SPAN',          (0, tr), (-1, tr)),
            ('BACKGROUND',    (0, tr), (-1, tr), _GREY_TRADE),
            ('LINEABOVE',     (0, tr), (-1, tr), 0.8, colors.black),
            ('TOPPADDING',    (0, tr), (-1, tr), 5),
            ('BOTTOMPADDING', (0, tr), (-1, tr), 5),
        ]

        trade_total = 0.0
        item_counter = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            item_counter += 1
            desc  = _apply_nrm2_desc(item.get('description') or item.get('desc') or '')
            qty   = float(item.get('quantity') or item.get('qty') or 0)
            unit  = _sanitise_unit(item.get('unit') or '')
            mat   = float(item.get('material_rate')      or 0)
            lab   = float(item.get('labour_rate')        or 0)
            plant = float(item.get('plant_rate')         or 0)
            waste = float(item.get('waste_disposal_rate') or 0)
            # Always recalculate — never trust a stored line_total
            line_tot = round(qty * (mat + lab + plant + waste), 2)
            trade_total += line_tot

            dim_str  = item.get('dimension_string', '')
            draw_ref = item.get('drawing_ref', '')
            cdp      = item.get('cdp', False)
            perf_req = item.get('performance_requirement', '')

            item_code = item.get('item_code') or f"{section_prefix}/{item_counter:03d}"

            desc_markup = f"<b>{item_code}</b>  {html.escape(desc)}"
            if dim_str:
                desc_markup += f'<br/><font size="8"><i>{html.escape(dim_str)}</i></font>'
            if draw_ref:
                desc_markup += f'<br/><font size="8"><i>Ref: {html.escape(draw_ref)}</i></font>'
            if cdp:
                desc_markup += '<br/><b>Contractor Designed Portion (CDP)</b>'
            if cdp and perf_req:
                desc_markup += f'<br/><i>Performance Requirement: {html.escape(perf_req)}</i>'

            ir = len(rows)
            rows.append([
                Paragraph(desc_markup,                      S_NORMAL),
                Paragraph(f'{qty:g}',                       S_RIGHT),
                Paragraph(unit,                             S_CENTER),
                Paragraph(_fmt(mat + lab + plant + waste),  S_RIGHT),
                Paragraph(_fmt(line_tot),                   S_RIGHT),
            ])
            if ir % 2 == 0:
                cmds.append(('BACKGROUND', (0, ir), (-1, ir), _GREY_ALT))

        # Trade subtotal — description spans cols 0–3, total in col 4
        sr = len(rows)
        rows.append([
            Paragraph(f'Subtotal — {trade_name}', S_RIGHT_BOLD),
            '', '', '',
            Paragraph(_fmt(trade_total), S_RIGHT_BOLD),
        ])
        cmds += [
            ('SPAN',          (0, sr), (_I_RATE, sr)),
            ('LINEABOVE',     (0, sr), (-1, sr), 0.5, colors.black),
            ('TOPPADDING',    (0, sr), (-1, sr), 4),
            ('BOTTOMPADDING', (0, sr), (-1, sr), 6),
        ]

        trade_summaries.append((trade_name, trade_total))

        base = _base_table_cmds() + [
            ('ALIGN', (_I_QTY,  0), (-1,        -1), 'RIGHT'),
            ('ALIGN', (_I_UNIT, 0), (_I_UNIT, -1), 'CENTER'),
        ]
        tbl = Table(rows, colWidths=COL_WIDTHS, repeatRows=1, splitByRow=True, hAlign='LEFT')
        tbl.setStyle(TableStyle(base + cmds))
        story.append(tbl)
        story.append(Spacer(1, 4 * mm))

    # Trade Collection Summary
    story += _section_heading("TRADE COLLECTION SUMMARY")

    coll_rows = [
        [Paragraph("Trade", S_COL_HDR), Paragraph("Total", S_COL_HDR_R)],
    ]
    coll_cmds = list(_col_header_cmds())
    measured_total = 0.0

    for tn, tt in trade_summaries:
        measured_total += tt
        ir = len(coll_rows)
        coll_rows.append([
            Paragraph(tn, S_NORMAL),
            Paragraph(_fmt(tt), S_RIGHT),
        ])
        if ir % 2 == 0:
            coll_cmds.append(('BACKGROUND', (0, ir), (-1, ir), _GREY_ALT))

    mr = len(coll_rows)
    coll_rows.append([
        Paragraph("Measured Works Total", S_RIGHT_BOLD),
        Paragraph(_fmt(measured_total), S_RIGHT_BOLD),
    ])
    coll_cmds += [
        ('LINEABOVE',     (0, mr), (-1, mr), 1.0, colors.black),
        ('TOPPADDING',    (0, mr), (-1, mr), 6),
        ('BOTTOMPADDING', (0, mr), (-1, mr), 6),
    ]

    coll_widths = [CONTENT_W - 100, 100]
    coll_base   = _base_table_cmds() + [('ALIGN', (1, 0), (1, -1), 'RIGHT')]
    coll_tbl    = Table(coll_rows, colWidths=coll_widths, repeatRows=1, hAlign='LEFT')
    coll_tbl.setStyle(TableStyle(coll_base + coll_cmds))
    story.append(coll_tbl)

    return story, measured_total


def _build_provisional_sums() -> tuple:
    """Section 03 — Provisional Sums, PC Sums, and Statutory Fees."""
    col_w = [CONTENT_W - 100, 100]
    story = _section_heading("SECTION 03 — PROVISIONAL SUMS, PC SUMS AND FEES")
    prov_total = 0.0

    def _sub_table(heading, items, show_ps_type=False):
        nonlocal prov_total
        rows = [[Paragraph("Description", S_COL_HDR),
                 Paragraph("Allowance",   S_COL_HDR_R)]]
        cmds = list(_col_header_cmds())
        sub_total = 0.0
        for item in items:
            if isinstance(item, dict):
                desc    = item.get('description', '')
                amt     = float(item.get('amount', 0.0))
                ps_type = item.get('ps_type')
            else:
                desc    = item[0]
                amt     = item[1]
                ps_type = item[2] if len(item) > 2 else None
            if show_ps_type:
                label     = ps_type if ps_type in ('Defined', 'Undefined') else 'Undefined'
                desc_text = f"{desc}<br/><i>({label} Provisional Sum)</i>"
            else:
                desc_text = desc
            prov_total += amt
            sub_total  += amt
            ir = len(rows)
            rows.append([Paragraph(desc_text, S_NORMAL),
                         Paragraph(_fmt(amt), S_RIGHT)])
            if ir % 2 == 0:
                cmds.append(('BACKGROUND', (0, ir), (-1, ir), _GREY_ALT))
        tr = len(rows)
        rows.append([
            Paragraph(f"{heading} Total", S_RIGHT_BOLD),
            Paragraph(_fmt(sub_total), S_RIGHT_BOLD),
        ])
        cmds += [
            ('LINEABOVE',     (0, tr), (-1, tr), 1.0, colors.black),
            ('TOPPADDING',    (0, tr), (-1, tr), 6),
            ('BOTTOMPADDING', (0, tr), (-1, tr), 6),
        ]
        base = _base_table_cmds() + [('ALIGN', (1, 0), (1, -1), 'RIGHT')]
        tbl = Table(rows, colWidths=col_w, repeatRows=1, hAlign='LEFT')
        tbl.setStyle(TableStyle(base + cmds))
        return tbl

    story.append(Paragraph("Provisional Sums", S_TRADE))
    story.append(_sub_table("Provisional Sums", PROVISIONAL_SUMS, show_ps_type=True))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Prime Cost Sums", S_TRADE))
    story.append(_sub_table("Prime Cost Sums", PC_SUMS))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Statutory Fees and Charges", S_TRADE))
    story.append(_sub_table("Statutory Fees and Charges", STATUTORY_FEES))
    story.append(Spacer(1, 4 * mm))

    # Section total row
    col_w2 = [CONTENT_W - 100, 100]
    total_rows = [[
        Paragraph("Section 03 Total", S_RIGHT_BOLD),
        Paragraph(_fmt(prov_total), S_RIGHT_BOLD),
    ]]
    total_cmds = [
        ('LINEABOVE',     (0, 0), (-1, 0), 1.5, colors.black),
        ('TOPPADDING',    (0, 0), (-1, 0), 6),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('ALIGN',         (1, 0), (1, 0),  'RIGHT'),
    ]
    base = _base_table_cmds()
    total_tbl = Table(total_rows, colWidths=col_w2, hAlign='LEFT')
    total_tbl.setStyle(TableStyle(base + total_cmds))
    story.append(total_tbl)

    return story, prov_total


def _build_risk_schedule(risks: list) -> list:
    """Risk Schedule section. Returns an empty list when no risks are present."""
    if not risks:
        return []

    _type_w  = 55
    _like_w  = 48
    _imp_w   = 85
    _mit_w   = 85
    _desc_w  = CONTENT_W - _type_w - _like_w - _imp_w - _mit_w

    rows = [[
        Paragraph("Description", S_COL_HDR),
        Paragraph("Risk Type",   S_COL_HDR_C),
        Paragraph("Impact",      S_COL_HDR),
        Paragraph("Likelihood",  S_COL_HDR_C),
        Paragraph("Mitigation",  S_COL_HDR),
    ]]
    cmds = list(_col_header_cmds())

    for risk in risks:
        if not isinstance(risk, dict):
            continue
        desc       = html.escape(risk.get('description', ''))
        risk_type  = html.escape(risk.get('risk_type', ''))
        impact     = html.escape(risk.get('impact', ''))
        likelihood = html.escape(risk.get('likelihood', ''))
        mitigation = html.escape(risk.get('mitigation', ''))

        ir = len(rows)
        rows.append([
            Paragraph(desc,       S_NORMAL),
            Paragraph(risk_type,  S_CENTER),
            Paragraph(impact,     S_NORMAL),
            Paragraph(likelihood, S_CENTER),
            Paragraph(mitigation, S_NORMAL),
        ])
        if ir % 2 == 0:
            cmds.append(('BACKGROUND', (0, ir), (-1, ir), _GREY_ALT))

    base = _base_table_cmds() + [
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('ALIGN', (3, 0), (3, -1), 'CENTER'),
    ]
    tbl = Table(
        rows,
        colWidths=[_desc_w, _type_w, _imp_w, _like_w, _mit_w],
        repeatRows=1,
        hAlign='LEFT',
    )
    tbl.setStyle(TableStyle(base + cmds))

    story = _section_heading("RISK SCHEDULE")
    story.append(tbl)
    story.append(Spacer(1, 4 * mm))
    return story


def _build_assumptions_register(entries: list) -> list:
    """Tender Queries & Assumptions Register — three-column table (Category | Status | Description).

    Returns [] when entries is empty so the caller can skip the section entirely.
    All user-supplied text is passed through html.escape() before rendering.
    Column widths sum to CONTENT_W.
    """
    if not entries:
        return []

    cat_w    = 28 * mm
    status_w = 45 * mm
    desc_w   = CONTENT_W - cat_w - status_w

    rows = [[
        Paragraph("Category",    S_COL_HDR),
        Paragraph("Status",      S_COL_HDR),
        Paragraph("Description", S_COL_HDR),
    ]]
    cmds = list(_col_header_cmds())

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        category    = html.escape(str(entry.get('category',    '') or ''))
        status      = html.escape(str(entry.get('status',      '') or ''))
        description = html.escape(str(entry.get('description', '') or ''))

        ir = len(rows)
        rows.append([
            Paragraph(category,    S_NORMAL),
            Paragraph(status,      S_CENTER),
            Paragraph(description, S_NORMAL),
        ])
        if ir % 2 == 0:
            cmds.append(('BACKGROUND', (0, ir), (-1, ir), _GREY_ALT))

    base = _base_table_cmds() + [
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('ALIGN', (3, 0), (3, -1), 'CENTER'),
    ]
    tbl = Table(
        rows,
        colWidths=[_desc_w, _type_w, _imp_w, _like_w, _mit_w],
        repeatRows=1,
        hAlign='LEFT',
    )
    tbl.setStyle(TableStyle(base + cmds))

    story = _section_heading("RISK SCHEDULE")
    base = _base_table_cmds() + [('ALIGN', (1, 0), (1, -1), 'CENTER')]
    tbl  = Table(rows, colWidths=[cat_w, status_w, desc_w], repeatRows=1, hAlign='LEFT')
    tbl.setStyle(TableStyle(base + cmds))

    story = _section_heading("Tender Queries & Assumptions Register")
    story.append(tbl)
    story.append(Spacer(1, 4 * mm))
    return story


def _build_dayworks() -> list:
    """Section 04 — Dayworks Schedule (blank rate template)."""
    res_w   = 28 * mm
    guide_w = 70
    rate_w  = 50
    unit_w  = 30
    grade_w = CONTENT_W - res_w - guide_w - rate_w - unit_w

    rows = [[
        Paragraph("Resource",               S_COL_HDR),
        Paragraph("Grade / Description",    S_COL_HDR),
        Paragraph("Guidance Range",         S_COL_HDR_C),
        Paragraph("Contractor's Rate (£)", S_COL_HDR_R),
        Paragraph("Unit",                   S_COL_HDR_C),
    ]]
    cmds = list(_col_header_cmds())

    for resource, grade, unit, guidance in DAYWORKS_ROWS:
        ir = len(rows)
        rows.append([
            Paragraph(resource, S_NORMAL),
            Paragraph(grade,    S_NORMAL),
            Paragraph(guidance, S_GUIDANCE_C),
            Paragraph("",       S_NORMAL),
            Paragraph(unit,     S_CENTER),
        ])
        if ir % 2 == 0:
            cmds.append(('BACKGROUND', (0, ir), (-1, ir), _GREY_ALT))

    base = _base_table_cmds() + [
        ('ALIGN', (2, 0), (2, -1), 'CENTER'),
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        ('ALIGN', (4, 0), (4, -1), 'CENTER'),
    ]
    tbl = Table(rows, colWidths=[res_w, grade_w, guide_w, rate_w, unit_w], repeatRows=1, hAlign='LEFT')
    tbl.setStyle(TableStyle(base + cmds))

    story = _section_heading("SECTION 04 — DAYWORKS SCHEDULE")
    story.append(tbl)
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(DAYWORKS_NOTE, S_DISCLAIMER))
    return story


def _build_annexes(boq_json) -> list:
    """Annexes — NRM2 supporting information. Returns [] if no annex content exists."""
    if not isinstance(boq_json, dict):
        return []

    annexes = boq_json.get('annexes')
    if not isinstance(annexes, dict):
        return []

    _ANNEX_DEFS = [
        ('schedules',                        'Annex A — Schedules'),
        ('performance_specifications',       'Annex B — Performance Specifications'),
        ('quotations',                       'Annex C — Quotations'),
        ('risk_notes',                       'Annex D — Risk Notes'),
        ('contractor_designed_scope',        'Annex E — Contractor Designed Scope'),
        ('statutory_undertaker_information', 'Annex F — Statutory Undertaker Information'),
    ]

    populated = [
        (title, annexes[key])
        for key, title in _ANNEX_DEFS
        if isinstance(annexes.get(key), list) and annexes[key]
    ]

    if not populated:
        return []

    story = _section_heading('ANNEXES')

    bul_w = 5 * mm
    txt_w = CONTENT_W - bul_w

    for title, entries in populated:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(title, S_BODY_BOLD))
        story.append(Spacer(1, 2 * mm))

        rows = [
            [Paragraph('•', S_NORMAL), Paragraph(html.escape(str(entry)), S_NORMAL)]
            for entry in entries
            if entry
        ]
        if rows:
            tbl = Table(rows, colWidths=[bul_w, txt_w], hAlign='LEFT')
            tbl.setStyle(TableStyle([
                ('TOPPADDING',    (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('LEFTPADDING',   (0, 0), (0,  -1), 10),
                ('LEFTPADDING',   (1, 0), (1,  -1), 4),
                ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
                ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(tbl)

    return story


def _build_grand_summary(prelim_total: float, measured_total: float, prov_total: float) -> list:
    """Grand Summary — tender BoQ version.

    Contingency and OHP are excluded from the issued tender BoQ.
    These are internal cost plan items and should not appear in
    the document issued to contractors for pricing.
    """
    works_total = round(prelim_total + measured_total + prov_total, 2)

    col_w = [CONTENT_W - 100, 100]
    rows  = [[Paragraph("Section", S_COL_HDR), Paragraph("Total", S_COL_HDR_R)]]
    cmds  = list(_col_header_cmds())

    summary_lines = [
        ("Section 01 — Preliminaries",          prelim_total,   False),
        ("Section 02 — Measured Works",          measured_total, False),
        ("Section 03 — Provisional & PC Sums",   prov_total,     False),
        ("WORKS TOTAL (excluding VAT)",          works_total,    True),
    ]

    for label, amount, is_bold in summary_lines:
        ir = len(rows)
        rows.append([
            Paragraph(label,        S_BOLD  if is_bold else S_NORMAL),
            Paragraph(_fmt(amount), S_RIGHT_BOLD if is_bold else S_RIGHT),
        ])
        if is_bold:
            cmds += [
                ('LINEABOVE',     (0, ir), (-1, ir), 1.0, colors.black),
                ('TOPPADDING',    (0, ir), (-1, ir), 6),
                ('BOTTOMPADDING', (0, ir), (-1, ir), 6),
            ]
        elif ir % 2 == 0:
            cmds.append(('BACKGROUND', (0, ir), (-1, ir), _GREY_ALT))

    gr = len(rows) - 1
    cmds.append(('LINEBELOW', (0, gr), (-1, gr), 1.5, colors.black))

    base = _base_table_cmds() + [('ALIGN', (1, 0), (1, -1), 'RIGHT')]
    tbl  = Table(rows, colWidths=col_w, repeatRows=1, hAlign='LEFT')
    tbl.setStyle(TableStyle(base + cmds))

    story = _section_heading("GRAND SUMMARY")
    story.append(tbl)
    return story


# ── Main function ──────────────────────────────────────────────────────────────

def _draw_watermark(canvas_obj, doc):
    """Draw a diagonal grey watermark on every page."""
    from reportlab.lib.colors import Color
    from reportlab.lib.units import mm
    canvas_obj.saveState()
    canvas_obj.setFont("Helvetica-Bold", 52)
    canvas_obj.setFillColor(Color(0.75, 0.75, 0.75, alpha=0.30))
    canvas_obj.translate(doc.pagesize[0] / 2, doc.pagesize[1] / 2)
    canvas_obj.rotate(45)
    canvas_obj.drawCentredString(0, 0, "AI MEASUREMENT DRAFT — UNVERIFIED")
    canvas_obj.restoreState()


def generate_boq_pdf(boq_json: dict, watermark: bool = False, branding=None) -> bytes:
    """Generate a professional NRM2-compliant Bill of Quantities PDF and return raw bytes.

    Args:
        boq_json: priced BoQ dict returned by /process.  Accepts all common shapes.
        branding: optional white-label dict with company_name, company_address,
            company_phone, company_email and logo_url. When omitted or empty the
            PDF is identical to the default Vulcan Quanta output.

    Returns:
        Raw PDF bytes.  Raises ValueError if boq_json contains no trade data.
    """
    trade_groups = _normalise_boq(boq_json)
    if not trade_groups:
        raise ValueError("boq_json contains no recognisable trade groups.")

    brand = _normalise_branding(branding)
    # Title source: configured company name, else the default. Only the title text
    # changes — every other element of the page chrome stays exactly as before.
    document_title = brand['company_name'] or DEFAULT_DOCUMENT_TITLE

    buf = io.BytesIO()
    d   = date.today()
    today_str = f"{d.day} {d.strftime('%B %Y')}"

    def _draw_chrome(canvas, doc):
        canvas.saveState()

        y_title = PAGE_H - TOP_M + 13 * mm
        canvas.setFont('Helvetica-Bold', 16)
        canvas.setFillColor(colors.black)
        canvas.drawString(LEFT_M, y_title, document_title)

        canvas.setFont('Helvetica', 8.5)
        canvas.drawRightString(PAGE_W - RIGHT_M, y_title, today_str)

        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.Color(0.3, 0.3, 0.3))
        canvas.drawString(LEFT_M, y_title - 12, 'Bill of Quantities — AI-Assisted Draft')

        rule_y = PAGE_H - TOP_M + 4 * mm
        canvas.setStrokeColor(colors.black)
        canvas.setLineWidth(0.8)
        canvas.line(LEFT_M, rule_y, PAGE_W - RIGHT_M, rule_y)

        canvas.setFont('Helvetica', 7.5)
        canvas.setFillColor(colors.black)
        canvas.drawRightString(PAGE_W - RIGHT_M, rule_y - 8, f'Page {doc.page}')

        canvas.restoreState()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=LEFT_M,
        rightMargin=RIGHT_M,
        topMargin=TOP_M,
        bottomMargin=BOT_M,
        title='Bill of Quantities',
        author=document_title,
    )

    prelim_flowables,   prelim_total   = _build_preliminaries()
    measured_flowables, measured_total = _build_measured_works(trade_groups)
    prov_flowables,     prov_total     = _build_provisional_sums()

    story = []
    story += _build_branding_header(brand)   # [] when no branding → unchanged output
    story += _build_form_of_tender(boq_json, today_str)
    story.append(PageBreak())
    story += _build_preambles()
    story.append(PageBreak())
    story += prelim_flowables
    story.append(PageBreak())
    story += measured_flowables
    story.append(PageBreak())
    story += prov_flowables

    assumptions_entries = (
        boq_json.get('assumptions_register', [])
        if isinstance(boq_json, dict) else []
    )
    assumptions_flowables = _build_assumptions_register(assumptions_entries or [])
    if assumptions_flowables:
        story.append(PageBreak())
        story += assumptions_flowables

    story.append(PageBreak())
    risks = boq_json.get('risk_schedule', []) if isinstance(boq_json, dict) else []
    risk_flowables = _build_risk_schedule(risks)
    if risk_flowables:
        story += risk_flowables
        story.append(PageBreak())
    story += _build_dayworks()
    annex_flowables = _build_annexes(boq_json)
    if annex_flowables:
        story.append(PageBreak())
        story += annex_flowables
    story.append(PageBreak())
    story += _build_grand_summary(prelim_total, measured_total, prov_total)

    def _first_page(canvas_obj, doc):
        _draw_chrome(canvas_obj, doc)
        if watermark:
            _draw_watermark(canvas_obj, doc)

    def _later_pages(canvas_obj, doc):
        _draw_chrome(canvas_obj, doc)
        if watermark:
            _draw_watermark(canvas_obj, doc)

    doc.build(story, onFirstPage=_first_page, onLaterPages=_later_pages)
    return buf.getvalue()
