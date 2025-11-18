"""
Pattern Detection Strategy
Identifies and exploits behavioral biases in prediction markets.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import numpy as np

from src.edge_detection.speed_arbitrage import TradeSignal

logger = logging.getLogger(__name__)


class RecencyBiasDetector:
    """
    Detect and exploit recency bias.

    Markets tend to overreact to recent news, creating mean reversion opportunities.
    """

    def __init__(self, config: Dict):
        self.lookback_days = config.get("lookback_days", 7)
        self.reversal_threshold = config.get("reversal_threshold", 0.20)

    def analyze_market(
        self, ticker: str, price_history: List[Dict], current_price: float
    ) -> Optional[TradeSignal]:
        """
        Analyze a market for recency bias.

        Args:
            ticker: Market ticker
            price_history: List of {'timestamp': datetime, 'price': float}
            current_price: Current market price

        Returns:
            Trade signal if opportunity found
        """
        if len(price_history) < 10:
            return None

        # Calculate 7-day price change
        cutoff = datetime.now() - timedelta(days=self.lookback_days)
        recent_prices = [
            p["price"]
            for p in price_history
            if p.get("timestamp", datetime.min) > cutoff
        ]

        if len(recent_prices) < 3:
            return None

        # Check for large recent move
        week_ago_price = recent_prices[0]
        price_change = current_price - week_ago_price

        # If moved >20% recently, bet on mean reversion
        if abs(price_change) > self.reversal_threshold:
            # Calculate historical mean (excluding recent spike)
            older_prices = [
                p["price"]
                for p in price_history
                if p.get("timestamp", datetime.min) < cutoff
            ]

            if len(older_prices) < 5:
                return None

            historical_mean = np.mean(older_prices)

            # Fair value is historical mean
            fair_value = historical_mean
            edge = abs(fair_value - current_price)

            if edge < 0.05:  # Minimum 5% edge
                return None

            # Trade toward mean
            if current_price > historical_mean:
                # Market too high, bet NO
                side = "no"
                reasoning = f"Market moved up {price_change:.1%} in {self.lookback_days} days. " \
                           f"Current {current_price:.1%} vs historical mean {historical_mean:.1%}. " \
                           f"Betting on mean reversion."
            else:
                # Market too low, bet YES
                side = "yes"
                reasoning = f"Market moved down {abs(price_change):.1%} in {self.lookback_days} days. " \
                           f"Current {current_price:.1%} vs historical mean {historical_mean:.1%}. " \
                           f"Betting on mean reversion."

            signal = TradeSignal(
                signal_id=f"recency_{ticker}_{datetime.now().timestamp()}",
                timestamp=datetime.utcnow(),
                source="recency_bias",
                ticker=ticker,
                side=side,
                signal_type="BUY",
                confidence=0.65,
                edge_percentage=edge,
                current_price=current_price,
                fair_value=fair_value,
                reasoning=reasoning,
            )

            logger.info(f"Recency bias signal: {signal}")
            return signal

        return None


class FavoriteLongshotDetector:
    """
    Detect favorite-longshot bias.

    People overbet longshots (low probability events) and underbet favorites.
    Middle probabilities (40-60%) often offer better value.
    """

    def __init__(self, config: Dict):
        self.extreme_threshold = config.get("extreme_probability_threshold", 0.10)

    def analyze_market(
        self, ticker: str, current_price: float, volume: float
    ) -> Optional[TradeSignal]:
        """
        Identify favorite-longshot bias opportunities.

        Strategy:
        - Avoid markets <10% or >90% (biased pricing)
        - Focus on middle probabilities
        - Look for value in favorites that are underpriced
        """
        # Check if extreme probability (avoid these)
        if current_price < self.extreme_threshold or current_price > (
            1 - self.extreme_threshold
        ):
            logger.debug(
                f"Skipping {ticker}: extreme probability {current_price:.1%}"
            )
            return None

        # Check if in the "sweet spot" (40-60%)
        if 0.40 <= current_price <= 0.60:
            # These often have less bias
            # Would need historical data to determine if underpriced
            # For now, just flag as potential opportunity
            pass

        return None  # Placeholder - would need more sophisticated modeling


class LowLiquidityDetector:
    """
    Exploit inefficiencies in low-liquidity markets.

    Low-volume markets often have wide spreads and inefficient pricing.
    """

    def __init__(self, config: Dict):
        self.min_volume_threshold = config.get("min_volume_threshold", 10000)
        self.min_spread_threshold = config.get("min_spread_threshold", 0.05)

    def analyze_market(
        self,
        ticker: str,
        bid_price: float,
        ask_price: float,
        volume: float,
        fair_value: Optional[float] = None,
    ) -> Optional[TradeSignal]:
        """
        Identify low-liquidity opportunities.

        Args:
            ticker: Market ticker
            bid_price: Best bid
            ask_price: Best ask
            volume: 24h volume
            fair_value: Optional model-derived fair value

        Returns:
            Signal to provide liquidity at better mid-market price
        """
        # Check if low volume
        if volume > self.min_volume_threshold:
            return None

        # Check if wide spread
        spread = ask_price - bid_price

        if spread < self.min_spread_threshold:
            return None

        # If we have a fair value estimate, use it
        if fair_value is not None:
            mid_price = (bid_price + ask_price) / 2
            edge = abs(fair_value - mid_price)

            if edge > 0.03:  # 3% edge minimum
                side = "yes" if fair_value > mid_price else "no"

                signal = TradeSignal(
                    signal_id=f"liquidity_{ticker}_{datetime.now().timestamp()}",
                    timestamp=datetime.utcnow(),
                    source="low_liquidity",
                    ticker=ticker,
                    side=side,
                    signal_type="BUY",
                    confidence=0.60,
                    edge_percentage=edge,
                    current_price=mid_price,
                    fair_value=fair_value,
                    reasoning=f"Low liquidity market (vol=${volume:.0f}). "
                    f"Wide spread {spread:.1%}. "
                    f"Fair value {fair_value:.1%} vs mid {mid_price:.1%}",
                )

                logger.info(f"Low liquidity signal: {signal}")
                return signal

        # Even without fair value, can provide liquidity at better mid-price
        # This is more of a market-making strategy
        return None


class PatternDetector:
    """
    Master pattern detection class that coordinates multiple bias detectors.
    """

    def __init__(self, config: Dict):
        self.config = config

        # Initialize sub-detectors
        self.recency_detector = None
        self.favorite_longshot_detector = None
        self.low_liquidity_detector = None

        if config.get("recency_bias", {}).get("enabled", False):
            self.recency_detector = RecencyBiasDetector(config["recency_bias"])

        if config.get("favorite_longshot", {}).get("enabled", False):
            self.favorite_longshot_detector = FavoriteLongshotDetector(
                config["favorite_longshot"]
            )

        if config.get("low_liquidity", {}).get("enabled", False):
            self.low_liquidity_detector = LowLiquidityDetector(config["low_liquidity"])

        logger.info("Pattern detector initialized")

    def analyze_markets(
        self,
        market_data: List[Dict],
        price_histories: Dict[str, List[Dict]],
    ) -> List[TradeSignal]:
        """
        Scan all markets for pattern-based opportunities.

        Args:
            market_data: List of market dicts with ticker, price, volume, bid, ask
            price_histories: Dict of ticker -> price history

        Returns:
            List of trade signals
        """
        signals = []

        for market in market_data:
            ticker = market.get("ticker")
            current_price = market.get("price")
            volume = market.get("volume", 0)
            bid = market.get("bid", current_price - 0.05)
            ask = market.get("ask", current_price + 0.05)

            if not ticker or current_price is None:
                continue

            # Recency bias
            if self.recency_detector:
                price_history = price_histories.get(ticker, [])
                signal = self.recency_detector.analyze_market(
                    ticker, price_history, current_price
                )
                if signal:
                    signals.append(signal)

            # Favorite-longshot
            if self.favorite_longshot_detector:
                signal = self.favorite_longshot_detector.analyze_market(
                    ticker, current_price, volume
                )
                if signal:
                    signals.append(signal)

            # Low liquidity
            if self.low_liquidity_detector:
                signal = self.low_liquidity_detector.analyze_market(
                    ticker, bid, ask, volume
                )
                if signal:
                    signals.append(signal)

        logger.info(f"Pattern detector generated {len(signals)} signals")
        return signals
