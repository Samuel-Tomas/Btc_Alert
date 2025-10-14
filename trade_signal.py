# trade_signal.py
import os, json, requests, math
from pathlib import Path

# ---------- CONFIG ----------
STATE_FILE = "state.json"
COINGECKO = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=eur"
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
# default starting capital (eur) - ak chceš iné, vlož secret START_CAPITAL alebo uprav state.json manuálne
DEFAULT_CAPITAL = float(os.getenv("START_CAPITAL") or 100.0)
# ----------------------------

if not BOT_TOKEN or not CHAT_ID:
    raise SystemExit("BOT_TOKEN alebo CHAT_ID nie sú nastavené v env.")

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    r = requests.post(url, data=data, timeout=15)
    try:
        r.raise_for_status()
    except Exception as e:
        print("Telegram error:", r.text)
        raise

def get_price_eur():
    r = requests.get(COINGECKO, timeout=10)
    r.raise_for_status()
    j = r.json()
    return float(j["bitcoin"]["eur"])

def load_state():
    p = Path(STATE_FILE)
    if not p.exists():
        return {
            "capital": DEFAULT_CAPITAL,
            "last_action": "SELL",   # takto najprv pošle BUY
            "buy_price": None,
            "quantity": None,
            "target_price": None,
            "history": []
        }
    return json.loads(p.read_text())

def save_state(state):
    Path(STATE_FILE).write_text(json.dumps(state, indent=2))

def commit_state_to_repo():
    # workflow step will commit changes after script runs (see workflow). This function is placeholder.
    pass

def format_eur(x):
    return f"{x:.2f} €"

def main():
    state = load_state()
    price = get_price_eur()
    price_str = format_eur(price)
    print("BTC price (EUR):", price)

    # If last action was SELL -> time to send BUY signal
    if state.get("last_action") in (None, "SELL"):
        capital = float(state.get("capital", DEFAULT_CAPITAL))
        qty = capital / price
        # target_price so that profit >= 1 EUR:
        # profit = qty * (target_price - buy_price) >= 1 => target_price = buy_price + 1/qty
        target_price = price + (1.0 / qty)
        state.update({
            "last_action": "AWAIT_SELL",
            "buy_price": price,
            "quantity": qty,
            "target_price": target_price
        })
        save_state(state)

        text = (
            f"🔔 SIGNAL: BUY (manuálne cez XTB)\n\n"
            f"Aktuálna cena: {price_str}\n"
            f"Navrhované množstvo: {qty:.6f} BTC (kapitál {format_eur(capital)})\n"
            f"Cieľ (SELL) pre min. profit 1€: {format_eur(target_price)}\n\n"
            f"Postup: vykúp manuálne v XTB za ~{price_str}. Po vykúpení čakaj na SELL signál.\n"
            f"Stav uložený v state.json."
        )
        send_telegram(text)
        print("BUY signal sent.")
        return

    # If waiting for sell:
    if state.get("last_action") == "AWAIT_SELL":
        target = float(state.get("target_price"))
        qty = float(state.get("quantity"))
        buy_price = float(state.get("buy_price"))
        capital = float(state.get("capital", DEFAULT_CAPITAL))
        # If price reached or exceeded target -> send SELL signal
        if price >= target:
            proceeds = qty * price
            profit = proceeds - (qty * buy_price)
            new_capital = proceeds  # we assume full sell and proceeds become new capital
            state.update({
                "last_action": "SELL",
                "sell_price": price,
                "last_profit": profit,
                "capital": new_capital
            })
            # add to history
            state["history"].append({
                "buy_price": buy_price,
                "sell_price": price,
                "quantity": qty,
                "profit": profit
            })
            save_state(state)

            text = (
                f"🔔 SIGNAL: SELL (manuálne cez XTB)\n\n"
                f"Aktuálna cena: {format_eur(price)}\n"
                f"Predaj množstva: {qty:.6f} BTC\n"
                f"Predpokladaný profit: {format_eur(profit)}\n"
                f"Nový kapitál (ak predáš): {format_eur(new_capital)}\n\n"
                f"Postup: predaj manuálne v XTB za ~{format_eur(price)}. Stav uložený v state.json."
            )
            send_telegram(text)
            print("SELL signal sent.")
            return
        else:
            # nie je cas na predaj
            text = (
                f"Info: AWAIT_SELL — cena {format_eur(price)} (cieľ {format_eur(target)})\n"
                f"Akcia: ešte nepredať."
            )
            print(text)
            # len logujeme, neposielame notifikáciu opakovane (aby neotravovalo)
            return

if __name__ == "__main__":
    main()
