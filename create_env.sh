#!/bin/bash
# Secure Environment Setup Script
# This creates your .env file with all your API credentials

echo "🔐 Creating .env file with your API credentials..."

cat > .env << 'EOF'
# Kalshi API Configuration
KALSHI_API_KEY=1ffd0a3b-60f9-4bf9-a15d-23118289e99e
KALSHI_API_SECRET=-----BEGIN RSA PRIVATE KEY-----
MIIEogIBAAKCAQEArUEdsrAXNbuzRlhnxHo1acuzzI2fG3DV55D6P8eZ1iaHMBIx
2VahtQPUkEbEZElGmz7kK9iUevIR3qgVJ67sg6N5AwS9ZEaYtDbnz89SiGknbi+V
h//3FJzgXfKrSEffb4BJl85Z0I1VPcl++Su7abaVQAxI025W516Azh/KNAT2AZXF
PMVCUfDHx5e+2hu69OibTLjFm33yK33NjYj7RHQghPyugcYV/q6y2tAgvIIQl9x5
yOLU9bLLBmJbThySRroBuqDwVW4bKK9jIzXD6VmV18pUFpxzll1TGXzMV7iJ/5QN
QT94JN3PrHyMV/6cJgNxH5NbyeV7xbHKF5yXKwIDAQABAoIBABAjpbmUj8TwpEWk
TJ5P6BPf5vLiKnUq8LIunjE8zcbWNfezajNdz5iGL9H01ayl6s7hb+3psgM185Yz
QC0/LUch/k7arS3fKbB4AOYp4P1WFlc8VYiivoiMCJaX2X7VOyou4CwlC9bSo6Mq
1wotGbtCR+r8efhAKhZJhmQtL+/icynM47dD2387fR0OSKxW1vXET2l8BBeJImkg
ElPm1mTAOXTT9NaJEBwL/sWcZcV8ay7h6o7di4IHsvtalm5rJbGNtxlQvXhqUU2D
fVotOs/GxC3K7GwhjSZpDEAK5qH/r15EjwnocA0nyuLeLpmXBgdLb78SJkwMjJXB
3s0sCQkCgYEA2dGb8FJIRfrAisbXGPnrbL1EfFPFjDxJFfU8mtz/27G9js6PwNkT
S6YIqS/HxgjiVT3gLRM47ka6g0qoKCw9Mn79BLsX0kBnUFM3f+guef7DVnv2E5Te
N32zr+L2NZQTFQV0HIOaObc6Fzd8kagCOi8vDcgOU/qcY44BZgn2ljcCgYEAy5+5
huoWN+Gmudsp/p8WYOTatcWFwVZD6pWBgQVxVcSA4u8vbUgsU6E63XIJ7oUSDf0O
5jwjUq2pRzpXNI7KMX+473PdM6vIs5wyXlwBVbMAbF8C/4I0mXDBWAYLh5a5EO1h
V8AOv6Py+MvXCH4veQ5K43elAoSRUXwlcaNFjK0CgYAM7BKEP11qSWYC1akNIkaF
PPVDKvUdTLZJRzNBPLsxHWpRfo+osTgj1MXOw7bmWMCUrgcOpYVLHYcTIuq292jq
Bf6cuTzAjHGUols4i122fxa3msMOhlZolFyEosJYi2BWbuxkhKoxol0f43rQaVc4
fHQeLTAsa0G75kDO/OhUIQKBgElebfz8z7Cm7+o72+/Q5sFW9K9WUpGNQb9+y0Dv
8xxSR5Z9VHtt6/reN1WfR5DYBd9gdUPkG14pELuHe/CGGrinKr2s4+FAXnrJJyT0
xc5ZRyfFPFFQWx+Gj0PmObVLS7ebsN1raGUI7/1RhVOcFALscXNwotY7ahkQQHWn
vOGpAoGAGHQ/7ecf5/ksVNGKz044BveAyD9fPZS3OXbC+P6FvEFEu6dYWCoxBt/B
9jZHJxMVWKQl2xnSozN67Fw6gz3QfWcmHSI9ZPXEtpO51qkAgG4uDWfFA6FTiwzc
lefr0PW4yjz1z4Me8rVIHqk2rswEHvwsm+Pe5i52whLzlO786hM=
-----END RSA PRIVATE KEY-----
KALSHI_BASE_URL=https://demo-api.kalshi.co/trade-api/v2

# Telegram Alerts
TELEGRAM_BOT_TOKEN=8350248676:AAHt8_4QP7jRIY0s9ZtDLctMWrqeg1D3LpU
TELEGRAM_CHAT_ID=6277192025

# Telegram News Monitoring (BossBot)
TELEGRAM_API_ID=38508832
TELEGRAM_API_HASH=163fd4aef2ff289fb3b4fc1916695431
TELEGRAM_PHONE=+15512620848
TELEGRAM_NEWS_CHANNELS=BossBotOfficial

# News APIs
TWITTER_BEARER_TOKEN=AAAAAAAAAAAAAAAAAAAAAIwB5gEAAAAARBejR0yUOkNvqjuEtaqaf7rz8v0%3DTk7UKw3ZOMgxaJMAMyKzZGFfVtmr5g4MIGXRVBmNuFcrFDo3be
NEWSAPI_KEY=8c324584b267402786928d1cb9fef5d2
ALPHAVANTAGE_KEY=EPQXYVZ9I0437FDO

# Database
DB_USER=kalshi_trader
DB_PASSWORD=kalshi_secure_2024_prod_db_pass_9x7k2m
DB_NAME=kalshi_trading
DB_HOST=postgres
DB_PORT=5432
DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}

# Redis
REDIS_URL=redis://redis:6379/0

# Trading Configuration
TRADING_ENABLED=false
MAX_POSITION_SIZE_USD=50
MAX_PORTFOLIO_HEAT=0.20
MIN_EDGE_THRESHOLD=0.05
MAX_DAILY_LOSS=100

# Environment
ENVIRONMENT=demo
LOG_LEVEL=INFO
EOF

chmod 600 .env

echo "✅ .env file created with secure permissions (600)"
echo ""
echo "🔐 Security check:"
ls -l .env
echo ""
echo "✅ Your credentials are configured!"
echo "✅ Kalshi: DEMO mode (safe testing)"
echo "✅ BossBot: Telegram monitoring enabled"
echo "✅ Trading: DISABLED (paper trading mode)"
echo ""
