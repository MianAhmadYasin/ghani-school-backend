# Production-ready backend
FROM python:3.11-slim

# Set environment variables for production
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Verify critical packages are installed
RUN python -c "import gunicorn; print('✅ gunicorn:', gunicorn.__version__)" && \
    python -c "import fastapi; print('✅ fastapi:', fastapi.__version__)" && \
    python -c "import uvicorn; print('✅ uvicorn:', uvicorn.__version__)" && \
    python -m gunicorn --version > /dev/null 2>&1 && echo "✅ gunicorn executable works"

# Create non-root user for security
RUN groupadd -r appuser && \
    useradd -r -g appuser -u 1000 appuser && \
    mkdir -p /app/logs && \
    chown -R appuser:appuser /app

# Copy application code (includes entrypoint.sh)
COPY --chown=appuser:appuser . .

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Switch to non-root user
USER appuser

# Expose port (Railway sets PORT env var)
EXPOSE 8000

# Health check - uses PORT from environment
# Railway handles health checks, but this is useful for Docker
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import os, urllib.request; port=os.getenv('PORT', '8000'); urllib.request.urlopen(f'http://localhost:{port}/health', timeout=5)" || exit 1

# Use entrypoint script for reliable PORT handling
ENTRYPOINT ["/app/entrypoint.sh"]

