# Gorgon API Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt psycopg2-binary

# Copy application code
COPY src/ ./src/
COPY migrations/ ./migrations/
COPY workflows/ ./workflows/
COPY pyproject.toml .

# Install the package
RUN pip install --no-cache-dir -e .

# Create non-root user
RUN useradd --create-home --shell /bin/bash gorgon
USER gorgon

# Expose API port
ENV PORT=8000
ENV HOST=0.0.0.0
EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run the API
CMD uvicorn test_ai.api:app --host ${HOST} --port ${PORT}
