#!/bin/bash
# Railway-optimized entrypoint script
# This script ensures the PORT environment variable is properly handled

set -e

# Enable production mode by default
export ENVIRONMENT=${ENVIRONMENT:-production}
export PYTHONUNBUFFERED=1

# ALWAYS print PORT for debugging (even in production for Railway)
echo "🔍 PORT environment variable check..."
echo "PORT env var value: '${PORT:-NOT_SET}'"
echo "PORT env var type: $(echo "${PORT}" | od -An -tx1 | head -1)"

# Get PORT from environment (Railway sets this automatically)
# Check if PORT is set and not the literal string "$PORT"
if [ -z "${PORT}" ] || [ "${PORT}" = "\$PORT" ] || [ "${PORT}" = '$PORT' ] || [ "${PORT}" = '${PORT}' ]; then
    echo "⚠️  PORT not set or invalid, using default: 8000"
    PORT=8000
else
    echo "✅ PORT found: $PORT"
    # Validate PORT is a number (remove any non-numeric characters)
    PORT_CLEANED=$(echo "$PORT" | tr -d '[:alpha:][:space:][$}{]')
    if [ -z "$PORT_CLEANED" ] || ! [[ "$PORT_CLEANED" =~ ^[0-9]+$ ]]; then
        echo "❌ ERROR: PORT must be a number, got invalid value: '$PORT'. Using default: 8000"
        PORT=8000
    else
        PORT=$PORT_CLEANED
    fi
fi

# Ensure PORT is within valid range
if [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
    echo "❌ ERROR: PORT out of range (1-65535), got: $PORT. Using default: 8000"
    PORT=8000
fi

# Export PORT so gunicorn can use it
export PORT

echo "🚀 Starting School Management System Backend..."
echo "📡 Final PORT value: $PORT"
echo "🌍 Environment: ${ENVIRONMENT}"

# Build bind address with validated PORT number
BIND_ADDRESS="0.0.0.0:$PORT"

# Verify BIND_ADDRESS is valid before starting
if [[ ! "$BIND_ADDRESS" =~ ^0\.0\.0\.0:[0-9]+$ ]]; then
    echo "❌ FATAL: Invalid bind address: $BIND_ADDRESS"
    exit 1
fi

# Calculate optimal worker count (Railway typically provides 1-2 vCPUs)
WORKERS=${GUNICORN_WORKERS:-4}

# Set log level based on environment
LOG_LEVEL=${LOG_LEVEL:-info}
if [ "${ENVIRONMENT}" = "production" ]; then
    LOG_LEVEL="info"
fi

# Start Gunicorn with Uvicorn workers
# Railway automatically sets PORT, so we use it directly
# Use python -m gunicorn to avoid PATH issues
# exec replaces the shell process, allowing proper signal handling
echo "🔗 Binding to: $BIND_ADDRESS with $WORKERS workers"

exec python -m gunicorn main:app \
    -w "$WORKERS" \
    -k uvicorn.workers.UvicornWorker \
    --bind "$BIND_ADDRESS" \
    --timeout 120 \
    --graceful-timeout 30 \
    --keep-alive 2 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --access-logfile - \
    --error-logfile - \
    --log-level "$LOG_LEVEL" \
    --capture-output \
    --enable-stdio-inheritance
