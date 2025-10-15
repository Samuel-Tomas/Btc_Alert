# trade_signal.py
import os, json, requests
from pathlib import Path

# ---------- CONFIG ----------
STATE_FILE = "state.json"
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CAPITAL_EUR = float(os.getenv("START_CAPITAL") or 100.0)  # pevný kapitál 100 €
TRAIL_DROP = float(os.getenv("TRAIL_DROP") or 0.01)       # 1% trailing drop
MIN_PROFIT_EUR = float(os.getenv("MIN_PROFIT_EUR") or 1.0) # minimálny profit 1 €
# -----------------------------

if not BOT_TOKEN or not CHAT_ID:
    raise SystemExit("❌ BOT_TOKEN alebo CHAT_ID nie sú nastavené v GitHub Secrets.")

def send_telegram(text):
    """Odošle správu do Telegramu"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    try:
        r = requests.post(url, data=data, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print("⚠️ Chyba pri odosielaní správy:", e)

def get_price_eur():
    """
    Načíta cenu Bitcoinu v EUR.
    Ak CoinGecko zlyhá, použije USD a prepočíta na EUR.
    """
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=eur",
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        eur_price = data["bitcoin"]["eur"]
        if eur_price < 1000:  # bezpečnostná kontrola (ak vráti USD)
            raise ValueError("Cena v EUR je podozrivo nízka.")
        return eur_price
    except Exception:
        # fallback: použijeme USD a prepočítame podľa aktuálneho kurzu
        usd = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
            timeout=10,
        ).json()["bitcoin"]["usd"]
        eur_usd = requests.get(
            "https://api.exchangerate.host/latest?base=USD&symbols=EUR",
            timeout=10,
        ).json()["rates"]["EUR"]
        return usd * eur_usd

def load_state():
    path = Path(STATE_FILE)
    if not path.exists():
        state = {
            "capital": CAPITAL_EUR,
            "last_action": "SELL",  # na začiatku čaká na BUY
            "buy_price": None,
            "quantity": None,
            "min_target_price": None,
            "max_price": None,
            "history": [],
        }
        save_state(state)
        return state
    return json.loads(path.read_text())

def save_state(state):
    Path(STATE_FILE).write_text(json.dumps(state, indent=2))

def format_eur(x): return f"{x:,.2f} €".replace(",", " ")

def main():
    state = load_state()
    try:
        price = get_price_eur()
    except Exception as e:
        print("❌ Chyba pri načítaní ceny:", e)
        return

    print(f"BTC cena: {format_eur(price)}")
    last_action = state.get("last_action")

    # === KROK 1: NÁKUP ===
    if last_action == "SELL":
        capital = state.get("capital", CAPITAL_EUR)
        qty = capital / price
        min_target_price = price + (MIN_PROFIT_EUR / qty)
        state.update({
            "last_action": "AWAIT_SELL",
            "buy_price": price,
            "quantity": qty,
            "min_target_price": min_target_price,
            "max_price": price
        })
        save_state(state)

        send_telegram(
            f"🔔 SIGNAL: BUY (manuálne cez XTB)\n\n"
            f"Aktuálna cena: {format_eur(price)}\n"
            f"Množstvo: {qty:.6f} BTC (kapitál {format_eur(capital)})\n"
            f"Cieľová cena (profit ≥ {MIN_PROFIT_EUR:.2f}€): {format_eur(min_target_price)}\n\n"
            f"➡️ Po nákupe počkaj na SELL signál."
        )
        print("📤 BUY signál odoslaný.")
        return

    # === KROK 2: ČAKANIE NA PREDAJ ===
    if last_action == "AWAIT_SELL":
        qty = float(state["quantity"])
        buy_price = float(state["buy_price"])
        min_target = float(state["min_target_price"])
        max_price = float(state["max_price"])

        # aktualizuj max, ak cena rastie
        if price > max_price:
            state["max_price"] = price
            save_state(state)
            print(f"📈 Nové maximum: {format_eur(price)}")

        # ak sme nad minimálnym profitom
        if price >= min_target:
            drop_from_max = price <= max_price * (1 - TRAIL_DROP)
            if drop_from_max:
                proceeds = qty * price
                profit = proceeds - (qty * buy_price)
                new_capital = proceeds

                state.update({
                    "last_action": "SELL",
                    "sell_price": price,
                    "last_profit": profit,
                    "capital": new_capital
                })
                state["history"].append({
                    "buy_price": buy_price,
                    "sell_price": price,
                    "profit": profit
                })
                save_state(state)

                send_telegram(
                    f"💰 SIGNAL: SELL (manuálne cez XTB)\n\n"
                    f"Aktuálna cena: {format_eur(price)}\n"
                    f"Predaj: {qty:.6f} BTC\n"
                    f"Zisk: {format_eur(profit)}\n"
                    f"Nový kapitál: {format_eur(new_capital)}\n\n"
                    f"➡️ Po predaji počkaj na ďalší BUY signál."
                )
                print("📤 SELL signál odoslaný.")
            else:
                print(f"✅ Profit dosiahnutý, ale ešte držíme. (max={format_eur(max_price)})")
        else:
            print(f"⏳ Čakáme na profit. Aktuálne {format_eur(price)} / cieľ {format_eur(min_target)}")

if __name__ == "__main__":
    main()

