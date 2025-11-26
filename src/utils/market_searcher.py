"""
Universal Kalshi Market Searcher
Searches for Kalshi markets related to any news message using keyword matching.
"""

import logging
import re
from typing import List, Dict, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MarketMatch:
    """Represents a Kalshi market matched to news"""
    ticker: str
    title: str
    close_time: str
    match_score: float  # 0-1, how well it matches
    matched_keywords: List[str]
    current_price: float = None


class UniversalMarketSearcher:
    """
    Search Kalshi markets using keyword matching.
    Works with ANY news type (economic, political, sports, weather, etc.)
    """

    def __init__(self, market_cache):
        """
        Initialize searcher with market cache.

        Args:
            market_cache: MarketCache instance with all Kalshi markets
        """
        self.market_cache = market_cache

    def search_markets(
        self,
        keywords: List[str],
        min_match_score: float = 0.3,
        max_results: int = 10
    ) -> List[MarketMatch]:
        """
        Search for Kalshi markets related to keywords.

        Args:
            keywords: List of keywords from news text
            min_match_score: Minimum match score (0-1) to include
            max_results: Maximum markets to return

        Returns:
            List of MarketMatch objects sorted by match score
        """
        if not keywords:
            return []

        markets = self.market_cache.get_all_markets()
        if not markets:
            logger.warning("No markets in cache")
            return []

        matches = []

        for ticker, market_data in markets.items():
            title = market_data.get('title', '').lower()
            subtitle = market_data.get('subtitle', '').lower()

            # Combine title and subtitle for matching
            searchable_text = f"{title} {subtitle}"

            # Calculate match score
            matched_keywords = []
            match_score = 0.0

            for keyword in keywords:
                keyword_lower = keyword.lower()

                # Exact match in ticker (highest priority)
                if keyword_lower in ticker.lower():
                    match_score += 2.0
                    matched_keywords.append(keyword)

                # Exact match in title
                elif keyword_lower in title:
                    match_score += 1.5
                    matched_keywords.append(keyword)

                # Exact match in subtitle
                elif keyword_lower in subtitle:
                    match_score += 1.0
                    matched_keywords.append(keyword)

                # Partial match (word boundary)
                elif re.search(rf'\b{re.escape(keyword_lower)}\w*', searchable_text):
                    match_score += 0.5
                    matched_keywords.append(keyword)

            # Normalize score (0-1)
            if len(keywords) > 0:
                match_score = min(1.0, match_score / (len(keywords) * 2.0))

            # Add to matches if above threshold
            if match_score >= min_match_score:
                matches.append(MarketMatch(
                    ticker=ticker,
                    title=market_data.get('title', ''),
                    close_time=market_data.get('close_time', ''),
                    match_score=match_score,
                    matched_keywords=matched_keywords,
                    current_price=market_data.get('yes_bid', None)
                ))

        # Sort by match score (highest first)
        matches.sort(key=lambda m: m.match_score, reverse=True)

        # Limit results
        results = matches[:max_results]

        if results:
            logger.info(
                f"Found {len(results)} markets for keywords {keywords[:5]}... "
                f"(top match: {results[0].ticker} score={results[0].match_score:.2f})"
            )
        else:
            logger.debug(f"No markets found for keywords: {keywords}")

        return results

    def search_by_text(
        self,
        news_text: str,
        keywords: List[str] = None,
        min_match_score: float = 0.3,
        max_results: int = 10
    ) -> List[MarketMatch]:
        """
        Search for markets related to news text.

        Args:
            news_text: Raw news text
            keywords: Pre-extracted keywords (optional, will extract if not provided)
            min_match_score: Minimum match score
            max_results: Maximum markets to return

        Returns:
            List of MarketMatch objects
        """
        # Extract keywords if not provided
        if keywords is None:
            from src.utils.keyword_extractor import KeywordExtractor
            keywords = KeywordExtractor.extract_keywords(news_text)

        # Search for markets
        return self.search_markets(keywords, min_match_score, max_results)

    def get_market_prices(self, matches: List[MarketMatch]) -> Dict[str, float]:
        """
        Get current prices for matched markets.

        Args:
            matches: List of MarketMatch objects

        Returns:
            Dict of {ticker: price}
        """
        prices = {}
        for match in matches:
            if match.current_price is not None:
                prices[match.ticker] = match.current_price
            else:
                # Try to fetch from cache
                market = self.market_cache.get_market(match.ticker)
                if market:
                    prices[match.ticker] = market.get('yes_bid', 0.5)

        return prices

    def filter_by_close_time(
        self,
        matches: List[MarketMatch],
        min_hours_remaining: int = 1
    ) -> List[MarketMatch]:
        """
        Filter matches by close time (only include markets closing soon).

        Args:
            matches: List of MarketMatch objects
            min_hours_remaining: Minimum hours until close

        Returns:
            Filtered list of matches
        """
        from datetime import datetime, timedelta

        filtered = []
        now = datetime.utcnow()
        min_time = now + timedelta(hours=min_hours_remaining)

        for match in matches:
            if match.close_time:
                try:
                    close_time = datetime.fromisoformat(match.close_time.replace('Z', '+00:00'))
                    if close_time >= min_time:
                        filtered.append(match)
                except:
                    # If can't parse, include it anyway
                    filtered.append(match)
            else:
                filtered.append(match)

        return filtered
