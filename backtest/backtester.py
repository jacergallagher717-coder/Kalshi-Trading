"""
Backtesting Framework
Simulates trading strategies using historical data to evaluate performance.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    """Represents a backtested trade"""

    timestamp: datetime
    ticker: str
    side: str
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    fees: float
    net_pnl: float
    hold_time_hours: float
    strategy: str
    signal_data: Dict


@dataclass
class BacktestResults:
    """Results from a backtest run"""

    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    total_fees: float
    net_pnl: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    sharpe_ratio: float
    max_drawdown: float
    profit_factor: float
    avg_latency_seconds: float
    trades: List[BacktestTrade]


class Backtester:
    """
    Backtesting engine for trading strategies.

    Usage:
        backtester = Backtester(historical_data)
        results = backtester.run(strategy, start_date, end_date)
        backtester.print_results(results)
    """

    def __init__(self, fee_rate: float = 0.03, slippage_rate: float = 0.01):
        """
        Initialize backtester.

        Args:
            fee_rate: Trading fee as percentage (0.03 = 3%)
            slippage_rate: Average slippage as percentage
        """
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate

    def load_historical_data(self, data_path: str) -> pd.DataFrame:
        """
        Load historical market data.

        Expected format:
        - timestamp, ticker, price, volume, bid, ask, ...
        """
        try:
            df = pd.read_csv(data_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            logger.info(f"Loaded {len(df)} historical data points")
            return df
        except Exception as e:
            logger.error(f"Error loading historical data: {e}")
            return pd.DataFrame()

    def load_historical_news(self, data_path: str) -> pd.DataFrame:
        """Load historical news events"""
        try:
            df = pd.read_csv(data_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            logger.info(f"Loaded {len(df)} historical news events")
            return df
        except Exception as e:
            logger.error(f"Error loading news data: {e}")
            return pd.DataFrame()

    def simulate_trade(
        self,
        entry_price: float,
        exit_price: float,
        quantity: int,
        side: str,
    ) -> Dict:
        """
        Simulate a trade with fees and slippage.

        Returns:
            Dict with P&L calculations
        """
        # Apply slippage
        actual_entry = entry_price * (1 + self.slippage_rate)
        actual_exit = exit_price * (1 - self.slippage_rate)

        # Calculate P&L
        if side == "yes":
            pnl_per_contract = actual_exit - actual_entry
        else:  # "no"
            pnl_per_contract = actual_entry - actual_exit

        gross_pnl = pnl_per_contract * quantity

        # Calculate fees (only on profits)
        fees = max(0, gross_pnl * self.fee_rate) if gross_pnl > 0 else 0

        net_pnl = gross_pnl - fees

        return {
            "entry_price": actual_entry,
            "exit_price": actual_exit,
            "gross_pnl": gross_pnl,
            "fees": fees,
            "net_pnl": net_pnl,
        }

    def run_speed_arb_backtest(
        self,
        market_data: pd.DataFrame,
        news_data: pd.DataFrame,
        strategy_config: Dict,
    ) -> BacktestResults:
        """
        Backtest speed arbitrage strategy.

        Simulates:
        1. News event occurs
        2. Signal generated
        3. Order placed with latency
        4. Position held until exit condition
        5. Calculate P&L
        """
        trades = []

        # For each news event
        for _, news in news_data.iterrows():
            news_time = news['timestamp']

            # Find related markets
            related_tickers = news.get('related_tickers', [])
            if not related_tickers:
                continue

            for ticker in related_tickers:
                # Get market data at news time
                market_slice = market_data[
                    (market_data['ticker'] == ticker)
                    & (market_data['timestamp'] >= news_time)
                    & (market_data['timestamp'] < news_time + timedelta(minutes=60))
                ]

                if market_slice.empty:
                    continue

                # Simulate signal generation (simplified)
                signal_time = news_time + timedelta(
                    seconds=np.random.uniform(1, 10)
                )  # 1-10 second latency

                # Entry price (first price after signal)
                entry_row = market_slice[market_slice['timestamp'] >= signal_time].iloc[0]
                entry_price = entry_row['price']
                entry_time = entry_row['timestamp']

                # Exit after 4 hours (simplified exit logic)
                exit_time = entry_time + timedelta(hours=4)
                exit_data = market_slice[market_slice['timestamp'] >= exit_time]

                if exit_data.empty:
                    continue

                exit_price = exit_data.iloc[0]['price']
                actual_exit_time = exit_data.iloc[0]['timestamp']

                # Determine side (simplified)
                side = "yes" if news.get('sentiment', 0) > 0 else "no"

                # Simulate trade
                quantity = 100  # Simplified position sizing

                trade_result = self.simulate_trade(
                    entry_price, exit_price, quantity, side
                )

                # Record trade
                hold_time = (actual_exit_time - entry_time).total_seconds() / 3600

                trade = BacktestTrade(
                    timestamp=entry_time,
                    ticker=ticker,
                    side=side,
                    entry_price=trade_result['entry_price'],
                    exit_price=trade_result['exit_price'],
                    quantity=quantity,
                    pnl=trade_result['gross_pnl'],
                    fees=trade_result['fees'],
                    net_pnl=trade_result['net_pnl'],
                    hold_time_hours=hold_time,
                    strategy="speed_arb",
                    signal_data=news.to_dict(),
                )

                trades.append(trade)

        # Calculate results
        return self.calculate_results(trades)

    def calculate_results(self, trades: List[BacktestTrade]) -> BacktestResults:
        """Calculate performance metrics from trades"""
        if not trades:
            logger.warning("No trades to analyze")
            return BacktestResults(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0,
                total_pnl=0,
                total_fees=0,
                net_pnl=0,
                avg_win=0,
                avg_loss=0,
                largest_win=0,
                largest_loss=0,
                sharpe_ratio=0,
                max_drawdown=0,
                profit_factor=0,
                avg_latency_seconds=0,
                trades=[],
            )

        # Basic metrics
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t.net_pnl > 0])
        losing_trades = len([t for t in trades if t.net_pnl < 0])
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        total_pnl = sum(t.pnl for t in trades)
        total_fees = sum(t.fees for t in trades)
        net_pnl = sum(t.net_pnl for t in trades)

        # Win/Loss analysis
        wins = [t.net_pnl for t in trades if t.net_pnl > 0]
        losses = [t.net_pnl for t in trades if t.net_pnl < 0]

        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0
        largest_win = max(wins) if wins else 0
        largest_loss = min(losses) if losses else 0

        # Sharpe ratio (simplified - assumes daily returns)
        returns = [t.net_pnl for t in trades]
        sharpe_ratio = (
            np.mean(returns) / np.std(returns) * np.sqrt(252)
            if len(returns) > 1 and np.std(returns) > 0
            else 0
        )

        # Max drawdown
        cumulative_pnl = np.cumsum([t.net_pnl for t in trades])
        running_max = np.maximum.accumulate(cumulative_pnl)
        drawdown = running_max - cumulative_pnl
        max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0

        # Profit factor
        total_wins = sum(wins)
        total_losses = abs(sum(losses))
        profit_factor = total_wins / total_losses if total_losses > 0 else 0

        # Average latency (would need actual latency data)
        avg_latency_seconds = 5.0  # Placeholder

        return BacktestResults(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_pnl=total_pnl,
            total_fees=total_fees,
            net_pnl=net_pnl,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            profit_factor=profit_factor,
            avg_latency_seconds=avg_latency_seconds,
            trades=trades,
        )

    def print_results(self, results: BacktestResults):
        """Print backtest results"""
        print("\n" + "=" * 60)
        print("BACKTEST RESULTS")
        print("=" * 60)
        print(f"\nTotal Trades: {results.total_trades}")
        print(f"Winning Trades: {results.winning_trades}")
        print(f"Losing Trades: {results.losing_trades}")
        print(f"Win Rate: {results.win_rate:.1%}")
        print(f"\nTotal P&L: ${results.total_pnl:.2f}")
        print(f"Total Fees: ${results.total_fees:.2f}")
        print(f"Net P&L: ${results.net_pnl:.2f}")
        print(f"\nAverage Win: ${results.avg_win:.2f}")
        print(f"Average Loss: ${results.avg_loss:.2f}")
        print(f"Largest Win: ${results.largest_win:.2f}")
        print(f"Largest Loss: ${results.largest_loss:.2f}")
        print(f"\nSharpe Ratio: {results.sharpe_ratio:.2f}")
        print(f"Max Drawdown: ${results.max_drawdown:.2f}")
        print(f"Profit Factor: {results.profit_factor:.2f}")
        print(f"\nAverage Latency: {results.avg_latency_seconds:.1f}s")
        print("=" * 60 + "\n")

    def export_results(self, results: BacktestResults, output_path: str):
        """Export results to CSV"""
        trades_df = pd.DataFrame([
            {
                'timestamp': t.timestamp,
                'ticker': t.ticker,
                'side': t.side,
                'entry_price': t.entry_price,
                'exit_price': t.exit_price,
                'quantity': t.quantity,
                'pnl': t.pnl,
                'fees': t.fees,
                'net_pnl': t.net_pnl,
                'hold_time_hours': t.hold_time_hours,
                'strategy': t.strategy,
            }
            for t in results.trades
        ])

        trades_df.to_csv(output_path, index=False)
        logger.info(f"Results exported to {output_path}")
