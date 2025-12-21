#!/bin/bash
# Railway-optimized entrypoint script
# This script ensures the PORT environment variable is properly handled

set -e

# Get PORT from environment (Railway sets this automatically)
PORT=${PORT:-8000}

# Export PORT so gunicorn can use it
export PORT

echo "🚀 Starting School Management System Backend..."
echo "📡 Port: $PORT"
echo "🌍 Environment: ${ENVIRONMENT:-production}"

# Start Gunicorn with Uvicorn workers
# Railway automatically sets PORT, so we use it directly
exec gunicorn main:app \
    -w 4 \
    -k uvicorn.workers.UvicornWorker \
    --bind "0.0.0.0:${PORT}" \
    --timeout 120 \
    --keep-alive 2 \
    --access-logfile - \
    --error-logfile - \
    --log-level info

