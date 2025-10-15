import requests
import os
import json

# ===== KONFIGURÁCIA =====
CAPITAL_EUR = 100.0         # štartovací kapitál
MIN_PROFIT_EUR = 1.0        # minimálny profit na transakciu
STATE_FILE = "state.json"   # uloženie posledného stavu

# ===== TELEGRAM =====
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_message(text):
    """Odošle správu na Telegram"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    requests.post(url, data=data)

# ===== CENA BITCOINU =====
def get_btc_price():
    """Vráti aktuálnu cenu BTC v EUR z CoinGecko"""
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=eur"
    try:
        response = requests.get(url, timeout=10).json()
        return float(response["bitcoin"]["eur"])
    except:
        return None

# ===== STAV =====
def load_state():
    if not os.path.exists(STATE_FILE):
        return {"mode": "BUY", "last_price": None}
    with open(STATE_FILE, "r") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

# ===== LOGIKA =====
def analyze_and_signal():
    state = load_state()
    mode = state["mode"]
    last_price = state.get("last_price")
    price = get_btc_price()

    if not price:
        send_message("⚠️ Nepodarilo sa získať cenu BTC.")
        return

    if mode == "BUY":
        btc_amount = CAPITAL_EUR / price
        target_price = price + (MIN_PROFIT_EUR / btc_amount)

        message = (
            f"📊 SIGNAL: BUY (manuálne cez XTB)\n\n"
            f"Aktuálna cena: {price:.2f} €\n"
            f"Navrhované množstvo: {btc_amount:.6f} BTC (kapitál {CAPITAL_EUR:.2f} €)\n"
            f"Min. cieľová cena (profit ≥ {MIN_PROFIT_EUR:.2f}€): {target_price:.2f} €\n\n"
            f"Po vykúpení manuálne v XTB aktualizuj stav — systém bude čakať na SELL."
        )
        send_message(message)

        # Uložíme stav
        state["mode"] = "SELL"
        state["last_price"] = price
        save_state(state)

    elif mode == "SELL":
        if price > last_price * 1.01:  # ak cena stúpla o viac než 1%
            send_message(f"📈 SIGNAL: SELL (profitová pozícia)\nAktuálna cena: {price:.2f} €")
            state["mode"] = "BUY"
            save_state(state)
        elif price < last_price * 0.995:  # ak padá o viac než 0.5 %
            send_message(f"📉 SIGNAL: SELL (ochrana pred stratou)\nAktuálna cena: {price:.2f} €")
            state["mode"] = "BUY"
            save_state(state)
        else:
            send_message(f"🤔 DRŽ (BTC): {price:.2f} €, čakám na vhodný moment na predaj.")

# ===== MAIN =====
if __name__ == "__main__":
    analyze_and_signal()

