"""
Trade Executor
Receives signals and executes trades with proper risk management and validation.
"""

import asyncio
import hashlib
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from dataclasses import dataclass

from src.edge_detection.speed_arbitrage import TradeSignal
from src.api.kalshi_client import KalshiClient, Order
from src.database.models import Trade, Signal as DBSignal, Position as DBPosition
from src.execution.paper_trader import PaperTrader

logger = logging.getLogger(__name__)


@dataclass
class RiskLimits:
    """Risk management configuration"""

    max_position_size_usd: float
    max_portfolio_heat: float  # % of total capital
    max_trades_per_hour: int
    max_trades_per_day: int
    max_daily_loss: float
    stop_loss_percentage: float
    cooldown_after_loss_seconds: int
    circuit_breaker_consecutive_losses: int


class PositionSizer:
    """Calculate optimal position sizes using Kelly Criterion"""

    @staticmethod
    def kelly_position_size(
        edge: float,
        confidence: float,
        kelly_fraction: float = 0.25,
        bankroll: float = 10000,
    ) -> float:
        """
        Calculate position size using fractional Kelly.

        Args:
            edge: Expected edge (e.g., 0.05 = 5%)
            confidence: Confidence in signal (0-1)
            kelly_fraction: Fraction of Kelly to use (0.25 = quarter Kelly)
            bankroll: Total available capital

        Returns:
            Position size in dollars
        """
        # Kelly formula: f* = (bp - q) / b
        # where b = odds, p = win probability, q = loss probability

        # Simplified: use edge and confidence
        win_prob = confidence
        loss_prob = 1 - win_prob

        # Odds are roughly edge / (1 - edge)
        if edge <= 0 or edge >= 1:
            return 0

        b = edge / (1 - edge)

        # Kelly percentage
        kelly_pct = (b * win_prob - loss_prob) / b

        # Apply fraction for safety
        kelly_pct *= kelly_fraction

        # Clamp to reasonable range
        kelly_pct = max(0, min(kelly_pct, 0.25))  # Never more than 25% of bankroll

        position_size = bankroll * kelly_pct
        return position_size

    @staticmethod
    def calculate_position_size(
        signal: TradeSignal,
        config: Dict,
        current_balance: float,
        current_exposure: float,
    ) -> int:
        """
        Calculate optimal position size for a signal.

        Args:
            signal: Trade signal
            config: Risk configuration
            current_balance: Available balance in USD
            current_exposure: Current total exposure in USD

        Returns:
            Number of contracts to trade
        """
        # Get risk limits
        max_position = config.get("max_position_size_usd", 500)
        max_heat = config.get("max_portfolio_heat", 0.20)
        kelly_fraction = config.get("kelly_fraction", 0.25)

        # Calculate Kelly size
        kelly_size = PositionSizer.kelly_position_size(
            edge=signal.edge_percentage,
            confidence=signal.confidence,
            kelly_fraction=kelly_fraction,
            bankroll=current_balance,
        )

        # Apply position limit
        position_size_usd = min(kelly_size, max_position)

        # Check portfolio heat limit
        max_exposure = current_balance * max_heat
        remaining_capacity = max_exposure - current_exposure

        if remaining_capacity <= 0:
            logger.warning("Portfolio heat limit reached")
            return 0

        position_size_usd = min(position_size_usd, remaining_capacity)

        # Convert to number of contracts
        # Each contract costs (price * 1), ranges from 1 to 99 cents
        price_cents = int(signal.current_price * 100) if signal.current_price else 50
        num_contracts = int(position_size_usd * 100 / price_cents)

        # Minimum 1 contract, maximum based on calculations
        num_contracts = max(1, num_contracts)

        logger.info(
            f"Position sizing: Kelly=${kelly_size:.2f}, Final=${position_size_usd:.2f}, "
            f"Contracts={num_contracts} @ {price_cents}¢"
        )

        return num_contracts


class OrderValidator:
    """Validate orders before execution"""

    @staticmethod
    def validate_signal(
        signal: TradeSignal, config: Dict, seen_signals: set
    ) -> tuple[bool, Optional[str]]:
        """
        Validate a trade signal.

        Returns:
            (is_valid, rejection_reason)
        """
        # Check if already executed
        signal_hash = hashlib.md5(signal.signal_id.encode()).hexdigest()
        if signal_hash in seen_signals:
            return False, "Duplicate signal"

        # Check confidence threshold
        min_confidence = config.get("min_edge_threshold", 0.05)
        if signal.confidence < min_confidence:
            return False, f"Confidence {signal.confidence:.2f} below threshold"

        # Check edge threshold
        min_edge = config.get("min_edge_threshold", 0.05)
        if signal.edge_percentage < min_edge:
            return False, f"Edge {signal.edge_percentage:.2%} below threshold"

        # Sanity checks
        if signal.current_price and (
            signal.current_price < 0.01 or signal.current_price > 0.99
        ):
            return False, f"Invalid price: {signal.current_price}"

        if signal.side not in ["yes", "no"]:
            return False, f"Invalid side: {signal.side}"

        return True, None

    @staticmethod
    def validate_order(
        ticker: str, side: str, quantity: int, price: int
    ) -> tuple[bool, Optional[str]]:
        """
        Validate order parameters.

        Returns:
            (is_valid, rejection_reason)
        """
        if not ticker:
            return False, "Missing ticker"

        if side not in ["yes", "no"]:
            return False, f"Invalid side: {side}"

        if quantity <= 0:
            return False, f"Invalid quantity: {quantity}"

        if not 1 <= price <= 99:
            return False, f"Invalid price: {price} (must be 1-99 cents)"

        return True, None


class CircuitBreaker:
    """Circuit breaker to pause trading during adverse conditions"""

    def __init__(self, config: Dict):
        self.max_consecutive_losses = config.get(
            "circuit_breaker_consecutive_losses", 3
        )
        self.consecutive_losses = 0
        self.is_tripped = False
        self.trip_time = None

    def record_trade(self, pnl: float):
        """Record a trade result"""
        if pnl < 0:
            self.consecutive_losses += 1
            logger.warning(
                f"Loss recorded. Consecutive losses: {self.consecutive_losses}"
            )

            if self.consecutive_losses >= self.max_consecutive_losses:
                self.trip()
        else:
            # Reset on win
            self.consecutive_losses = 0
            if self.is_tripped:
                logger.info("Circuit breaker reset after winning trade")
                self.reset()

    def trip(self):
        """Trip the circuit breaker"""
        if not self.is_tripped:
            self.is_tripped = True
            self.trip_time = datetime.now()
            logger.critical(
                f"🔴 CIRCUIT BREAKER TRIPPED after {self.consecutive_losses} "
                f"consecutive losses. Trading paused."
            )

    def reset(self):
        """Reset the circuit breaker"""
        self.is_tripped = False
        self.trip_time = None
        self.consecutive_losses = 0
        logger.info("Circuit breaker reset")

    def can_trade(self) -> tuple[bool, Optional[str]]:
        """Check if trading is allowed"""
        if self.is_tripped:
            return False, "Circuit breaker tripped - trading paused"
        return True, None


class TradeExecutor:
    """
    Main trade execution engine.

    Responsibilities:
    - Validate signals
    - Calculate position sizes
    - Execute orders via Kalshi API
    - Monitor fills
    - Manage risk limits
    """

    def __init__(
        self,
        kalshi_client: KalshiClient,
        config: Dict,
        db_session,
        alert_callback=None,
    ):
        self.kalshi = kalshi_client
        self.config = config
        self.db = db_session
        self.alert_callback = alert_callback

        # Risk management
        self.risk_limits = RiskLimits(
            max_position_size_usd=config.get("max_position_size_usd", 500),
            max_portfolio_heat=config.get("max_portfolio_heat", 0.20),
            max_trades_per_hour=config.get("max_trades_per_hour", 20),
            max_trades_per_day=config.get("max_trades_per_day", 100),
            max_daily_loss=config.get("max_daily_loss", 1000),
            stop_loss_percentage=config.get("stop_loss_percentage", 0.30),
            cooldown_after_loss_seconds=config.get("cooldown_after_loss_seconds", 300),
            circuit_breaker_consecutive_losses=config.get(
                "circuit_breaker_consecutive_losses", 3
            ),
        )

        # State tracking
        self.seen_signals: set = set()
        self.recent_trades: List[datetime] = []
        self.last_loss_time: Optional[datetime] = None
        self.daily_pnl: float = 0

        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(config)

        # Master kill switch
        self.trading_enabled = config.get("enabled", False)

        # Paper trading mode
        self.paper_trading = os.getenv("PAPER_TRADING_MODE", "true").lower() == "true"
        self.paper_trader = PaperTrader(config) if self.paper_trading else None

        if self.paper_trading:
            logger.warning("📝 PAPER TRADING MODE ACTIVE - No real money at risk!")
        else:
            logger.critical("💰 LIVE TRADING MODE - Real money will be traded!")

        logger.info(f"Trade executor initialized. Trading enabled: {self.trading_enabled}")

    async def execute_signal(self, signal: TradeSignal) -> Optional[Trade]:
        """
        Execute a trade signal.

        Args:
            signal: TradeSignal to execute

        Returns:
            Trade object if successful, None otherwise
        """
        # Check if trading is enabled
        if not self.trading_enabled:
            logger.info("Trading disabled - signal not executed")
            return None

        # Check circuit breaker
        can_trade, reason = self.circuit_breaker.can_trade()
        if not can_trade:
            logger.warning(f"Signal rejected: {reason}")
            await self._send_alert(f"🔴 Signal rejected: {reason}")
            return None

        # Validate signal
        is_valid, rejection_reason = OrderValidator.validate_signal(
            signal, self.config, self.seen_signals
        )

        if not is_valid:
            logger.info(f"Signal rejected: {rejection_reason}")
            self._record_rejected_signal(signal, rejection_reason)
            return None

        # Check rate limits
        if not self._check_rate_limits():
            logger.warning("Rate limit exceeded - signal not executed")
            return None

        # Check daily loss limit
        if self.daily_pnl < -self.risk_limits.max_daily_loss:
            logger.critical(
                f"Daily loss limit reached: ${self.daily_pnl:.2f}. Trading paused."
            )
            await self._send_alert(
                f"🔴 Daily loss limit reached: ${self.daily_pnl:.2f}"
            )
            return None

        # Check cooldown after loss
        if self.last_loss_time:
            seconds_since_loss = (datetime.now() - self.last_loss_time).total_seconds()
            if seconds_since_loss < self.risk_limits.cooldown_after_loss_seconds:
                logger.info(
                    f"In cooldown period ({seconds_since_loss:.0f}s / "
                    f"{self.risk_limits.cooldown_after_loss_seconds}s)"
                )
                return None

        # Get current balance and exposure
        if self.paper_trading:
            balance_info = self.paper_trader.get_balance()
            current_balance = balance_info.get("balance", 10000)
            current_exposure = balance_info.get("total_exposure", 0)
        else:
            balance_info = self.kalshi.get_balance()
            current_balance = balance_info.get("balance", 0)
            current_exposure = self._calculate_current_exposure()

        # Calculate position size
        quantity = PositionSizer.calculate_position_size(
            signal, self.config, current_balance, current_exposure
        )

        if quantity == 0:
            logger.info("Position size calculated as 0 - signal not executed")
            return None

        # Calculate limit price (start at current price, adjust based on urgency)
        limit_price = int(signal.current_price * 100) if signal.current_price else 50

        # Validate order
        is_valid, rejection_reason = OrderValidator.validate_order(
            signal.ticker, signal.side, quantity, limit_price
        )

        if not is_valid:
            logger.error(f"Order validation failed: {rejection_reason}")
            return None

        # Place order (real or paper)
        try:
            mode_str = "PAPER" if self.paper_trading else "LIVE"
            logger.info(
                f"[{mode_str}] Placing order: {quantity} {signal.side} @ {limit_price}¢ on {signal.ticker}"
            )

            if self.paper_trading:
                # Paper trading - simulate execution
                order = self.paper_trader.place_order(
                    ticker=signal.ticker,
                    side=signal.side,
                    quantity=quantity,
                    limit_price=limit_price,
                    order_type="limit",
                ).to_order()
            else:
                # Live trading - real execution
                order = self.kalshi.place_order(
                    ticker=signal.ticker,
                    side=signal.side,
                    quantity=quantity,
                    limit_price=limit_price,
                    order_type="limit",
                )

            if not order:
                logger.error("Order placement failed")
                return None

            # Record trade
            trade = self._record_trade(signal, order, quantity, limit_price)

            # Mark signal as executed
            signal_hash = hashlib.md5(signal.signal_id.encode()).hexdigest()
            self.seen_signals.add(signal_hash)
            self._mark_signal_executed(signal)

            # Track for rate limiting
            self.recent_trades.append(datetime.now())

            # Send alert
            prefix = "📝 PAPER" if self.paper_trading else "✅ LIVE"
            await self._send_alert(
                f"{prefix} Trade executed: {quantity} {signal.side} {signal.ticker} @ {limit_price}¢\n"
                f"Edge: {signal.edge_percentage:.1%}, Confidence: {signal.confidence:.2f}\n"
                f"Reason: {signal.reasoning[:100]}"
            )

            logger.info(f"[{mode_str}] Trade executed successfully: {order}")
            return trade

        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            await self._send_alert(f"❌ Trade execution failed: {e}")
            return None

    def _check_rate_limits(self) -> bool:
        """Check if we're within rate limits"""
        now = datetime.now()

        # Clean old trades
        hour_ago = now - timedelta(hours=1)
        self.recent_trades = [t for t in self.recent_trades if t > hour_ago]

        # Check hourly limit
        if len(self.recent_trades) >= self.risk_limits.max_trades_per_hour:
            logger.warning(
                f"Hourly trade limit reached: {len(self.recent_trades)} trades"
            )
            return False

        # Check daily limit (would need to query DB for accuracy)
        today_start = datetime.combine(now.date(), datetime.min.time())
        daily_trades = (
            self.db.query(Trade)
            .filter(Trade.executed_at >= today_start)
            .count()
        )

        if daily_trades >= self.risk_limits.max_trades_per_day:
            logger.warning(f"Daily trade limit reached: {daily_trades} trades")
            return False

        return True

    def _calculate_current_exposure(self) -> float:
        """Calculate total current position exposure"""
        positions = self.kalshi.get_positions()
        total_exposure = sum(
            abs(p.total_cost) / 100 for p in positions  # Convert cents to dollars
        )
        return total_exposure

    def _record_trade(
        self, signal: TradeSignal, order: Order, quantity: int, price: int
    ) -> Trade:
        """Record trade in database"""
        # Find signal in DB
        db_signal = (
            self.db.query(DBSignal)
            .filter(DBSignal.signal_id == signal.signal_id)
            .first()
        )

        trade = Trade(
            signal_id=db_signal.id if db_signal else None,
            order_id=order.order_id,
            ticker=signal.ticker,
            side=signal.side,
            quantity=quantity,
            entry_price=price / 100,  # Convert cents to dollars
            fill_price=None,  # Will update when filled
            status="open",
        )

        self.db.add(trade)
        self.db.commit()

        return trade

    def _mark_signal_executed(self, signal: TradeSignal):
        """Mark signal as executed in database"""
        db_signal = (
            self.db.query(DBSignal)
            .filter(DBSignal.signal_id == signal.signal_id)
            .first()
        )

        if db_signal:
            db_signal.executed = True
            db_signal.executed_at = datetime.utcnow()
            self.db.commit()

    def _record_rejected_signal(self, signal: TradeSignal, reason: str):
        """Record rejected signal in database"""
        db_signal = (
            self.db.query(DBSignal)
            .filter(DBSignal.signal_id == signal.signal_id)
            .first()
        )

        if db_signal:
            db_signal.rejected = True
            db_signal.rejection_reason = reason
            self.db.commit()

    async def _send_alert(self, message: str):
        """Send alert via callback"""
        if self.alert_callback:
            try:
                await self.alert_callback(message)
            except Exception as e:
                logger.error(f"Error sending alert: {e}")
