#!/bin/bash
# Startup script for Kalshi Trading System

set -e

echo "🚀 Starting Kalshi Trading System..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please copy .env.example to .env and configure your API keys."
    exit 1
fi

# Check if database is ready
echo "⏳ Waiting for database..."
until docker-compose exec -T postgres pg_isready -U kalshi_trader; do
    sleep 2
done
echo "✅ Database ready"

# Run database migrations
echo "🔄 Running database migrations..."
python -m alembic upgrade head || echo "⚠️ Migrations not configured yet"

# Start the application
echo "🎯 Starting main application..."
python main.py
