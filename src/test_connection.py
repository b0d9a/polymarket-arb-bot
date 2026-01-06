import os
import requests
from dotenv import load_dotenv

# Загружаем данные из .env
# Скрипт ищет файл .env на один уровень выше, в корне проекта
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


def test_simple_connection():
    print("--- Тест связи с Polymarket (Direct API) ---")

    # 1. Проверка ключей в .env
    api_key = os.getenv("POLYMARKET_API_KEY")
    private_key = os.getenv("POLYGON_PRIVATE_KEY")

    if not api_key or not private_key:
        print("❌ Ошибка: Не удалось прочитать .env. Проверьте, что файл лежит в корне папки 'script'")
        return

    print(f"✅ Ключи загружены (API Key: {api_key[:5]}...)")

    # 2. Проверка публичного доступа к Polymarket
    # Мы запрашиваем список рынков, чтобы понять, видит ли нас сервер
    host = "https://clob.polymarket.com"
    try:
        print(f"Подключаюсь к {host}...")
        response = requests.get(f"{host}/sampling-simplified-markets")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Успех! Сервер ответил. Найдено рынков: {len(data)}")
            print("\nВаша среда полностью готова к работе!")
        else:
            print(f"❌ Сервер ответил с кодом: {response.status_code}")

    except Exception as e:
        print(f"❌ Ошибка сети: {e}")


if __name__ == "__main__":
    test_simple_connection()