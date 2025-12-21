# Multi-stage build for production-ready backend
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Copy application code (includes entrypoint.sh)
COPY --chown=appuser:appuser . .

# Create logs directory and make entrypoint executable
RUN mkdir -p logs && \
    chown -R appuser:appuser logs && \
    chmod +x /app/entrypoint.sh

# Switch to non-root user
USER appuser

# Expose port (Railway sets PORT env var)
EXPOSE 8000

# Health check (using curl instead of requests for smaller image)
# Note: Railway handles health checks, but this is useful for Docker
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os, urllib.request; port=os.getenv('PORT', '8000'); urllib.request.urlopen(f'http://localhost:{port}/health')" || exit 1

# Use entrypoint script for reliable PORT handling
ENTRYPOINT ["/app/entrypoint.sh"]

