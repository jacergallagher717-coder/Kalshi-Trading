# Kalshi Trading System - Complete Setup Guide

This guide will walk you through every step of setting up the Kalshi automated trading system, from API key generation to live trading.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [API Key Setup](#api-key-setup)
3. [Server Setup](#server-setup)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Testing](#testing)
7. [Deployment](#deployment)
8. [Monitoring](#monitoring)

---

## Prerequisites

### Required Knowledge

- Basic command line usage
- Understanding of Docker
- Familiarity with prediction markets
- Basic understanding of trading concepts

### Required Accounts

- Kalshi account
- Telegram account
- (Optional) Twitter Developer account
- (Optional) NewsAPI account
- (Optional) Alpha Vantage account

### Hardware Requirements

**Minimum:**
- 2 GB RAM
- 20 GB disk space
- Stable internet connection

**Recommended:**
- 4 GB RAM
- 50 GB SSD
- Low-latency internet connection

---

## API Key Setup

### 1. Kalshi API (REQUIRED)

**Step 1: Create Account**
1. Go to https://kalshi.com
2. Click "Sign Up"
3. Complete registration
4. **Fund account** with starting capital ($500-2000 recommended)

**Step 2: Generate API Keys**
1. Log in to Kalshi
2. Navigate to Settings → API
3. Click "Generate API Key"
4. **Save both API Key and API Secret securely**
5. Enable API trading permissions

**Step 3: Test Environment Setup**
1. Also create demo account at https://demo.kalshi.com
2. Generate demo API keys
3. **Always test with demo keys first!**

**Your keys will look like:**
```
API Key: kalshi_xxxxxxxxxxxxx
API Secret: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

### 2. Telegram Bot (REQUIRED)

**Step 1: Create Bot**
1. Open Telegram
2. Search for @BotFather
3. Send `/newbot` command
4. Choose a name: "Kalshi Trading Bot"
5. Choose username: "your_kalshi_bot"
6. **Save the bot token** (looks like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

**Step 2: Get Chat ID**
1. Search for @userinfobot on Telegram
2. Start chat with the bot
3. It will send your Chat ID
4. **Save your Chat ID** (looks like: `123456789`)

**Step 3: Start Your Bot**
1. Search for your bot by username
2. Click "Start" or send `/start`

---

### 3. Twitter API (OPTIONAL)

**Required for real-time news monitoring**

**Step 1: Apply for Developer Account**
1. Go to https://developer.twitter.com/en/portal/dashboard
2. Click "Sign up"
3. Choose "Hobbyist" → "Exploring the API"
4. Fill out application (describe: "Financial data analysis")
5. Wait for approval (usually 1-2 days)

**Step 2: Create Project**
1. Once approved, create new Project
2. Create new App
3. Go to "Keys and Tokens"
4. Generate "Bearer Token"
5. **Save the bearer token**

**Cost:** $100/month for Basic tier (required for real-time)

---

### 4. NewsAPI (OPTIONAL)

**Step 1: Register**
1. Go to https://newsapi.org/register
2. Fill out registration form
3. Verify email
4. **Save your API key**

**Limits:**
- Free: 100 requests/day
- Developer ($449/month): 25,000 requests/day

---

### 5. Alpha Vantage (OPTIONAL)

**Step 1: Get Free Key**
1. Go to https://www.alphavantage.co/support/#api-key
2. Enter email
3. **Save your API key** (sent via email)

**Limits:**
- Free: 25 requests/day
- Premium ($50/month): 75 requests/minute

---

## Server Setup

### Option A: DigitalOcean (Recommended for beginners)

**Step 1: Create Droplet**
1. Go to https://digitalocean.com
2. Click "Create" → "Droplets"
3. Choose:
   - **Image**: Ubuntu 22.04 LTS
   - **Plan**: Basic
   - **CPU**: Regular, $24/month (4GB RAM)
   - **Datacenter**: Closest to you
   - **Authentication**: SSH keys (recommended)

**Step 2: Access Server**
```bash
ssh root@your_server_ip
```

**Step 3: Install Docker**
```bash
# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt install docker-compose -y

# Verify installation
docker --version
docker-compose --version
```

---

### Option B: AWS EC2

**Step 1: Launch Instance**
1. Go to AWS Console → EC2
2. Click "Launch Instance"
3. Choose:
   - **AMI**: Ubuntu Server 22.04 LTS
   - **Instance Type**: t3.medium (4GB RAM)
   - **Storage**: 30GB gp3
   - **Security Group**: Allow SSH (22), HTTP (80), HTTPS (443)

**Step 2: Connect and Setup**
```bash
ssh -i your-key.pem ubuntu@your_instance_ip

# Install Docker (same as above)
```

---

## Installation

### Step 1: Clone Repository

```bash
cd /opt
git clone <your-repository-url> kalshi_trading
cd kalshi_trading
```

### Step 2: Set Environment Variables

```bash
# Copy template
cp .env.example .env

# Edit with your keys
nano .env
```

**Fill in your API keys:**

```bash
# Kalshi API (DEMO environment first!)
KALSHI_API_KEY=your_demo_api_key
KALSHI_API_SECRET=your_demo_api_secret
KALSHI_BASE_URL=https://demo-api.kalshi.co/trade-api/v2

# Telegram
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789

# Optional: Twitter, NewsAPI, Alpha Vantage
TWITTER_BEARER_TOKEN=your_twitter_bearer_token
NEWSAPI_KEY=your_newsapi_key
ALPHAVANTAGE_KEY=your_alphavantage_key

# Database
DB_PASSWORD=your_strong_password_here

# Trading (KEEP FALSE UNTIL READY!)
TRADING_ENABLED=false
```

Save with `Ctrl+O`, exit with `Ctrl+X`.

---

## Configuration

### Step 1: Review Trading Config

```bash
nano config/config.yaml
```

**Key settings to adjust:**

```yaml
trading:
  enabled: false  # IMPORTANT: Keep false during testing!
  max_position_size_usd: 50  # Start small!
  max_daily_loss: 100  # Conservative limit

strategies:
  speed_arbitrage:
    enabled: true  # Main strategy

  weather_model:
    enabled: false  # Disable until validated

  pattern_detection:
    enabled: false  # Disable until validated
```

### Step 2: Configure News Sources

```yaml
news_monitoring:
  twitter:
    enabled: false  # Set to true if you have Twitter API
    accounts:
      - FirstSquawk
      - BNONews
      - CNBCnow

  newsapi:
    enabled: true  # Use free tier

  weather:
    enabled: false  # Only if trading weather markets
```

---

## Testing

### Step 1: Build Containers

```bash
docker-compose build
```

### Step 2: Start Services

```bash
docker-compose up -d
```

### Step 3: Check Logs

```bash
# Watch application logs
docker-compose logs -f app

# You should see:
# "Kalshi Trading System initialized"
# "Telegram bot connected"
# "Starting news monitoring..."
```

### Step 4: Verify Telegram Connection

You should receive a message: "🤖 Kalshi Trading Bot connected successfully!"

If not:
```bash
# Check Telegram logs
docker-compose logs app | grep -i telegram

# Manually test
docker-compose exec app python -c "
from src.alerts.telegram_bot import TelegramAlerter
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
bot = TelegramAlerter(os.getenv('TELEGRAM_BOT_TOKEN'), os.getenv('TELEGRAM_CHAT_ID'), {})
asyncio.run(bot.test_connection())
"
```

### Step 5: Run Unit Tests

```bash
docker-compose run --rm app pytest tests/unit/ -v
```

All tests should pass ✅

### Step 6: Paper Trading (No Real Orders)

```bash
# In .env, ensure:
TRADING_ENABLED=false
```

**Let it run for 24-48 hours.** You'll see:
- News events detected
- Signals generated
- "Trading disabled - signal not executed" messages

**Review the signals in Telegram/logs to understand what the system is identifying.**

---

## Deployment

### Phase 1: Demo Trading (Week 1)

**Goal:** Test with Kalshi demo environment, no real money.

```bash
# .env settings:
KALSHI_BASE_URL=https://demo-api.kalshi.co/trade-api/v2
TRADING_ENABLED=true  # Now enable trading
```

**Restart:**
```bash
docker-compose restart app
```

**Monitor:**
- Check trades in Kalshi demo account
- Verify Telegram alerts work
- Review Grafana dashboards (http://your_server_ip:3000)

**Run for 7 days minimum.**

---

### Phase 2: Live Micro-Trading (Week 2)

**Goal:** Real money, but tiny positions.

```bash
# .env settings:
KALSHI_BASE_URL=https://trading-api.kalshi.com/trade-api/v2
KALSHI_API_KEY=your_production_api_key
KALSHI_API_SECRET=your_production_api_secret
TRADING_ENABLED=true
```

```yaml
# config.yaml settings:
trading:
  max_position_size_usd: 50  # Very small
  max_daily_loss: 50
  max_trades_per_day: 10
```

**Restart and monitor closely:**
```bash
docker-compose restart app
docker-compose logs -f app
```

**Daily checklist:**
- Check P&L on Telegram digest
- Review Grafana metrics
- Scan logs for errors
- Verify no circuit breaker trips

**Run for 7-14 days minimum.**

---

### Phase 3: Scale Up (Month 1+)

**Only if Phase 2 was profitable!**

```yaml
# Gradually increase limits:
trading:
  max_position_size_usd: 100  # Week 3
  max_position_size_usd: 200  # Week 4
  max_position_size_usd: 500  # Month 2
```

**Enable additional strategies only if backtested:**
```yaml
strategies:
  weather_model:
    enabled: true  # After backtesting validates
```

---

## Monitoring

### Grafana Dashboards

**Access:** http://your_server_ip:3000

**Default credentials:**
- Username: `admin`
- Password: `admin` (change immediately!)

**Key dashboards:**
1. **Trading Performance**: P&L, win rate, trades
2. **System Health**: API latency, errors, uptime
3. **Positions**: Open positions, exposure

---

### Telegram Monitoring

**Alerts you'll receive:**

- ✅ **Trade executed:** Immediate notification
- 💰 **P&L milestone:** When you hit $100, $250, $500 profit (or losses)
- 🔴 **Circuit breaker:** If system pauses due to losses
- 📊 **Daily digest:** Summary at 8 PM UTC
- ⚠️ **Errors:** Any system errors

---

### Log Monitoring

```bash
# Real-time logs
docker-compose logs -f app

# Error logs only
docker-compose logs app | grep ERROR

# Today's trades
docker-compose logs app | grep "Trade executed"

# Save logs to file
docker-compose logs app > logs/kalshi_$(date +%Y%m%d).log
```

---

## Maintenance

### Daily Tasks

1. Check Telegram digest
2. Review P&L
3. Scan for errors in logs
4. Verify system is running: `docker-compose ps`

### Weekly Tasks

1. Review Grafana dashboards
2. Check database size
3. Update performance metrics
4. Review and optimize strategies

### Monthly Tasks

1. Database backup: `docker-compose exec postgres pg_dump...`
2. Update dependencies: `docker-compose pull && docker-compose up -d`
3. Review and adjust risk limits
4. Backtest new strategies

---

## Troubleshooting

### System won't start

```bash
# Check all services
docker-compose ps

# Check specific service logs
docker-compose logs postgres
docker-compose logs redis
docker-compose logs app

# Restart everything
docker-compose down
docker-compose up -d
```

### No trades executing

**Check:**
1. `TRADING_ENABLED=true` in .env
2. Kalshi API credentials are correct
3. Sufficient balance in Kalshi account
4. Signals are being generated: `docker-compose logs app | grep signal`
5. No circuit breaker trip: `docker-compose logs app | grep circuit`

### Telegram not working

```bash
# Test manually
docker-compose exec app python tests/test_telegram.py

# Check token/chat ID
cat .env | grep TELEGRAM
```

### High latency (>30 seconds)

**Causes:**
- Server too slow (upgrade to 4GB RAM minimum)
- Network issues (use server close to US for Kalshi API)
- Too many strategies enabled (disable unused ones)

---

## Security Best Practices

1. **Never commit .env to git**
2. **Use strong database password**
3. **Limit API key permissions** (read/trade only, no withdrawals)
4. **Enable 2FA** on all accounts
5. **Regular backups** of database
6. **Monitor for unusual activity**
7. **Start with separate Kalshi account** (not your main funds)

---

## Next Steps

After successful setup:

1. ✅ Read [STRATEGY_GUIDE.md](docs/STRATEGY_GUIDE.md) to understand each strategy
2. ✅ Review [API_MANUAL.md](docs/API_MANUAL.md) for API reference
3. ✅ Join community discussions
4. ✅ Contribute improvements!

---

## Support

**Issues?**
- Check logs first
- Search GitHub issues
- Create new issue with logs attached

**Questions?**
- Read documentation
- Check FAQ
- Ask in discussions

---

**Good luck and trade responsibly! 🚀**
