"""
Централизованная конфигурация арбитражного бота для Polymarket
Все настройки загружаются из .env файла
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Определяем базовую директорию проекта
BASE_DIR = Path(__file__).resolve().parent.parent

# Загружаем переменные окружения из .env
env_path = BASE_DIR / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    print(f"⚠️  WARNING: .env file not found at {env_path}")
    print("Create .env file based on .env.example")


class Settings:
    """Централизованные настройки бота"""

    # ========================================
    # POLYMARKET API
    # ========================================
    POLYMARKET_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws"
    POLYMARKET_REST_API = "https://clob.polymarket.com"
    POLYMARKET_API_KEY = os.getenv("POLYMARKET_API_KEY")
    POLYMARKET_SECRET = os.getenv("POLYMARKET_SECRET")
    POLYMARKET_PASSPHRASE = os.getenv("POLYMARKET_PASSPHRASE")

    # ========================================
    # BLOCKCHAIN (POLYGON)
    # ========================================
    POLYGON_RPC_URL = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")
    PRIVATE_KEY = os.getenv("PRIVATE_KEY")
    CHAIN_ID = 137  # Polygon Mainnet

    # Contract addresses (Polymarket)
    CTF_EXCHANGE_ADDRESS = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
    COLLATERAL_TOKEN = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"  # USDC on Polygon

    # ========================================
    # REDIS
    # ========================================
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    REDIS_KEY_TTL = 60  # Время жизни ключей в секундах

    # ========================================
    # ARBITRAGE STRATEGY
    # ========================================
    # Порог для арбитража: если P_yes + P_no < ARB_THRESHOLD, это возможность
    ARB_THRESHOLD = float(os.getenv("ARB_THRESHOLD", 0.998))

    # Минимальная прибыль в процентах для входа в сделку
    MIN_PROFIT_PERCENT = float(os.getenv("MIN_PROFIT_PERCENT", 0.2))

    # Минимальная ликвидность в стакане (USD)
    MIN_LIQUIDITY_USD = float(os.getenv("MIN_LIQUIDITY_USD", 50))

    # Максимальное проскальзывание при исполнении (%)
    MAX_SLIPPAGE_PERCENT = 0.5

    # ========================================
    # RISK MANAGEMENT
    # ========================================
    # Максимальный размер одной позиции в USD
    MAX_POSITION_SIZE_USD = float(os.getenv("MAX_POSITION_SIZE_USD", 100))

    # Лимит дневных потерь (%)
    DAILY_LOSS_LIMIT_PERCENT = float(os.getenv("DAILY_LOSS_LIMIT_PERCENT", 5))

    # Максимальное количество открытых позиций одновременно
    MAX_OPEN_POSITIONS = 10

    # ========================================
    # EXECUTION
    # ========================================
    # Таймаут для ордера (секунды)
    ORDER_TIMEOUT_SECONDS = 30

    # Множитель для gas price (для быстрой отправки)
    GAS_PRICE_MULTIPLIER = 1.2

    # Максимальное количество попыток отправки транзакции
    MAX_RETRIES = 3

    # Задержка между попытками (секунды)
    RETRY_DELAY = 2

    # ========================================
    # TELEGRAM NOTIFICATIONS
    # ========================================
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    TELEGRAM_ENABLED = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

    # Отправлять уведомления о каждой найденной возможности
    NOTIFY_OPPORTUNITIES = True

    # Отправлять уведомления о каждой сделке
    NOTIFY_TRADES = True

    # ========================================
    # LOGGING
    # ========================================
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = BASE_DIR / "logs" / "bot.log"
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5

    # ========================================
    # PATHS
    # ========================================
    DATA_DIR = BASE_DIR / "data"
    HISTORICAL_DIR = DATA_DIR / "historical"
    TRADES_FILE = DATA_DIR / "trades.json"
    LOGS_DIR = BASE_DIR / "logs"

    # ========================================
    # MONITORING
    # ========================================
    # Интервал проверки health check (секунды)
    HEALTH_CHECK_INTERVAL = 60

    # Интервал отправки дневного отчета (часы)
    DAILY_REPORT_HOUR = 18  # 18:00

    @classmethod
    def validate(cls):
        """
        Проверка обязательных настроек перед запуском бота
        Raises ValueError если критичные настройки не установлены
        """
        errors = []

        # Проверка критичных параметров
        if not cls.PRIVATE_KEY:
            errors.append("❌ PRIVATE_KEY не установлен в .env")

        if not cls.POLYMARKET_API_KEY:
            errors.append("❌ POLYMARKET_API_KEY не установлен в .env")

        if not cls.POLYMARKET_SECRET:
            errors.append("❌ POLYMARKET_SECRET не установлен в .env")

        if not cls.POLYMARKET_PASSPHRASE:
            errors.append("❌ POLYMARKET_PASSPHRASE не установлен в .env")

        # Проверка корректности числовых параметров
        if cls.ARB_THRESHOLD >= 1.0 or cls.ARB_THRESHOLD <= 0:
            errors.append("❌ ARB_THRESHOLD должен быть между 0 и 1")

        if cls.MAX_POSITION_SIZE_USD <= 0:
            errors.append("❌ MAX_POSITION_SIZE_USD должен быть больше 0")

        # Если есть ошибки, выбрасываем исключение
        if errors:
            error_msg = "\n".join(errors)
            raise ValueError(f"\n⚠️  Ошибки конфигурации:\n{error_msg}\n")

        # Создание необходимых директорий
        cls._create_directories()

        # Вывод успешной валидации
        print("✅ Конфигурация успешно загружена и валидирована")
        return True

    @classmethod
    def _create_directories(cls):
        """Создание необходимых директорий для работы бота"""
        directories = [
            cls.DATA_DIR,
            cls.HISTORICAL_DIR,
            cls.LOGS_DIR
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    @classmethod
    def print_config(cls):
        """Вывод текущей конфигурации (без приватных ключей)"""
        print("\n" + "=" * 60)
        print("📊 КОНФИГУРАЦИЯ БОТА")
        print("=" * 60)
        print(f"🔗 Polymarket API: {cls.POLYMARKET_REST_API}")
        print(f"🔗 WebSocket: {cls.POLYMARKET_WS_URL}")
        print(f"⛓️  Blockchain: Polygon (Chain ID: {cls.CHAIN_ID})")
        print(f"🗄️  Redis: {cls.REDIS_HOST}:{cls.REDIS_PORT}")
        print(f"\n💰 СТРАТЕГИЯ:")
        print(f"   Threshold: {cls.ARB_THRESHOLD}")
        print(f"   Min Profit: {cls.MIN_PROFIT_PERCENT}%")
        print(f"   Min Liquidity: ${cls.MIN_LIQUIDITY_USD}")
        print(f"\n🛡️  РИСК-МЕНЕДЖМЕНТ:")
        print(f"   Max Position: ${cls.MAX_POSITION_SIZE_USD}")
        print(f"   Daily Loss Limit: {cls.DAILY_LOSS_LIMIT_PERCENT}%")
        print(f"   Max Open Positions: {cls.MAX_OPEN_POSITIONS}")
        print(f"\n📱 Telegram: {'✅ Включен' if cls.TELEGRAM_ENABLED else '❌ Выключен'}")
        print("=" * 60 + "\n")


# Создаем singleton экземпляр настроек
settings = Settings()

# Автоматическая валидация при импорте (опционально)
if __name__ == "__main__":
    try:
        settings.validate()
        settings.print_config()
    except ValueError as e:
        print(e)
        exit(1)