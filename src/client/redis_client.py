import json
import redis
from typing import Optional, Dict, Any
from config.settings import settings
from src.utils.logger import setup_logger

logger = setup_logger("RedisClient")


class RedisClient:
    """Клиент для работы с Redis - быстрое хранилище данных о ценах"""

    def __init__(self):
        self.client: Optional[redis.Redis] = None
        self.connected = False

    def connect(self):
        """Подключение к Redis"""
        try:
            self.client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
                db=settings.REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True
            )
            # Проверка подключения
            self.client.ping()
            self.connected = True
            logger.info(f"Connected to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
            return True
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Отключение от Redis"""
        if self.client:
            self.client.close()
            self.connected = False
            logger.info("Disconnected from Redis")

    def set_orderbook(self, market_id: str, side: str, price: float,
                      size: float, timestamp: float):
        """
        Сохранение данных о стакане ордеров

        Args:
            market_id: ID рынка
            side: 'yes' или 'no'
            price: Цена лучшего аска
            size: Объем по этой цене
            timestamp: Временная метка
        """
        if not self.connected:
            return False

        key = f"orderbook:{market_id}:{side}"
        data = {
            "price": price,
            "size": size,
            "timestamp": timestamp
        }

        try:
            self.client.setex(
                key,
                settings.REDIS_KEY_TTL,
                json.dumps(data)
            )
            return True
        except Exception as e:
            logger.error(f"Failed to set orderbook data: {e}")
            return False

    def get_orderbook(self, market_id: str, side: str) -> Optional[Dict[str, Any]]:
        """
        Получение данных о стакане ордеров

        Args:
            market_id: ID рынка
            side: 'yes' или 'no'

        Returns:
            Dict с ценой, размером и временной меткой или None
        """
        if not self.connected:
            return None

        key = f"orderbook:{market_id}:{side}"

        try:
            data = self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get orderbook data: {e}")
            return None

    def get_both_sides(self, market_id: str) -> Optional[Dict[str, Dict]]:
        """
        Получение данных о обеих сторонах рынка (yes и no)

        Returns:
            Dict с ключами 'yes' и 'no' или None
        """
        yes_data = self.get_orderbook(market_id, "yes")
        no_data = self.get_orderbook(market_id, "no")

        if yes_data and no_data:
            return {
                "yes": yes_data,
                "no": no_data
            }
        return None

    def set_market_status(self, market_id: str, status: str):
        """Сохранение статуса рынка (active/halted/closed)"""
        if not self.connected:
            return False

        key = f"market:status:{market_id}"
        try:
            self.client.setex(key, settings.REDIS_KEY_TTL * 10, status)
            return True
        except Exception as e:
            logger.error(f"Failed to set market status: {e}")
            return False

    def get_market_status(self, market_id: str) -> Optional[str]:
        """Получение статуса рынка"""
        if not self.connected:
            return None

        key = f"market:status:{market_id}"
        try:
            return self.client.get(key)
        except Exception as e:
            logger.error(f"Failed to get market status: {e}")
            return None

    def increment_trade_counter(self, date: str) -> int:
        """Увеличение счетчика сделок за день"""
        if not self.connected:
            return 0

        key = f"trades:count:{date}"
        try:
            count = self.client.incr(key)
            self.client.expire(key, 86400 * 2)  # 2 дня TTL
            return count
        except Exception as e:
            logger.error(f"Failed to increment trade counter: {e}")
            return 0

    def set_daily_pnl(self, date: str, pnl: float):
        """Сохранение дневного P&L"""
        if not self.connected:
            return False

        key = f"pnl:daily:{date}"
        try:
            self.client.setex(key, 86400 * 7, str(pnl))  # 7 дней TTL
            return True
        except Exception as e:
            logger.error(f"Failed to set daily PnL: {e}")
            return False

    def get_daily_pnl(self, date: str) -> float:
        """Получение дневного P&L"""
        if not self.connected:
            return 0.0

        key = f"pnl:daily:{date}"
        try:
            pnl = self.client.get(key)
            return float(pnl) if pnl else 0.0
        except Exception as e:
            logger.error(f"Failed to get daily PnL: {e}")
            return 0.0

    def health_check(self) -> bool:
        """Проверка работоспособности Redis"""
        try:
            return self.client.ping() if self.client else False
        except:
            return False


# Singleton instance
_redis_client_instance = None


def get_redis_client() -> RedisClient:
    """Получение singleton экземпляра Redis клиента"""
    global _redis_client_instance
    if _redis_client_instance is None:
        _redis_client_instance = RedisClient()
        _redis_client_instance.connect()
    return _redis_client_instance