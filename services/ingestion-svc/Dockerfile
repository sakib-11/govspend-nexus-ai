FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    poppler-utils \
    libmagic-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependencies
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry install --no-root

# Copy application
COPY . .

# Create directories
RUN mkdir -p /tmp/uploads /tmp/processed

# Run the service
CMD ["poetry", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
