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
COPY wsgi.py .

# UBI / OpenShift: non-root user required
# UID 1001 is the default non-root user in UBI images
USER 1001

EXPOSE 8080

# Use gunicorn for production; workers tuned for containerised single-pod use
CMD ["gunicorn", "wsgi:app", \
     "--bind", "0.0.0.0:8080", \
     "--workers", "2", \
     "--threads", "4", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
