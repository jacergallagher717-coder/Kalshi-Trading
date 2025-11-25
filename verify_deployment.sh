#!/bin/bash
# Verification script for frequency upgrade deployment

echo "========================================"
echo "🔍 VERIFYING FREQUENCY UPGRADE DEPLOYMENT"
echo "========================================"
echo ""

echo "1️⃣  Checking if containers are running..."
docker-compose ps
echo ""

echo "2️⃣  Checking for new thresholds (should see 0.03 and 0.6)..."
docker-compose logs --tail=200 app | grep -E "min_confidence|min_edge" | head -5
echo ""

echo "3️⃣  Checking for Weather Model..."
docker-compose logs --tail=200 app | grep -i "weather model" | head -3
echo ""

echo "4️⃣  Checking for Jobless Claims in consensus..."
docker-compose logs --tail=200 app | grep -i "JOBLESS_CLAIMS" | head -3
echo ""

echo "5️⃣  Checking scipy installation..."
docker-compose exec -T app pip list | grep scipy
echo ""

echo "6️⃣  Checking recent signals (last 10)..."
docker-compose logs --tail=500 app | grep -E "Generated signal|SIGNAL" | tail -10
echo ""

echo "7️⃣  Checking paper trades today..."
TRADES_TODAY=$(docker-compose logs app | grep "\[PAPER\]" | grep "$(date +%Y-%m-%d)" | wc -l)
echo "Paper trades today: $TRADES_TODAY"
echo ""

echo "========================================"
echo "✅ VERIFICATION COMPLETE"
echo "========================================"
echo ""
echo "Expected results:"
echo "  ✓ Thresholds: min_edge=0.03, min_confidence=0.6"
echo "  ✓ Weather model: initialized"
echo "  ✓ Jobless claims: in consensus data"
echo "  ✓ scipy: version 1.11.x"
echo "  ✓ Signals: 2-5x more than before"
echo ""
