FROM python:3.11-slim AS base

# Security: non-root user
RUN groupadd -r audit && useradd -r -g audit -u 1000 audit

WORKDIR /app

# System dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Python dependencies (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Own everything to non-root user
RUN chown -R audit:audit /app

USER audit

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8010/health || exit 1

EXPOSE 8010

CMD ["python", "main.py"]
