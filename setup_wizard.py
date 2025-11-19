#!/usr/bin/env python3
"""
Kalshi Trading System - Automated Setup Wizard
Configures all API keys, tests connections, and deploys the system.
"""

import os
import sys
import time
from getpass import getpass
import subprocess

# Color codes for terminal
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
BOLD = '\033[1m'
RESET = '\033[0m'

def print_header(text):
    print(f"\n{BOLD}{BLUE}{'='*60}{RESET}")
    print(f"{BOLD}{BLUE}{text.center(60)}{RESET}")
    print(f"{BOLD}{BLUE}{'='*60}{RESET}\n")

def print_success(text):
    print(f"{GREEN}✅ {text}{RESET}")

def print_error(text):
    print(f"{RED}❌ {text}{RESET}")

def print_warning(text):
    print(f"{YELLOW}⚠️  {text}{RESET}")

def print_info(text):
    print(f"{BLUE}ℹ️  {text}{RESET}")

def test_kalshi_connection(api_key, api_secret, base_url):
    """Test Kalshi API connection"""
    print_info("Testing Kalshi API connection...")

    try:
        # Create a simple test script
        test_code = f"""
import sys
sys.path.append('/home/user/kalshi-trading-clean')
from src.api.kalshi_client import KalshiClient

client = KalshiClient(
    api_key="{api_key}",
    api_secret="{api_secret}",
    base_url="{base_url}"
)

token = client.authenticate()
print(f"Token: {{token[:20]}}...")

markets = client.get_markets(limit=3)
print(f"Fetched {{len(markets)}} markets")
"""

        with open('/tmp/test_kalshi.py', 'w') as f:
            f.write(test_code)

        result = subprocess.run(
            ['python3', '/tmp/test_kalshi.py'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0 and 'Token:' in result.stdout:
            print_success("Kalshi API connected successfully!")
            return True
        else:
            print_error(f"Kalshi API failed: {result.stderr}")
            return False

    except Exception as e:
        print_error(f"Kalshi test error: {e}")
        return False

def test_telegram_connection(bot_token, chat_id):
    """Test Telegram bot connection"""
    print_info("Testing Telegram bot...")

    try:
        test_code = f"""
import asyncio
import sys
sys.path.append('/home/user/kalshi-trading-clean')
from src.alerts.telegram_bot import TelegramAlerter

bot = TelegramAlerter(
    bot_token="{bot_token}",
    chat_id="{chat_id}",
    config={{}}
)

asyncio.run(bot.send_message("🤖 Kalshi Trading System - Setup Wizard Test"))
print("Message sent successfully")
"""

        with open('/tmp/test_telegram.py', 'w') as f:
            f.write(test_code)

        result = subprocess.run(
            ['python3', '/tmp/test_telegram.py'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0 and 'successfully' in result.stdout:
            print_success("Telegram bot connected! Check your Telegram for test message.")
            return True
        else:
            print_error(f"Telegram failed: {result.stderr}")
            return False

    except Exception as e:
        print_error(f"Telegram test error: {e}")
        return False

def create_env_file(config):
    """Create .env file with all API keys"""
    print_info("Creating .env configuration file...")

    env_content = f"""# Kalshi API Configuration
KALSHI_API_KEY={config['kalshi_key']}
KALSHI_API_SECRET={config['kalshi_secret']}
KALSHI_BASE_URL={config['kalshi_url']}

# Telegram Alerts
TELEGRAM_BOT_TOKEN={config['telegram_token']}
TELEGRAM_CHAT_ID={config['telegram_chat_id']}

# News APIs
TWITTER_BEARER_TOKEN={config.get('twitter_token', '')}
NEWSAPI_KEY={config.get('newsapi_key', '')}
ALPHAVANTAGE_KEY={config.get('alphavantage_key', '')}

# Database
DB_USER=kalshi_trader
DB_PASSWORD={config.get('db_password', 'kalshi_secure_password_' + str(int(time.time())))}
DB_NAME=kalshi_trading
DB_HOST=localhost
DB_PORT=5432
DATABASE_URL=postgresql://${{DB_USER}}:${{DB_PASSWORD}}@${{DB_HOST}}:${{DB_PORT}}/${{DB_NAME}}

# Redis
REDIS_URL=redis://localhost:6379/0

# Trading Configuration
TRADING_ENABLED={config['trading_enabled']}
MAX_POSITION_SIZE_USD={config['max_position_size']}
MAX_PORTFOLIO_HEAT=0.20
MIN_EDGE_THRESHOLD=0.05
MAX_DAILY_LOSS={config['max_daily_loss']}

# Environment
ENVIRONMENT={config['environment']}
LOG_LEVEL=INFO
"""

    env_path = '/home/user/kalshi-trading-clean/.env'
    with open(env_path, 'w') as f:
        f.write(env_content)

    print_success(f".env file created at {env_path}")
    return True

def main():
    print_header("🚀 KALSHI TRADING SYSTEM - SETUP WIZARD 🚀")

    print(f"{BOLD}This wizard will:{RESET}")
    print("  1. Collect your API keys")
    print("  2. Test all connections")
    print("  3. Configure the system")
    print("  4. Deploy with Docker\n")

    input(f"{YELLOW}Press ENTER to start...{RESET}")

    config = {}

    # ===== KALSHI API =====
    print_header("Step 1: Kalshi API")
    print_info("Enter your Kalshi credentials")
    print_warning("Use DEMO credentials first to test safely!")
    print("")

    config['kalshi_key'] = input("Kalshi API Key ID: ").strip()
    config['kalshi_secret'] = getpass("Kalshi Private Key (hidden): ").strip()

    print("\nWhich environment?")
    print("  1. DEMO (recommended for testing)")
    print("  2. PRODUCTION (real money)")

    env_choice = input("Choice (1 or 2): ").strip()

    if env_choice == "1":
        config['kalshi_url'] = "https://demo-api.kalshi.co/trade-api/v2"
        config['environment'] = "demo"
        print_success("Using DEMO environment (safe testing)")
    else:
        config['kalshi_url'] = "https://trading-api.kalshi.com/trade-api/v2"
        config['environment'] = "production"
        print_warning("Using PRODUCTION environment (real money!)")

    # Test Kalshi
    if not test_kalshi_connection(config['kalshi_key'], config['kalshi_secret'], config['kalshi_url']):
        print_error("Kalshi connection failed. Check your credentials.")
        sys.exit(1)

    time.sleep(1)

    # ===== TELEGRAM =====
    print_header("Step 2: Telegram Bot")
    print_info("Enter your Telegram bot credentials")
    print("")

    config['telegram_token'] = input("Telegram Bot Token: ").strip()
    config['telegram_chat_id'] = input("Telegram Chat ID: ").strip()

    # Test Telegram
    if not test_telegram_connection(config['telegram_token'], config['telegram_chat_id']):
        print_error("Telegram connection failed. Check your credentials.")
        sys.exit(1)

    time.sleep(1)

    # ===== OPTIONAL APIs =====
    print_header("Step 3: News APIs (Optional)")

    print_info("Twitter API (for speed arbitrage - main edge)")
    has_twitter = input("Do you have Twitter Bearer Token? (y/n): ").strip().lower()
    if has_twitter == 'y':
        config['twitter_token'] = input("Twitter Bearer Token: ").strip()
        print_success("Twitter API will be enabled")
    else:
        config['twitter_token'] = ''
        print_warning("Twitter API disabled - speed arbitrage won't work optimally")

    print("")
    print_info("NewsAPI (backup news source)")
    has_newsapi = input("Do you have NewsAPI key? (y/n): ").strip().lower()
    if has_newsapi == 'y':
        config['newsapi_key'] = input("NewsAPI Key: ").strip()
        print_success("NewsAPI will be enabled")
    else:
        config['newsapi_key'] = ''

    print("")
    print_info("Alpha Vantage (economic data)")
    has_alphavantage = input("Do you have Alpha Vantage key? (y/n): ").strip().lower()
    if has_alphavantage == 'y':
        config['alphavantage_key'] = input("Alpha Vantage Key: ").strip()
        print_success("Alpha Vantage will be enabled")
    else:
        config['alphavantage_key'] = ''

    time.sleep(1)

    # ===== TRADING CONFIG =====
    print_header("Step 4: Trading Configuration")

    print_info("Should the system execute trades?")
    print_warning("Start with 'No' to paper trade first (see signals without trading)")
    trade_now = input("Enable live trading? (y/n): ").strip().lower()

    config['trading_enabled'] = 'true' if trade_now == 'y' else 'false'

    if trade_now == 'y':
        print_warning("Live trading enabled!")
        print_info("Set conservative limits:")
        config['max_position_size'] = input("Max position size in USD (recommended: 50): ").strip() or "50"
        config['max_daily_loss'] = input("Max daily loss in USD (recommended: 50): ").strip() or "50"
    else:
        print_success("Paper trading mode - signals generated but no trades executed")
        config['max_position_size'] = "500"
        config['max_daily_loss'] = "1000"

    time.sleep(1)

    # ===== CREATE CONFIG =====
    print_header("Step 5: Creating Configuration")

    if not create_env_file(config):
        print_error("Failed to create .env file")
        sys.exit(1)

    time.sleep(1)

    # ===== SUMMARY =====
    print_header("📋 CONFIGURATION SUMMARY")

    print(f"{BOLD}Kalshi:{RESET}")
    print(f"  Environment: {config['environment'].upper()}")
    print(f"  API Key: {config['kalshi_key'][:10]}...")

    print(f"\n{BOLD}Alerts:{RESET}")
    print(f"  Telegram: ✅ Configured")

    print(f"\n{BOLD}News Sources:{RESET}")
    print(f"  Twitter: {'✅ Enabled' if config.get('twitter_token') else '❌ Disabled'}")
    print(f"  NewsAPI: {'✅ Enabled' if config.get('newsapi_key') else '❌ Disabled'}")
    print(f"  Alpha Vantage: {'✅ Enabled' if config.get('alphavantage_key') else '❌ Disabled'}")

    print(f"\n{BOLD}Trading:{RESET}")
    print(f"  Enabled: {config['trading_enabled']}")
    if config['trading_enabled'] == 'true':
        print(f"  Max Position: ${config['max_position_size']}")
        print(f"  Max Daily Loss: ${config['max_daily_loss']}")

    print("")

    # ===== DEPLOY =====
    print_header("Step 6: Deploy with Docker")

    deploy = input("Deploy now with docker-compose? (y/n): ").strip().lower()

    if deploy == 'y':
        print_info("Starting Docker deployment...")

        os.chdir('/home/user/kalshi-trading-clean')

        # Build
        print_info("Building Docker images...")
        result = subprocess.run(['docker-compose', 'build'], capture_output=True)
        if result.returncode != 0:
            print_error("Docker build failed")
            print(result.stderr.decode())
            sys.exit(1)

        print_success("Docker images built")

        # Start
        print_info("Starting services...")
        result = subprocess.run(['docker-compose', 'up', '-d'], capture_output=True)
        if result.returncode != 0:
            print_error("Docker start failed")
            print(result.stderr.decode())
            sys.exit(1)

        print_success("Services started!")

        time.sleep(3)

        # Check logs
        print_info("Checking logs...")
        subprocess.run(['docker-compose', 'logs', '--tail=20', 'app'])

    else:
        print_info("Skipping deployment. To deploy later, run:")
        print(f"  cd /home/user/kalshi-trading-clean")
        print(f"  docker-compose up -d")

    # ===== DONE =====
    print_header("✅ SETUP COMPLETE!")

    print(f"{BOLD}What's Next:{RESET}")
    print("")
    print(f"{GREEN}1. Check your Telegram{RESET} - You should have received a test message")
    print(f"{GREEN}2. Monitor logs:{RESET} docker-compose logs -f app")
    print(f"{GREEN}3. Access Grafana:{RESET} http://localhost:3000 (admin/admin)")
    print(f"{GREEN}4. Read the docs:{RESET} /home/user/kalshi-trading-clean/QUICK_START.md")
    print("")

    if config['trading_enabled'] == 'false':
        print_warning("PAPER TRADING MODE: System will generate signals but NOT execute trades")
        print_info("When ready to trade, edit .env and set TRADING_ENABLED=true")
    else:
        print_warning("🔴 LIVE TRADING ENABLED - Monitor closely!")

    print("")
    print(f"{BOLD}Repository:{RESET} https://github.com/jacergallagher717-coder/Kalshi-Trading")
    print("")
    print(f"{GREEN}Good luck and trade responsibly! 🚀{RESET}")
    print("")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{RED}Setup cancelled by user{RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n{RED}Setup failed: {e}{RESET}")
        sys.exit(1)
