@echo off
REM Production startup script for backend (Windows)

echo Starting School Management System Backend...

REM Check if .env file exists
if not exist .env (
    echo ERROR: .env file not found!
    echo Please create .env file from .env.example
    exit /b 1
)

REM Create logs directory if it doesn't exist
if not exist logs mkdir logs

REM Install/upgrade dependencies
echo Checking dependencies...
pip install --no-cache-dir -q -r requirements.txt

REM Start the application
echo Starting application server...

REM Use gunicorn in production, uvicorn in development
if "%DEBUG%"=="true" (
    echo Starting in development mode with uvicorn...
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
) else (
    echo Starting in production mode with gunicorn...
    gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout 120 --keep-alive 2 --access-logfile - --error-logfile - --log-level info
)






