#!/bin/bash
# Railway-optimized entrypoint script
# This script ensures the PORT environment variable is properly handled

set -e

# Debug: Print all environment variables related to PORT
echo "🔍 Debugging PORT environment variable..."
echo "PORT env var: '${PORT:-NOT_SET}'"
env | grep -i port || echo "No PORT-related env vars found"

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
echo "📡 Using Port: $PORT"
echo "🌍 Environment: ${ENVIRONMENT:-production}"

# Start Gunicorn with Uvicorn workers
# Railway automatically sets PORT, so we use it directly
# Use python -m gunicorn to avoid PATH issues
# Build bind address with validated PORT number (use direct variable, not expansion)
BIND_ADDRESS="0.0.0.0:$PORT"
echo "🔗 Binding to: $BIND_ADDRESS"

# Verify BIND_ADDRESS is valid before starting
if [[ ! "$BIND_ADDRESS" =~ ^0\.0\.0\.0:[0-9]+$ ]]; then
    echo "❌ FATAL: Invalid bind address: $BIND_ADDRESS"
    exit 1
fi

exec python -m gunicorn main:app \
    -w 4 \
    -k uvicorn.workers.UvicornWorker \
    --bind "$BIND_ADDRESS" \
    --timeout 120 \
    --keep-alive 2 \
    --access-logfile - \
    --error-logfile - \
    --log-level info

