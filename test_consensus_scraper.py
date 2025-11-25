#!/usr/bin/env python3
"""
Test Automated Consensus Scraper
Verifies that automated consensus fetching works
"""

import asyncio
import logging
from src.data.consensus_fetcher import get_consensus_fetcher
from src.data.consensus_scraper import get_consensus_scraper

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_consensus_scraper():
    """Test the automated consensus scraper"""

    logger.info("="*60)
    logger.info("🧪 TESTING AUTOMATED CONSENSUS SCRAPER")
    logger.info("="*60)

    # Get consensus fetcher
    consensus_fetcher = get_consensus_fetcher()

    logger.info("\n📊 Current consensus values (before update):")
    consensus_fetcher.print_summary()

    # Get scraper
    scraper = get_consensus_scraper(consensus_fetcher)

    logger.info("\n🔄 Testing automated consensus fetch...")
    updated_count = await scraper.update_all_consensus()

    logger.info(f"\n✅ Update complete: {updated_count} indicators updated")

    logger.info("\n📊 Updated consensus values:")
    consensus_fetcher.print_summary()

    logger.info("\n" + "="*60)
    logger.info("✅ TEST COMPLETE")
    logger.info("="*60)

    # Show what was updated
    logger.info("\nKey metrics:")
    for metric in ['CPI', 'UNEMPLOYMENT', 'GDP']:
        value = consensus_fetcher.get_consensus(metric)
        logger.info(f"  {metric}: {value}%")


if __name__ == "__main__":
    asyncio.run(test_consensus_scraper())
