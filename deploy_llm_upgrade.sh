#!/bin/bash
# Deploy LLM Upgrade - Add qualitative news analysis with Claude

set -e

echo "🤖 Deploying LLM-Enhanced Trading System"
echo ""
echo "This upgrade adds Claude Haiku to analyze qualitative news that regex can't parse."
echo "Example: 'Fed's Williams says inflation progress has stalled' → detects rate cut impact"
echo ""

# Check if we're on the server
if [ ! -f ~/Kalshi-Trading/.env ]; then
    echo "❌ Error: Run this on your server (root@kalshi-trading-bot)"
    echo "Usage: cd ~/Kalshi-Trading && ./deploy_llm_upgrade.sh"
    exit 1
fi

cd ~/Kalshi-Trading

# Step 1: Check for Anthropic API key
echo "📝 Checking Anthropic API configuration..."
if grep -q "ANTHROPIC_API_KEY" .env; then
    echo "✅ ANTHROPIC_API_KEY already configured"
else
    echo ""
    echo "⚠️  ANTHROPIC_API_KEY not found in .env"
    echo ""
    echo "To enable LLM analysis, you need a Claude API key:"
    echo "1. Go to: https://console.anthropic.com/"
    echo "2. Create an account and get an API key"
    echo "3. Add to .env file:"
    echo ""
    echo "   ANTHROPIC_API_KEY=sk-ant-api03-xxxxx"
    echo ""
    read -p "Do you have an Anthropic API key to add now? (y/n): " has_key

    if [ "$has_key" = "y" ]; then
        read -p "Enter your Anthropic API key: " api_key
        echo "" >> .env
        echo "# LLM Analysis (Claude Haiku for qualitative news)" >> .env
        echo "ANTHROPIC_API_KEY=$api_key" >> .env
        echo "✅ API key added to .env"
    else
        echo ""
        echo "ℹ️  Continuing without LLM - only regex-based analysis will work"
        echo "   You can add the API key later to .env and restart containers"
    fi
fi

echo ""
echo "📥 Pulling latest code from GitHub..."
git pull origin main

echo ""
echo "🔨 Rebuilding containers with LLM support..."
docker-compose down
docker-compose build --no-cache app
docker-compose up -d

echo ""
echo "⏳ Waiting for system to start..."
sleep 10

echo ""
echo "📊 Checking system status..."
docker logs kalshi_app --tail 30 | grep -E "LLM|Trading enabled|initialized"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🔍 The system now uses a 2-layer approach:"
echo "   1. FAST: Regex extracts 'CPI at 3.2%' → instant trade signal"
echo "   2. SMART: LLM interprets 'inflation stalled' → 2-3 second analysis"
echo ""
echo "💡 Monitor LLM signals with:"
echo "   docker logs -f kalshi_app | grep -i 'llm'"
echo ""
echo "💰 Cost estimate: ~$0.01 per news item analyzed by LLM (uses Haiku)"
echo "   Only triggered when regex finds nothing, so mostly free!"
