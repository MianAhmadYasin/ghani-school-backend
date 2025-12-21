#!/bin/bash
# Railway Setup Script
# This script helps set up environment variables for Railway deployment

echo "🚂 Railway Deployment Setup"
echo "=========================="
echo ""

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "⚠️  Railway CLI not found. Installing..."
    npm install -g @railway/cli
fi

echo "📋 Setting up environment variables..."
echo ""
echo "Please provide the following information:"
echo ""

# Get Supabase URL
read -p "Supabase URL (https://xxx.supabase.co): " SUPABASE_URL
railway variables set SUPABASE_URL="$SUPABASE_URL"

# Get Supabase Key
read -p "Supabase Anon Key: " SUPABASE_KEY
railway variables set SUPABASE_KEY="$SUPABASE_KEY"

# Get Supabase Service Key
read -p "Supabase Service Role Key: " SUPABASE_SERVICE_KEY
railway variables set SUPABASE_SERVICE_KEY="$SUPABASE_SERVICE_KEY"

# Generate JWT Secret
echo ""
echo "Generating JWT secret..."
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
railway variables set JWT_SECRET_KEY="$JWT_SECRET"
echo "✅ JWT secret generated and set"

# Get Frontend URL
read -p "Frontend URL (https://your-frontend.com): " FRONTEND_URL
railway variables set FRONTEND_URL="$FRONTEND_URL"

# Set other variables
railway variables set DEBUG=false
railway variables set ENVIRONMENT=production
railway variables set APP_NAME="School Management System"
railway variables set APP_VERSION="1.0.0"

echo ""
echo "✅ Environment variables set!"
echo ""
echo "🚀 Ready to deploy! Run: railway up"
echo ""



