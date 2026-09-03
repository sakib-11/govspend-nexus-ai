FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies
COPY pyproject.toml poetry.lock* ./
COPY libs/ ./libs/
COPY services/detection_core/ ./services/detection_core/

# Install Python dependencies
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-root --no-interaction --no-ansi

EXPOSE 8003

CMD ["uvicorn", "services.detection_core.main:app", "--host", "0.0.0.0", "--port", "8003"]
