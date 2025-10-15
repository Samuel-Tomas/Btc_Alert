import requests
import time
import json
import os

# ---- KONFIGURÁCIA ----
TELEGRAM_BOT_TOKEN = "TU_DAJ_SVOJ_TOKEN"
CHAT_ID = "TU_DAJ_CHAT_ID"
STATE_FILE = "state.json"
ALERT_INTERVAL = 300  # každých 5 minút
PRICE_CHANGE_THRESHOLD = 1.0  # percentuálna zmena pre BUY/SELL signál

# ---- FUNKCIE ----
def get_btc_price_eur():
    """Získa aktuálnu cenu BTC v EUR z CoinGecko API"""
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=eur",
            timeout=10
        )
        data = response.json()
        return data["bitcoin"]["eur"]
    except Exception as e:
        print("Chyba pri načítaní ceny BTC:", e)
        return None


def send_telegram_message(message):
    """Odošle správu na Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print("Chyba pri odosielaní správy:", e)


def load_state():
    """Načíta posledný stav (napr. posledný signál a cena)"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    else:
        return {"last_signal": None, "last_price": None}


def save_state(state):
    """Uloží aktuálny stav"""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def analyze_and_signal():
    """Analyzuje cenu a posiela signály len pri zmene trendu"""
    state = load_state()
    current_price = get_btc_price_eur()

    if current_price is None:
        print("Nepodarilo sa načítať cenu BTC.")
        return

    last_price = state["last_price"]
    last_signal = state["last_signal"]

    print(f"Aktuálna cena BTC: {current_price:.2f} €")

    if last_price is not None:
        change = ((current_price - last_price) / last_price) * 100
        print(f"Zmena od poslednej ceny: {change:.2f}%")

        if change > PRICE_CHANGE_THRESHOLD and last_signal != "BUY":
            send_telegram_message(f"📈 BUY signal — BTC rastie ({change:.2f}%), cena: {current_price:.2f} €")
            state["last_signal"] = "BUY"

        elif change < -PRICE_CHANGE_THRESHOLD and last_signal != "SELL":
            send_telegram_message(f"📉 SELL signal — BTC klesá ({change:.2f}%), cena: {current_price:.2f} €")
            state["last_signal"] = "SELL"
    else:
        print("Prvá detekcia — zatiaľ bez signálu.")

    # Uložíme novú cenu
    state["last_price"] = current_price
    save_state(state)


# ---- HLAVNÁ SLUČKA ----
if __name__ == "__main__":
    print("🚀 BTC Alert Bot spustený — kontrola každých 5 minút.")
    while True:
        analyze_and_signal()
        time.sleep(ALERT_INTERVAL)
