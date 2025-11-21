#!/bin/bash
# Fix Kalshi Trading System - RSA Key & Deploy

set -e

echo "🔧 Fixing Kalshi Trading System..."

cd ~/Kalshi-Trading

# Backup .env
echo "📦 Backing up .env..."
cp .env .env.backup

# Create Python script to fix the private key
cat > /tmp/fix_kalshi_env.py << 'ENDPYTHON'
import re

print("Reading .env file...")
with open('/root/Kalshi-Trading/.env', 'r') as f:
    content = f.read()

# Find the private key section
key_pattern = r'(KALSHI_API_SECRET=)(-----BEGIN RSA PRIVATE KEY-----.*?-----END RSA PRIVATE KEY-----)'
match = re.search(key_pattern, content, re.DOTALL)

if match:
    prefix = match.group(1)
    key_multiline = match.group(2)

    # Replace actual newlines with \n
    key_singleline = key_multiline.replace('\n', '\\n')

    # Replace the multi-line key with single-line version
    new_content = content[:match.start()] + prefix + key_singleline + content[match.end():]

    # Write back
    with open('/root/Kalshi-Trading/.env', 'w') as f:
        f.write(new_content)

    print("✅ Fixed .env file - private key is now on one line")
else:
    print("❌ Could not find private key in .env")
    exit(1)
ENDPYTHON

# Run the fix
echo "🔑 Fixing RSA private key format..."
python3 /tmp/fix_kalshi_env.py

# Clean up
rm /tmp/fix_kalshi_env.py

# Pull latest code
echo "📥 Pulling latest code from GitHub..."
git pull origin main

# Rebuild and restart
echo "🐳 Rebuilding Docker containers..."
docker-compose down
docker-compose build --no-cache

echo "🚀 Starting all services..."
docker-compose up -d

# Wait a few seconds
sleep 5

echo ""
echo "📊 Container Status:"
docker-compose ps

echo ""
echo "📝 Recent logs from main app:"
docker logs kalshi_app --tail 20

echo ""
echo "✅ Done! Check logs above for any errors."
