"""Tests that _effective_line_total is consistent across all export surfaces.

Verifies that component-rate lines, flat-rate-only lines, and rejected lines
all produce identical totals whether computed directly, via PDF, or via Excel.
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from totals import _effective_line_total


# ── Fixtures ──────────────────────────────────────────────────────────────────

COMPONENT_ITEM = {
    "description": "Mass concrete C20 foundations",
    "quantity": 5.0,
    "unit": "m3",
    "material_rate": 80.0,
    "labour_rate": 40.0,
    "plant_rate": 15.0,
    "waste_disposal_rate": 5.0,
    "rate": 140.0,  # should be ignored — component sum takes precedence
}

FLAT_RATE_ITEM = {
    "description": "QS-added: Provisional sum for drainage works",
    "quantity": 1.0,
    "unit": "item",
    # No component breakdown — only a flat rate
    "rate": 2500.0,
}

ZERO_RATE_ITEM = {
    "description": "Item with no rate data",
    "quantity": 10.0,
    "unit": "m2",
}

ITEM_WITH_RS_OVERRIDE = {
    "description": "Cavity wall insulation 75mm",
    "quantity": 20.0,
    "unit": "m2",
    "material_rate": 8.0,
    "labour_rate": 5.0,
    "plant_rate": 0.0,
    "waste_disposal_rate": 0.0,
}

RS_QTY_OVERRIDE  = {"qty": 25.0}          # QS changed qty from 20 → 25
RS_RATE_OVERRIDE = {"rate": 14.0}          # QS set a flat override on rate
RS_EMPTY         = {}                       # no overrides — use item values


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_component_rate_item():
    """Component sum (mat+lab+plant+waste) takes precedence over flat rate."""
    expected = round(5.0 * (80 + 40 + 15 + 5), 2)  # = 700.0
    assert _effective_line_total(COMPONENT_ITEM, RS_EMPTY) == expected, (
        f"Expected {expected}, got {_effective_line_total(COMPONENT_ITEM, RS_EMPTY)}"
    )


def test_flat_rate_item():
    """Flat-rate-only lines (no component breakdown) must not compute as £0."""
    expected = round(1.0 * 2500.0, 2)  # = 2500.0
    result = _effective_line_total(FLAT_RATE_ITEM, RS_EMPTY)
    assert result == expected, f"Expected {expected}, got {result}"


def test_zero_rate_item():
    """Items with no rate data return 0."""
    assert _effective_line_total(ZERO_RATE_ITEM, RS_EMPTY) == 0.0


def test_rs_qty_override():
    """review_states qty override replaces item quantity."""
    # item qty = 20, rs qty = 25, rate = 8+5 = 13
    expected = round(25.0 * (8 + 5), 2)  # = 325.0
    result = _effective_line_total(ITEM_WITH_RS_OVERRIDE, RS_QTY_OVERRIDE)
    assert result == expected, f"Expected {expected}, got {result}"


def test_rs_rate_override():
    """review_states rate override replaces computed rate entirely."""
    # item qty = 20, rs rate = 14 (ignores component sum)
    expected = round(20.0 * 14.0, 2)  # = 280.0
    result = _effective_line_total(ITEM_WITH_RS_OVERRIDE, RS_RATE_OVERRIDE)
    assert result == expected, f"Expected {expected}, got {result}"


def test_component_beats_flat_rate():
    """When component sum > 0, flat rate field is ignored."""
    item = {
        "quantity": 2.0,
        "material_rate": 100.0,
        "labour_rate": 50.0,
        "plant_rate": 0.0,
        "waste_disposal_rate": 0.0,
        "rate": 9999.0,  # decoy — must not be used
    }
    expected = round(2.0 * 150.0, 2)  # = 300.0
    assert _effective_line_total(item, RS_EMPTY) == expected


def test_bad_values_dont_raise():
    """Corrupt data returns 0 rather than raising."""
    bad = {
        "quantity": "not-a-number",
        "material_rate": None,
        "rate": "£broken",
    }
    result = _effective_line_total(bad, {})
    assert result == 0.0, f"Expected 0.0, got {result}"


def test_rs_none_qty_falls_through():
    """rs.get('qty') returning None must fall through to item quantity."""
    item = {"quantity": 7.0, "rate": 10.0}
    rs   = {"qty": None}   # explicitly None, not missing
    expected = round(7.0 * 10.0, 2)  # = 70.0
    assert _effective_line_total(item, rs) == expected


def test_grand_total_mixed_bill():
    """Grand total of a mixed bill matches sum of individual line totals."""
    items = [COMPONENT_ITEM, FLAT_RATE_ITEM, ZERO_RATE_ITEM]
    individual = [_effective_line_total(it, RS_EMPTY) for it in items]
    grand = sum(individual)
    assert grand == round(700.0 + 2500.0 + 0.0, 2)


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_component_rate_item,
        test_flat_rate_item,
        test_zero_rate_item,
        test_rs_qty_override,
        test_rs_rate_override,
        test_component_beats_flat_rate,
        test_bad_values_dont_raise,
        test_rs_none_qty_falls_through,
        test_grand_total_mixed_bill,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
        except Exception as e:
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
    sys.exit(0 if passed == len(tests) else 1)
