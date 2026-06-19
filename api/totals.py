"""Shared line-total arithmetic for Vulcan Quanta.

All surfaces that compute money — Review workspace, PDF export, Excel export —
import _effective_line_total from here.  One function; one result; no divergence.
"""


def _effective_line_total(item: dict, rs: dict) -> float:
    """Canonical line-total computation for the entire codebase.

    Priority for the unit rate:
      1. Component sum: material_rate + labour_rate + plant_rate + waste_disposal_rate
         (all four — the sum is trusted when any component is non-zero)
      2. Flat rate field — used by QS-added lines that carry only item['rate']
         (no component breakdown at all)
      3. Zero — no rate data available

    When a legacy review_states row carries qty / rate overrides (old action-based
    modify), rs.qty / rs.rate take precedence over the item's own values.
    For items whose edits are baked directly into working_boq, rs is {} and the
    item's own values are used directly.

    Returns a rounded float (2 d.p.) — never raises, even on bad input.
    """
    try:
        qty = float(
            rs.get("qty") if rs.get("qty") is not None
            else (item.get("quantity") or item.get("qty") or 0)
        )
    except (TypeError, ValueError):
        qty = 0.0

    try:
        component_total = (
            float(item.get("material_rate")       or 0) +
            float(item.get("labour_rate")         or 0) +
            float(item.get("plant_rate")          or 0) +
            float(item.get("waste_disposal_rate") or 0)
        )
    except (TypeError, ValueError):
        component_total = 0.0

    try:
        flat_rate = float(item.get("rate") or 0)
    except (TypeError, ValueError):
        flat_rate = 0.0

    base_rate = component_total if component_total > 0 else flat_rate

    try:
        rate = float(rs.get("rate") if rs.get("rate") is not None else base_rate)
    except (TypeError, ValueError):
        rate = base_rate

    return round(qty * rate, 2)
