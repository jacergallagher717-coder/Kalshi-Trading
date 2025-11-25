#!/usr/bin/env python3
"""
System Validation Script
Tests all components to ensure the trading system is ready to run.

Run this BEFORE starting the bot to verify everything is configured correctly.
"""

import os
import sys
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class SystemValidator:
    """Validates all system components"""

    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []

    def test(self, name: str, func):
        """Run a validation test"""
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"Testing: {name}")
            logger.info('='*60)
            func()
            self.passed.append(name)
            logger.info(f"✅ PASSED: {name}")
        except AssertionError as e:
            self.failed.append((name, str(e)))
            logger.error(f"❌ FAILED: {name} - {e}")
        except Exception as e:
            self.failed.append((name, str(e)))
            logger.error(f"❌ ERROR: {name} - {e}")

    def warn(self, message: str):
        """Add a warning"""
        self.warnings.append(message)
        logger.warning(f"⚠️  {message}")

    def validate_environment(self):
        """Check .env file exists and has required variables"""
        env_path = Path('.env')
        assert env_path.exists(), ".env file not found - run create_env.sh first"

        from dotenv import load_dotenv
        load_dotenv()

        # Required variables
        required = [
            'KALSHI_API_KEY',
            'KALSHI_API_SECRET',
            'KALSHI_BASE_URL',
            'DATABASE_URL',
            'TELEGRAM_BOT_TOKEN',
            'TELEGRAM_CHAT_ID',
        ]

        for var in required:
            value = os.getenv(var)
            assert value, f"Missing required environment variable: {var}"
            logger.info(f"  ✓ {var}: {'*' * min(len(value), 10)}...")

        # Optional but recommended
        optional = [
            'TELEGRAM_API_ID',
            'TELEGRAM_API_HASH',
            'TELEGRAM_PHONE',
            'TELEGRAM_NEWS_CHANNELS',
        ]

        for var in optional:
            value = os.getenv(var)
            if not value:
                self.warn(f"Optional variable not set: {var} (BossBot monitoring disabled)")
            else:
                logger.info(f"  ✓ {var}: configured")

        # Check paper trading mode
        paper_mode = os.getenv('PAPER_TRADING_MODE', 'true').lower() == 'true'
        if paper_mode:
            logger.info("  ✅ PAPER_TRADING_MODE: true (SAFE - no real money)")
        else:
            logger.warning("  ⚠️  PAPER_TRADING_MODE: false (LIVE TRADING - REAL MONEY!)")

    def validate_dependencies(self):
        """Check all required Python packages are installed"""
        required_packages = [
            ('anthropic', 'LLM analysis'),
            ('httpx', 'HTTP client'),
            ('sqlalchemy', 'Database ORM'),
            ('telethon', 'Telegram monitoring'),
            ('python-telegram-bot', 'Telegram alerts'),
            ('cryptography', 'Kalshi API auth'),
        ]

        for package, purpose in required_packages:
            try:
                __import__(package.replace('-', '_'))
                logger.info(f"  ✓ {package}: installed ({purpose})")
            except ImportError:
                raise AssertionError(f"{package} not installed - needed for {purpose}")

    def validate_kalshi_api(self):
        """Test Kalshi API connection"""
        from dotenv import load_dotenv
        load_dotenv()

        from src.api.kalshi_client import KalshiClient

        client = KalshiClient(
            api_key=os.getenv('KALSHI_API_KEY'),
            api_secret=os.getenv('KALSHI_API_SECRET'),
            base_url=os.getenv('KALSHI_BASE_URL'),
        )

        # Test API connection
        balance = client.get_balance()
        assert balance is not None, "Failed to get balance from Kalshi API"
        logger.info(f"  ✓ Connected to Kalshi API")
        logger.info(f"  ✓ Balance: ${balance.get('balance', 0):.2f}")

        # Test market fetching
        markets = client.get_markets(status="open", limit=10)
        assert markets, "No markets returned from API"
        logger.info(f"  ✓ Fetched {len(markets)} open markets")

    def validate_database(self):
        """Test database connection"""
        from dotenv import load_dotenv
        load_dotenv()

        from src.database.models import Database

        db_url = os.getenv('DATABASE_URL')
        # Handle docker vs local database URL
        if 'postgres:5432' in db_url:
            # Replace docker hostname with localhost for validation script
            db_url = db_url.replace('@postgres:', '@localhost:')
            logger.info("  Using localhost for database (not in Docker)")

        try:
            db = Database(db_url)
            db.create_tables()
            logger.info("  ✓ Database connection successful")
            logger.info("  ✓ Tables created/verified")
            db.close()
        except Exception as e:
            raise AssertionError(f"Database connection failed: {e}")

    def validate_consensus_data(self):
        """Check consensus data is configured"""
        from src.data.consensus_fetcher import get_consensus_fetcher

        fetcher = get_consensus_fetcher()

        # Check key metrics
        key_metrics = ['CPI', 'UNEMPLOYMENT', 'GDP']
        for metric in key_metrics:
            value = fetcher.get_consensus(metric)
            assert value is not None, f"No consensus data for {metric}"
            logger.info(f"  ✓ {metric} consensus: {value}%")

        logger.info("  ✓ Consensus data file exists and is valid")

    def validate_paper_trader(self):
        """Test paper trading module"""
        from src.execution.paper_trader import PaperTrader

        trader = PaperTrader({})

        # Test order placement
        order = trader.place_order(
            ticker="TEST-TICKER",
            side="yes",
            quantity=10,
            limit_price=50
        )

        assert order is not None, "Paper order failed"
        assert order.order_id.startswith("PAPER_"), "Invalid paper order ID"
        logger.info(f"  ✓ Paper trading simulation works")
        logger.info(f"  ✓ Test order: {order.order_id}")

    def validate_config_files(self):
        """Check all config files exist"""
        config_files = [
            'config/config.yaml',
            'config/consensus_values.json',
        ]

        for config_file in config_files:
            path = Path(config_file)
            if not path.exists():
                # Create if missing
                logger.info(f"  Creating missing config: {config_file}")
                if 'consensus_values' in config_file:
                    from src.data.consensus_fetcher import ConsensusDataFetcher
                    ConsensusDataFetcher()  # Creates default config
            assert path.exists(), f"Config file not found: {config_file}"
            logger.info(f"  ✓ {config_file}: exists")

    def validate_regex_patterns(self):
        """Test regex pattern extraction"""
        from src.edge_detection.speed_arbitrage import EconomicDataParser

        # Test cases
        test_cases = [
            ("CPI: 3.2% vs est 3.0%", "CPI", 3.2, 3.0),
            ("Unemployment 4.1%", "UNEMPLOYMENT", 4.1, None),
            ("GDP 2.8% vs expected 2.5%", "GDP", 2.8, 2.5),
        ]

        for text, expected_metric, expected_actual, expected_est in test_cases:
            result = EconomicDataParser.extract_economic_data(text)
            assert result is not None, f"Failed to parse: {text}"
            assert result['metric'] == expected_metric, f"Wrong metric for: {text}"
            assert result['value'] == expected_actual, f"Wrong value for: {text}"

            if expected_est:
                assert result.get('expected') == expected_est, f"Failed to extract 'expected' from: {text}"

            logger.info(f"  ✓ Parsed: {text}")

        logger.info("  ✅ All regex patterns working correctly")

    def run_all_tests(self):
        """Run all validation tests"""
        logger.info("\n" + "="*60)
        logger.info("🔍 KALSHI TRADING SYSTEM VALIDATION")
        logger.info("="*60)

        tests = [
            ("Environment Variables", self.validate_environment),
            ("Python Dependencies", self.validate_dependencies),
            ("Config Files", self.validate_config_files),
            ("Consensus Data", self.validate_consensus_data),
            ("Kalshi API Connection", self.validate_kalshi_api),
            ("Database Connection", self.validate_database),
            ("Paper Trading Module", self.validate_paper_trader),
            ("Regex Pattern Extraction", self.validate_regex_patterns),
        ]

        for name, func in tests:
            self.test(name, func)

        # Print summary
        logger.info("\n" + "="*60)
        logger.info("📊 VALIDATION SUMMARY")
        logger.info("="*60)
        logger.info(f"✅ Passed: {len(self.passed)}")
        logger.info(f"❌ Failed: {len(self.failed)}")
        logger.info(f"⚠️  Warnings: {len(self.warnings)}")

        if self.passed:
            logger.info("\n✅ Passed tests:")
            for test in self.passed:
                logger.info(f"   - {test}")

        if self.failed:
            logger.info("\n❌ Failed tests:")
            for test, reason in self.failed:
                logger.info(f"   - {test}: {reason}")

        if self.warnings:
            logger.info("\n⚠️  Warnings:")
            for warning in self.warnings:
                logger.info(f"   - {warning}")

        logger.info("\n" + "="*60)

        if self.failed:
            logger.error("❌ VALIDATION FAILED - Fix errors before running the bot")
            sys.exit(1)
        else:
            logger.info("✅ ALL TESTS PASSED - System is ready to run!")
            logger.info("")
            logger.info("Next steps:")
            logger.info("  1. Review consensus values in config/consensus_values.json")
            logger.info("  2. Update expected values before economic releases")
            logger.info("  3. Start the system: docker-compose up -d")
            logger.info("  4. Monitor logs: docker-compose logs -f app")
            logger.info("")
            logger.info("🚀 Ready for paper trading!")
            sys.exit(0)


if __name__ == "__main__":
    validator = SystemValidator()
    validator.run_all_tests()
