"""
Market Data Cache
Caches Kalshi market data to eliminate API fetch bottleneck on every news event.

Instead of fetching 1000+ markets on every news event (300ms each time),
we cache markets and refresh every 5 minutes in the background.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from collections import defaultdict
import re

logger = logging.getLogger(__name__)


class MarketCache:
    """
    High-performance market data cache with background refresh.

    Features:
    - Caches all open markets
    - Refreshes every 5 minutes
    - Pre-indexes markets by keywords for O(1) lookup
    - Provides instant access (no API latency)
    """

    def __init__(self, kalshi_client, refresh_interval_seconds: int = 300):
        self.kalshi = kalshi_client
        self.refresh_interval = refresh_interval_seconds

        # Cache storage
        self.markets = []  # All markets
        self.markets_by_ticker = {}  # Fast ticker lookup
        self.markets_by_keyword = defaultdict(list)  # Fast keyword search
        self.market_prices = {}  # Current prices

        # State
        self.last_refresh = None
        self.refresh_count = 0
        self.running = False

        # Keyword patterns for indexing (same as MarketMatcher)
        self.keyword_patterns = {
            "cpi": ["CPI", "INF"],
            "inflation": ["INF", "CPI"],
            "unemployment": ["UNEMP", "JOBS"],
            "gdp": ["GDP"],
            "nonfarm": ["NFP", "JOBS"],
            "fed": ["FED", "RATE", "FOMC"],
            "rates": ["RATE", "FED"],
            "hurricane": ["HURRICANE"],
            "temperature": ["TEMP", "HOT", "COLD"],
            "precipitation": ["RAIN", "SNOW"],
            "weather": ["TEMP", "RAIN", "SNOW", "HURRICANE"],
        }

        logger.info(
            f"Market cache initialized (refresh interval: {refresh_interval_seconds}s)"
        )

    async def start(self):
        """Start background refresh loop"""
        self.running = True
        logger.info("Market cache background refresh started")

        # Initial load
        await self.refresh()

        # Background refresh loop
        while self.running:
            try:
                await asyncio.sleep(self.refresh_interval)
                if self.running:
                    await self.refresh()
            except Exception as e:
                logger.error(f"Error in market cache refresh loop: {e}")
                await asyncio.sleep(60)  # Wait 1min before retry

    async def refresh(self):
        """Refresh market data from Kalshi API"""
        start_time = datetime.utcnow()
        logger.info("Refreshing market cache...")

        try:
            # Fetch all open markets
            markets = self.kalshi.get_markets(status="open", limit=1000)

            if not markets:
                logger.warning("No markets returned from API")
                return

            # Clear old cache
            self.markets = markets
            self.markets_by_ticker = {}
            self.markets_by_keyword = defaultdict(list)
            self.market_prices = {}

            # Index markets
            for market in markets:
                ticker = market.ticker
                self.markets_by_ticker[ticker] = market
                self.market_prices[ticker] = market.last_price or 0.50

                # Index by keywords
                ticker_upper = ticker.upper()
                for keyword, patterns in self.keyword_patterns.items():
                    for pattern in patterns:
                        if pattern in ticker_upper:
                            self.markets_by_keyword[keyword].append(ticker)
                            break

            # Update state
            self.last_refresh = datetime.utcnow()
            self.refresh_count += 1

            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"✅ Market cache refreshed: {len(markets)} markets in {elapsed:.2f}s "
                f"(refresh #{self.refresh_count})"
            )

            # Log cache stats
            self._log_cache_stats()

        except Exception as e:
            logger.error(f"Error refreshing market cache: {e}")

    def _log_cache_stats(self):
        """Log cache statistics"""
        keyword_counts = {k: len(v) for k, v in self.markets_by_keyword.items()}
        top_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        logger.info(
            f"Cache stats: {len(self.markets)} markets, "
            f"{len(self.markets_by_keyword)} keyword groups"
        )
        logger.info(f"Top keywords: {top_keywords}")

    def get_markets_by_keywords(self, keywords: List[str]) -> List[str]:
        """
        Get market tickers matching any of the keywords.

        Args:
            keywords: List of keywords to search for

        Returns:
            List of matching market tickers (deduplicated)
        """
        matching_tickers = set()

        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in self.markets_by_keyword:
                matching_tickers.update(self.markets_by_keyword[keyword_lower])

        return list(matching_tickers)

    def get_market(self, ticker: str):
        """Get market by ticker"""
        return self.markets_by_ticker.get(ticker)

    def get_price(self, ticker: str) -> Optional[float]:
        """Get current price for ticker"""
        return self.market_prices.get(ticker)

    def get_all_prices(self) -> Dict[str, float]:
        """Get all market prices"""
        return self.market_prices.copy()

    def get_all_tickers(self) -> List[str]:
        """Get all market tickers"""
        return list(self.markets_by_ticker.keys())

    def is_stale(self, max_age_seconds: int = 600) -> bool:
        """Check if cache is stale"""
        if not self.last_refresh:
            return True
        age = (datetime.utcnow() - self.last_refresh).total_seconds()
        return age > max_age_seconds

    def get_cache_info(self) -> Dict:
        """Get cache information"""
        age_seconds = (
            (datetime.utcnow() - self.last_refresh).total_seconds()
            if self.last_refresh
            else None
        )

        return {
            "total_markets": len(self.markets),
            "last_refresh": self.last_refresh.isoformat() if self.last_refresh else None,
            "age_seconds": age_seconds,
            "refresh_count": self.refresh_count,
            "is_stale": self.is_stale(),
            "keyword_groups": len(self.markets_by_keyword),
        }

    async def stop(self):
        """Stop background refresh"""
        self.running = False
        logger.info("Market cache stopped")


# Singleton instance
_market_cache = None


def get_market_cache(kalshi_client=None):
    """Get singleton instance of market cache"""
    global _market_cache
    if _market_cache is None and kalshi_client:
        _market_cache = MarketCache(kalshi_client)
    return _market_cache
