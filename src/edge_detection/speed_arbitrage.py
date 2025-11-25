"""
Speed Arbitrage Engine
Identifies and exploits pricing inefficiencies from news events before markets fully adjust.
"""

import logging
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from src.monitors.news_monitor import NewsEvent, EventType
from src.data.consensus_fetcher import get_consensus_fetcher

logger = logging.getLogger(__name__)


@dataclass
class TradeSignal:
    """Represents a trading signal"""

    signal_id: str
    timestamp: datetime
    source: str  # Which strategy generated this
    ticker: str
    side: str  # 'yes' or 'no'
    signal_type: str  # 'BUY' or 'SELL'
    confidence: float  # 0-1
    edge_percentage: float  # Expected edge
    current_price: Optional[float]
    fair_value: float  # Model-derived fair price
    reasoning: str  # Human-readable explanation
    event_data: Optional[Dict] = None

    def __repr__(self):
        return (
            f"Signal({self.ticker}, {self.signal_type} {self.side} @ "
            f"{self.current_price}, edge={self.edge_percentage:.1%}, "
            f"confidence={self.confidence:.2f})"
        )


class EconomicDataParser:
    """Parse economic data releases and calculate expected impact"""

    # Expected market reactions to economic surprises
    CPI_IMPACT_PER_TENTH = 0.05  # 5% market move per 0.1% CPI surprise
    UNEMPLOYMENT_IMPACT = 0.08  # 8% market move per 0.1% unemployment surprise
    GDP_IMPACT = 0.03  # 3% market move per 0.1% GDP surprise

    @staticmethod
    def extract_cpi_data(text: str) -> Optional[Dict]:
        """Extract CPI data from news text with enhanced patterns + expected value"""
        # Enhanced patterns to handle more variations including BossBot format
        patterns = [
            r"cpi\s*:?\s+([\d.]+)%",  # "CPI: 3.2%" or "CPI 3.2%"
            r"cpi\s+(?:at|of|is|rose to|fell to|comes in at)\s+([\d.]+)%",
            r"inflation\s*:?\s+([\d.]+)%",
            r"inflation\s+(?:at|is|rose to|fell to|comes in at)\s+([\d.]+)%",
            r"consumer price index\s*:?\s*([\d.]+)%",
            r"core\s+cpi\s*:?\s+([\d.]+)%",
        ]

        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                actual = float(match.group(1))

                # Try to extract expected value ("vs est 3.0%")
                expected = None
                expected_patterns = [
                    r"(?:vs|versus|v)\s+(?:est|expected|forecast|consensus)\s+([\d.]+)%",
                    r"(?:expected|est|forecast)\s+([\d.]+)%",
                ]
                for exp_pattern in expected_patterns:
                    exp_match = re.search(exp_pattern, text.lower())
                    if exp_match:
                        expected = float(exp_match.group(1))
                        break

                return {"metric": "CPI", "value": actual, "expected": expected, "unit": "percent"}

        return None

    @staticmethod
    def extract_unemployment_data(text: str) -> Optional[Dict]:
        """Extract unemployment data from news text"""
        patterns = [
            r"unemployment\s+(?:rate\s+)?(?:at|is|rose to|fell to)\s+([\d.]+)%",
            r"jobless\s+(?:rate\s+)?(?:at|is)\s+([\d.]+)%",
        ]

        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                value = float(match.group(1))
                return {"metric": "UNEMPLOYMENT", "value": value, "unit": "percent"}

        return None

    @staticmethod
    def extract_gdp_data(text: str) -> Optional[Dict]:
        """Extract GDP growth data from news text"""
        patterns = [
            r"gdp\s+(?:growth\s+)?(?:at|is|grew|expanded)\s+([\d.]+)%",
            r"economic growth\s+(?:at|is)\s+([\d.]+)%",
        ]

        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                value = float(match.group(1))
                return {"metric": "GDP", "value": value, "unit": "percent"}

        return None

    @classmethod
    def extract_economic_data(cls, text: str) -> Optional[Dict]:
        """Extract any economic data from text"""
        # Try each parser
        for parser in [
            cls.extract_cpi_data,
            cls.extract_unemployment_data,
            cls.extract_gdp_data,
        ]:
            result = parser(text)
            if result:
                return result

        return None

    @classmethod
    def calculate_surprise_impact(
        cls, metric: str, actual: float, expected: float
    ) -> float:
        """
        Calculate expected market impact from economic surprise.

        Returns:
            Expected probability change (e.g., 0.05 = 5% increase)
        """
        surprise = actual - expected

        if metric == "CPI":
            # Higher CPI = higher inflation probability
            return surprise * 10 * cls.CPI_IMPACT_PER_TENTH

        elif metric == "UNEMPLOYMENT":
            # Higher unemployment = more likely recession
            return surprise * 10 * cls.UNEMPLOYMENT_IMPACT

        elif metric == "GDP":
            # Higher GDP = less likely recession
            return -surprise * 10 * cls.GDP_IMPACT  # Negative because inverse

        return 0.0


class MarketMatcher:
    """Match news events to relevant Kalshi markets"""

    # Keyword to ticker patterns
    TICKER_PATTERNS = {
        "cpi": [r"CPI-\d{2}[A-Z]{3}\d{2}", r"INF-\d{2}[A-Z]{3}\d{2}"],
        "inflation": [r"INF-\d{2}[A-Z]{3}\d{2}", r"CPI-\d{2}[A-Z]{3}\d{2}"],
        "unemployment": [r"UNEMP-\d{2}[A-Z]{3}\d{2}", r"JOBS-\d{2}[A-Z]{3}\d{2}"],
        "gdp": [r"GDP-\d{2}Q\d"],
        "nonfarm": [r"NFP-\d{2}[A-Z]{3}\d{2}"],
        "fed": [r"FED-\d{2}[A-Z]{3}\d{2}", r"RATE-\d{2}[A-Z]{3}\d{2}"],
        "hurricane": [r"HURRICANE-"],
        "temperature": [r"TEMP-", r"HOT-", r"COLD-"],
        "precipitation": [r"RAIN-", r"SNOW-"],
    }

    @classmethod
    def find_related_markets(
        cls, event: NewsEvent, available_markets: List[str]
    ) -> List[str]:
        """
        Find Kalshi market tickers related to news event.

        Args:
            event: News event
            available_markets: List of all available market tickers

        Returns:
            List of related market tickers
        """
        related = []

        # Get relevant patterns based on keywords
        patterns_to_check = []
        for keyword in event.keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in cls.TICKER_PATTERNS:
                patterns_to_check.extend(cls.TICKER_PATTERNS[keyword_lower])

        # Match patterns against available markets
        for market_ticker in available_markets:
            for pattern in patterns_to_check:
                if re.search(pattern, market_ticker, re.IGNORECASE):
                    related.append(market_ticker)
                    break

        return related


class SpeedArbitrage:
    """
    Speed arbitrage strategy: React to news before market fully adjusts.

    Workflow:
    1. Receive news event
    2. Parse event details (what happened, actual vs expected)
    3. Identify affected markets
    4. Calculate fair value based on news
    5. Compare to current market price
    6. Generate signal if edge exceeds threshold
    """

    def __init__(self, config: Dict):
        self.config = config
        self.min_confidence = config.get("min_confidence", 0.70)
        self.min_edge = config.get("min_edge", 0.05)
        self.latency_target = config.get("latency_target_seconds", 10)

        # Initialize consensus data fetcher
        self.consensus_fetcher = get_consensus_fetcher()
        self.consensus_fetcher.print_summary()

        logger.info(
            f"Speed arbitrage initialized: min_confidence={self.min_confidence}, "
            f"min_edge={self.min_edge}"
        )

    def analyze_event(
        self, event: NewsEvent, available_markets: List[str], market_prices: Dict[str, float]
    ) -> List[TradeSignal]:
        """
        Analyze news event and generate trade signals.

        Args:
            event: News event to analyze
            available_markets: List of available market tickers
            market_prices: Dict of ticker -> current price

        Returns:
            List of trade signals
        """
        signals = []

        # Step 1: Find related markets
        related_markets = MarketMatcher.find_related_markets(event, available_markets)

        if not related_markets:
            logger.debug(f"No related markets found for event: {event.headline[:50]}")
            return signals

        # Step 2: Parse event data
        event_data = None
        expected_impact = 0.0

        if event.event_type == EventType.ECONOMIC_DATA:
            event_data = EconomicDataParser.extract_economic_data(event.content)

            if event_data:
                metric = event_data["metric"]
                actual = event_data["value"]

                # Prefer expected value from news text (most accurate & timely)
                # If not in news, fall back to cached consensus
                expected = event_data.get("expected")  # From BossBot "vs est X%"

                if expected is None:
                    # Fall back to consensus fetcher
                    expected = self.consensus_fetcher.get_consensus(metric)
                    source = "cached consensus"
                else:
                    source = "news text"

                if expected is None:
                    logger.warning(
                        f"No consensus data for {metric}, using actual value (no surprise)"
                    )
                    expected = actual  # Fallback: assume no surprise
                    source = "fallback (no surprise)"

                expected_impact = EconomicDataParser.calculate_surprise_impact(
                    metric, actual, expected
                )

                surprise = actual - expected
                logger.info(
                    f"Economic data: {metric}={actual}% (expected: {expected}% from {source}), "
                    f"surprise={surprise:+.2f}, impact={expected_impact:.2%}"
                )

        # Step 3: Generate signals for each related market
        for ticker in related_markets:
            current_price = market_prices.get(ticker)

            if current_price is None:
                continue

            # Calculate fair value based on impact
            if expected_impact != 0:
                # Determine direction based on ticker and event
                direction = self._determine_direction(ticker, event, event_data)

                if direction == "up":
                    fair_value = min(0.99, current_price + abs(expected_impact))
                    side = "yes"
                elif direction == "down":
                    fair_value = max(0.01, current_price - abs(expected_impact))
                    side = "yes"
                else:
                    continue

                # Calculate edge
                edge = abs(fair_value - current_price)

                # Check if edge meets threshold
                if edge < self.min_edge:
                    continue

                # Calculate confidence based on event reliability and data quality
                confidence = event.reliability_score * 0.8

                if event_data:
                    confidence += 0.2  # Boost for quantifiable data

                # Check if confidence meets threshold
                if confidence < self.min_confidence:
                    continue

                # Create signal
                signal = TradeSignal(
                    signal_id=f"speed_{event.event_id}_{ticker}",
                    timestamp=datetime.utcnow(),
                    source="speed_arbitrage",
                    ticker=ticker,
                    side=side,
                    signal_type="BUY",
                    confidence=confidence,
                    edge_percentage=edge,
                    current_price=current_price,
                    fair_value=fair_value,
                    reasoning=f"News: {event.headline[:100]}. "
                    f"Expected {direction} movement of {abs(expected_impact):.1%}. "
                    f"Current price {current_price:.2%} vs fair value {fair_value:.2%}",
                    event_data=event_data,
                )

                signals.append(signal)
                logger.info(f"Generated signal: {signal}")

        return signals

    def _determine_direction(
        self, ticker: str, event: NewsEvent, event_data: Optional[Dict]
    ) -> str:
        """
        Determine if market should move up or down based on news.

        Returns:
            'up', 'down', or 'none'
        """
        if not event_data:
            return "none"

        metric = event_data.get("metric")

        # CPI markets: higher inflation = YES to "CPI above X%"
        if "CPI" in ticker or "INF" in ticker:
            if metric == "CPI":
                return "up"  # Higher CPI increases probability

        # Unemployment markets: higher unemployment = YES to "unemployment above X%"
        if "UNEMP" in ticker or "JOBS" in ticker:
            if metric == "UNEMPLOYMENT":
                return "up"

        # GDP markets: higher GDP = NO to "recession" or YES to "growth above X%"
        if "GDP" in ticker:
            if metric == "GDP":
                if "RECESSION" in ticker:
                    return "down"  # Higher GDP = less recession risk
                else:
                    return "up"  # Higher GDP = more growth

        return "none"
