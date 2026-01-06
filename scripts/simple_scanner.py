"""
Упрощенный сканер для быстрого тестирования
НЕ требует Redis, Telegram, полной настройки .env

Использование:
    python scripts/simple_scanner.py
"""

import requests
import time
from datetime import datetime


class SimpleScanner:
    """Минималистичный сканер арбитража"""

    def __init__(self, threshold=0.998):
        self.threshold = threshold
        self.api_url = "https://clob.polymarket.com"
        self.opportunities = []

    def get_markets(self, limit=20):
        """Получить список активных рынков"""
        try:
            url = f"{self.api_url}/markets"
            params = {"limit": limit, "closed": False}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ Ошибка загрузки рынков: {e}")
            return []

    def get_orderbook(self, token_id):
        """Получить книгу ордеров"""
        try:
            url = f"{self.api_url}/book"
            params = {"token_id": token_id}
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            return response.json()
        except:
            return None

    def check_arbitrage(self, market):
        """Проверить рынок на арбитраж"""
        try:
            tokens = market.get("tokens", [])
            if len(tokens) < 2:
                return None

            # Получаем книги ордеров
            yes_book = self.get_orderbook(tokens[0]["token_id"])
            no_book = self.get_orderbook(tokens[1]["token_id"])

            if not yes_book or not no_book:
                return None

            # Лучшие цены
            yes_asks = yes_book.get("asks", [])
            no_asks = no_book.get("asks", [])

            if not yes_asks or not no_asks:
                return None

            yes_price = float(yes_asks[0]["price"])
            no_price = float(no_asks[0]["price"])
            yes_size = float(yes_asks[0]["size"])
            no_size = float(no_asks[0]["size"])

            price_sum = yes_price + no_price

            # Проверка на арбитраж
            if price_sum < self.threshold:
                profit_percent = ((1.0 - price_sum) / price_sum) * 100
                max_volume = min(yes_size, no_size)

                return {
                    "market": market.get("question", "Unknown")[:60],
                    "market_id": market.get("id"),
                    "yes_price": yes_price,
                    "no_price": no_price,
                    "sum": price_sum,
                    "profit_pct": profit_percent,
                    "volume": max_volume,
                    "profit_usd": (1.0 - price_sum) * max_volume
                }

            return None

        except Exception as e:
            print(f"⚠️  Ошибка проверки: {e}")
            return None

    def scan_once(self):
        """Одно сканирование всех рынков"""
        print(f"\n{'=' * 70}")
        print(f"🔍 Сканирование {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'=' * 70}")

        markets = self.get_markets(limit=20)
        print(f"📊 Загружено рынков: {len(markets)}")

        found = 0
        for i, market in enumerate(markets, 1):
            print(f"[{i}/{len(markets)}] Проверка: {market.get('question', '')[:50]}...", end="\r")

            opp = self.check_arbitrage(market)
            if opp:
                found += 1
                self.opportunities.append(opp)
                self.print_opportunity(opp, found)

            time.sleep(0.3)  # Задержка между запросами

        print(f"\n✅ Сканирование завершено. Найдено возможностей: {found}")

    def print_opportunity(self, opp, num):
        """Красивый вывод возможности"""
        print(f"\n{'=' * 70}")
        print(f"🎯 ВОЗМОЖНОСТЬ #{num}")
        print(f"{'=' * 70}")
        print(f"📊 Рынок: {opp['market']}")
        print(f"🆔 ID: {opp['market_id']}")
        print(f"\n💰 ЦЕНЫ:")
        print(f"   Yes: ${opp['yes_price']:.4f}")
        print(f"   No:  ${opp['no_price']:.4f}")
        print(f"   Сумма: ${opp['sum']:.4f}")
        print(f"\n📈 ПРИБЫЛЬ:")
        print(f"   {opp['profit_pct']:.2f}% (${opp['profit_usd']:.2f})")
        print(f"   Макс. объем: ${opp['volume']:.2f}")
        print(f"{'=' * 70}\n")

    def run_continuous(self, interval=10):
        """Непрерывное сканирование"""
        print(f"\n{'=' * 70}")
        print(f"🚀 POLYMARKET SIMPLE SCANNER")
        print(f"{'=' * 70}")
        print(f"⚙️  Threshold: {self.threshold}")
        print(f"⏱️  Интервал: {interval} секунд")
        print(f"⚠️  Нажмите Ctrl+C для остановки")
        print(f"{'=' * 70}")

        iteration = 0
        try:
            while True:
                iteration += 1
                print(f"\n\n📡 ИТЕРАЦИЯ #{iteration}")
                self.scan_once()
                print(f"\n⏳ Ждем {interval} секунд до следующего сканирования...")
                time.sleep(interval)
        except KeyboardInterrupt:
            print(f"\n\n{'=' * 70}")
            print(f"📊 СТАТИСТИКА")
            print(f"{'=' * 70}")
            print(f"Итераций: {iteration}")
            print(f"Всего возможностей: {len(self.opportunities)}")
            print(f"{'=' * 70}\n")
            print("👋 Остановлено пользователем")


def main():
    """Точка входа"""
    print("\n🔍 Простой сканер арбитража Polymarket")
    print("Не требует настройки .env, Redis, Telegram\n")

    # Выбор режима
    print("Выберите режим:")
    print("1 - Одно сканирование")
    print("2 - Непрерывное сканирование (каждые 10 сек)")

    choice = input("\nВаш выбор (1/2): ").strip()

    scanner = SimpleScanner(threshold=0.998)

    if choice == "1":
        scanner.scan_once()
    else:
        scanner.run_continuous(interval=10)


if __name__ == "__main__":
    main()