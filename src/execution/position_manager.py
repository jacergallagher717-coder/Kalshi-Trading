"""
Position Manager
Monitors and manages open positions, handles exits based on profit targets, stop losses, etc.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from src.api.kalshi_client import KalshiClient
from src.database.models import Trade, Position as DBPosition

logger = logging.getLogger(__name__)


class ExitCondition:
    """Represents a condition for exiting a position"""

    PROFIT_TARGET = "profit_target"
    STOP_LOSS = "stop_loss"
    TIME_DECAY = "time_decay"
    MANUAL = "manual"
    MARKET_CLOSED = "market_closed"


class PositionManager:
    """
    Manages open positions and determines when to exit.

    Exit strategies:
    - Profit target: Close at 2x expected edge capture
    - Stop loss: Close if down 30%
    - Time decay: Close 24h before event
    - Manual: User-initiated close
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

        # Exit parameters
        self.profit_target_multiplier = config.get("profit_target_multiplier", 2.0)
        self.stop_loss_pct = config.get("stop_loss_percentage", 0.30)
        self.time_before_close_hours = config.get("position_timeout_hours", 24)

        logger.info("Position manager initialized")

    async def monitor_positions(self):
        """Monitor all open positions and check exit conditions"""
        # Get open trades from database
        open_trades = self.db.query(Trade).filter(Trade.status == "open").all()

        if not open_trades:
            logger.debug("No open positions to monitor")
            return

        logger.info(f"Monitoring {len(open_trades)} open positions")

        # Get current positions from Kalshi
        kalshi_positions = self.kalshi.get_positions()
        position_map = {p.ticker: p for p in kalshi_positions}

        for trade in open_trades:
            try:
                await self._check_position(trade, position_map.get(trade.ticker))
            except Exception as e:
                logger.error(f"Error checking position {trade.ticker}: {e}")

    async def _check_position(self, trade: Trade, kalshi_position):
        """Check if a position should be closed"""
        # Get market info
        market = self.kalshi.get_market(trade.ticker)

        if not market:
            logger.warning(f"Market not found: {trade.ticker}")
            return

        # Check if market is closed
        if market.status in ["closed", "settled"]:
            logger.info(f"Market {trade.ticker} is {market.status}")
            await self._close_position(trade, market.last_price, ExitCondition.MARKET_CLOSED)
            return

        # Get current price
        current_price = market.last_price or market.yes_bid

        if not current_price:
            logger.warning(f"No price data for {trade.ticker}")
            return

        # Calculate P&L
        entry_price = trade.entry_price
        quantity = trade.quantity

        # P&L in cents per contract
        if trade.side == "yes":
            pnl_per_contract = current_price - entry_price
        else:
            pnl_per_contract = entry_price - current_price

        total_pnl = pnl_per_contract * quantity
        pnl_pct = pnl_per_contract / entry_price if entry_price > 0 else 0

        logger.debug(
            f"{trade.ticker}: Entry=${entry_price:.2f}, Current=${current_price:.2f}, "
            f"P&L=${total_pnl:.2f} ({pnl_pct:.1%})"
        )

        # Check profit target
        # If we entered expecting 5% edge, take profit at 10% (2x)
        profit_target = (
            entry_price * (1 + self.profit_target_multiplier * 0.05)
            if trade.side == "yes"
            else entry_price * (1 - self.profit_target_multiplier * 0.05)
        )

        if trade.side == "yes" and current_price >= profit_target:
            logger.info(
                f"Profit target hit for {trade.ticker}: {current_price:.2f} >= {profit_target:.2f}"
            )
            await self._close_position(trade, current_price, ExitCondition.PROFIT_TARGET)
            return

        if trade.side == "no" and current_price <= profit_target:
            logger.info(
                f"Profit target hit for {trade.ticker}: {current_price:.2f} <= {profit_target:.2f}"
            )
            await self._close_position(trade, current_price, ExitCondition.PROFIT_TARGET)
            return

        # Check stop loss
        if pnl_pct < -self.stop_loss_pct:
            logger.warning(
                f"Stop loss hit for {trade.ticker}: {pnl_pct:.1%} < -{self.stop_loss_pct:.1%}"
            )
            await self._close_position(trade, current_price, ExitCondition.STOP_LOSS)
            return

        # Check time decay
        if market.close_time:
            try:
                if isinstance(market.close_time, str):
                    close_time = datetime.fromisoformat(
                        market.close_time.replace("Z", "+00:00")
                    )
                else:
                    close_time = market.close_time

                hours_until_close = (close_time - datetime.now()).total_seconds() / 3600

                if hours_until_close < self.time_before_close_hours:
                    logger.info(
                        f"Time decay exit for {trade.ticker}: {hours_until_close:.1f}h until close"
                    )
                    await self._close_position(trade, current_price, ExitCondition.TIME_DECAY)
                    return
            except Exception as e:
                logger.error(f"Error parsing close time: {e}")

    async def _close_position(
        self, trade: Trade, current_price: float, reason: str
    ):
        """Close a position"""
        try:
            logger.info(f"Closing position: {trade.ticker} at ${current_price:.2f}, reason: {reason}")

            # Place opposite order to close
            opposite_side = "no" if trade.side == "yes" else "yes"
            price_cents = int(current_price * 100)

            order = self.kalshi.place_order(
                ticker=trade.ticker,
                side=opposite_side,
                quantity=trade.quantity,
                limit_price=price_cents,
                order_type="limit",
            )

            if not order:
                logger.error(f"Failed to close position {trade.ticker}")
                return

            # Calculate P&L
            entry_price = trade.entry_price
            exit_price = current_price

            if trade.side == "yes":
                pnl_per_contract = exit_price - entry_price
            else:
                pnl_per_contract = entry_price - exit_price

            total_pnl = pnl_per_contract * trade.quantity

            # Estimate fees (Kalshi charges ~3% on profits)
            fees = abs(total_pnl) * 0.03 if total_pnl > 0 else 0

            net_pnl = total_pnl - fees

            # Update trade record
            trade.exit_price = exit_price
            trade.pnl = net_pnl
            trade.fees = fees
            trade.status = "closed"
            trade.close_reason = reason
            trade.closed_at = datetime.utcnow()

            self.db.commit()

            # Send alert
            pnl_emoji = "✅" if net_pnl > 0 else "❌"
            await self._send_alert(
                f"{pnl_emoji} Position closed: {trade.ticker}\n"
                f"Entry: ${entry_price:.2f}, Exit: ${exit_price:.2f}\n"
                f"P&L: ${net_pnl:.2f} ({pnl_per_contract/entry_price:.1%})\n"
                f"Reason: {reason}"
            )

            logger.info(
                f"Position closed: {trade.ticker}, P&L=${net_pnl:.2f}, reason={reason}"
            )

        except Exception as e:
            logger.error(f"Error closing position {trade.ticker}: {e}")
            await self._send_alert(f"❌ Error closing position {trade.ticker}: {e}")

    async def close_all_positions(self, reason: str = "manual"):
        """Emergency close all positions"""
        logger.warning(f"Closing all positions: {reason}")

        open_trades = self.db.query(Trade).filter(Trade.status == "open").all()

        for trade in open_trades:
            market = self.kalshi.get_market(trade.ticker)
            if market:
                current_price = market.last_price or market.yes_bid or trade.entry_price
                await self._close_position(trade, current_price, reason)

        await self._send_alert(f"🔴 All positions closed. Reason: {reason}")

    def get_position_summary(self) -> Dict:
        """Get summary of all open positions"""
        open_trades = self.db.query(Trade).filter(Trade.status == "open").all()

        total_positions = len(open_trades)
        total_unrealized_pnl = 0
        position_details = []

        for trade in open_trades:
            market = self.kalshi.get_market(trade.ticker)
            if not market:
                continue

            current_price = market.last_price or market.yes_bid or trade.entry_price

            if trade.side == "yes":
                pnl_per_contract = current_price - trade.entry_price
            else:
                pnl_per_contract = trade.entry_price - current_price

            total_pnl = pnl_per_contract * trade.quantity
            total_unrealized_pnl += total_pnl

            position_details.append(
                {
                    "ticker": trade.ticker,
                    "side": trade.side,
                    "quantity": trade.quantity,
                    "entry_price": trade.entry_price,
                    "current_price": current_price,
                    "unrealized_pnl": total_pnl,
                    "pnl_pct": pnl_per_contract / trade.entry_price
                    if trade.entry_price > 0
                    else 0,
                }
            )

        return {
            "total_positions": total_positions,
            "total_unrealized_pnl": total_unrealized_pnl,
            "positions": position_details,
        }

    async def _send_alert(self, message: str):
        """Send alert via callback"""
        if self.alert_callback:
            try:
                await self.alert_callback(message)
            except Exception as e:
                logger.error(f"Error sending alert: {e}")
