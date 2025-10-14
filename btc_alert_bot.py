import requests
import time
import os

# Sem vlož svoj Telegram token od BotFather
TOKEN = os.getenv("BOT_TOKEN")

# Tvoj chat ID (najprv si ho zistíš v kroku 3)
CHAT_ID = os.getenv("CHAT_ID")

# Funkcia na odoslanie správy
def send_message(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    requests.post(url, data=data)

# Príklad: sledovanie ceny Bitcoinu cez CoinGecko
def get_btc_price():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
    response = requests.get(url).json()
    return response["bitcoin"]["usd"]

# Hlavný cyklus – každých 5 minút skontroluje cenu
last_price = None
while True:
    price = get_btc_price()
    if last_price is None:
        send_message(f"BTC alert aktivovaný. Aktuálna cena: {price} USD")
    elif abs(price - last_price) > 100:  # ak sa zmení o viac ako 100 USD
        send_message(f"⚠️ BTC cena sa zmenila: {price} USD")
    last_price = price
    time.sleep(300)  # počká 5 minút

