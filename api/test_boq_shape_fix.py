#!/usr/bin/env python3
"""Regression tests for the two /process 502 bugs the Railway logs pinned down.

Background
──────────
A failed `POST /process` logged:

    JSON_EXTRACTION_FAILED: JSONDecodeError at line 1 col 1: Expecting value.
    First 500 chars of raw_text: ```json
    { "bill_of_quantities": { "project": ..., "client": ..., ... } ...

revealing TWO independent bugs:
  • Bug 1 — Claude wrapped its JSON in a ```json markdown fence, so json.loads
    failed at char 0 despite the prompt forbidding fences.
  • Bug 2 — Claude returned `bill_of_quantities` as an OBJECT of metadata instead
    of the schema-required ARRAY of {trade, items} groups, and invented top-level
    keys (project/client/currency/notes).

The fix forces structured output via tool use (tool_use.input is a schema-shaped
dict — no text, no fence) and adds defense-in-depth: _strip_code_fence for any text
that slips through, and _normalize_boq_shape to coerce drift back to the schema.

These tests run fully offline (the Anthropic client is monkeypatched), so they can
gate CI without burning credits. Run:  pytest api/test_boq_shape_fix.py
"""
import io
import json
import os
import types

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-used")

import app  # noqa: E402  (env var must be set before import)

# A real RATES_DB key so the schema's rate_key enum passes validation.
_RK = list(app.RATES_DB.keys())[0]


def _item(desc="Excavate to reduced level"):
    return {
        "description": desc, "rate_key": _RK, "quantity": 12.5, "unit": "m3",
        "dimension_string": "5 x 2.5 = 12.5m3",
    }


# ── Bug 1: markdown code-fence stripping ─────────────────────────────────────────
def test_strip_code_fence_variants():
    assert app._strip_code_fence('```json\n{"a":1}\n```') == '{"a":1}'
    assert app._strip_code_fence('```\n{"a":1}\n```') == '{"a":1}'
    assert app._strip_code_fence('  ```json\n{"a":1}```  ') == '{"a":1}'
    assert app._strip_code_fence('{"a":1}') == '{"a":1}'   # no fence → unchanged
    assert app._strip_code_fence('') == ''


def test_strip_code_fence_on_real_payload():
    payload = {"bill_of_quantities": [{"trade": "5.1 Groundworks", "items": [_item()]}]}
    fenced = "```json\n" + json.dumps(payload) + "\n```"
    assert json.loads(app._strip_code_fence(fenced)) == payload


def test_extract_first_json_object_handles_prose():
    assert app._extract_first_json_object('Here is your bill: {"x": 1} thanks!') == {"x": 1}
    assert app._extract_first_json_object("no json here") is None


# ── Bug 2: shape normalization ───────────────────────────────────────────────────
def test_normalize_bill_of_quantities_as_object():
    """The EXACT logged drift: bill_of_quantities is an object + invented top-level keys."""
    bug = {
        "project": "Office Ext", "client": "Northshore", "currency": "GBP", "notes": "draft",
        "bill_of_quantities": {
            "revision": "A", "issue_status": "Tender Issue",
            "sections": [
                {"trade": "5.1 Groundworks", "items": [_item(), _item("Disposal")]},
                {"trade": "5.8 Masonry", "items": [_item("Facing brick")]},
            ],
        },
    }
    norm = app._normalize_boq_shape(bug)
    app._validate_boq_output(norm)                       # must not raise
    assert isinstance(norm["bill_of_quantities"], list) and len(norm["bill_of_quantities"]) == 2
    assert norm.get("revision") == "A" and norm.get("issue_status") == "Tender Issue"  # metadata lifted
    for k in ("project", "client", "currency", "notes"):
        assert k not in norm                              # invented keys dropped


def test_normalize_trade_name_mapping_and_trades_wrapper():
    m = app._normalize_boq_shape({"5.1 Groundworks": [_item()], "5.8 Masonry": [_item("Brick")]})
    app._validate_boq_output(m)
    assert len(m["bill_of_quantities"]) == 2
    w = app._normalize_boq_shape({"trades": [{"trade": "5.1", "items": [_item()]}]})
    app._validate_boq_output(w)
    assert len(w["bill_of_quantities"]) == 1


def test_normalize_drops_truncation_tail():
    trunc = {"bill_of_quantities": [
        {"trade": "5.1", "items": [_item(), {"description": "half written"}]},  # 2nd item incomplete
        {"trade": "5.8", "items": [{"rate_key": _RK}]},                          # whole group invalid
    ]}
    norm = app._normalize_boq_shape(trunc)
    app._validate_boq_output(norm)
    assert len(norm["bill_of_quantities"]) == 1
    assert len(norm["bill_of_quantities"][0]["items"]) == 1


def test_normalize_strips_model_item_code():
    n = app._normalize_boq_shape(
        {"bill_of_quantities": [{"trade": "5.8 Masonry", "items": [{**_item(), "item_code": "GARBAGE/999"}]}]}
    )
    assert "item_code" not in n["bill_of_quantities"][0]["items"][0]
    e = app._enrich_boq(n)
    assert e["bill_of_quantities"][0]["items"][0]["item_code"] == "5.8/001"


def test_extract_tool_use_input():
    payload = {"bill_of_quantities": [{"trade": "5.1", "items": [_item()]}]}
    block = types.SimpleNamespace(type="tool_use", name=app.BOQ_TOOL_NAME, input=payload)
    msg = types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text=""), block])
    assert app._extract_tool_use_input(msg) is payload
    assert app._extract_tool_use_input(types.SimpleNamespace(content=[])) is None


def test_boq_tool_schema_excludes_item_code():
    item_props = (app.BOQ_TOOL["input_schema"]["properties"]["bill_of_quantities"]
                  ["items"]["properties"]["items"]["items"]["properties"])
    assert "item_code" not in item_props                  # enrichment-only, never model-generated
    assert app.BOQ_TOOL["name"] == app.BOQ_TOOL_NAME
    assert len(item_props["rate_key"]["enum"]) == len(app.RATES_DB)


# ── End-to-end: the real _run_boq_pipeline with a monkeypatched Claude client ─────
def _make_pdf():
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 750, "Proposed Two-Storey Office Extension, Belfast.")
    c.drawString(72, 730, "Groundworks, masonry, drainage and finishes specification.")
    c.save()
    return buf.getvalue()


_PDF = _make_pdf()


class _FakeStream:
    def __init__(self, final):
        self._final = final

    def __iter__(self):
        return iter([])                                   # no events; pipeline still calls get_final_message()

    def get_final_message(self):
        return self._final


class _FakeCtx:
    def __init__(self, final):
        self._final = final

    def __enter__(self):
        return _FakeStream(self._final)

    def __exit__(self, *a):
        return False


class _FakeClient:
    def __init__(self, final):
        self.messages = types.SimpleNamespace(
            stream=lambda **kw: _FakeCtx(final),
            create=lambda **kw: final,
        )


def _final_tool(input_dict, stop="tool_use"):
    blk = types.SimpleNamespace(type="tool_use", name=app.BOQ_TOOL_NAME, input=input_dict)
    return types.SimpleNamespace(content=[blk], stop_reason=stop,
                                 usage=types.SimpleNamespace(input_tokens=1000, output_tokens=2000))


def _final_text(text, stop="end_turn"):
    blk = types.SimpleNamespace(type="text", text=text)
    return types.SimpleNamespace(content=[blk], stop_reason=stop,
                                 usage=types.SimpleNamespace(input_tokens=1000, output_tokens=2000))


def _run(final, monkeypatch):
    monkeypatch.setattr(app.anthropic, "Anthropic", lambda **kw: _FakeClient(final))
    with app.app.test_request_context(
        "/process", method="POST",
        data={"file": (io.BytesIO(_PDF), "office-extension.pdf")},
        content_type="multipart/form-data",
    ):
        return app._run_boq_pipeline(user=None)           # user=None → demo path, skips DB gates


def _assert_good(res, want_truncated=False):
    boq, _pages, _up, err = res
    assert err is None, f"pipeline error: {err[0].get_json() if err else err}"
    assert isinstance(boq, dict) and boq.get("bill_of_quantities")
    for g in boq["bill_of_quantities"]:
        for it in g["items"]:
            assert "line_total" in it and "item_code" in it   # enrichment ran
    assert bool(boq.get("_truncated")) == want_truncated
    json.dumps(boq)                                       # response is serializable


def test_pipeline_tool_use_correct_shape(monkeypatch):
    _assert_good(_run(_final_tool(
        {"revision": "A", "bill_of_quantities": [{"trade": "5.1 Groundworks", "items": [_item(), _item("Disposal")]}]}
    ), monkeypatch))


def test_pipeline_tool_use_logged_bug_shape(monkeypatch):
    _assert_good(_run(_final_tool({
        "project": "Office Ext", "client": "Northshore",
        "bill_of_quantities": {
            "revision": "A", "issue_status": "Tender Issue",
            "sections": [{"trade": "5.1 Groundworks", "items": [_item()]},
                         {"trade": "5.8 Masonry", "items": [_item("Facing brick")]}],
        },
    }), monkeypatch))


def test_pipeline_tool_use_truncated_partial(monkeypatch):
    _assert_good(_run(_final_tool(
        {"bill_of_quantities": [{"trade": "5.1 Groundworks", "items": [_item()]},
                                {"trade": "5.8 Masonry", "items": [{"description": "half"}]}]},
        stop="max_tokens",
    ), monkeypatch), want_truncated=True)


def test_pipeline_text_fallback_fenced(monkeypatch):
    fenced = "```json\n" + json.dumps(
        {"bill_of_quantities": [{"trade": "5.1 Groundworks", "items": [_item()]}]}) + "\n```"
    _assert_good(_run(_final_text(fenced), monkeypatch))


def test_pipeline_text_fallback_fenced_bug_shape(monkeypatch):
    fenced = "```json\n" + json.dumps(
        {"project": "X", "bill_of_quantities": {"revision": "B", "sections": [
            {"trade": "5.8 Masonry", "items": [_item()]}]}}) + "\n```"
    _assert_good(_run(_final_text(fenced), monkeypatch))


def test_pipeline_unparseable_returns_502(monkeypatch):
    _boq, _pages, _up, err = _run(_final_text("I could not produce a bill."), monkeypatch)
    assert err is not None and err[1] == 502
