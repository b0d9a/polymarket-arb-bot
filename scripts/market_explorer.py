"""
Скрипт-сканер для поиска арбитражных возможностей на Polymarket
БЕЗ реальной торговли - только мониторинг и логирование

Использование:
    python scripts/market_explorer.py
"""

import sys
import asyncio
import time
from pathlib import Path
from datetime import datetime

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings
from src.utils.logger import BotLogger
from src.utils.notifier import get_notifier
from src.clients.redis_client import get_redis_client
import requests


class MarketExplorer:
    """Простой сканер для поиска арбитражных возможностей"""

    def __init__(self):
        self.logger = BotLogger(settings.LOG_FILE)
        self.notifier = get_notifier()
        self.redis = get_redis_client()
        self.running = False

        # Статистика
        self.opportunities_found = 0
        self.markets_scanned = 0
        self.start_time = None

    def get_active_markets(self, limit: int = 50):
        """
        Получение списка активных рынков через REST API

        Returns:
            List[dict]: Список рынков с их ID и метаданными
        """
        try:
            url = f"{settings.POLYMARKET_REST_API}/markets"
            params = {
                "limit": limit,
                "closed": False  # Только активные рынки
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            markets = response.json()
            self.logger.info(f"Загружено {len(markets)} активных рынков")
            return markets

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Ошибка при загрузке рынков: {e}")
            return []

    def get_orderbook(self, token_id: str):
        """
        Получение книги ордеров для конкретного токена

        Args:
            token_id: ID токена (Yes или No outcome)

        Returns:
            dict: Книга ордеров с asks и bids
        """
        try:
            url = f"{settings.POLYMARKET_REST_API}/book"
            params = {"token_id": token_id}

            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            self.logger.debug(f"Ошибка при получении orderbook для {token_id}: {e}")
            return None

    def calculate_arbitrage(self, yes_price: float, no_price: float,
                            yes_size: float, no_size: float):
        """
        Расчет возможности арбитража

        Returns:
            dict: Информация о возможности или None
        """
        price_sum = yes_price + no_price

        # Проверка на арбитраж
        if price_sum < settings.ARB_THRESHOLD:
            # Расчет потенциальной прибыли
            # Если мы купим по 1$ каждого исхода, то заработаем (1 - price_sum)
            profit_per_dollar = 1.0 - price_sum
            profit_percent = (profit_per_dollar / price_sum) * 100

            # Максимальный объем ограничен минимальной ликвидностью
            max_volume = min(yes_size, no_size)

            # Проверка на минимальную ликвидность
            if max_volume >= settings.MIN_LIQUIDITY_USD:
                return {
                    "yes_price": yes_price,
                    "no_price": no_price,
                    "price_sum": price_sum,
                    "profit_percent": profit_percent,
                    "max_volume": max_volume,
                    "expected_profit_usd": profit_per_dollar * max_volume
                }

        return None

    def scan_market(self, market: dict):
        """
        Сканирование одного рынка на наличие арбитража

        Args:
            market: Данные рынка из API
        """
        try:
            market_id = market.get("id")
            question = market.get("question", "Unknown")

            # Получаем токены Yes и No
            tokens = market.get("tokens", [])
            if len(tokens) < 2:
                return

            yes_token = tokens[0].get("token_id")
            no_token = tokens[1].get("token_id")

            # Получаем книги ордеров для обоих исходов
            yes_book = self.get_orderbook(yes_token)
            no_book = self.get_orderbook(no_token)

            if not yes_book or not no_book:
                return

            # Извлекаем лучшие цены продажи (asks)
            yes_asks = yes_book.get("asks", [])
            no_asks = no_book.get("asks", [])

            if not yes_asks or not no_asks:
                return

            # Берем лучший ask (минимальная цена продажи)
            best_yes_ask = yes_asks[0]
            best_no_ask = no_asks[0]

            yes_price = float(best_yes_ask["price"])
            no_price = float(best_no_ask["price"])
            yes_size = float(best_yes_ask["size"])
            no_size = float(best_no_ask["size"])

            # Проверяем на арбитраж
            opportunity = self.calculate_arbitrage(
                yes_price, no_price, yes_size, no_size
            )

            if opportunity:
                self.opportunities_found += 1

                # Логирование
                self.logger.opportunity_found(
                    market_id=market_id,
                    yes_price=yes_price,
                    no_price=no_price,
                    profit=opportunity["profit_percent"]
                )

                # Детальный вывод
                print("\n" + "=" * 70)
                print(f"🎯 АРБИТРАЖНАЯ ВОЗМОЖНОСТЬ #{self.opportunities_found}")
                print("=" * 70)
                print(f"📊 Рынок: {question[:60]}")
                print(f"🆔 Market ID: {market_id}")
                print(f"\n💰 ЦЕНЫ:")
                print(f"   Yes: ${yes_price:.4f} (объем: ${yes_size:.2f})")
                print(f"   No:  ${no_price:.4f} (объем: ${no_size:.2f})")
                print(f"   Сумма: ${opportunity['price_sum']:.4f}")
                print(f"\n📈 ПРИБЫЛЬ:")
                print(f"   Процент: {opportunity['profit_percent']:.2f}%")
                print(f"   Макс. объем: ${opportunity['max_volume']:.2f}")
                print(f"   Ожидаемая прибыль: ${opportunity['expected_profit_usd']:.2f}")
                print(f"\n⏰ Время: {datetime.now().strftime('%H:%M:%S')}")
                print("=" * 70 + "\n")

                # Отправка уведомления в Telegram
                if settings.TELEGRAM_ENABLED and settings.NOTIFY_OPPORTUNITIES:
                    asyncio.create_task(
                        self.notifier.notify_opportunity(
                            market_id=market_id,
                            yes_price=yes_price,
                            no_price=no_price,
                            profit=opportunity["profit_percent"]
                        )
                    )

            self.markets_scanned += 1

        except Exception as e:
            self.logger.error(f"Ошибка при сканировании рынка: {e}", exc_info=True)

    async def scan_loop(self, interval: int = 10):
        """
        Основной цикл сканирования

        Args:
            interval: Интервал между сканированиями в секундах
        """
        self.running = True
        self.start_time = time.time()

        self.logger.info("🚀 Запуск сканера арбитражных возможностей")
        self.logger.info(f"⚙️  Настройки: Threshold={settings.ARB_THRESHOLD}, "
                         f"Min Profit={settings.MIN_PROFIT_PERCENT}%")

        # Уведомление о старте
        if settings.TELEGRAM_ENABLED:
            await self.notifier.notify_bot_status(
                "started",
                f"Сканер запущен\nИнтервал: {interval}с"
            )

        iteration = 0

        while self.running:
            try:
                iteration += 1
                self.logger.info(f"\n{'=' * 50}")
                self.logger.info(f"📡 Итерация #{iteration}")
                self.logger.info(f"{'=' * 50}")

                # Получаем активные рынки
                markets = self.get_active_markets(limit=20)

                if not markets:
                    self.logger.warning("Не удалось загрузить рынки")
                    await asyncio.sleep(interval)
                    continue

                # Сканируем каждый рынок
                for market in markets:
                    self.scan_market(market)
                    await asyncio.sleep(0.5)  # Небольшая задержка между запросами

                # Статистика
                elapsed = time.time() - self.start_time
                self.logger.info(
                    f"\n📊 Статистика: Рынков отсканировано: {self.markets_scanned} | "
                    f"Возможностей найдено: {self.opportunities_found} | "
                    f"Работает: {elapsed / 60:.1f} мин"
                )

                # Ждем следующую итерацию
                self.logger.info(f"⏳ Следующее сканирование через {interval} секунд...")
                await asyncio.sleep(interval)

            except KeyboardInterrupt:
                self.logger.info("\n⚠️  Получен сигнал остановки")
                break
            except Exception as e:
                self.logger.error(f"Ошибка в цикле сканирования: {e}", exc_info=True)
                await asyncio.sleep(interval)

        # Финальная статистика
        await self.print_final_stats()

    async def print_final_stats(self):
        """Вывод финальной статистики"""
        elapsed = time.time() - self.start_time

        print("\n" + "=" * 70)
        print("📊 ФИНАЛЬНАЯ СТАТИСТИКА")
        print("=" * 70)
        print(f"⏱️  Время работы: {elapsed / 60:.1f} минут")
        print(f"🔍 Рынков отсканировано: {self.markets_scanned}")
        print(f"🎯 Возможностей найдено: {self.opportunities_found}")

        if self.opportunities_found > 0:
            rate = (self.opportunities_found / self.markets_scanned) * 100
            print(f"📈 Процент возможностей: {rate:.2f}%")

        print("=" * 70 + "\n")

        # Уведомление об остановке
        if settings.TELEGRAM_ENABLED:
            await self.notifier.notify_bot_status(
                "stopped",
                f"Возможностей найдено: {self.opportunities_found}\n"
                f"Время работы: {elapsed / 60:.1f} мин"
            )

    def stop(self):
        """Остановка сканера"""
        self.running = False


async def main():
    """Точка входа"""
    print("\n" + "=" * 70)
    print("🔍 POLYMARKET ARBITRAGE SCANNER")
    print("=" * 70)
    print("Этот скрипт ищет арбитражные возможности БЕЗ реальной торговли")
    print("Нажмите Ctrl+C для остановки")
    print("=" * 70 + "\n")

    # Валидация настроек
    try:
        # Для сканера не нужны все ключи, только API
        settings.print_config()
    except Exception as e:
        print(f"❌ Ошибка конфигурации: {e}")
        return

    # Создаем и запускаем сканер
    explorer = MarketExplorer()

    try:
        await explorer.scan_loop(interval=10)
    except KeyboardInterrupt:
        print("\n⚠️  Остановка сканера...")
        explorer.stop()
    finally:
        print("👋 Сканер остановлен")


if __name__ == "__main__":
    asyncio.run(main())