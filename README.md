# Kalshi Automated Trading System

A production-ready automated trading system for Kalshi prediction markets that identifies and exploits pricing inefficiencies through real-time news monitoring, statistical modeling, and algorithmic trading strategies.

## 🎯 Features

- **Real-Time News Monitoring**: Multi-source news aggregation (Twitter, NewsAPI, Alpha Vantage, NOAA weather)
- **Speed Arbitrage**: React to news before markets fully adjust
- **Weather Modeling**: Compare NOAA forecasts to market prices
- **Pattern Detection**: Exploit behavioral biases (recency bias, favorite-longshot, low liquidity)
- **Risk Management**: Kelly criterion position sizing, circuit breakers, stop losses
- **Telegram Alerts**: Real-time notifications for trades, P&L, and errors
- **Prometheus Metrics**: Comprehensive monitoring and observability
- **Backtesting Framework**: Validate strategies on historical data

## 📋 Prerequisites

### Required API Keys

1. **Kalshi Account** (REQUIRED)
   - Sign up at [kalshi.com](https://kalshi.com)
   - Generate API credentials at [kalshi.com/settings/api](https://kalshi.com/settings/api)
   - **Start with demo environment first!**

2. **Telegram Bot** (REQUIRED for alerts)
   - Message @BotFather on Telegram
   - Create new bot with `/newbot`
   - Get chat ID from @userinfobot

3. **News APIs** (OPTIONAL but recommended)
   - **Twitter API v2**: [developer.twitter.com](https://developer.twitter.com) ($100/month for real-time)
   - **NewsAPI**: [newsapi.org](https://newsapi.org) (free tier available)
   - **Alpha Vantage**: [alphavantage.co](https://www.alphavantage.co/support/#api-key) (free tier available)

### Infrastructure

- **Server**: VPS with 2GB+ RAM (DigitalOcean, AWS EC2, etc.)
- **Docker & Docker Compose**: For containerized deployment
- **PostgreSQL 15+**: For data storage
- **Redis**: For task queue

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd kalshi_trading

# Copy environment template
cp .env.example .env
```

### 2. Configure Environment Variables

Edit `.env` and add your API keys:

```bash
# Kalshi (REQUIRED)
KALSHI_API_KEY=your_kalshi_api_key
KALSHI_API_SECRET=your_kalshi_api_secret
KALSHI_BASE_URL=https://demo-api.kalshi.co/trade-api/v2  # Use demo first!

# Telegram (REQUIRED)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id

# News APIs (OPTIONAL)
TWITTER_BEARER_TOKEN=your_twitter_bearer_token
NEWSAPI_KEY=your_newsapi_key
ALPHAVANTAGE_KEY=your_alphavantage_key

# Database
DB_PASSWORD=your_secure_password
```

### 3. Start the System

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f app

# Check status
docker-compose ps
```

### 4. Verify Setup

1. **Check Telegram**: You should receive a "System started" message
2. **Access Grafana**: Open http://localhost:3000 (admin/admin)
3. **Check logs**: `docker-compose logs -f app`

## ⚙️ Configuration

### Trading Configuration (`config/config.yaml`)

```yaml
trading:
  enabled: false  # SET TO TRUE WHEN READY FOR LIVE TRADING
  max_position_size_usd: 500
  max_portfolio_heat: 0.20  # 20% of capital max
  min_edge_threshold: 0.05  # 5% edge required
  max_daily_loss: 1000

strategies:
  speed_arbitrage:
    enabled: true
    min_confidence: 0.70

  weather_model:
    enabled: true
    min_edge: 0.08

  pattern_detection:
    enabled: true
```

### Risk Management

- **Position Sizing**: Fractional Kelly Criterion (default 0.25)
- **Stop Loss**: 30% of position
- **Circuit Breaker**: Pause after 3 consecutive losses
- **Daily Loss Limit**: Configurable (default $1000)
- **Rate Limiting**: Max trades per hour/day

## 📊 Monitoring

### Grafana Dashboards

Access at http://localhost:3000:

- Real-time P&L tracking
- Trade frequency and success rate
- Latency distribution
- Position exposure
- API health

### Telegram Alerts

Real-time notifications for:
- ✅ Trade executions
- 💰 P&L milestones
- ⚠️ Errors and circuit breakers
- 📈 Daily performance digest

### Prometheus Metrics

Available at http://localhost:9091:

- `kalshi_trades_total`: Total trades executed
- `kalshi_trade_pnl_dollars`: Trade P&L distribution
- `kalshi_signal_latency_seconds`: Signal generation latency
- `kalshi_open_positions`: Current open positions
- `kalshi_portfolio_value_dollars`: Portfolio value

## 🧪 Testing

### Run Unit Tests

```bash
# Run all tests
docker-compose run --rm app pytest tests/

# Run with coverage
docker-compose run --rm app pytest --cov=src tests/

# Run specific test file
docker-compose run --rm app pytest tests/unit/test_kalshi_client.py -v
```

### Backtesting

```bash
# Run backtest on historical data
python backtest/backtester.py --data data/historical_markets.csv --strategy speed_arb

# Export results
python backtest/backtester.py --data data/historical_markets.csv --output results/backtest_2024.csv
```

## 📈 Performance Expectations

After 1 month of operation (starting with $1-2k capital):

- **Win Rate**: >55%
- **Sharpe Ratio**: >1.5
- **Average Latency**: <15 seconds (news to execution)
- **Daily Profit Target**: $50-$100
- **Max Drawdown**: <15%

## 🛡️ Safety Features

### Before Live Trading

1. **Paper Trading**: Start with `TRADING_ENABLED=false`
2. **Demo Environment**: Use `https://demo-api.kalshi.co` first
3. **Small Positions**: Set `max_position_size_usd: 50` initially
4. **Monitor Closely**: Check Telegram alerts frequently
5. **Review Logs**: Ensure no errors in first 48 hours

### Circuit Breakers

- Automatic pause after 3 consecutive losses
- Daily loss limit enforcement
- Position size limits
- Cooldown periods after losses

## 📁 Project Structure

```
kalshi_trading/
├── src/
│   ├── api/              # Kalshi API client
│   ├── monitors/         # News monitoring
│   ├── edge_detection/   # Trading strategies
│   ├── execution/        # Trade executor
│   ├── database/         # ORM models
│   ├── alerts/           # Telegram bot
│   └── monitoring/       # Prometheus metrics
├── backtest/             # Backtesting framework
├── tests/                # Unit & integration tests
├── config/               # Configuration files
├── monitoring/           # Grafana/Prometheus configs
├── docker-compose.yml    # Docker orchestration
└── main.py              # Main application
```

## 🔧 Troubleshooting

### Common Issues

**1. Telegram bot not working**
```bash
# Test connection
docker-compose run --rm app python -c "
from src.alerts.telegram_bot import TelegramAlerter
import asyncio
import os
bot = TelegramAlerter(os.getenv('TELEGRAM_BOT_TOKEN'), os.getenv('TELEGRAM_CHAT_ID'), {})
asyncio.run(bot.test_connection())
"
```

**2. Database connection errors**
```bash
# Check PostgreSQL
docker-compose ps postgres

# View PostgreSQL logs
docker-compose logs postgres
```

**3. No trades executing**
- Check `TRADING_ENABLED=true` in .env
- Verify Kalshi API credentials
- Check logs for signal generation: `docker-compose logs app | grep "signal"`

## 📚 Documentation

- [SETUP_GUIDE.md](docs/SETUP_GUIDE.md) - Detailed setup instructions
- [API_MANUAL.md](docs/API_MANUAL.md) - API reference
- [STRATEGY_GUIDE.md](docs/STRATEGY_GUIDE.md) - Trading strategies explained
- [DEPLOYMENT.md](docs/DEPLOYMENT.md) - Production deployment guide

## ⚠️ Disclaimer

This system involves real money trading in prediction markets. **Use at your own risk.**

- Start with small amounts ($500-1000)
- Use demo environment for testing
- Monitor constantly in first weeks
- Understand all strategies before enabling
- Only trade with money you can afford to lose

## 📝 License

MIT License - see LICENSE file for details

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/kalshi-trading/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/kalshi-trading/discussions)

---

**Built with ❤️ for algorithmic traders**
