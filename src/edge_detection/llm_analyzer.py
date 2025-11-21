"""
LLM-based News Analyzer
Uses Claude to interpret qualitative news that regex can't parse.
Fallback layer when pattern matching fails.
"""

import logging
import os
import json
from typing import Optional, Dict, List
from datetime import datetime

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from src.monitors.news_monitor import NewsEvent
from src.edge_detection.speed_arbitrage import TradeSignal

logger = logging.getLogger(__name__)


class LLMNewsAnalyzer:
    """
    Use LLM to analyze qualitative news when regex fails.
    Fast model (Haiku) for speed, structured output for reliability.
    """

    def __init__(self, api_key: Optional[str] = None, enabled: bool = True):
        """
        Initialize LLM analyzer.

        Args:
            api_key: Anthropic API key (defaults to env var)
            enabled: Whether to use LLM analysis
        """
        self.enabled = enabled and ANTHROPIC_AVAILABLE

        if not ANTHROPIC_AVAILABLE:
            logger.warning("anthropic library not installed - LLM analysis disabled")
            self.enabled = False
            return

        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY not set - LLM analysis disabled")
            self.enabled = False
            return

        self.client = anthropic.Anthropic(api_key=self.api_key)
        logger.info("LLM news analyzer initialized (model: claude-haiku)")

    def analyze_news(
        self,
        event: NewsEvent,
        available_markets: List[str]
    ) -> Optional[Dict]:
        """
        Analyze news event and identify trading opportunities.

        Args:
            event: News event to analyze
            available_markets: List of Kalshi market tickers

        Returns:
            Dict with market, direction, confidence, reasoning
            None if no opportunity or analysis fails
        """
        if not self.enabled:
            return None

        try:
            # Build prompt with news and available markets
            prompt = self._build_prompt(event, available_markets)

            # Call Claude Haiku for fast analysis
            response = self.client.messages.create(
                model="claude-haiku-4-20250514",
                max_tokens=1000,
                temperature=0,  # Deterministic for trading
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Parse structured response
            result = self._parse_response(response.content[0].text)

            if result:
                logger.info(
                    f"LLM identified opportunity: {result.get('ticker')} "
                    f"{result.get('side')} (confidence: {result.get('confidence'):.2f})"
                )

            return result

        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return None

    def _build_prompt(self, event: NewsEvent, available_markets: List[str]) -> str:
        """Build analysis prompt for Claude"""

        # Filter markets to Fed/economic related (reduce noise)
        relevant_market_patterns = ['FED', 'RATE', 'CPI', 'INF', 'GDP', 'UNEMP', 'JOBS', 'NFP', 'FOMC']
        filtered_markets = [
            m for m in available_markets
            if any(pattern in m.upper() for pattern in relevant_market_patterns)
        ]

        market_list = "\n".join(filtered_markets[:50])  # Limit to 50 to save tokens

        return f"""You are a quantitative trading analyst specializing in prediction markets.

NEWS EVENT:
Headline: {event.headline}
Content: {event.content}
Source: {event.source}
Keywords: {', '.join(event.keywords)}

AVAILABLE KALSHI MARKETS:
{market_list if market_list else "No relevant markets found"}

TASK:
Analyze this news and determine if it creates a trading opportunity in the Kalshi prediction markets listed above.

Consider:
1. What is the key information in this news?
2. Which Kalshi market(s) would be most affected?
3. Should we buy YES or NO contracts?
4. How confident are you (0.0 to 1.0)?
5. What is the estimated probability shift this news should cause?

Respond ONLY with a JSON object in this exact format:
{{
  "opportunity": true/false,
  "ticker": "MARKET-TICKER" or null,
  "side": "yes" or "no" or null,
  "confidence": 0.0-1.0,
  "probability_shift": -0.5 to +0.5 (estimated change in market probability),
  "reasoning": "brief explanation"
}}

If no clear opportunity exists, set "opportunity": false and all other fields to null.
Be conservative - only recommend trades with clear directional impact and confidence >= 0.7.

RESPOND WITH ONLY THE JSON OBJECT, NO OTHER TEXT."""

    def _parse_response(self, response_text: str) -> Optional[Dict]:
        """Parse LLM response into structured data"""
        try:
            # Extract JSON from response
            response_text = response_text.strip()

            # Handle markdown code blocks if present
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[1:-1])

            data = json.loads(response_text)

            # Validate response
            if not data.get('opportunity'):
                return None

            required_fields = ['ticker', 'side', 'confidence', 'probability_shift', 'reasoning']
            if not all(field in data for field in required_fields):
                logger.warning(f"LLM response missing required fields: {data}")
                return None

            # Validate values
            if data['confidence'] < 0.7:
                logger.info(f"LLM confidence too low: {data['confidence']}")
                return None

            if data['side'] not in ['yes', 'no']:
                logger.warning(f"Invalid side: {data['side']}")
                return None

            return data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}\nResponse: {response_text}")
            return None
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return None

    def create_trade_signal(
        self,
        analysis: Dict,
        event: NewsEvent,
        current_price: Optional[float] = None
    ) -> TradeSignal:
        """
        Convert LLM analysis into trade signal.

        Args:
            analysis: LLM analysis result
            event: Original news event
            current_price: Current market price (if available)

        Returns:
            TradeSignal object
        """
        # Calculate fair value based on probability shift
        # If we don't have current price, we can't calculate exact fair value
        # but we can still generate a signal
        probability_shift = analysis['probability_shift']

        # Estimate edge as absolute value of probability shift
        # This is conservative - actual edge might be higher if market hasn't moved yet
        edge_percentage = abs(probability_shift)

        # If we have current price, calculate more accurate fair value
        if current_price is not None:
            if analysis['side'] == 'yes':
                fair_value = current_price + probability_shift
            else:
                fair_value = current_price - probability_shift

            # Clamp to valid probability range
            fair_value = max(0.01, min(0.99, fair_value))

            # Recalculate edge based on fair value vs current price
            edge_percentage = abs(fair_value - current_price)
        else:
            # No current price, use shifted probability as fair value estimate
            fair_value = 0.5 + probability_shift
            fair_value = max(0.01, min(0.99, fair_value))

        signal = TradeSignal(
            signal_id=f"llm_{event.event_id}_{datetime.now().timestamp()}",
            timestamp=datetime.now(),
            source="llm_analyzer",
            ticker=analysis['ticker'],
            side=analysis['side'],
            signal_type="BUY",
            confidence=analysis['confidence'],
            edge_percentage=edge_percentage,
            current_price=current_price,
            fair_value=fair_value,
            reasoning=f"LLM Analysis: {analysis['reasoning']}",
            event_data={
                'event_id': event.event_id,
                'headline': event.headline,
                'source': event.source,
                'llm_analysis': analysis
            }
        )

        return signal
