import redis

try:
    # Пытаемся подключиться к локальному серверу
    r = redis.Redis(host='localhost', port=6379, db=0)
    # Отправляем команду PING
    if r.ping():
        print("✅ Успех! Redis на Windows работает и видит Python.")
except Exception as e:
    print(f"❌ Ошибка подключения: {e}")