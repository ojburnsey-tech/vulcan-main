# api/gunicorn.conf.py — SINGLE SOURCE OF TRUTH for the gunicorn runtime config.
#
# Why this file exists
# ────────────────────
# Before this file, the gunicorn worker timeout was declared in TWO places that
# disagreed with each other:
#   • Procfile (repo root):   --timeout 180
#   • api/Dockerfile  (CMD):  --timeout 300
# Whichever one Railway actually built from, the value was too low for the
# /process pipeline. A large NRM2 BoQ does, inside ONE request:
#   pdfplumber extract → Supabase quota gate → Supabase project gate →
#   Claude messages.create (max_tokens=16000, 60–150+s for big bills) →
#   JSON parse → schema validation → rate enrichment → Supabase auto-save.
# When that combined duration exceeded the worker --timeout, the gevent worker
# was killed (GreenletExit) AFTER Claude had already billed tokens but BEFORE
# Flask's after_request hook ran — so the browser got a connection reset / a
# response with no Access-Control-Allow-Origin header, which fetch() surfaces as
# an opaque "Network error". Every one of those failures cost real Claude money.
#
# Fix: both the Procfile and the Dockerfile now start gunicorn with
#   --config gunicorn.conf.py
# so there is ONE place that owns timeout/workers/worker_class, no matter which
# build path Railway uses (Dockerfile build vs Railpack/Procfile build).

import os
import sys
import time

# ── Bind ──────────────────────────────────────────────────────────────────────
# Railway injects $PORT and routes to whatever the container listens on. Default
# to 8080 (matches the Dockerfile EXPOSE) when PORT is unset, e.g. local runs.
bind = "0.0.0.0:" + os.environ.get("PORT", "8080")

# ── Workers ───────────────────────────────────────────────────────────────────
# gevent (async) workers so a single worker can serve other requests while one
# is blocked waiting on the long Claude HTTP call. 2 workers keeps memory modest
# on Railway's small instances while still surviving one worker restart.
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
worker_class = "gevent"

# ── Timeout ───────────────────────────────────────────────────────────────────
# 360s, deliberately chosen with comfortable headroom over the worst-case
# /process pipeline. Budget (worst case, large NRM2 BoQ):
#   pdfplumber + 2 Supabase gates ........ ~20s
#   Claude messages.create (max_tokens=16000, single attempt, no retries) ≤ 240s
#       (the Anthropic client in app.py is pinned to timeout=240, max_retries=0
#        precisely so a single attempt can never outlast this worker timeout and
#        can never silently retry-and-re-bill — see the comment at that call.)
#   usage persist + enrich + auto-save + jsonify .. ~10s
#   ──────────────────────────────────────────────
#   total ........................................ ~270s  →  90s of headroom < 360s
# Raising this above the Anthropic client timeout guarantees Flask gets the
# chance to build a proper CORS-decorated JSON response (success OR clean error)
# instead of being killed mid-request.
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "360"))

# graceful_timeout matches `timeout` so a worker told to shut down is given the
# same window to finish an in-flight BoQ before being force-killed.
graceful_timeout = timeout

# Surface gunicorn's own logs on stdout/stderr so Railway's log viewer captures
# them alongside app.logger output (this is what makes the worker_abort
# diagnostics below actually visible in Railway — a key part of the logging fix).
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOGLEVEL", "info")


# ── Diagnostic: log which request was in flight when a worker is killed ────────
# gevent worker kills can otherwise produce NO log line at all, making the
# timeout class of bug invisible in Railway's log viewer. gunicorn calls
# worker_abort() in the worker process right before a timed-out worker is
# aborted (SIGABRT). We use that window to record:
#   (1) the in-flight HTTP requests app.py is tracking (method + path + age), and
#   (2) the live greenlet stacks, which pinpoint the blocking call (the Claude
#       socket read, pdfplumber, a Supabase round trip, etc.).
# Every line is best-effort and wrapped so the hook itself can never crash the
# abort path.
def worker_abort(worker):
    try:
        worker.log.error(
            "WORKER_ABORT: gunicorn is killing worker pid=%s after exceeding "
            "timeout=%ss. Something in this worker blocked longer than the "
            "configured worker timeout.",
            worker.pid, timeout,
        )
    except Exception:
        pass

    # (1) In-flight requests, tracked by app.py's before/teardown_request hooks.
    try:
        import app as _app  # same module object already loaded into this worker
        inflight = getattr(_app, "_INFLIGHT_REQUESTS", None)
        if inflight:
            now = time.time()
            for key, info in list(inflight.items()):
                method, path, started = info
                worker.log.error(
                    "WORKER_ABORT in-flight request: %s %s running_for=%.1fs",
                    method, path, now - started,
                )
        else:
            worker.log.error("WORKER_ABORT: no in-flight request was registered.")
    except Exception as exc:  # never let diagnostics mask the abort
        worker.log.error("WORKER_ABORT: could not read in-flight requests: %s", exc)

    # (2) Greenlet stacks — show exactly what code was executing at abort time.
    try:
        import gc
        import traceback
        import greenlet
        dumped = 0
        for obj in gc.get_objects():
            if isinstance(obj, greenlet.greenlet) and getattr(obj, "gr_frame", None):
                stack = "".join(traceback.format_stack(obj.gr_frame))
                worker.log.error("WORKER_ABORT greenlet stack:\n%s", stack)
                dumped += 1
        if not dumped:
            worker.log.error(
                "WORKER_ABORT main-thread stack:\n%s",
                "".join(traceback.format_stack()),
            )
    except Exception as exc:
        worker.log.error("WORKER_ABORT: could not dump greenlet stacks: %s", exc)
