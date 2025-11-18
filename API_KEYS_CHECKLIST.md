# API Keys Setup Checklist

Use this checklist to track your API key setup progress.

## ✅ Required APIs (Must Have)

### 1. Kalshi API
- [ ] Created Kalshi account at https://kalshi.com
- [ ] Generated production API key
- [ ] Generated demo/test API key
- [ ] Funded account with starting capital ($500-2000)
- [ ] Tested API connection

**Demo Environment:**
```
KALSHI_API_KEY=demo_xxxxxxxx
KALSHI_API_SECRET=demo_xxxxxxxx
KALSHI_BASE_URL=https://demo-api.kalshi.co/trade-api/v2
```

**Production Environment:**
```
KALSHI_API_KEY=prod_xxxxxxxx
KALSHI_API_SECRET=prod_xxxxxxxx
KALSHI_BASE_URL=https://trading-api.kalshi.com/trade-api/v2
```

---

### 2. Telegram Bot
- [ ] Created bot with @BotFather
- [ ] Saved bot token
- [ ] Got chat ID from @userinfobot
- [ ] Started conversation with bot
- [ ] Tested bot connection

```
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

---

## 📰 Optional APIs (Highly Recommended)

### 3. Twitter API v2
- [ ] Applied for Twitter Developer account
- [ ] Application approved
- [ ] Created project and app
- [ ] Generated Bearer Token
- [ ] Verified token works

**Cost:** $100/month for Basic tier (required for real-time)

```
TWITTER_BEARER_TOKEN=AAAAAAAAAAAAAAAAAAAAAxxxxxxxxxxxxxxxxxx
```

**Skip if:** Budget constrained (can use NewsAPI only)

---

### 4. NewsAPI
- [ ] Registered at newsapi.org
- [ ] Received API key via email
- [ ] Tested API key

**Free tier:** 100 requests/day
**Paid tier:** $449/month for 25,000 requests/day

```
NEWSAPI_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Skip if:** Budget constrained (Twitter API is more valuable)

---

### 5. Alpha Vantage
- [ ] Registered at alphavantage.co
- [ ] Received API key via email
- [ ] Tested API key

**Free tier:** 25 requests/day
**Paid tier:** $50/month

```
ALPHAVANTAGE_KEY=XXXXXXXXXXXXXXXX
```

**Skip if:** Not using economic data strategies

---

## 🌤️ Weather Markets (Optional)

### 6. NOAA Weather API
- [ ] No API key needed - public API ✅
- [ ] Tested connection to api.weather.gov

**Note:** Free, no registration required!

---

## 🔄 Cross-Platform (Optional)

### 7. Polymarket
- [ ] Created Polymarket account
- [ ] Set up crypto wallet
- [ ] Funded account

**Skip if:** Not using cross-platform arbitrage

---

## 📊 Summary

### Minimum Setup (Start Trading)
- ✅ Kalshi API (REQUIRED)
- ✅ Telegram Bot (REQUIRED)
- ⚠️ At least ONE news source (Twitter OR NewsAPI)

**Estimated monthly cost:** $0-$100

### Recommended Setup
- ✅ Kalshi API
- ✅ Telegram Bot
- ✅ Twitter API ($100/month)
- ✅ NewsAPI (free tier)
- ✅ Alpha Vantage (free tier)

**Estimated monthly cost:** $100/month

### Full Setup
- ✅ All of the above
- ✅ Premium NewsAPI tier ($449/month)
- ✅ Alpha Vantage Premium ($50/month)

**Estimated monthly cost:** $600/month

---

## 🧪 Testing Your Setup

### 1. Test Kalshi Connection
```bash
cd kalshi_trading
docker-compose run --rm app python -c "
from src.api.kalshi_client import KalshiClient
import os
from dotenv import load_dotenv
load_dotenv()
client = KalshiClient(
    api_key=os.getenv('KALSHI_API_KEY'),
    api_secret=os.getenv('KALSHI_API_SECRET'),
    base_url=os.getenv('KALSHI_BASE_URL')
)
token = client.authenticate()
print(f'✅ Kalshi connected! Token: {token[:20]}...')
markets = client.get_markets(limit=5)
print(f'✅ Fetched {len(markets)} markets')
"
```

### 2. Test Telegram Bot
```bash
docker-compose run --rm app python -c "
from src.alerts.telegram_bot import TelegramAlerter
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
bot = TelegramAlerter(
    bot_token=os.getenv('TELEGRAM_BOT_TOKEN'),
    chat_id=os.getenv('TELEGRAM_CHAT_ID'),
    config={}
)
asyncio.run(bot.test_connection())
"
```

You should receive a test message on Telegram!

### 3. Test News APIs
```bash
# Test Twitter (if enabled)
docker-compose run --rm app python -c "
import tweepy
import os
from dotenv import load_dotenv
load_dotenv()
client = tweepy.Client(bearer_token=os.getenv('TWITTER_BEARER_TOKEN'))
user = client.get_user(username='Reuters')
print(f'✅ Twitter API working! Found user: {user.data.name}')
"

# Test NewsAPI (if enabled)
docker-compose run --rm app python -c "
from newsapi import NewsApiClient
import os
from dotenv import load_dotenv
load_dotenv()
newsapi = NewsApiClient(api_key=os.getenv('NEWSAPI_KEY'))
headlines = newsapi.get_top_headlines(country='us', page_size=5)
print(f'✅ NewsAPI working! Fetched {len(headlines[\"articles\"])} headlines')
"
```

---

## 🚨 Common Issues

### Issue: "Invalid API key"
**Solution:**
- Check for typos in .env file
- Verify key is for correct environment (demo vs production)
- Regenerate key if needed

### Issue: "Rate limit exceeded"
**Solution:**
- Using free tier? You hit daily limit
- Upgrade to paid tier
- Reduce polling frequency in config.yaml

### Issue: Telegram bot not responding
**Solution:**
- Verify bot token is correct
- Check chat ID is correct
- Make sure you started conversation with bot
- Bot must be running for messages to send

---

## 📝 Notes

- **Always start with DEMO environment** for Kalshi
- **Keep API keys secret** - never commit to git
- **Enable 2FA** on all accounts
- **Monitor usage** to avoid surprise bills
- **Test each API** before enabling in production

---

## ✅ Ready to Trade?

Once you have checked off:
- [x] Kalshi API (demo + production)
- [x] Telegram Bot
- [x] At least one news source
- [x] All tests passing

You're ready to proceed with [SETUP_GUIDE.md](SETUP_GUIDE.md)!
