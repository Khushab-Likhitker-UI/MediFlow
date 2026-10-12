# ==============================================================================
# Smart Health Sentinel (MediFlow) — Production Cloud Run Dockerfile
# Multi-stage / lightweight Debian-based Python 3.11 image
# Non-root execution, Cloud Run injected PORT handling, healthcheck probe
# ==============================================================================

FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered standard out/err
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    APP_HOME=/app

WORKDIR ${APP_HOME}

# Install essential system dependencies if needed and clean apt cache
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (leverages Docker layer caching)
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY backend/ ./

# Create an unprivileged non-root user and group
RUN groupadd -g 10001 sentinel && \
    useradd -u 10001 -g sentinel -s /bin/sh -M -d /app sentinel && \
    chown -R sentinel:sentinel ${APP_HOME}

# Switch to non-root user
USER sentinel:sentinel

# Cloud Run defaults to port 8080
EXPOSE 8080

# In-container healthcheck probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, os; port = os.environ.get('PORT', '8080'); urllib.request.urlopen(f'http://127.0.0.1:{port}/api/v1/health')" || exit 1

# Start Uvicorn via exec to ensure SIGTERM / graceful shutdown signals are handled by PID 1
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --no-access-log"]
