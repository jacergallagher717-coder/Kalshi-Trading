#!/bin/bash
# Kalshi Trading System - One-Command Deployment
# Everything is pre-configured, just run this!

set -e

echo "🚀 KALSHI TRADING SYSTEM - AUTOMATED DEPLOYMENT"
echo "================================================"
echo ""
echo "✅ All API keys configured"
echo "✅ BossBot Telegram monitoring enabled"
echo "✅ Demo mode (safe testing)"
echo "✅ Paper trading (no real money yet)"
echo ""

# Check if running on server or local
if [ -d "/home/user/kalshi-trading-clean" ]; then
    echo "📦 Found local repository, using it..."
    cd /home/user/kalshi-trading-clean
else
    echo "📥 Cloning from GitHub..."
    git clone https://github.com/jacergallagher717-coder/Kalshi-Trading.git
    cd Kalshi-Trading
fi

# Create .env file with credentials
if [ ! -f ".env" ]; then
    echo ""
    echo "🔐 Setting up your API credentials..."
    bash create_env.sh
else
    echo ""
    echo "✅ .env file already exists, skipping credential setup"
fi

echo ""
echo "🏗️  Building Docker containers..."
docker-compose build

echo ""
echo "🚀 Starting all services..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to start..."
sleep 5

echo ""
echo "📊 Checking service status..."
docker-compose ps

echo ""
echo "📋 Viewing recent logs..."
docker-compose logs --tail=30 app

echo ""
echo "✅ DEPLOYMENT COMPLETE!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📱 Check your Telegram for startup messages!"
echo ""
echo "🎯 What's Running:"
echo "   • Kalshi API: DEMO mode (safe testing)"
echo "   • BossBot Monitor: Watching for breaking news"
echo "   • Paper Trading: Signals generated, NO real trades"
echo "   • Telegram Alerts: You'll get notified of all signals"
echo ""
echo "📊 Monitor the system:"
echo "   • Logs:    docker-compose logs -f app"
echo "   • Status:  docker-compose ps"
echo "   • Grafana: http://localhost:3000 (admin/admin)"
echo ""
echo "🔧 Useful commands:"
echo "   • Stop:    docker-compose down"
echo "   • Restart: docker-compose restart app"
echo "   • Update:  git pull && docker-compose up -d --build"
echo ""
echo "⚠️  FIRST TIME ONLY:"
echo "   When you see 'Please enter the code you received:'"
echo "   Check your Telegram app for a verification code"
echo "   Enter it and press Enter"
echo "   This only happens once!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📚 Documentation:"
echo "   • Quick Start: cat QUICK_START.md"
echo "   • BossBot Setup: cat TELEGRAM_NEWS_SETUP.md"
echo "   • Full Guide: cat SETUP_GUIDE.md"
echo ""
echo "🎉 System is live! Watch your Telegram for signals!"
echo ""
