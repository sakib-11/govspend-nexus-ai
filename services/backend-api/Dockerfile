# =============================================================================
# Builder stage - install Python dependencies
# =============================================================================
FROM python:3.11-slim AS builder

# Avoid interactive prompts during package installation
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System build dependencies (needed for psycopg2/libpq)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create a virtual environment so we can cleanly copy only runtime artifacts
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies first (leverage Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# =============================================================================
# Runtime stage - minimal image for production
# =============================================================================
FROM python:3.11-slim

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install only the runtime system libraries needed by our wheels
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user to run the application
RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app

WORKDIR /app

# Copy the virtual environment (with installed deps) from the builder
COPY --from=builder --chown=app:app /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source code
COPY --chown=app:app main.py config.py ./
COPY --chown=app:app routes/ ./routes/
COPY --chown=app:app services/ ./services/
COPY --chown=app:app models/ ./models/

# Switch to non-root user
USER app

# Expose the port expected by docker-compose.prod.yml
EXPOSE 8008

# Healthcheck - verifies the Python app can at least import successfully.
# If main.py imports fail, the container is considered unhealthy.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import main, config" || exit 1

# Entrypoint - main.py is the uvicorn entry point (runs `python main.py`)
CMD ["python", "main.py"]
