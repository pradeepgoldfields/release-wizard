# ── Build stage ──────────────────────────────────────────────────────────────
FROM registry.access.redhat.com/ubi9/python-312 AS builder

WORKDIR /build

COPY requirements.txt requirements-prod.txt ./
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir --prefix=/install -r requirements-prod.txt

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM registry.access.redhat.com/ubi9/python-312

# Labels for OpenShift / container catalog
LABEL name="conduit" \
      version="0.1.0" \
      maintainer="your-team@example.com" \
      description="Conduit web application"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    HOST=0.0.0.0 \
    LOG_LEVEL=INFO

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY app/ app/
COPY wsgi.py gunicorn.conf.py ./

# UBI / OpenShift: non-root user required
# UID 1001 is the default non-root user in UBI images
USER 1001

EXPOSE 8080

# gunicorn.conf.py drives all worker/timeout/logging settings.
# Individual values can be overridden at runtime via GUNICORN_* env vars.
CMD ["gunicorn", "wsgi:app", "--config", "gunicorn.conf.py"]
