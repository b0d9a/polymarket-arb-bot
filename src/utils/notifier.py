import asyncio
from typing import Optional
from telegram import Bot
from telegram.error import TelegramError
from config.settings import settings
from src.utils.logger import setup_logger

logger = setup_logger("Notifier")


class TelegramNotifier:
    """Отправка уведомлений в Telegram"""

    def __init__(self, token: str = None, chat_id: str = None):
        self.token = token or settings.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or settings.TELEGRAM_CHAT_ID
        self.enabled = settings.TELEGRAM_ENABLED and bool(self.token and self.chat_id)
        self.bot: Optional[Bot] = None

        if self.enabled:
            self.bot = Bot(token=self.token)
            logger.info("Telegram notifier initialized")
        else:
            logger.warning("Telegram notifier disabled (missing credentials)")

    async def send_message(self, message: str, parse_mode: str = "HTML"):
        """Отправка сообщения в Telegram"""
        if not self.enabled:
            return False

        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=parse_mode
            )
            return True
        except TelegramError as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    async def notify_opportunity(self, market_id: str, yes_price: float,
                                 no_price: float, profit: float):
        """Уведомление о найденной возможности"""
        message = (
            f"🎯 <b>Arbitrage Opportunity</b>\n\n"
            f"Market: <code>{market_id}</code>\n"
            f"Yes Price: {yes_price:.4f}\n"
            f"No Price: {no_price:.4f}\n"
            f"Sum: {yes_price + no_price:.4f}\n"
            f"Expected Profit: <b>{profit:.2f}%</b>"
        )
        await self.send_message(message)

    async def notify_trade(self, market_id: str, volume: float,
                           expected_profit: float, success: bool = True):
        """Уведомление о выполненной сделке"""
        emoji = "✅" if success else "❌"
        status = "Executed" if success else "Failed"

        message = (
            f"{emoji} <b>Trade {status}</b>\n\n"
            f"Market: <code>{market_id}</code>\n"
            f"Volume: ${volume:.2f}\n"
            f"Expected Profit: {expected_profit:.2f}%"
        )
        await self.send_message(message)

    async def notify_risk_alert(self, alert_type: str, message: str):
        """Критическое уведомление о рисках"""
        alert_message = (
            f"🚨 <b>RISK ALERT: {alert_type}</b>\n\n"
            f"{message}"
        )
        await self.send_message(alert_message)

    async def notify_bot_status(self, status: str, details: str = ""):
        """Уведомление о статусе бота"""
        emoji = "🟢" if status == "started" else "🔴"
        message = (
            f"{emoji} <b>Bot {status.upper()}</b>\n\n"
            f"{details}"
        )
        await self.send_message(message)

    async def notify_daily_report(self, trades_count: int, profit: float,
                                  volume: float, win_rate: float):
        """Ежедневный отчет"""
        message = (
            f"📊 <b>Daily Report</b>\n\n"
            f"Trades: {trades_count}\n"
            f"Total Profit: ${profit:.2f}\n"
            f"Volume: ${volume:.2f}\n"
            f"Win Rate: {win_rate:.1f}%"
        )
        await self.send_message(message)


# Singleton instance
_notifier_instance = None


def get_notifier() -> TelegramNotifier:
    """Получение singleton экземпляра notifier"""
    global _notifier_instance
    if _notifier_instance is None:
        _notifier_instance = TelegramNotifier()
    return _notifier_instance