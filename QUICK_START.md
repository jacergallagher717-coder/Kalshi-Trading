# Kalshi Trading System - Quick Start

**Get up and running in 15 minutes!**

## Prerequisites Checklist

Before you start, you MUST have:

- [ ] Kalshi account with API keys ([kalshi.com](https://kalshi.com))
- [ ] Telegram bot token (message @BotFather)
- [ ] Telegram chat ID (message @userinfobot)
- [ ] Server with Docker installed (2GB+ RAM)

**Optional but recommended:**
- [ ] Twitter API bearer token
- [ ] NewsAPI key
- [ ] Alpha Vantage API key

See [API_KEYS_CHECKLIST.md](API_KEYS_CHECKLIST.md) for detailed setup.

---

## 5-Minute Setup

### 1. Clone Repository
```bash
git clone <your-repo-url> kalshi_trading
cd kalshi_trading
```

### 2. Configure Environment
```bash
# Copy template
cp .env.example .env

# Edit with your keys
nano .env
```

**Minimum required in `.env`:**
```bash
# IMPORTANT: Use DEMO environment first!
KALSHI_API_KEY=your_demo_api_key_here
KALSHI_API_SECRET=your_demo_api_secret_here
KALSHI_BASE_URL=https://demo-api.kalshi.co/trade-api/v2

TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

DB_PASSWORD=strong_password_here

# CRITICAL: Keep false until tested!
TRADING_ENABLED=false
```

### 3. Start System
```bash
docker-compose up -d
```

### 4. Verify
```bash
# Check logs
docker-compose logs -f app

# You should see:
# ✅ "Kalshi Trading System initialized"
# ✅ "Telegram bot connected"

# Check Telegram - you should receive: "🤖 Kalshi Trading Bot connected successfully!"
```

---

## Testing Phase (24-48 hours)

### What to expect:

**Paper trading mode** (TRADING_ENABLED=false):
- News events will be detected ✅
- Signals will be generated ✅
- But NO actual trades will execute ✅

### Monitor:
```bash
# Watch for signals
docker-compose logs app | grep "signal"

# Watch for news events
docker-compose logs app | grep "news event"

# Check Telegram for alerts
```

### What you'll see in logs:
```
INFO - New economic_data event: CPI rises to 3.2%
INFO - Processing signal: BUY yes CPI-24JAN15-T320 @ 0.65
INFO - Trading disabled - signal not executed
```

This is GOOD! The system is working, just not executing trades yet.

---

## Enable Demo Trading (After 24+ hours of testing)

### 1. Update Config
```bash
nano .env
```

Change:
```bash
TRADING_ENABLED=true
```

### 2. Restart
```bash
docker-compose restart app
```

### 3. Monitor First Trades
You should now see in Telegram:
```
✅ Trade Executed

Market: CPI-24JAN15-T320
Side: YES
Quantity: 10 contracts
Price: $0.65
Edge: 8.2%
Confidence: 0.75

Reasoning: CPI came in at 3.2% vs expected 3.0%...
```

---

## Go Live (After successful demo trading)

### ⚠️ ONLY proceed if:
- [x] Demo trading was profitable for 7+ days
- [x] No critical errors in logs
- [x] You understand what the system is doing
- [x] You've tested Telegram alerts work
- [x] You're comfortable with the risk

### 1. Switch to Production
```bash
nano .env
```

Change:
```bash
KALSHI_API_KEY=your_PRODUCTION_api_key
KALSHI_API_SECRET=your_PRODUCTION_api_secret
KALSHI_BASE_URL=https://trading-api.kalshi.com/trade-api/v2
```

### 2. Start with Tiny Positions
```bash
nano config/config.yaml
```

```yaml
trading:
  enabled: true
  max_position_size_usd: 50  # START SMALL!
  max_daily_loss: 50
  max_trades_per_day: 10
```

### 3. Restart and Monitor CLOSELY
```bash
docker-compose restart app

# Watch every trade
docker-compose logs -f app
```

**Monitor for at least 7 days before increasing position sizes!**

---

## Monitoring

### Grafana Dashboard
http://your_server_ip:3000
- Username: `admin`
- Password: `admin` (change immediately!)

### Telegram Alerts
You'll receive:
- ✅ Trade executions
- 💰 P&L milestones
- 🔴 Circuit breaker trips
- 📊 Daily digest at 8 PM UTC

### Logs
```bash
# Real-time
docker-compose logs -f app

# Errors only
docker-compose logs app | grep ERROR

# Today's trades
docker-compose logs app | grep "Trade executed"
```

---

## Common Commands

```bash
# Start system
docker-compose up -d

# Stop system
docker-compose down

# Restart
docker-compose restart app

# View logs
docker-compose logs -f app

# Run tests
docker-compose run --rm app pytest tests/

# Access database
docker-compose exec postgres psql -U kalshi_trader -d kalshi_trading

# Check system status
docker-compose ps
```

---

## Emergency Stop

If something goes wrong:

```bash
# Stop all trading immediately
docker-compose stop app

# OR edit .env and set:
TRADING_ENABLED=false

# Then restart:
docker-compose restart app
```

The system will stop executing new trades but keep monitoring.

---

## Performance Expectations

### Week 1 (Demo)
- Goal: Validate system works
- Expected P&L: Not important (demo money)
- Key metric: No critical errors

### Week 2-3 (Live, small positions)
- Goal: Prove profitability
- Expected P&L: $10-50/week
- Key metric: Win rate >50%

### Month 2+ (Scaled up)
- Goal: Consistent returns
- Expected P&L: $50-100/day (with $2k capital)
- Key metric: Sharpe ratio >1.5

---

## Troubleshooting

### No trades executing?
1. Check `TRADING_ENABLED=true` in .env
2. Check Kalshi API credentials are correct (production, not demo)
3. Check sufficient balance in Kalshi account
4. Check logs: `docker-compose logs app | grep -i error`

### Telegram not working?
1. Verify bot token and chat ID in .env
2. Make sure you started chat with bot
3. Test: `docker-compose run --rm app python tests/test_telegram.py`

### System crashed?
1. Check logs: `docker-compose logs app`
2. Check disk space: `df -h`
3. Check memory: `free -h`
4. Restart: `docker-compose restart`

---

## Next Steps

✅ **You're running!** Now:

1. Read [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed instructions
2. Review [API_KEYS_CHECKLIST.md](API_KEYS_CHECKLIST.md) for optional APIs
3. Check Grafana dashboards regularly
4. Join community discussions
5. Contribute improvements!

---

## Support

- 📖 Full docs: [README.md](README.md)
- 🔧 Detailed setup: [SETUP_GUIDE.md](SETUP_GUIDE.md)
- 🔑 API setup: [API_KEYS_CHECKLIST.md](API_KEYS_CHECKLIST.md)
- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/kalshi-trading/issues)

---

**Remember:**
- Start with DEMO environment
- Use small positions initially
- Monitor closely
- Only trade what you can afford to lose

**Good luck! 🚀**
