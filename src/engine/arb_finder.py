import asyncio
from typing import List, Optional
from datetime import datetime
from src.clients.redis_client import redis_client
from src.engine.calculator import ArbCalculator, ArbOpportunity
from src.utils.logger import BotLogger
from src.utils.notifier import notifier

logger = BotLogger("ArbFinder")


class ArbitrageFinder:
    """
    Сканер арбитражных возможностей
    Постоянно мониторит Redis на предмет появления аномалий P_yes + P_no < 1
    """

    def __init__(self, scan_interval: float = 0.1):
        """
        Args:
            scan_interval: Интервал сканирования в секундах (0.1 = 100ms)
        """
        self.scan_interval = scan_interval
        self.calculator = ArbCalculator()
        self.is_running = False
        self._active_markets: set = set()

        # Кэш для предотвращения дублирования уведомлений
        self._last_notified: dict = {}
        self._notification_cooldown = 60  # секунд

    async def start(self, market_ids: List[str]):
        """
        Запуск сканера

        Args:
            market_ids: Список ID рынков для мониторинга
        """
        self.is_running = True
        self._active_markets = set(market_ids)

        logger.info(f"🔍 Arb Finder started, monitoring {len(market_ids)} markets")
        logger.info(f"📊 Scan interval: {self.scan_interval * 1000:.0f}ms")

        # Сохраняем активные рынки в Redis
        redis_client.set_active_markets(market_ids)
        redis_client.set_bot_status("running")

        try:
            while self.is_running:
                await self._scan_cycle()
                await asyncio.sleep(self.scan_interval)
        except Exception as e:
            logger.error(f"Arb Finder crashed: {e}", exc_info=True)
            await notifier.notify_error(f"Arb Finder crashed: {e}", critical=True)
        finally:
            redis_client.set_bot_status("stopped")

    async def _scan_cycle(self):
        """Один цикл сканирования всех рынков"""
        opportunities = []

        for market_id in self._active_markets:
            opportunity = await self._check_market(market_id)
            if opportunity:
                opportunities.append(opportunity)

        # Обработка найденных возможностей
        if opportunities:
            await self._process_opportunities(opportunities)

    async def _check_market(self, market_id: str) -> Optional[ArbOpportunity]:
        """
        Проверка одного рынка на наличие арбитража

        Returns:
            ArbOpportunity если найдена аномалия, иначе None
        """
        try:
            # Получаем данные из Redis
            orderbook = redis_client.get_both_sides(market_id)

            if not orderbook:
                return None

            # Расчет возможности
            opportunity = self.calculator.calculate_opportunity(
                market_id=market_id,
                yes_data=orderbook['yes'],
                no_data=orderbook['no']
            )

            return opportunity

        except Exception as e:
            logger.debug(f"Error checking market {market_id[:8]}: {e}")
            return None

    async def _process_opportunities(self, opportunities: List[ArbOpportunity]):
        """
        Обработка найденных арбитражных возможностей

        В этой версии: логирование и уведомления
        В полной версии: отправка в Execution Engine
        """
        # Сортировка по прибыльности
        opportunities.sort(key=lambda x: x.profit_percent, reverse=True)

        for opp in opportunities:
            # Инкремент счетчика
            redis_client.increment_opportunities_found()

            # Логирование
            logger.opportunity_found(
                opp.market_id,
                opp.sum_price,
                opp.profit_percent
            )

            # Детальный вывод
            logger.debug(
                f"  YES: {opp.yes_ask_price:.4f} x {opp.yes_ask_size:.2f} | "
                f"NO: {opp.no_ask_price:.4f} x {opp.no_ask_size:.2f}"
            )
            logger.debug(
                f"  Max Volume: ${opp.max_volume:.2f} | "
                f"Expected Profit: ${opp.expected_profit_usd:.2f}"
            )

            # Уведомление в Telegram (с cooldown)
            if self._should_notify(opp.market_id):
                await notifier.notify_opportunity(
                    opp.market_id,
                    opp.sum_price,
                    opp.profit_percent
                )
                self._last_notified[opp.market_id] = datetime.now()

            # TODO: Отправить в Execution Engine
            # await self.execution_engine.execute(opp)

    def _should_notify(self, market_id: str) -> bool:
        """
        Проверка, нужно ли отправлять уведомление
        (чтобы не спамить при повторяющихся возможностях)
        """
        if market_id not in self._last_notified:
            return True

        time_since_last = (datetime.now() - self._last_notified[market_id]).total_seconds()
        return time_since_last > self._notification_cooldown

    def stop(self):
        """Остановка сканера"""
        self.is_running = False
        logger.info("🛑 Arb Finder stopped")

    def add_market(self, market_id: str):
        """Добавление рынка в мониторинг"""
        self._active_markets.add(market_id)
        redis_client.set_active_markets(list(self._active_markets))
        logger.info(f"➕ Added market to monitoring: {market_id[:16]}...")

    def remove_market(self, market_id: str):
        """Удаление рынка из мониторинга"""
        self._active_markets.discard(market_id)
        redis_client.set_active_markets(list(self._active_markets))
        logger.info(f"➖ Removed market from monitoring: {market_id[:16]}...")

    def get_stats(self) -> dict:
        """Получение статистики работы"""
        redis_stats = redis_client.get_stats()
        return {
            'active_markets': len(self._active_markets),
            'is_running': self.is_running,
            'scan_interval_ms': self.scan_interval * 1000,
            **redis_stats
        }