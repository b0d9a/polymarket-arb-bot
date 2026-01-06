"""Клиенты для подключения к внешним сервисам"""

# Эти строки позволяют делать импорт короче:
# вместо: from src.clients.redis_client import RedisClient
# можно будет писать: from src.clients import RedisClient

try:
    from .redis_client import RedisClient
    from .polymarket_clob import PolymarketClient
except ImportError:
    # Если файлов еще нет, Python не выдаст ошибку при запуске
    pass

__all__ = ["RedisClient", "PolymarketClient"]