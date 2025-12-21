# Railway Setup Script for PowerShell
# This script helps set up environment variables for Railway deployment

Write-Host "🚂 Railway Deployment Setup" -ForegroundColor Cyan
Write-Host "==========================" -ForegroundColor Cyan
Write-Host ""

# Check if Railway CLI is installed
try {
    railway --version | Out-Null
} catch {
    Write-Host "⚠️  Railway CLI not found. Installing..." -ForegroundColor Yellow
    npm install -g @railway/cli
}

Write-Host "📋 Setting up environment variables..." -ForegroundColor Green
Write-Host ""

# Get Supabase URL
$SUPABASE_URL = Read-Host "Supabase URL (https://xxx.supabase.co)"
railway variables set SUPABASE_URL="$SUPABASE_URL"

# Get Supabase Key
$SUPABASE_KEY = Read-Host "Supabase Anon Key"
railway variables set SUPABASE_KEY="$SUPABASE_KEY"

# Get Supabase Service Key
$SUPABASE_SERVICE_KEY = Read-Host "Supabase Service Role Key"
railway variables set SUPABASE_SERVICE_KEY="$SUPABASE_SERVICE_KEY"

# Generate JWT Secret
Write-Host ""
Write-Host "Generating JWT secret..." -ForegroundColor Yellow
$JWT_SECRET = python -c "import secrets; print(secrets.token_urlsafe(32))"
railway variables set JWT_SECRET_KEY="$JWT_SECRET"
Write-Host "✅ JWT secret generated and set" -ForegroundColor Green

# Get Frontend URL
$FRONTEND_URL = Read-Host "Frontend URL (https://your-frontend.com)"
railway variables set FRONTEND_URL="$FRONTEND_URL"

# Set other variables
railway variables set DEBUG=false
railway variables set ENVIRONMENT=production
railway variables set APP_NAME="School Management System"
railway variables set APP_VERSION="1.0.0"

Write-Host ""
Write-Host "✅ Environment variables set!" -ForegroundColor Green
Write-Host ""
Write-Host "🚀 Ready to deploy! Run: railway up" -ForegroundColor Cyan
Write-Host ""



