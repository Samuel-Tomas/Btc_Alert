import requests
import json
import os
from datetime import datetime

# ============ KONFIGURÁCIA ============
CAPITAL = 100.0          # fixný kapitál v €
MIN_PROFIT = 1.0         # minimálny zisk v €
STATE_FILE = "state.json"
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
# =====================================

def send_message(text):
    """Pošle správu na Telegram"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    requests.post(url, data=data)

def get_btc_price_eur():
    response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=eur")
    data = response.json()
    return data["bitcoin"]["eur"]

def load_state():
    """Načíta alebo inicializuje stav"""
    if not os.path.exists(STATE_FILE):
        default_state = {"mode": "BUY", "last_price": None}
        with open(STATE_FILE, "w") as f:
            json.dump(default_state, f)
        return default_state

    with open(STATE_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {"mode": "BUY", "last_price": None}

def save_state(state):
    """Uloží stav"""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def analyze_and_signal():
    """Vyhodnotí trend a pošle signál"""
    state = load_state()
    mode = state["mode"]
    last_price = state["last_price"]

    price = get_btc_price_eur()
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")

    if mode == "BUY":
        message = (
            f"🟢 {timestamp}\n"
            f"SIGNAL: BUY (manuálne cez XTB)\n\n"
            f"Aktuálna cena: {price:.2f} €\n"
            f"Navrhované množstvo: {CAPITAL / price:.6f} BTC (kapitál {CAPITAL:.2f} €)\n"
            f"Min. cieľová cena (profit ≥ {MIN_PROFIT:.2f}€): {price + (MIN_PROFIT / (CAPITAL / price)):.2f} €\n\n"
            f"Po nákupe manuálne zmeň stav na SELL (skript to urobí automaticky)."
        )
        send_message(message)
        state["mode"] = "SELL"
        state["last_price"] = price
        save_state(state)

    elif mode == "SELL":
        if last_price is None:
            state["mode"] = "BUY"
            save_state(state)
            return

        change = (price - last_price) / last_price * 100
        if change >= 1.0:  # profit ≥ 1 %
            message = (
                f"🔴 {timestamp}\n"
                f"SIGNAL: SELL (manuálne cez XTB)\n\n"
                f"Aktuálna cena: {price:.2f} €\n"
                f"Zisk od nákupu: {change:.2f}%\n"
                f"Odporúčanie: Predaj, ak chceš realizovať zisk."
            )
            send_message(message)
            state["mode"] = "BUY"
            state["last_price"] = None
            save_state(state)
        else:
            print(f"[{timestamp}] Držím pozíciu, zmena: {change:.2f}%")

if __name__ == "__main__":
    analyze_and_signal()
