FROM python:3.11.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# Start command delegates ALL runtime tuning (timeout, workers, worker_class,
# bind, worker_abort diagnostics) to gunicorn.conf.py — the single source of
# truth shared with the repo-root Procfile. Do NOT re-add --timeout/--workers
# flags here; that is exactly the drift (Dockerfile=300 vs Procfile=180) that let
# the worker be killed mid-/process after Claude had already billed tokens.
# WORKDIR is /app and `COPY . .` puts gunicorn.conf.py at /app/gunicorn.conf.py,
# which gunicorn loads via --config below.
CMD ["gunicorn", "app:app", "--config", "gunicorn.conf.py"]
