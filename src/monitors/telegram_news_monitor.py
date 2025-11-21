"""
Telegram Channel News Monitor
Monitors Telegram channels/bots for real-time breaking news.

This is the SECRET WEAPON - free, real-time, filtered news that's as good as Twitter Enterprise.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Callable
import re

try:
    from telethon import TelegramClient, events
    from telethon.tl.types import Message
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    logging.warning("Telethon not installed. Install with: pip install telethon")

from src.monitors.news_monitor import NewsEvent, EventType, NewsClassifier

logger = logging.getLogger(__name__)


class TelegramNewsMonitor:
    """
    Monitor Telegram channels for breaking news in real-time.

    Perfect for channels like BossBot that post:
    - Breaking economic data (CPI, jobs, GDP)
    - Market-moving political news
    - Fed announcements
    - Geopolitical events

    Advantages over Twitter:
    - FREE (no $5k/month cost)
    - Real-time (sub-second latency)
    - Already filtered for trading relevance
    - Easy to set up
    """

    def __init__(
        self,
        api_id: str,
        api_hash: str,
        phone: str,
        channels: List[str],
        session_name: str = "kalshi_trader"
    ):
        """
        Initialize Telegram news monitor.

        Args:
            api_id: Telegram API ID (get from https://my.telegram.org)
            api_hash: Telegram API Hash
            phone: Your phone number (for authentication)
            channels: List of channel usernames to monitor (e.g., ['bossbot', 'breakingnews'])
            session_name: Session file name for persistent login
        """
        if not TELETHON_AVAILABLE:
            raise ImportError("Telethon required. Install: pip install telethon")

        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.channels = channels
        self.session_name = session_name

        self.client = None
        self.running = False
        self.callbacks = []

        logger.info(f"Telegram monitor initialized for channels: {channels}")

    def register_callback(self, callback: Callable):
        """Register callback to receive news events"""
        self.callbacks.append(callback)

    async def start(self):
        """Start monitoring Telegram channels"""
        self.running = True

        # Create Telegram client
        self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)

        await self.client.start(phone=self.phone)
        logger.info("Telegram client started and authenticated")

        # Get channel entities
        channel_entities = []
        for channel in self.channels:
            try:
                entity = await self.client.get_entity(channel)
                channel_entities.append(entity)
                logger.info(f"Monitoring channel: {channel}")
            except Exception as e:
                logger.error(f"Failed to get channel {channel}: {e}")

        if not channel_entities:
            logger.error("No valid channels to monitor")
            return

        # Register message handler
        @self.client.on(events.NewMessage(chats=channel_entities))
        async def handle_message(event):
            await self._process_message(event.message)

        logger.info("Telegram news monitor active - listening for messages...")

        # Keep running
        await self.client.run_until_disconnected()

    async def _process_message(self, message: Message):
        """Process incoming Telegram message"""
        try:
            # Extract message text
            text = message.message
            if not text:
                return

            logger.info(f"New message from Telegram: {text[:100]}")

            # Parse and classify
            event = self._parse_message(text, message)

            if event:
                # Call all registered callbacks
                for callback in self.callbacks:
                    try:
                        await callback(event)
                    except Exception as e:
                        logger.error(f"Error in callback: {e}")

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def _parse_message(self, text: str, message: Message) -> Optional[NewsEvent]:
        """Parse Telegram message into NewsEvent"""

        # Generate unique event ID
        event_id = f"telegram_{message.chat_id}_{message.id}"

        # Classify event type
        event_type = NewsClassifier.classify_event(text)

        # Extract keywords
        keywords = NewsClassifier.extract_keywords(text)

        # Extract entities
        entities = NewsClassifier.extract_entities(text)

        # Create NewsEvent
        event = NewsEvent(
            event_id=event_id,
            timestamp=message.date or datetime.utcnow(),
            source=f"telegram_{message.chat.username or message.chat_id}",
            event_type=event_type,
            headline=text[:200],  # First 200 chars as headline
            content=text,
            keywords=keywords,
            entities=entities,
            related_tickers=[],
            reliability_score=0.9,  # High reliability for curated channels
            url=None,
            raw_data={"chat_id": message.chat_id, "message_id": message.id}
        )

        return event

    async def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.client:
            await self.client.disconnect()
        logger.info("Telegram monitor stopped")


class TelegramNewsParser:
    """
    Enhanced parser for common Telegram news formats.

    Handles patterns like:
    - "🚨 BREAKING: CPI comes in at 3.5% vs expected 3.2%"
    - "⚡️ Fed raises rates by 25bps to 5.25%"
    - "📊 Unemployment rate falls to 3.6%"
    """

    @staticmethod
    def extract_economic_data(text: str) -> Optional[dict]:
        """Extract economic data from Telegram message"""

        # CPI patterns
        cpi_patterns = [
            r'CPI.*?(\d+\.?\d*)%',
            r'inflation.*?(\d+\.?\d*)%',
            r'consumer price.*?(\d+\.?\d*)%',
        ]

        for pattern in cpi_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = float(match.group(1))

                # Try to extract expected value
                expected_match = re.search(r'(?:expected|est|forecast).*?(\d+\.?\d*)%', text, re.IGNORECASE)
                expected = float(expected_match.group(1)) if expected_match else None

                return {
                    'metric': 'CPI',
                    'actual': value,
                    'expected': expected,
                    'unit': 'percent'
                }

        # Unemployment patterns
        unemp_patterns = [
            r'unemployment.*?(\d+\.?\d*)%',
            r'jobless.*?(\d+\.?\d*)%',
        ]

        for pattern in unemp_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = float(match.group(1))
                expected_match = re.search(r'(?:expected|est).*?(\d+\.?\d*)%', text, re.IGNORECASE)
                expected = float(expected_match.group(1)) if expected_match else None

                return {
                    'metric': 'UNEMPLOYMENT',
                    'actual': value,
                    'expected': expected,
                    'unit': 'percent'
                }

        # Fed rate patterns
        rate_patterns = [
            r'(?:fed|federal reserve).*?(?:raises|cuts|hikes).*?(\d+)(?:\s)?(?:bp|bps|basis points)',
            r'interest rate.*?(\d+\.?\d*)%',
        ]

        for pattern in rate_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = float(match.group(1))

                return {
                    'metric': 'FED_RATE',
                    'actual': value,
                    'expected': None,
                    'unit': 'bps' if 'bp' in text.lower() else 'percent'
                }

        return None

    @staticmethod
    def detect_urgency(text: str) -> float:
        """
        Detect urgency/importance of news (0-1 score).

        Higher score = more urgent = higher priority
        """
        score = 0.5  # Base score

        # Urgency indicators
        urgent_keywords = ['breaking', 'alert', 'urgent', 'just in', 'now']
        for keyword in urgent_keywords:
            if keyword.lower() in text.lower():
                score += 0.1

        # Emoji indicators (often used for important news)
        urgent_emojis = ['🚨', '⚡', '🔥', '📊', '💥', '⚠️']
        for emoji in urgent_emojis:
            if emoji in text:
                score += 0.05

        # ALL CAPS words (usually important)
        caps_words = re.findall(r'\b[A-Z]{3,}\b', text)
        if len(caps_words) > 2:
            score += 0.1

        return min(score, 1.0)


# Integration helper
async def integrate_telegram_monitor(
    main_news_monitor,
    api_id: str,
    api_hash: str,
    phone: str,
    channels: List[str]
):
    """
    Integrate Telegram monitor with main news monitoring system.

    Usage in main.py:
        telegram_task = asyncio.create_task(
            integrate_telegram_monitor(
                news_monitor,
                api_id="YOUR_API_ID",
                api_hash="YOUR_API_HASH",
                phone="+1234567890",
                channels=["bossbot", "breakingnews"]
            )
        )
    """
    telegram_monitor = TelegramNewsMonitor(
        api_id=api_id,
        api_hash=api_hash,
        phone=phone,
        channels=channels,
        session_name="config/bossbot_session"
    )

    # Register callback to feed events to main news monitor
    async def forward_to_main(event: NewsEvent):
        # Process event through main news monitor's callbacks
        for callback in main_news_monitor.event_callbacks:
            await callback(event)

    telegram_monitor.register_callback(forward_to_main)

    # Start monitoring
    await telegram_monitor.start()


"""
SETUP INSTRUCTIONS:

1. Get Telegram API credentials:
   - Go to: https://my.telegram.org
   - Login with your phone
   - Click "API development tools"
   - Create an app (any name)
   - Copy api_id and api_hash

2. Install Telethon:
   pip install telethon

3. Add to .env:
   TELEGRAM_API_ID=your_api_id
   TELEGRAM_API_HASH=your_api_hash
   TELEGRAM_PHONE=+1234567890
   TELEGRAM_CHANNELS=bossbot,otherchannel

4. In main.py, add:

   from src.monitors.telegram_news_monitor import integrate_telegram_monitor
   import os

   # In main() function, after starting news monitor:
   if os.getenv('TELEGRAM_API_ID'):
       channels = os.getenv('TELEGRAM_CHANNELS', '').split(',')
       telegram_task = asyncio.create_task(
           integrate_telegram_monitor(
               self.news_monitor,
               api_id=os.getenv('TELEGRAM_API_ID'),
               api_hash=os.getenv('TELEGRAM_API_HASH'),
               phone=os.getenv('TELEGRAM_PHONE'),
               channels=channels
           )
       )

5. First run will ask for verification code (sent to your Telegram)

6. After first login, creates session file - no verification needed again

That's it! You now have FREE real-time news monitoring.
"""
