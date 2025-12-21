#!/bin/bash
# Production startup script for backend

set -e

echo "Starting School Management System Backend..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found!"
    echo "Please create .env file from .env.example"
    exit 1
fi

# Validate Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "ERROR: Python 3.11 or higher is required. Found: $python_version"
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Install/upgrade dependencies if requirements.txt changed
echo "Checking dependencies..."
pip install --no-cache-dir -q -r requirements.txt

# Run database migrations if needed (future feature)
# echo "Running database migrations..."
# alembic upgrade head

# Start the application
echo "Starting application server..."

# Use gunicorn in production, uvicorn in development
# PORT is set by Railway automatically, default to 8000
PORT=${PORT:-8000}

if [ "${DEBUG:-false}" = "true" ]; then
    echo "Starting in development mode with uvicorn..."
    exec uvicorn main:app --host 0.0.0.0 --port $PORT --reload
else
    echo "Starting in production mode with gunicorn..."
    # Calculate workers: (2 * CPU cores) + 1
    workers=$((2 * $(nproc) + 1))
    echo "Using $workers workers on port $PORT"
    exec gunicorn main:app \
        -w $workers \
        -k uvicorn.workers.UvicornWorker \
        --bind 0.0.0.0:$PORT \
        --timeout 120 \
        --keep-alive 2 \
        --access-logfile - \
        --error-logfile - \
        --log-level info
fi




