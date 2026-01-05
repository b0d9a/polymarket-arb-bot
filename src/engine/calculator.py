from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from config.settings import settings
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class ArbOpportunity:
    """Структура данных для арбитражной возможности"""
    market_id: str
    sum_price: float  # P_yes + P_no
    profit_percent: float  # Потенциальная прибыль в %

    yes_ask_price: float
    yes_ask_size: float
    no_ask_price: float
    no_ask_size: float

    max_volume: float  # Максимальный объем для торговли
    expected_profit_usd: float

    def __str__(self):
        return (
            f"ArbOpportunity(market={self.market_id[:8]}..., "
            f"sum={self.sum_price:.4f}, profit={self.profit_percent:.2f}%, "
            f"volume={self.max_volume:.2f})"
        )


class ArbCalculator:
    """Калькулятор для расчета арбитражных возможностей"""

    @staticmethod
    def calculate_opportunity(
            market_id: str,
            yes_data: Dict,
            no_data: Dict
    ) -> Optional[ArbOpportunity]:
        """
        Проверка наличия арбитражной возможности

        Args:
            market_id: ID рынка
            yes_data: {'best_ask': float, 'ask_size': float, ...}
            no_data: {'best_ask': float, 'ask_size': float, ...}

        Returns:
            ArbOpportunity если возможность есть, иначе None
        """
        try:
            yes_ask = yes_data.get('best_ask')
            yes_size = yes_data.get('ask_size')
            no_ask = no_data.get('best_ask')
            no_size = no_data.get('ask_size')

            # Проверка наличия всех необходимых данных
            if None in [yes_ask, yes_size, no_ask, no_size]:
                return None

            # Расчет суммы цен
            sum_price = yes_ask + no_ask

            # Проверка порога
            if sum_price >= settings.ARB_THRESHOLD:
                return None

            # Расчет потенциальной прибыли
            # При покупке обоих исходов за sum_price получаем $1.00 в любом случае
            profit_percent = ((1.00 - sum_price) / sum_price) * 100

            # Проверка минимальной прибыли
            if profit_percent < settings.MIN_PROFIT_PERCENT:
                return None

            # Расчет максимального объема
            max_volume = ArbCalculator._calculate_max_volume(
                yes_ask, yes_size, no_ask, no_size
            )

            if max_volume < settings.MIN_LIQUIDITY_USD:
                logger.debug(
                    f"Insufficient liquidity for {market_id[:8]}: "
                    f"{max_volume:.2f} < {settings.MIN_LIQUIDITY_USD}"
                )
                return None

            # Ограничение размера позиции
            max_volume = min(max_volume, settings.MAX_POSITION_SIZE_USD)

            # Расчет ожидаемой прибыли в USD
            expected_profit = max_volume * (1.00 - sum_price)

            return ArbOpportunity(
                market_id=market_id,
                sum_price=sum_price,
                profit_percent=profit_percent,
                yes_ask_price=yes_ask,
                yes_ask_size=yes_size,
                no_ask_price=no_ask,
                no_ask_size=no_size,
                max_volume=max_volume,
                expected_profit_usd=expected_profit
            )

        except Exception as e:
            logger.error(f"Error calculating opportunity for {market_id}: {e}")
            return None

    @staticmethod
    def _calculate_max_volume(
            yes_ask: float,
            yes_size: float,
            no_ask: float,
            no_size: float
    ) -> float:
        """
        Расчет максимального объема с учетом ликвидности

        Важно: Мы должны купить ОДИНАКОВОЕ количество обоих исходов.
        Поэтому берем минимум из доступных размеров.

        Returns:
            Максимальный объем в USD
        """
        # Количество акций, которое можем купить
        max_shares_yes = yes_size / yes_ask if yes_ask > 0 else 0
        max_shares_no = no_size / no_ask if no_ask > 0 else 0

        # Берем минимум
        max_shares = min(max_shares_yes, max_shares_no)

        # Переводим в USD (общая стоимость обеих позиций)
        total_cost = max_shares * (yes_ask + no_ask)

        return total_cost

    @staticmethod
    def calculate_trade_sizes(
            opportunity: ArbOpportunity,
            target_volume_usd: float
    ) -> Tuple[float, float]:
        """
        Расчет размеров сделок для Yes и No

        Args:
            opportunity: Найденная возможность
            target_volume_usd: Целевой объем в USD

        Returns:
            (yes_shares, no_shares) - количество акций для покупки
        """
        # Ограничиваем целевой объем максимальной ликвидностью
        actual_volume = min(target_volume_usd, opportunity.max_volume)

        # Расчет количества акций
        sum_price = opportunity.yes_ask_price + opportunity.no_ask_price
        shares = actual_volume / sum_price

        return shares, shares

    @staticmethod
    def calculate_slippage(
            expected_price: float,
            executed_price: float
    ) -> float:
        """
        Расчет проскальзывания в процентах

        Returns:
            Проскальзывание в % (положительное = хуже ожидаемого)
        """
        return ((executed_price - expected_price) / expected_price) * 100

    @staticmethod
    def is_slippage_acceptable(slippage_percent: float) -> bool:
        """Проверка допустимости проскальзывания"""
        return abs(slippage_percent) <= settings.MAX_SLIPPAGE_PERCENT

    @staticmethod
    def calculate_fees(volume_usd: float, fee_rate: float = 0.002) -> float:
        """
        Расчет комиссий биржи

        Args:
            volume_usd: Объем сделки в USD
            fee_rate: Ставка комиссии (0.002 = 0.2%)

        Returns:
            Сумма комиссии в USD
        """
        return volume_usd * fee_rate

    @staticmethod
    def calculate_net_profit(
            opportunity: ArbOpportunity,
            actual_yes_price: float,
            actual_no_price: float,
            volume: float
    ) -> float:
        """
        Расчет чистой прибыли с учетом фактических цен исполнения и комиссий

        Returns:
            Чистая прибыль в USD
        """
        # Фактическая стоимость покупки
        actual_sum = actual_yes_price + actual_no_price
        total_cost = volume  # Мы тратим volume USD

        # Выплата всегда $1.00 за пару
        shares = volume / actual_sum
        payout = shares * 1.00

        # Комиссии (на обе сделки)
        fees = ArbCalculator.calculate_fees(volume * 2)

        # Чистая прибыль
        net_profit = payout - total_cost - fees

        return net_profit