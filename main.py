"""
Kalshi Automated Trading System - Main Application
Orchestrates all components: news monitoring, edge detection, trade execution, position management.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from datetime import datetime
import yaml
from dotenv import load_dotenv
import os

from src.api.kalshi_client import KalshiClient
from src.monitors.news_monitor import NewsMonitor, NewsEvent
from src.monitors.telegram_news_monitor import integrate_telegram_monitor
from src.edge_detection.speed_arbitrage import SpeedArbitrage
from src.execution.trade_executor import TradeExecutor
from src.database.models import Market as MarketModel
from src.execution.position_manager import PositionManager
from src.alerts.telegram_bot import TelegramAlerter
from src.monitoring.metrics import MetricsCollector, start_metrics_server
from src.database.models import Database, NewsEvent as DBNewsEvent, Signal as DBSignal

# Optional imports - pattern detection and weather model require numpy/scipy
try:
    from src.edge_detection.pattern_detection import PatternDetector
except ImportError:
    PatternDetector = None

try:
    from src.edge_detection.weather_model import WeatherModel
except ImportError:
    WeatherModel = None

try:
    from src.edge_detection.llm_analyzer import LLMNewsAnalyzer
except ImportError:
    LLMNewsAnalyzer = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/kalshi_trading/app.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class KalshiTradingSystem:
    """Main trading system orchestrator"""

    def __init__(self, config_path: str = "config/config.yaml"):
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Load environment variables
        load_dotenv()

        # Initialize database
        database_url = os.getenv('DATABASE_URL')
        self.db = Database(database_url)
        self.db.create_tables()

        # Initialize Kalshi API client
        self.kalshi = KalshiClient(
            api_key=os.getenv('KALSHI_API_KEY'),
            api_secret=os.getenv('KALSHI_API_SECRET'),
            base_url=os.getenv('KALSHI_BASE_URL'),
        )

        # Initialize Telegram bot
        telegram_config = self.config.get('alerts', {}).get('telegram', {})
        self.telegram = TelegramAlerter(
            bot_token=os.getenv('TELEGRAM_BOT_TOKEN'),
            chat_id=os.getenv('TELEGRAM_CHAT_ID'),
            config=telegram_config,
        )

        # Initialize news monitor
        news_config = {
            'twitter': {
                'enabled': self.config.get('news_monitoring', {}).get('twitter', {}).get('enabled', False),
                'bearer_token': os.getenv('TWITTER_BEARER_TOKEN'),
                'accounts': self.config.get('news_monitoring', {}).get('twitter', {}).get('accounts', []),
                'poll_interval_seconds': self.config.get('news_monitoring', {}).get('twitter', {}).get('poll_interval_seconds', 2),
            },
            'newsapi': {
                'enabled': self.config.get('news_monitoring', {}).get('newsapi', {}).get('enabled', False),
                'api_key': os.getenv('NEWSAPI_KEY'),
                'poll_interval_seconds': self.config.get('news_monitoring', {}).get('newsapi', {}).get('poll_interval_seconds', 10),
            },
            'alphavantage': {
                'enabled': self.config.get('news_monitoring', {}).get('alphavantage', {}).get('enabled', False),
                'api_key': os.getenv('ALPHAVANTAGE_KEY'),
                'poll_interval_seconds': self.config.get('news_monitoring', {}).get('alphavantage', {}).get('poll_interval_seconds', 30),
            },
            'weather': {
                'enabled': self.config.get('news_monitoring', {}).get('weather', {}).get('enabled', False),
                'poll_interval_seconds': self.config.get('news_monitoring', {}).get('weather', {}).get('poll_interval_seconds', 300),
            },
        }

        self.news_monitor = NewsMonitor(news_config)
        self.news_monitor.register_callback(self.on_news_event)

        # Initialize edge detection strategies
        self.speed_arb = None
        self.weather_model = None
        self.pattern_detector = None
        self.llm_analyzer = None

        strategies = self.config.get('strategies', {})

        if strategies.get('speed_arbitrage', {}).get('enabled', False):
            self.speed_arb = SpeedArbitrage(strategies['speed_arbitrage'])

        if strategies.get('weather_model', {}).get('enabled', False):
            if WeatherModel:
                self.weather_model = WeatherModel(strategies['weather_model'])
            else:
                logger.warning("WeatherModel disabled - scipy not installed")

        if strategies.get('pattern_detection', {}).get('enabled', False):
            if PatternDetector:
                self.pattern_detector = PatternDetector(strategies['pattern_detection'])
            else:
                logger.warning("PatternDetector disabled - numpy not installed")

        # Initialize LLM analyzer for qualitative news analysis (fallback when regex fails)
        llm_enabled = strategies.get('llm_analysis', {}).get('enabled', True)  # Default ON
        if llm_enabled and LLMNewsAnalyzer:
            self.llm_analyzer = LLMNewsAnalyzer(
                api_key=os.getenv('ANTHROPIC_API_KEY'),
                enabled=llm_enabled
            )
        elif llm_enabled:
            logger.warning("LLMNewsAnalyzer disabled - anthropic library not installed")

        # Initialize trade executor
        trading_config = self.config.get('trading', {})
        risk_config = self.config.get('risk', {})
        combined_config = {**trading_config, **risk_config}

        session = self.db.get_session()
        self.trade_executor = TradeExecutor(
            kalshi_client=self.kalshi,
            config=combined_config,
            db_session=session,
            alert_callback=self.send_alert,
        )

        # Initialize position manager
        self.position_manager = PositionManager(
            kalshi_client=self.kalshi,
            config=combined_config,
            db_session=session,
            alert_callback=self.send_alert,
        )

        # System state
        self.running = False
        self.shutdown_requested = False

        logger.info("Kalshi Trading System initialized")

    def _store_markets(self, markets):
        """Store/update markets in database"""
        session = self.db.get_session()
        try:
            for market in markets:
                # Use merge to insert or update
                db_market = session.merge(MarketModel(
                    ticker=market.ticker,
                    title=market.title,
                    category=market.category,
                    close_date=market.close_time,
                    status=market.status,
                    volume_24h=market.volume,
                    last_price=market.last_price,
                    yes_bid=market.yes_bid,
                    yes_ask=market.yes_ask,
                    no_bid=market.no_bid,
                    no_ask=market.no_ask,
                    open_interest=market.open_interest,
                ))
            session.commit()
            logger.debug(f"Stored/updated {len(markets)} markets in database")
        except Exception as e:
            logger.error(f"Error storing markets: {e}")
            session.rollback()
        finally:
            session.close()

    async def on_news_event(self, event: NewsEvent):
        """Callback for when a news event is detected"""
        logger.info(f"Processing news event: {event.headline[:100]}")

        # Record in database
        session = self.db.get_session()
        try:
            db_event = DBNewsEvent(
                event_id=event.event_id,
                timestamp=event.timestamp,
                source=event.source,
                event_type=event.event_type.value,
                headline=event.headline,
                content=event.content,
                keywords=event.keywords,
                entities=event.entities,
                related_tickers=event.related_tickers,
                reliability_score=event.reliability_score,
                url=event.url,
            )
            session.add(db_event)
            session.commit()

            # Record metric
            MetricsCollector.record_news_event(event.source, event.event_type.value)

        except Exception as e:
            logger.error(f"Error storing news event: {e}")
            session.rollback()
        finally:
            session.close()

        # Generate signals based on event
        if self.speed_arb:
            await self.generate_speed_arb_signals(event)

    async def generate_speed_arb_signals(self, event: NewsEvent):
        """Generate speed arbitrage signals from news event"""
        try:
            # Get available markets (fetch all, not just first 100)
            markets = self.kalshi.get_markets(status="open", limit=1000)
            market_tickers = [m.ticker for m in markets]

            # Store/update markets in database before creating signals
            self._store_markets(markets)

            # Get current prices
            market_prices = {m.ticker: m.last_price or 0.50 for m in markets}

            # FAST PATH: Try regex-based speed arbitrage first
            signals = self.speed_arb.analyze_event(event, market_tickers, market_prices)

            # FALLBACK: If regex found nothing, try LLM analysis for qualitative news
            if not signals and self.llm_analyzer:
                logger.info(f"Speed arb found no signals - trying LLM analysis for: {event.headline[:80]}")

                llm_analysis = self.llm_analyzer.analyze_news(event, market_tickers)

                if llm_analysis:
                    # Get current price for the identified market
                    ticker = llm_analysis['ticker']
                    current_price = market_prices.get(ticker)

                    # Create trade signal from LLM analysis
                    signal = self.llm_analyzer.create_trade_signal(
                        llm_analysis,
                        event,
                        current_price
                    )

                    signals = [signal]
                    logger.info(f"LLM generated signal: {signal}")

            # Process each signal
            for signal in signals:
                await self.process_signal(signal)

        except Exception as e:
            logger.error(f"Error generating speed arb signals: {e}")
            MetricsCollector.record_system_error("speed_arb", "signal_generation")

    async def process_signal(self, signal):
        """Process a trading signal"""
        logger.info(f"Processing signal: {signal}")

        # Store signal in database
        session = self.db.get_session()
        try:
            db_signal = DBSignal(
                signal_id=signal.signal_id,
                timestamp=signal.timestamp,
                source=signal.source,
                ticker=signal.ticker,
                side=signal.side,
                signal_type=signal.signal_type,
                confidence=signal.confidence,
                edge_percentage=signal.edge_percentage,
                market_price=signal.current_price,
                fair_value=signal.fair_value,
                reasoning=signal.reasoning,
            )
            session.add(db_signal)
            session.commit()

            # Record metric
            MetricsCollector.record_signal(signal.source, False)

            # Execute signal
            trade = await self.trade_executor.execute_signal(signal)

            if trade:
                MetricsCollector.record_signal(signal.source, True)
                MetricsCollector.record_trade(
                    signal.side,
                    signal.ticker,
                    "executed",
                    None  # P&L unknown at execution
                )

        except Exception as e:
            logger.error(f"Error processing signal: {e}")
            session.rollback()
        finally:
            session.close()

    async def send_alert(self, message: str):
        """Send alert via Telegram"""
        try:
            await self.telegram.send_message(message)
        except Exception as e:
            logger.error(f"Error sending alert: {e}")

    async def monitor_positions_loop(self):
        """Periodic position monitoring loop"""
        while self.running:
            try:
                await self.position_manager.monitor_positions()

                # Update metrics
                summary = self.position_manager.get_position_summary()
                MetricsCollector.update_positions(
                    summary['total_positions'],
                    summary.get('total_value', 0),
                    summary['total_unrealized_pnl']
                )

            except Exception as e:
                logger.error(f"Error in position monitoring loop: {e}")
                MetricsCollector.record_system_error("position_manager", "monitoring")

            # Check every 30 seconds
            await asyncio.sleep(30)

    async def scan_weather_markets_loop(self):
        """Periodic weather market scanning"""
        if not self.weather_model:
            return

        while self.running:
            try:
                # Get weather markets
                markets = self.kalshi.get_markets(status="open", category="weather")
                market_tickers = [m.ticker for m in markets]
                market_prices = {m.ticker: m.last_price or 0.50 for m in markets}

                # Scan for opportunities
                signals = await self.weather_model.scan_weather_markets(
                    market_tickers,
                    market_prices
                )

                # Process signals
                for signal in signals:
                    await self.process_signal(signal)

            except Exception as e:
                logger.error(f"Error scanning weather markets: {e}")
                MetricsCollector.record_system_error("weather_model", "scanning")

            # Check every hour
            await asyncio.sleep(3600)

    async def start(self):
        """Start the trading system"""
        self.running = True

        logger.info("🚀 Starting Kalshi Trading System...")

        # Test Telegram connection
        telegram_ok = await self.telegram.test_connection()
        if not telegram_ok:
            logger.warning("Telegram bot not connected - alerts disabled")

        # Start metrics server
        start_metrics_server(port=9090)

        # Start all async tasks
        tasks = [
            asyncio.create_task(self.news_monitor.start()),
            asyncio.create_task(self.monitor_positions_loop()),
            asyncio.create_task(self.scan_weather_markets_loop()),
        ]

        # Start Telegram news monitoring if configured
        if os.getenv('TELEGRAM_API_ID'):
            telegram_api_id = os.getenv('TELEGRAM_API_ID')
            telegram_api_hash = os.getenv('TELEGRAM_API_HASH')
            telegram_phone = os.getenv('TELEGRAM_PHONE')
            telegram_channels_str = os.getenv('TELEGRAM_NEWS_CHANNELS', '')

            if telegram_api_id and telegram_api_hash and telegram_phone and telegram_channels_str:
                telegram_channels = [c.strip() for c in telegram_channels_str.split(',')]
                logger.info(f"🎯 Starting Telegram news monitor for channels: {telegram_channels}")

                telegram_news_task = asyncio.create_task(
                    integrate_telegram_monitor(
                        self.news_monitor,
                        api_id=telegram_api_id,
                        api_hash=telegram_api_hash,
                        phone=telegram_phone,
                        channels=telegram_channels
                    )
                )
                tasks.append(telegram_news_task)

                await self.send_alert(f"🎯 Telegram news monitor active for: {', '.join(telegram_channels)}")
            else:
                logger.warning("Telegram news monitoring configured but missing required fields")
        else:
            logger.info("Telegram news monitoring not configured (optional)")

        # Send startup alert
        await self.send_alert("🚀 Kalshi Trading System started")

        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Graceful shutdown"""
        if self.shutdown_requested:
            return

        self.shutdown_requested = True
        logger.info("Shutting down trading system...")

        self.running = False

        # Send shutdown alert
        await self.send_alert("🛑 Kalshi Trading System shutting down")

        # Close connections
        self.kalshi.close()
        self.db.close()

        logger.info("Shutdown complete")

    def handle_signal(self, sig, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {sig}")
        asyncio.create_task(self.shutdown())


def main():
    """Main entry point"""
    # Create system
    system = KalshiTradingSystem()

    # Register signal handlers
    signal.signal(signal.SIGINT, system.handle_signal)
    signal.signal(signal.SIGTERM, system.handle_signal)

    # Run
    try:
        asyncio.run(system.start())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
