"""Gunicorn configuration for Conduit — used in container and local production runs.

Override any value via environment variable:  GUNICORN_<UPPER_KEY>=value
e.g.  GUNICORN_WORKERS=4

Reference: https://docs.gunicorn.org/en/stable/settings.html
"""

import multiprocessing
import os

# ── Binding ───────────────────────────────────────────────────────────────────
host = os.getenv("HOST", "0.0.0.0")
port = os.getenv("PORT", "8080")
bind = f"{host}:{port}"

# ── Workers ───────────────────────────────────────────────────────────────────
# gthread: each worker is a thread-pool — best for I/O-bound Flask apps.
# Formula: 2 × CPU cores + 1 is the standard recommendation; cap at 4 inside
# containers with limited CPU to avoid thrashing.
worker_class = "gthread"
workers = int(os.getenv("GUNICORN_WORKERS", min(2 * multiprocessing.cpu_count() + 1, 4)))
threads = int(os.getenv("GUNICORN_THREADS", 4))

# ── Timeouts ─────────────────────────────────────────────────────────────────
# timeout: worker silent timeout (kill if no response within N seconds)
# graceful_timeout: time given to finish in-flight requests on SIGTERM
# keepalive: seconds to wait for next request on a keep-alive connection
timeout = int(os.getenv("GUNICORN_TIMEOUT", 60))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", 30))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", 5))

# ── Memory leak prevention ────────────────────────────────────────────────────
# Workers are recycled after handling this many requests (±jitter) to prevent
# slow memory leaks from accumulating indefinitely.
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", 1000))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", 100))

# ── Logging ───────────────────────────────────────────────────────────────────
# Direct Gunicorn's own access + error logs to stdout/stderr so the container
# runtime (Docker / K8s) captures them.  Application logs go through the
# Python logging system configured in app/logging_config.py.
accesslog = "-"  # stdout
errorlog = "-"  # stderr
loglevel = os.getenv("LOG_LEVEL", "info").lower()

# Use the same JSON-ish access log format so log aggregators parse it easily.
access_log_format = (
    '{"time":"%(t)s","method":"%(m)s","path":"%(U)s%(q)s",'
    '"status":%(s)s,"bytes":%(B)s,"duration_ms":%(D)s,'
    '"referer":"%(f)s","agent":"%(a)s"}'
)

# ── Process naming ────────────────────────────────────────────────────────────
proc_name = "conduit"

# ── Socket backlog ────────────────────────────────────────────────────────────
# Number of pending connections the OS will queue before refusing new ones.
backlog = 2048

# ── Forwarded headers (behind ingress / load balancer) ───────────────────────
forwarded_allow_ips = os.getenv("GUNICORN_FORWARDED_ALLOW_IPS", "127.0.0.1")
secure_scheme_headers = {"X-Forwarded-Proto": "https"}
