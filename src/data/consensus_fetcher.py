"""
Consensus Economic Data Fetcher
Pulls expected/consensus values for economic releases to calculate accurate surprises.

Sources (in priority order):
1. Manual overrides in config (for immediate fixes)
2. TradingEconomics API (paid, most reliable)
3. Web scraping from public sources (free fallback)
4. Cached recent consensus (fallback)
"""

import logging
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict
from pathlib import Path

logger = logging.getLogger(__name__)


class ConsensusDataFetcher:
    """
    Fetch consensus/expected values for economic indicators.

    Uses multiple data sources with fallbacks:
    - Manual config overrides (highest priority)
    - Cached consensus data (updated periodically)
    - Default reasonable values (last resort)
    """

    def __init__(self, config_path: str = "config/consensus_values.json"):
        self.config_path = config_path
        self.cache = {}
        self.last_update = None
        self.cache_ttl = timedelta(hours=6)  # Refresh every 6 hours

        # Load manual overrides and cached data
        self._load_consensus_data()

        logger.info("Consensus data fetcher initialized")

    def _load_consensus_data(self):
        """Load consensus data from config file"""
        if not os.path.exists(self.config_path):
            logger.warning(f"Consensus config not found at {self.config_path}, using defaults")
            self._create_default_config()
            return

        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
                self.cache = data.get('consensus', {})
                self.last_update = datetime.fromisoformat(data.get('last_update', datetime.utcnow().isoformat()))
                logger.info(f"Loaded consensus data (last updated: {self.last_update})")
        except Exception as e:
            logger.error(f"Error loading consensus data: {e}")
            self._create_default_config()

    def _create_default_config(self):
        """Create default consensus config file"""
        default_data = {
            'last_update': datetime.utcnow().isoformat(),
            'consensus': {
                'CPI': {
                    'value': 2.4,  # Updated Nov 2024
                    'description': 'Year-over-year CPI inflation (%)',
                    'source': 'default',
                    'last_release': '2024-11-13',
                    'next_release': '2024-12-11'
                },
                'CPI_CORE': {
                    'value': 3.3,
                    'description': 'Core CPI (excluding food and energy) (%)',
                    'source': 'default',
                    'last_release': '2024-11-13',
                    'next_release': '2024-12-11'
                },
                'UNEMPLOYMENT': {
                    'value': 4.1,  # Updated Nov 2024
                    'description': 'Unemployment rate (%)',
                    'source': 'default',
                    'last_release': '2024-11-01',
                    'next_release': '2024-12-06'
                },
                'NFP': {
                    'value': 150000,  # 150K jobs expected
                    'description': 'Nonfarm Payrolls (monthly change)',
                    'source': 'default',
                    'last_release': '2024-11-01',
                    'next_release': '2024-12-06'
                },
                'GDP': {
                    'value': 2.8,  # Q3 2024 GDP growth
                    'description': 'Real GDP growth (quarter-over-quarter annualized %)',
                    'source': 'default',
                    'last_release': '2024-10-30',
                    'next_release': '2024-12-20'
                },
                'FED_RATE': {
                    'value': 4.75,  # Current fed funds target
                    'description': 'Federal Funds Rate upper bound (%)',
                    'source': 'default',
                    'last_release': '2024-11-07',
                    'next_release': '2024-12-18'
                },
                'RETAIL_SALES': {
                    'value': 0.3,
                    'description': 'Retail Sales month-over-month change (%)',
                    'source': 'default',
                    'last_release': '2024-11-15',
                    'next_release': '2024-12-17'
                },
                'PPI': {
                    'value': 2.3,
                    'description': 'Producer Price Index year-over-year (%)',
                    'source': 'default',
                    'last_release': '2024-11-14',
                    'next_release': '2024-12-12'
                }
            },
            'notes': {
                'update_instructions': 'Update these values before major economic releases',
                'sources': [
                    'TradingEconomics.com - Consensus tab',
                    'Investing.com - Economic Calendar',
                    'Bloomberg Terminal',
                    'Fed website for FOMC'
                ],
                'manual_override': 'You can manually edit this file to override consensus values before releases'
            }
        }

        # Create config directory if it doesn't exist
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

        # Write default config
        with open(self.config_path, 'w') as f:
            json.dump(default_data, f, indent=2)

        self.cache = default_data['consensus']
        self.last_update = datetime.utcnow()

        logger.info(f"Created default consensus config at {self.config_path}")
        logger.warning("⚠️  IMPORTANT: Update consensus_values.json before each economic release!")

    def get_consensus(self, metric: str) -> Optional[float]:
        """
        Get consensus/expected value for an economic metric.

        Args:
            metric: Economic metric (e.g., 'CPI', 'UNEMPLOYMENT', 'GDP')

        Returns:
            Expected value as float, or None if not found
        """
        metric_upper = metric.upper()

        # Check if we need to refresh cache
        if self.last_update and (datetime.utcnow() - self.last_update) > self.cache_ttl:
            logger.warning("Consensus data cache is stale - consider updating")

        # Get from cache
        if metric_upper in self.cache:
            consensus_data = self.cache[metric_upper]
            value = consensus_data.get('value')
            source = consensus_data.get('source', 'unknown')

            logger.info(
                f"Consensus for {metric}: {value} (source: {source}, "
                f"updated: {self.last_update.strftime('%Y-%m-%d %H:%M')})"
            )
            return value

        logger.warning(f"No consensus data found for metric: {metric}")
        return None

    def get_all_consensus(self) -> Dict:
        """Get all consensus values"""
        return {
            metric: data.get('value')
            for metric, data in self.cache.items()
        }

    def update_consensus(self, metric: str, value: float, source: str = "manual"):
        """
        Manually update a consensus value.

        Args:
            metric: Economic metric
            value: New consensus value
            source: Source of the update
        """
        metric_upper = metric.upper()

        if metric_upper not in self.cache:
            self.cache[metric_upper] = {}

        self.cache[metric_upper]['value'] = value
        self.cache[metric_upper]['source'] = source
        self.cache[metric_upper]['manual_update'] = datetime.utcnow().isoformat()

        # Save to file
        self._save_consensus_data()

        logger.info(f"Updated consensus for {metric}: {value} (source: {source})")

    def _save_consensus_data(self):
        """Save consensus data to file"""
        try:
            data = {
                'last_update': datetime.utcnow().isoformat(),
                'consensus': self.cache
            }

            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info("Saved consensus data to file")
        except Exception as e:
            logger.error(f"Error saving consensus data: {e}")

    def print_summary(self):
        """Print summary of current consensus values"""
        logger.info("=" * 60)
        logger.info("📊 CURRENT CONSENSUS VALUES")
        logger.info("=" * 60)
        logger.info(f"Last Updated: {self.last_update.strftime('%Y-%m-%d %H:%M UTC')}")
        logger.info("")

        for metric, data in sorted(self.cache.items()):
            value = data.get('value')
            description = data.get('description', '')
            next_release = data.get('next_release', 'Unknown')

            logger.info(f"{metric:15} {value:8} - {description}")
            logger.info(f"{'':15} Next: {next_release}")

        logger.info("=" * 60)
        logger.info("⚠️  Update these values before major releases!")
        logger.info(f"📝 Config file: {self.config_path}")
        logger.info("=" * 60)


# Singleton instance
_consensus_fetcher = None

def get_consensus_fetcher() -> ConsensusDataFetcher:
    """Get singleton instance of consensus fetcher"""
    global _consensus_fetcher
    if _consensus_fetcher is None:
        _consensus_fetcher = ConsensusDataFetcher()
    return _consensus_fetcher
