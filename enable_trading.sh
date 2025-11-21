#!/bin/bash
# Enable Paper Trading - Pull latest config and restart

set -e

echo "🚀 Enabling Paper Trading on Kalshi Demo API..."
echo ""

cd ~/Kalshi-Trading

# Pull latest code with updated config
echo "📥 Pulling latest config from GitHub..."
git pull origin main

# Restart only the app container (faster than full rebuild)
echo "🔄 Restarting app container..."
docker-compose restart app

# Wait for app to start
echo "⏳ Waiting for app to start..."
sleep 5

# Check if trading is enabled
echo ""
echo "📊 Trading Status:"
docker logs kalshi_app --tail 50 | grep -i "trading enabled" || echo "Checking logs..."

echo ""
echo "📝 Recent App Logs:"
docker logs kalshi_app --tail 20

echo ""
echo "✅ Done! Paper trading should now be enabled."
echo "💡 Monitor logs with: docker logs -f kalshi_app"
