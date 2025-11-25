"""
Automated Consensus Data Scraper
Automatically fetches expected values from free public sources.
Runs daily to keep consensus data fresh without manual updates.

Sources (in priority order):
1. TradingEconomics.com API (free tier)
2. FRED API (Federal Reserve Economic Data) - free
3. Web scraping TradingEconomics as fallback
"""

import logging
import requests
import re
from datetime import datetime, timedelta
from typing import Optional, Dict
import asyncio

logger = logging.getLogger(__name__)


class ConsensusScraper:
    """
    Automatically fetch consensus/expected values from public sources.

    Updates consensus data daily without manual intervention.
    """

    def __init__(self, consensus_fetcher):
        self.consensus_fetcher = consensus_fetcher
        self.last_update = None
        self.update_interval = timedelta(hours=12)  # Update twice daily

        # TradingEconomics country code
        self.country = "united-states"

        logger.info("Consensus scraper initialized - will auto-update every 12 hours")

    async def auto_update_loop(self):
        """Background loop to auto-update consensus data"""
        while True:
            try:
                logger.info("Starting automated consensus update...")
                await self.update_all_consensus()
                self.last_update = datetime.utcnow()
                logger.info(f"✅ Consensus auto-update completed at {self.last_update}")

                # Wait 12 hours before next update
                await asyncio.sleep(self.update_interval.total_seconds())

            except Exception as e:
                logger.error(f"Error in consensus auto-update loop: {e}")
                # Wait 1 hour before retry on error
                await asyncio.sleep(3600)

    async def update_all_consensus(self):
        """Update all economic indicators"""
        indicators = [
            ('CPI', 'inflation-cpi'),
            ('UNEMPLOYMENT', 'unemployment-rate'),
            ('GDP', 'gdp-growth-annual'),
            ('NFP', 'non-farm-payrolls'),
            ('RETAIL_SALES', 'retail-sales-mom'),
        ]

        updated_count = 0
        for metric, te_indicator in indicators:
            try:
                value = await self.fetch_consensus(metric, te_indicator)
                if value is not None:
                    self.consensus_fetcher.update_consensus(
                        metric,
                        value,
                        source='auto-scraped'
                    )
                    updated_count += 1
                    logger.info(f"✅ Auto-updated {metric}: {value}%")
                else:
                    logger.warning(f"⚠️  Could not fetch consensus for {metric}")
            except Exception as e:
                logger.error(f"Error fetching {metric}: {e}")

        logger.info(f"Auto-updated {updated_count}/{len(indicators)} indicators")
        return updated_count

    async def fetch_consensus(self, metric: str, te_indicator: str) -> Optional[float]:
        """
        Fetch consensus from TradingEconomics.com

        Uses their free economic calendar page (no API key needed)
        """
        try:
            # Method 1: Try FRED API first (most reliable, free)
            if metric in ['CPI', 'UNEMPLOYMENT', 'GDP']:
                fred_value = await self._fetch_from_fred(metric)
                if fred_value is not None:
                    return fred_value

            # Method 2: Scrape TradingEconomics calendar
            te_value = await self._scrape_tradingeconomics(metric, te_indicator)
            if te_value is not None:
                return te_value

            # Method 3: Scrape Investing.com as final fallback
            investing_value = await self._scrape_investing(metric)
            if investing_value is not None:
                return investing_value

            return None

        except Exception as e:
            logger.error(f"Error fetching consensus for {metric}: {e}")
            return None

    async def _fetch_from_fred(self, metric: str) -> Optional[float]:
        """
        Fetch from FRED (Federal Reserve Economic Data) - free API, no key needed

        Note: FRED has actual data, not consensus forecasts
        We use the latest actual as a baseline when no consensus available
        """
        try:
            # FRED series IDs
            fred_series = {
                'CPI': 'CPIAUCSL',  # CPI All Urban Consumers
                'UNEMPLOYMENT': 'UNRATE',  # Unemployment Rate
                'GDP': 'A191RL1Q225SBEA',  # Real GDP % change
            }

            if metric not in fred_series:
                return None

            series_id = fred_series[metric]

            # FRED API endpoint (no key needed for basic access)
            url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"

            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                return None

            # Parse CSV to get latest value
            lines = response.text.strip().split('\n')
            if len(lines) < 2:
                return None

            # Last line has most recent data
            last_line = lines[-1]
            parts = last_line.split(',')

            if len(parts) >= 2:
                try:
                    value = float(parts[1])
                    logger.info(f"FRED latest {metric}: {value}%")
                    # Use latest actual as baseline for consensus
                    return value
                except ValueError:
                    return None

            return None

        except Exception as e:
            logger.debug(f"FRED fetch failed for {metric}: {e}")
            return None

    async def _scrape_tradingeconomics(self, metric: str, indicator: str) -> Optional[float]:
        """
        Scrape consensus from TradingEconomics.com calendar

        Free, no API key needed, but may break if they change HTML structure
        """
        try:
            url = f"https://tradingeconomics.com/{self.country}/{indicator}"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                logger.debug(f"TradingEconomics returned {response.status_code}")
                return None

            # Look for "Forecast" or "Consensus" in the HTML
            # Pattern: looks for numbers near "Forecast" keyword
            patterns = [
                r'Forecast[:\s]+?([\d.]+)%?',
                r'Consensus[:\s]+?([\d.]+)%?',
                r'Expected[:\s]+?([\d.]+)%?',
            ]

            for pattern in patterns:
                match = re.search(pattern, response.text, re.IGNORECASE)
                if match:
                    value = float(match.group(1))
                    logger.info(f"TradingEconomics scraped {metric}: {value}%")
                    return value

            return None

        except Exception as e:
            logger.debug(f"TradingEconomics scrape failed for {metric}: {e}")
            return None

    async def _scrape_investing(self, metric: str) -> Optional[float]:
        """
        Scrape from Investing.com economic calendar as final fallback
        """
        try:
            # Map metrics to Investing.com event IDs
            investing_events = {
                'CPI': 'cpi',
                'UNEMPLOYMENT': 'unemployment-rate',
                'GDP': 'gdp-growth-rate',
                'NFP': 'nonfarm-payrolls',
            }

            if metric not in investing_events:
                return None

            event = investing_events[metric]
            url = f"https://www.investing.com/economic-calendar/{event}-733"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                return None

            # Look for forecast value in HTML
            patterns = [
                r'Forecast.*?>([\d.]+)%?<',
                r'forecast.*?>([\d.]+)%?<',
            ]

            for pattern in patterns:
                match = re.search(pattern, response.text, re.IGNORECASE)
                if match:
                    value = float(match.group(1))
                    logger.info(f"Investing.com scraped {metric}: {value}%")
                    return value

            return None

        except Exception as e:
            logger.debug(f"Investing.com scrape failed for {metric}: {e}")
            return None

    def should_update(self) -> bool:
        """Check if consensus data needs updating"""
        if not self.last_update:
            return True

        age = datetime.utcnow() - self.last_update
        return age > self.update_interval

    async def force_update(self):
        """Force immediate update (for manual trigger)"""
        logger.info("🔄 Forcing consensus update...")
        count = await self.update_all_consensus()
        logger.info(f"✅ Force update complete: {count} indicators updated")
        return count


# Singleton instance
_consensus_scraper = None


def get_consensus_scraper(consensus_fetcher=None):
    """Get singleton instance of consensus scraper"""
    global _consensus_scraper
    if _consensus_scraper is None and consensus_fetcher:
        _consensus_scraper = ConsensusScraper(consensus_fetcher)
    return _consensus_scraper


async def start_auto_update(consensus_fetcher):
    """
    Start background consensus auto-update loop.

    Call this from main.py to enable automated consensus updates.
    """
    scraper = get_consensus_scraper(consensus_fetcher)

    # Do immediate update on startup
    logger.info("🔄 Running initial consensus update...")
    await scraper.update_all_consensus()

    # Start background loop
    logger.info("🔄 Starting consensus auto-update background loop (every 12 hours)")
    await scraper.auto_update_loop()
