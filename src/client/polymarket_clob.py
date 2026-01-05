import json
import asyncio
import websockets
import time
from typing import Callable, Optional, List
from config.settings import settings
from src.utils.logger import setup_logger
from src.clients.redis_client import get_redis_client

logger = setup_logger("PolymarketCLOB")


class PolymarketCLOBClient:
    """
    WebSocket клиент для подключения к Polymarket CLOB API
    Отвечает ТОЛЬКО за получение данных и запись в Redis
    """

    def __init__(self, market_ids: List[str]):
        self.ws_url = settings.POLYMARKET_WS_URL
        self.market_ids = market_ids
        self.websocket = None
        self.running = False
        self.redis = get_redis_client()
        self.reconnect_delay = 5
        self.max_reconnect_delay = 60

    async def connect(self):
        """Установка WebSocket соединения"""
        try:
            self.websocket = await websockets.connect(
                self.ws_url,
                ping_interval=20,
                ping_timeout=10
            )
            logger.info(f"Connected to Polymarket WebSocket: {self.ws_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            return False

    async def subscribe_to_markets(self):
        """Подписка на обновления книги ордеров для списка рынков"""
        if not self.websocket:
            logger.error("WebSocket not connected")
            return False

        for market_id in self.market_ids:
            subscribe_msg = {
                "type": "subscribe",
                "channel": "book",
                "market": market_id
            }

            try:
                await self.websocket.send(json.dumps(subscribe_msg))
                logger.info(f"Subscribed to market: {market_id}")
            except Exception as e:
                logger.error(f"Failed to subscribe to market {market_id}: {e}")
                return False

        return True

    def process_orderbook_update(self, data: dict):
        """
        Обработка обновления книги ордеров и запись в Redis

        Ожидаемая структура данных:
        {
            "market": "market_id",
            "bids": [[price, size], ...],
            "asks": [[price, size], ...],
            "timestamp": 1234567890
        }
        """
        try:
            market_id = data.get("market")
            timestamp = data.get("timestamp", time.time())

            # Получаем лучшие цены продажи (asks) для Yes и No
            # В Polymarket каждый исход торгуется отдельно
            asks = data.get("asks", [])

            if not asks or len(asks) == 0:
                return

            # Берем лучший ask (наименьшая цена продажи)
            best_ask = asks[0]
            price = float(best_ask[0])
            size = float(best_ask[1])

            # Определяем сторону (yes/no) из данных
            # Обычно это приходит в поле "asset" или "side"
            side = data.get("asset", "yes").lower()

            # Сохраняем в Redis
            self.redis.set_orderbook(
                market_id=market_id,
                side=side,
                price=price,
                size=size,
                timestamp=timestamp
            )

            logger.debug(
                f"Orderbook updated | Market: {market_id} | "
                f"Side: {side} | Price: {price:.4f} | Size: {size:.2f}"
            )

        except Exception as e:
            logger.error(f"Error processing orderbook update: {e}", exc_info=True)

    async def listen(self):
        """Основной цикл прослушивания WebSocket"""
        self.running = True

        while self.running:
            try:
                if not self.websocket:
                    connected = await self.connect()
                    if not connected:
                        await asyncio.sleep(self.reconnect_delay)
                        self.reconnect_delay = min(
                            self.reconnect_delay * 2,
                            self.max_reconnect_delay
                        )
                        continue

                    # Подписываемся на рынки после подключения
                    await self.subscribe_to_markets()
                    self.reconnect_delay = 5  # Сброс задержки после успешного подключения

                # Слушаем сообщения
                message = await self.websocket.recv()
                data = json.loads(message)

                # Обработка разных типов сообщений
                msg_type = data.get("type")

                if msg_type == "book_update":
                    self.process_orderbook_update(data)
                elif msg_type == "subscribed":
                    logger.info(f"Subscription confirmed for market: {data.get('market')}")
                elif msg_type == "error":
                    logger.error(f"WebSocket error: {data.get('message')}")

            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket connection closed. Reconnecting...")
                self.websocket = None
                await asyncio.sleep(self.reconnect_delay)

            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode JSON message: {e}")

            except Exception as e:
                logger.error(f"Unexpected error in listen loop: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def stop(self):
        """Остановка клиента"""
        self.running = False
        if self.websocket:
            await self.websocket.close()
            logger.info("WebSocket connection closed")

    def add_market(self, market_id: str):
        """Добавление нового рынка для отслеживания"""
        if market_id not in self.market_ids:
            self.market_ids.append(market_id)
            logger.info(f"Added market to watch list: {market_id}")

    def remove_market(self, market_id: str):
        """Удаление рынка из отслеживания"""
        if market_id in self.market_ids:
            self.market_ids.remove(market_id)
            logger.info(f"Removed market from watch list: {market_id}")