import json
import time
import threading
from websocket import WebSocketApp

symbols = ["btcusdt", "ethusdt", "solusdt"]
latest = {s.upper(): None for s in symbols}

def on_message(ws, message):
    data = json.loads(message)
    symbol = data["s"]
    price = float(data["c"])
    latest[symbol] = price

def start_socket(symbol):
    url = f"wss://stream.binance.com:9443/ws/{symbol}@ticker"
    ws = WebSocketApp(url, on_message=on_message)
    ws.run_forever()

# Запускаем сокеты
for s in symbols:
    threading.Thread(target=start_socket, args=(s,), daemon=True).start()

# Печатаем цены каждую секунду
while True:
    time.sleep(1)
    print(
        f"BTC: {latest['BTCUSDT']} | "
        f"ETH: {latest['ETHUSDT']} | "
        f"SOL: {latest['SOLUSDT']}"
    )
