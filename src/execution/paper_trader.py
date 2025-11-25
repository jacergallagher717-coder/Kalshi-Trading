"""
Paper Trading Module
Simulates trade execution for testing without risking capital.
Logs all trades, tracks hypothetical P&L, validates strategy.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional, Dict
from dataclasses import dataclass

from src.edge_detection.speed_arbitrage import TradeSignal
from src.database.models import Trade, Signal as DBSignal
from src.api.kalshi_client import Order

logger = logging.getLogger(__name__)


@dataclass
class PaperOrder:
    """Simulated order for paper trading"""
    order_id: str
    ticker: str
    side: str
    quantity: int
    price: int
    status: str
    created_time: datetime
    filled_count: int = 0

    def to_order(self) -> Order:
        """Convert to Order object for compatibility"""
        return Order({
            'order_id': self.order_id,
            'ticker': self.ticker,
            'side': self.side,
            'count': self.quantity,
            'price': self.price,
            'status': self.status,
            'created_time': self.created_time.isoformat(),
            'filled_count': self.filled_count
        })


class PaperTrader:
    """
    Paper trading simulator that mimics real execution.

    Simulates:
    - Order placement
    - Realistic fills (with slippage)
    - Position tracking
    - P&L calculation
    - Fee estimation
    """

    def __init__(self, config: Dict):
        self.config = config
        self.paper_trades = []
        self.paper_positions = {}
        self.total_pnl = 0.0
        self.simulated_fill_rate = 0.95  # 95% of orders fill in paper trading
        self.simulated_slippage = 0.01  # 1 cent average slippage

        logger.info("📝 Paper trading mode enabled - NO REAL MONEY AT RISK")

    def place_order(
        self,
        ticker: str,
        side: str,
        quantity: int,
        limit_price: int,
        order_type: str = "limit"
    ) -> Optional[PaperOrder]:
        """
        Simulate order placement.

        Args:
            ticker: Market ticker
            side: 'yes' or 'no'
            quantity: Number of contracts
            limit_price: Limit price in cents (1-99)
            order_type: Order type (currently only 'limit')

        Returns:
            PaperOrder object if successful
        """
        # Generate fake order ID
        order_id = f"PAPER_{uuid.uuid4().hex[:16]}"

        # Simulate order submission
        logger.info(
            f"📝 PAPER TRADE: Placing {quantity} {side} @ {limit_price}¢ on {ticker}"
        )

        # Create paper order
        paper_order = PaperOrder(
            order_id=order_id,
            ticker=ticker,
            side=side,
            quantity=quantity,
            price=limit_price,
            status="resting",  # Kalshi's status for limit orders
            created_time=datetime.utcnow(),
            filled_count=0
        )

        # Simulate fill (instant fill for simplicity in paper trading)
        # In real life, limit orders might not fill immediately
        fill_quantity = int(quantity * self.simulated_fill_rate)

        if fill_quantity > 0:
            # Simulate some slippage (worse price by 1 cent average)
            slippage_cents = 1 if limit_price < 90 else 0
            fill_price = limit_price + slippage_cents

            paper_order.filled_count = fill_quantity
            paper_order.status = "filled" if fill_quantity == quantity else "partial"

            logger.info(
                f"✅ PAPER FILL: {fill_quantity}/{quantity} filled @ {fill_price}¢ "
                f"(slippage: {slippage_cents}¢)"
            )

            # Track position
            position_key = f"{ticker}_{side}"
            if position_key not in self.paper_positions:
                self.paper_positions[position_key] = {
                    'ticker': ticker,
                    'side': side,
                    'quantity': 0,
                    'avg_price': 0,
                    'total_cost': 0
                }

            pos = self.paper_positions[position_key]
            prev_qty = pos['quantity']
            prev_cost = pos['total_cost']

            new_cost = fill_quantity * fill_price
            pos['quantity'] += fill_quantity
            pos['total_cost'] += new_cost
            pos['avg_price'] = pos['total_cost'] / pos['quantity']

            logger.info(
                f"📊 PAPER POSITION: {pos['quantity']} {side} {ticker} @ "
                f"avg {pos['avg_price']:.2f}¢ (cost: ${pos['total_cost']/100:.2f})"
            )
        else:
            paper_order.status = "canceled"
            logger.warning(f"❌ PAPER ORDER: No fill simulated")

        # Store trade record
        self.paper_trades.append({
            'timestamp': datetime.utcnow(),
            'order': paper_order,
            'fill_price': fill_price if fill_quantity > 0 else None,
            'fill_quantity': fill_quantity
        })

        return paper_order

    def get_positions(self) -> list:
        """Get simulated positions"""
        positions = []
        for key, pos in self.paper_positions.items():
            if pos['quantity'] > 0:
                # Simulate position object
                positions.append(type('Position', (), {
                    'ticker': pos['ticker'],
                    'position': pos['quantity'],
                    'total_cost': pos['total_cost'],
                    'raw_data': pos
                }))
        return positions

    def get_balance(self) -> Dict:
        """Get simulated balance"""
        # Start with simulated $10,000 bankroll
        starting_capital = 10000.0

        # Calculate total exposure
        total_exposure = sum(pos['total_cost'] / 100 for pos in self.paper_positions.values())

        # Calculate available balance
        available = starting_capital - total_exposure + self.total_pnl

        return {
            'balance': available,
            'total_exposure': total_exposure,
            'starting_capital': starting_capital,
            'total_pnl': self.total_pnl
        }

    def simulate_position_close(self, ticker: str, side: str, exit_price: int):
        """
        Simulate closing a position.

        Args:
            ticker: Market ticker
            side: 'yes' or 'no'
            exit_price: Exit price in cents
        """
        position_key = f"{ticker}_{side}"

        if position_key not in self.paper_positions:
            logger.warning(f"No paper position to close for {position_key}")
            return

        pos = self.paper_positions[position_key]

        if pos['quantity'] == 0:
            logger.warning(f"Paper position already closed for {position_key}")
            return

        # Calculate P&L
        entry_cost = pos['total_cost']  # in cents
        exit_value = pos['quantity'] * exit_price  # in cents
        pnl_cents = exit_value - entry_cost
        pnl_dollars = pnl_cents / 100

        # Simulate fees (Kalshi charges on winning side only)
        fee_rate = 0.07  # 7% on profits
        fees = max(0, pnl_dollars * fee_rate) if pnl_dollars > 0 else 0
        net_pnl = pnl_dollars - fees

        self.total_pnl += net_pnl

        logger.info(
            f"💰 PAPER CLOSE: {pos['quantity']} {side} {ticker} @ {exit_price}¢ | "
            f"Entry: {pos['avg_price']:.2f}¢ | "
            f"P&L: ${net_pnl:.2f} (fees: ${fees:.2f})"
        )

        # Clear position
        pos['quantity'] = 0
        pos['total_cost'] = 0
        pos['avg_price'] = 0

    def get_summary(self) -> Dict:
        """Get paper trading summary statistics"""
        wins = sum(1 for t in self.paper_trades if t.get('pnl', 0) > 0)
        losses = sum(1 for t in self.paper_trades if t.get('pnl', 0) < 0)
        total_trades = len(self.paper_trades)

        return {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': wins / total_trades if total_trades > 0 else 0,
            'total_pnl': self.total_pnl,
            'open_positions': sum(1 for p in self.paper_positions.values() if p['quantity'] > 0),
            'balance': self.get_balance()
        }

    def print_summary(self):
        """Print paper trading performance summary"""
        summary = self.get_summary()
        balance = summary['balance']

        logger.info("=" * 60)
        logger.info("📊 PAPER TRADING SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Trades: {summary['total_trades']}")
        logger.info(f"Wins: {summary['wins']} | Losses: {summary['losses']}")
        logger.info(f"Win Rate: {summary['win_rate']:.1%}")
        logger.info(f"Total P&L: ${summary['total_pnl']:.2f}")
        logger.info(f"Open Positions: {summary['open_positions']}")
        logger.info(f"Starting Capital: ${balance['starting_capital']:.2f}")
        logger.info(f"Current Balance: ${balance['balance']:.2f}")
        logger.info(f"Total Exposure: ${balance['total_exposure']:.2f}")
        logger.info(f"Return: {(summary['total_pnl'] / balance['starting_capital']) * 100:.2f}%")
        logger.info("=" * 60)
