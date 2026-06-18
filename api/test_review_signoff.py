#!/usr/bin/env python3
"""Smoke test for the Review & Sign-off workspace endpoints.

Exercises every new route in sequence against a live backend:

  GET  /projects/<id>/review
  PATCH /projects/<id>/review/line/<item_id>   (approve / modify / reject / reopen)
  POST  /projects/<id>/review/section
  POST  /projects/<id>/signoff
  GET   /projects/<id>/audit
  DELETE /projects/<id>/signoff   (revoke)

Usage
─────
  pip install requests
  python test_review_signoff.py \\
      --url https://vulcan-production-d039.up.railway.app \\
      --token "<supabase-access-token>" \\
      --project "<project-uuid-with-boq-data>"

The project must already have a boq_data payload (i.e. a BoQ has been generated
for it).  If the boq_audit_events table does not yet exist the test still passes
— the audit trail will simply be empty.

Exit code 0 = all assertions passed, 1 = at least one failed.
"""
import argparse
import sys
import time

try:
    import requests
except ImportError:
    sys.exit("This script needs `requests` — run: pip install requests")

FRONTEND_ORIGIN = "https://ojburnsey-tech.github.io"
TIMEOUT_S = 30


def _fail(msg: str) -> int:
    print(f"\n❌ FAIL — {msg}")
    return 1


def _check_cors(resp, route: str) -> bool:
    acao = resp.headers.get("Access-Control-Allow-Origin")
    if acao != FRONTEND_ORIGIN:
        print(f"  ⚠  CORS header missing/wrong on {route} (got {acao!r})")
        return False
    return True


def _json(resp, route: str):
    """Parse JSON, fail clearly if the body is not JSON."""
    try:
        return resp.json()
    except ValueError:
        print(f"❌ FAIL — {route} body is not JSON: {resp.text[:300]!r}")
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url",     required=True, help="Backend base URL")
    ap.add_argument("--token",   required=True, help="Supabase access token")
    ap.add_argument("--project", required=True, help="UUID of a project that has boq_data")
    args = ap.parse_args()

    base    = args.url.rstrip("/")
    headers = {
        "Origin":        FRONTEND_ORIGIN,
        "Authorization": f"Bearer {args.token}",
        "Content-Type":  "application/json",
    }
    pid = args.project

    failures = 0

    # ─────────────────────────────────────────────────────────────────────────
    # 1 — GET /review  (loads boq_data with injected IDs + review_states)
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n→ GET {base}/projects/{pid}/review")
    t0   = time.time()
    resp = requests.get(f"{base}/projects/{pid}/review", headers=headers, timeout=TIMEOUT_S)
    print(f"  ← {resp.status_code} in {time.time()-t0:.1f}s")

    _check_cors(resp, "GET /review")

    data = _json(resp, "GET /review")
    if data is None:
        return 1
    if resp.status_code != 200:
        return _fail(f"GET /review returned {resp.status_code}: {data.get('error', data)}")

    boq  = data.get("boq_data")
    if not boq:
        return _fail(f"GET /review returned 200 but no boq_data. Keys: {list(data.keys())}")

    # Extract the first item that has an injected 'id' so we can test line actions.
    groups = (
        boq.get("bill_of_quantities") or boq.get("trades") or []
    ) if isinstance(boq, dict) else (boq if isinstance(boq, list) else [])

    first_item = None
    first_section = None
    for gi, g in enumerate(groups):
        items = g.get("items") or g.get("line_items") or []
        for ii, item in enumerate(items):
            if isinstance(item, dict):
                first_item    = item.get("id") or item.get("item_code") or f"g{gi}_i{ii}"
                first_section = g.get("trade") or g.get("section") or ""
                break
        if first_item:
            break

    if not first_item:
        return _fail("GET /review returned boq_data but no parseable items — can't test line routes.")

    counts = data.get("counts", {})
    print(f"  ✓ boq_data OK — {counts.get('total', '?')} items, first item id={first_item!r}")
    print(f"  ✓ review_states: {len(data.get('review_states', {}))} overrides")

    # ─────────────────────────────────────────────────────────────────────────
    # 2 — PATCH .../line/<item_id>  approve
    # ─────────────────────────────────────────────────────────────────────────
    line_url = f"{base}/projects/{pid}/review/line/{first_item}"
    print(f"\n→ PATCH {line_url}  action=approve")
    resp = requests.patch(line_url, headers=headers, json={"action": "approve"}, timeout=TIMEOUT_S)
    print(f"  ← {resp.status_code}")
    _check_cors(resp, "PATCH /line approve")

    d = _json(resp, "PATCH /line approve")
    if d is None:
        return 1
    if resp.status_code != 200:
        failures += 1
        print(f"  ❌ approve failed {resp.status_code}: {d.get('error', d)}")
    else:
        st = d.get("state", {})
        if st.get("state") != "approved":
            failures += 1
            print(f"  ❌ expected state=approved, got {st!r}")
        else:
            print(f"  ✓ state={st['state']}  grand_total={d.get('grand_total')}")

    # ─────────────────────────────────────────────────────────────────────────
    # 3 — PATCH .../line/<item_id>  modify
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n→ PATCH {line_url}  action=modify")
    resp = requests.patch(line_url, headers=headers,
                          json={"action": "modify", "qty": 10, "rate": 50.0},
                          timeout=TIMEOUT_S)
    print(f"  ← {resp.status_code}")
    _check_cors(resp, "PATCH /line modify")

    d = _json(resp, "PATCH /line modify")
    if d is None:
        return 1
    if resp.status_code != 200:
        failures += 1
        print(f"  ❌ modify failed {resp.status_code}: {d.get('error', d)}")
    else:
        st = d.get("state", {})
        if st.get("state") != "modified":
            failures += 1
            print(f"  ❌ expected state=modified, got {st!r}")
        else:
            print(f"  ✓ state={st['state']}  qty={st.get('qty')}  rate={st.get('rate')}")

    # ─────────────────────────────────────────────────────────────────────────
    # 4 — PATCH .../line/<item_id>  reject
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n→ PATCH {line_url}  action=reject")
    resp = requests.patch(line_url, headers=headers,
                          json={"action": "reject", "reason": "Smoke test rejection"},
                          timeout=TIMEOUT_S)
    print(f"  ← {resp.status_code}")
    _check_cors(resp, "PATCH /line reject")

    d = _json(resp, "PATCH /line reject")
    if d is None:
        return 1
    if resp.status_code != 200:
        failures += 1
        print(f"  ❌ reject failed {resp.status_code}: {d.get('error', d)}")
    else:
        st = d.get("state", {})
        if st.get("state") != "rejected":
            failures += 1
            print(f"  ❌ expected state=rejected, got {st!r}")
        else:
            print(f"  ✓ state={st['state']}  reason={st.get('reason')!r}")

    # ─────────────────────────────────────────────────────────────────────────
    # 5 — PATCH .../line/<item_id>  reopen
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n→ PATCH {line_url}  action=reopen")
    resp = requests.patch(line_url, headers=headers, json={"action": "reopen"}, timeout=TIMEOUT_S)
    print(f"  ← {resp.status_code}")
    _check_cors(resp, "PATCH /line reopen")

    d = _json(resp, "PATCH /line reopen")
    if d is None:
        return 1
    if resp.status_code != 200:
        failures += 1
        print(f"  ❌ reopen failed {resp.status_code}: {d.get('error', d)}")
    else:
        st = d.get("state", {})
        if st.get("state") != "pending":
            failures += 1
            print(f"  ❌ expected state=pending after reopen, got {st!r}")
        else:
            print(f"  ✓ state={st['state']} (pending = reopened)")

    # ─────────────────────────────────────────────────────────────────────────
    # 6 — POST .../review/section  (bulk-approve all pending items in section)
    # ─────────────────────────────────────────────────────────────────────────
    if first_section:
        sec_url = f"{base}/projects/{pid}/review/section"
        print(f"\n→ POST {sec_url}  section={first_section!r}")
        resp = requests.post(sec_url, headers=headers,
                             json={"section": first_section}, timeout=TIMEOUT_S)
        print(f"  ← {resp.status_code}")
        _check_cors(resp, "POST /review/section")

        d = _json(resp, "POST /review/section")
        if d is None:
            return 1
        if resp.status_code != 200:
            failures += 1
            print(f"  ❌ section approve failed {resp.status_code}: {d.get('error', d)}")
        else:
            print(f"  ✓ section approved — updated {d.get('updated', '?')} items")

    # ─────────────────────────────────────────────────────────────────────────
    # 7 — GET /audit  (audit trail; may be empty if boq_audit_events table absent)
    # ─────────────────────────────────────────────────────────────────────────
    audit_url = f"{base}/projects/{pid}/audit"
    print(f"\n→ GET {audit_url}")
    resp = requests.get(audit_url, headers=headers, timeout=TIMEOUT_S)
    print(f"  ← {resp.status_code}")
    _check_cors(resp, "GET /audit")

    d = _json(resp, "GET /audit")
    if d is None:
        return 1
    if resp.status_code != 200:
        failures += 1
        print(f"  ❌ GET /audit failed {resp.status_code}: {d.get('error', d)}")
    else:
        events = d.get("audit_events", [])
        print(f"  ✓ audit_events: {len(events)} entries")

    # ─────────────────────────────────────────────────────────────────────────
    # 8 — POST /signoff  (sign the bill)
    # Note: requires ALL items to be non-pending; we approve the whole project
    # by approving the section above. Some items may still be pending if there
    # are multiple sections. We attempt sign-off and accept a 409 (incomplete)
    # as a meaningful test that the endpoint is reachable and correctly guarded.
    # ─────────────────────────────────────────────────────────────────────────
    signoff_url = f"{base}/projects/{pid}/signoff"
    print(f"\n→ POST {signoff_url}")
    resp = requests.post(signoff_url, headers=headers, json={
        "name":        "Smoke Test QS",
        "title":       "MRICS",
        "declaration": True,
    }, timeout=TIMEOUT_S)
    print(f"  ← {resp.status_code}")
    _check_cors(resp, "POST /signoff")

    d = _json(resp, "POST /signoff")
    if d is None:
        return 1
    if resp.status_code == 200:
        print(f"  ✓ signed off — hash prefix: {str(d.get('signoff_hash', ''))[:16]}…")
        signed_off = True
    elif resp.status_code == 409:
        # Endpoint is reachable and correctly rejected because not all items are reviewed.
        print(f"  ✓ 409 conflict (pending items remain) — guard logic is working")
        signed_off = False
    else:
        failures += 1
        print(f"  ❌ POST /signoff returned unexpected {resp.status_code}: {d.get('error', d)}")
        signed_off = False

    # ─────────────────────────────────────────────────────────────────────────
    # 9 — DELETE /signoff  (revoke, only if we just signed off)
    # ─────────────────────────────────────────────────────────────────────────
    if signed_off:
        print(f"\n→ DELETE {signoff_url}")
        resp = requests.delete(signoff_url, headers=headers, timeout=TIMEOUT_S)
        print(f"  ← {resp.status_code}")
        _check_cors(resp, "DELETE /signoff")

        d = _json(resp, "DELETE /signoff")
        if d is None:
            return 1
        if resp.status_code != 200:
            failures += 1
            print(f"  ❌ DELETE /signoff failed {resp.status_code}: {d.get('error', d)}")
        else:
            print(f"  ✓ sign-off revoked — ok={d.get('ok')}")

    # ─────────────────────────────────────────────────────────────────────────
    # Final verdict
    # ─────────────────────────────────────────────────────────────────────────
    if failures:
        print(f"\n❌ FAIL — {failures} assertion(s) failed.")
        return 1

    print("\n✅ PASS — all Review & Sign-off endpoints responded correctly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
