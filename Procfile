# Single source of truth for gunicorn tuning is api/gunicorn.conf.py (timeout,
# workers, worker_class, bind, worker_abort diagnostics). This Procfile is only
# used if Railway builds via Railpack/Nixpacks from the repo root instead of the
# api/Dockerfile; either way the same 360s worker timeout now applies, so the
# previous 180-vs-300 drift that killed /process mid-request can't recur.
# --chdir api puts app.py on the path; --config points at the shared file.
web: gunicorn app:app --chdir api --config api/gunicorn.conf.py
