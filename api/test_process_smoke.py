#!/usr/bin/env python3
"""End-to-end smoke test for the /process upload → BoQ pipeline.

Purpose
───────
Reproduce the EXACT request the frontend makes (multipart PDF + Bearer JWT) and
prove the fix for the credit-draining timeout bug: the client now receives a
usable, CORS-decorated JSON BoQ instead of hanging or failing opaquely.

It checks the two things that were silently broken before:
  1. The response actually ARRIVES within the timeout budget (no worker kill).
  2. The response carries Access-Control-Allow-Origin (so the browser fetch()
     can read it instead of reporting an opaque "Network error").

Usage
─────
  pip install requests
  python test_process_smoke.py \
      --url https://vulcan-production-d039.up.railway.app \
      --token "<a-valid-supabase-access-token>" \
      --pdf /path/to/a/real/multi-page-drawing.pdf

  # Public demo path (no token needed):
  python test_process_smoke.py --url https://vulcan-production-d039.up.railway.app \
      --pdf /path/to/sample.pdf --demo

Exit code 0 = pass, 1 = fail. Safe to wire into CI.
"""
import argparse
import sys
import time

try:
    import requests
except ImportError:
    sys.exit("This script needs `requests` — run: pip install requests")

# Mirrors the frontend Origin (GitHub Pages). The backend only echoes CORS headers
# back when the Origin is in _ALLOWED_ORIGINS, so we send the real one.
FRONTEND_ORIGIN = "https://ojburnsey-tech.github.io"
# Just under the server's 360s gunicorn worker timeout (same budget as the
# frontend AbortController) — if we exceed this, the bug has regressed.
CLIENT_TIMEOUT_S = 280


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", required=True, help="Backend base URL (Railway or http://localhost:8080)")
    ap.add_argument("--pdf", required=True, help="Path to a real multi-page PDF")
    ap.add_argument("--token", default="", help="Supabase access token (required unless --demo)")
    ap.add_argument("--demo", action="store_true", help="Hit /demo-process (no auth) instead of /process")
    args = ap.parse_args()

    endpoint = "/demo-process" if args.demo else "/process"
    if not args.demo and not args.token:
        return _fail("--token is required for /process (use --demo for the public path)")

    url = args.url.rstrip("/") + endpoint
    headers = {"Origin": FRONTEND_ORIGIN}
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"

    print(f"→ POST {url}")
    print(f"  Origin={FRONTEND_ORIGIN}  auth={'yes' if args.token else 'no'}  timeout={CLIENT_TIMEOUT_S}s")

    try:
        with open(args.pdf, "rb") as fh:
            files = {"file": (args.pdf.split("/")[-1], fh, "application/pdf")}
            t0 = time.time()
            resp = requests.post(url, headers=headers, files=files, timeout=CLIENT_TIMEOUT_S)
            elapsed = time.time() - t0
    except requests.exceptions.Timeout:
        return _fail(f"Request exceeded {CLIENT_TIMEOUT_S}s — the timeout bug may have regressed "
                     "(worker killed before responding).")
    except requests.exceptions.RequestException as exc:
        return _fail(f"Network/connection error: {exc}")
    except FileNotFoundError:
        return _fail(f"PDF not found: {args.pdf}")

    print(f"← {resp.status_code} in {elapsed:.1f}s")

    # Check 1 — the CORS header that was missing under the worker-kill scenario.
    acao = resp.headers.get("Access-Control-Allow-Origin")
    if acao != FRONTEND_ORIGIN:
        return _fail(f"Missing/incorrect Access-Control-Allow-Origin (got {acao!r}). "
                     "A browser fetch() would report this as an opaque Network/CORS error.")
    print(f"  ✓ Access-Control-Allow-Origin = {acao}")

    # Check 2 — a clean JSON body (success OR a structured error, never a raw crash).
    try:
        data = resp.json()
    except ValueError:
        return _fail(f"Response body was not JSON (first 300 chars): {resp.text[:300]!r}")

    if resp.status_code != 200:
        # A clean, CORS-decorated error is itself a PASS for the lifecycle fix —
        # the point is the client can read it. Surface it and exit non-zero.
        return _fail(f"Server returned {resp.status_code}: {data.get('error', data)}")

    # Check 3 — the BoQ shape the frontend renders.
    groups = data.get("bill_of_quantities") or data.get("trades") if isinstance(data, dict) else None
    if not groups:
        return _fail(f"200 OK but no bill_of_quantities/trades in response. Keys: "
                     f"{list(data.keys()) if isinstance(data, dict) else type(data).__name__}")

    n_items = sum(len(g.get("items") or g.get("line_items") or []) for g in groups if isinstance(g, dict))
    print(f"  ✓ BoQ parsed: {len(groups)} trade groups, {n_items} line items")
    print(f"\n✅ PASS — /{endpoint.lstrip('/')} returned a usable, CORS-decorated BoQ in {elapsed:.1f}s.")
    return 0


def _fail(msg: str) -> int:
    print(f"\n❌ FAIL — {msg}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
