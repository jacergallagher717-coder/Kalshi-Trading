"""
Telegram Bot for alerts and notifications.
Sends real-time alerts for trades, errors, and daily summaries.
"""

import logging
from datetime import datetime, time
from typing import Optional, Dict
import asyncio

from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


class TelegramAlerter:
    """
    Telegram bot for sending trading alerts.

    Alert types:
    - CRITICAL: Trade executions, errors, circuit breakers
    - INFO: Daily digests, system status
    """

    def __init__(self, bot_token: str, chat_id: str, config: Dict):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.config = config
        self.bot = None

        # Alert settings
        self.alert_on_trade = config.get("alert_on_trade", True)
        self.alert_on_signal = config.get("alert_on_signal", False)
        self.alert_on_error = config.get("alert_on_error", True)
        self.alert_on_pnl_milestone = config.get("alert_on_pnl_milestone", True)
        self.pnl_milestones = config.get(
            "pnl_milestones", [100, 250, 500, -50, -100, -200]
        )
        self.daily_digest_time = config.get("daily_digest_time", "20:00")

        # Track milestones hit today
        self.milestones_hit = set()

        # Initialize bot
        if bot_token and chat_id:
            try:
                self.bot = Bot(token=bot_token)
                logger.info("Telegram bot initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Telegram bot: {e}")

    async def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        Send a message via Telegram.

        Args:
            message: Message text (supports HTML formatting)
            parse_mode: Formatting mode (HTML or Markdown)

        Returns:
            True if successful
        """
        if not self.bot:
            logger.warning("Telegram bot not initialized - message not sent")
            return False

        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=parse_mode,
            )
            logger.debug(f"Telegram message sent: {message[:50]}...")
            return True

        except TelegramError as e:
            logger.error(f"Telegram error: {e}")
            return False

    async def alert_trade_executed(
        self,
        ticker: str,
        side: str,
        quantity: int,
        price: float,
        edge: float,
        confidence: float,
        reasoning: str,
    ):
        """Alert when a trade is executed"""
        if not self.alert_on_trade:
            return

        message = (
            f"✅ <b>Trade Executed</b>\n\n"
            f"<b>Market:</b> {ticker}\n"
            f"<b>Side:</b> {side.upper()}\n"
            f"<b>Quantity:</b> {quantity} contracts\n"
            f"<b>Price:</b> ${price:.2f}\n"
            f"<b>Edge:</b> {edge:.1%}\n"
            f"<b>Confidence:</b> {confidence:.2f}\n\n"
            f"<b>Reasoning:</b>\n{reasoning[:200]}"
        )

        await self.send_message(message)

    async def alert_position_closed(
        self,
        ticker: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        reason: str,
    ):
        """Alert when a position is closed"""
        pnl_emoji = "✅" if pnl > 0 else "❌"

        message = (
            f"{pnl_emoji} <b>Position Closed</b>\n\n"
            f"<b>Market:</b> {ticker}\n"
            f"<b>Entry:</b> ${entry_price:.2f}\n"
            f"<b>Exit:</b> ${exit_price:.2f}\n"
            f"<b>P&L:</b> ${pnl:.2f} ({pnl_pct:.1%})\n"
            f"<b>Reason:</b> {reason}"
        )

        await self.send_message(message)

    async def alert_signal_generated(
        self, source: str, ticker: str, edge: float, confidence: float
    ):
        """Alert when a signal is generated (optional, can be noisy)"""
        if not self.alert_on_signal:
            return

        message = (
            f"📊 <b>Signal Generated</b>\n\n"
            f"<b>Source:</b> {source}\n"
            f"<b>Market:</b> {ticker}\n"
            f"<b>Edge:</b> {edge:.1%}\n"
            f"<b>Confidence:</b> {confidence:.2f}"
        )

        await self.send_message(message)

    async def alert_error(self, error_type: str, message: str):
        """Alert on system errors"""
        if not self.alert_on_error:
            return

        alert = (
            f"🔴 <b>Error: {error_type}</b>\n\n"
            f"{message[:500]}"
        )

        await self.send_message(alert)

    async def alert_circuit_breaker(self, consecutive_losses: int):
        """Alert when circuit breaker trips"""
        message = (
            f"🔴 <b>CIRCUIT BREAKER TRIPPED</b>\n\n"
            f"Trading paused after {consecutive_losses} consecutive losses.\n"
            f"Manual intervention required."
        )

        await self.send_message(message)

    async def alert_daily_loss_limit(self, daily_pnl: float, limit: float):
        """Alert when daily loss limit is reached"""
        message = (
            f"🔴 <b>Daily Loss Limit Reached</b>\n\n"
            f"<b>Daily P&L:</b> ${daily_pnl:.2f}\n"
            f"<b>Limit:</b> ${limit:.2f}\n\n"
            f"Trading paused for today."
        )

        await self.send_message(message)

    async def alert_pnl_milestone(self, daily_pnl: float):
        """Alert when P&L milestone is hit"""
        if not self.alert_on_pnl_milestone:
            return

        # Check if any milestone crossed
        for milestone in self.pnl_milestones:
            milestone_key = f"{datetime.now().date()}_{milestone}"

            # Skip if already alerted today
            if milestone_key in self.milestones_hit:
                continue

            # Check if milestone crossed
            if (milestone > 0 and daily_pnl >= milestone) or (
                milestone < 0 and daily_pnl <= milestone
            ):
                self.milestones_hit.add(milestone_key)

                emoji = "🎉" if milestone > 0 else "⚠️"
                message = (
                    f"{emoji} <b>P&L Milestone</b>\n\n"
                    f"Daily P&L reached <b>${daily_pnl:.2f}</b>\n"
                    f"Milestone: ${milestone}"
                )

                await self.send_message(message)

    async def send_daily_digest(self, stats: Dict):
        """Send daily performance summary"""
        total_trades = stats.get("total_trades", 0)
        winning_trades = stats.get("winning_trades", 0)
        total_pnl = stats.get("total_pnl", 0)
        win_rate = stats.get("win_rate", 0)
        top_performer = stats.get("top_performer", "N/A")
        worst_performer = stats.get("worst_performer", "N/A")
        strategies = stats.get("strategy_breakdown", {})

        emoji = "📈" if total_pnl > 0 else "📉"

        message = (
            f"{emoji} <b>Daily Performance Summary</b>\n"
            f"<b>Date:</b> {datetime.now().strftime('%Y-%m-%d')}\n\n"
            f"<b>Total Trades:</b> {total_trades}\n"
            f"<b>Wins:</b> {winning_trades} ({win_rate:.1%})\n"
            f"<b>Total P&L:</b> ${total_pnl:.2f}\n\n"
            f"<b>Best Trade:</b> {top_performer}\n"
            f"<b>Worst Trade:</b> {worst_performer}\n\n"
            f"<b>Strategy Breakdown:</b>\n"
        )

        for strategy, pnl in strategies.items():
            message += f"  • {strategy}: ${pnl:.2f}\n"

        await self.send_message(message)

    async def send_system_status(self, status: Dict):
        """Send system health status"""
        uptime = status.get("uptime_hours", 0)
        last_trade = status.get("last_trade_time", "Never")
        open_positions = status.get("open_positions", 0)
        balance = status.get("balance", 0)
        errors_24h = status.get("errors_24h", 0)

        message = (
            f"ℹ️ <b>System Status</b>\n\n"
            f"<b>Uptime:</b> {uptime:.1f} hours\n"
            f"<b>Balance:</b> ${balance:.2f}\n"
            f"<b>Open Positions:</b> {open_positions}\n"
            f"<b>Last Trade:</b> {last_trade}\n"
            f"<b>Errors (24h):</b> {errors_24h}\n"
            f"<b>Status:</b> 🟢 Running"
        )

        await self.send_message(message)

    async def start_daily_digest_scheduler(self, stats_callback):
        """
        Start scheduler for daily digest.

        Args:
            stats_callback: Async function that returns daily stats dict
        """
        # Parse digest time
        try:
            hour, minute = map(int, self.daily_digest_time.split(":"))
            digest_time = time(hour, minute)
        except:
            logger.error(f"Invalid digest time: {self.daily_digest_time}")
            return

        logger.info(f"Daily digest scheduled for {self.daily_digest_time} UTC")

        while True:
            now = datetime.now().time()

            # Check if it's time for digest
            if now.hour == digest_time.hour and now.minute == digest_time.minute:
                try:
                    stats = await stats_callback()
                    await self.send_daily_digest(stats)
                except Exception as e:
                    logger.error(f"Error sending daily digest: {e}")

                # Sleep for 60 seconds to avoid sending multiple times
                await asyncio.sleep(60)

            # Check every minute
            await asyncio.sleep(60)

    async def test_connection(self) -> bool:
        """Test Telegram bot connection"""
        if not self.bot:
            return False

        try:
            me = await self.bot.get_me()
            logger.info(f"Telegram bot connected: @{me.username}")

            # Send test message
            await self.send_message("🤖 Kalshi Trading Bot connected successfully!")
            return True

        except Exception as e:
            logger.error(f"Telegram connection test failed: {e}")
            return False
