import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
import colorlog


def setup_logger(name: str, log_file: Path = None, level: str = "INFO"):
    """
    Настройка логгера с цветным выводом в консоль и ротацией файлов

    Args:
        name: Имя логгера
        log_file: Путь к файлу логов
        level: Уровень логирования
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Избегаем дублирования handlers
    if logger.handlers:
        return logger

    # Формат логов
    log_format = "%(log_color)s%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Консольный handler с цветами
    console_handler = colorlog.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_formatter = colorlog.ColoredFormatter(
        log_format,
        datefmt=date_format,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Файловый handler с ротацией
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt=date_format
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


class BotLogger:
    """Специализированный логгер для арбитражного бота"""

    def __init__(self, log_file: Path = None):
        self.logger = setup_logger("ArbBot", log_file)

    def opportunity_found(self, market_id: str, yes_price: float, no_price: float, profit: float):
        """Логирование найденной возможности"""
        self.logger.info(
            f"🎯 OPPORTUNITY | Market: {market_id} | "
            f"Yes: {yes_price:.4f} | No: {no_price:.4f} | "
            f"Sum: {yes_price + no_price:.4f} | Profit: {profit:.2f}%"
        )

    def trade_executed(self, market_id: str, volume: float, expected_profit: float):
        """Логирование выполненной сделки"""
        self.logger.info(
            f"✅ TRADE EXECUTED | Market: {market_id} | "
            f"Volume: ${volume:.2f} | Expected Profit: {expected_profit:.2f}%"
        )

    def trade_failed(self, market_id: str, reason: str):
        """Логирование неудачной сделки"""
        self.logger.error(
            f"❌ TRADE FAILED | Market: {market_id} | Reason: {reason}"
        )

    def risk_limit_hit(self, limit_type: str, value: float):
        """Логирование достижения риск-лимита"""
        self.logger.critical(
            f"🚨 RISK LIMIT HIT | Type: {limit_type} | Value: {value}"
        )

    def connection_status(self, service: str, status: str):
        """Логирование статуса подключения"""
        emoji = "🟢" if status == "connected" else "🔴"
        self.logger.info(f"{emoji} {service.upper()} | Status: {status}")

    def info(self, msg: str):
        self.logger.info(msg)

    def warning(self, msg: str):
        self.logger.warning(msg)

    def error(self, msg: str, exc_info=False):
        self.logger.error(msg, exc_info=exc_info)

    def debug(self, msg: str):
        self.logger.debug(msg)