# trade_signal.py
import os, json, requests, math
from pathlib import Path

# ---------- CONFIG ----------
STATE_FILE = "state.json"
COINGECKO = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=eur"
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CAPITAL_EUR = float(os.getenv("START_CAPITAL") or 100.0)  # pevný kapitál 100 €
TRAIL_DROP = float(os.getenv("TRAIL_DROP") or 0.01)      # 1% trailing drop
MIN_PROFIT_EUR = float(os.getenv("MIN_PROFIT_EUR") or 1.0) # minimálny profit 1 €
# -----------------------------

if not BOT_TOKEN or not CHAT_ID:
    raise SystemExit("BOT_TOKEN alebo CHAT_ID nie sú nastavené v env (nastav v GitHub Secrets).")

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    try:
        r = requests.post(url, data=data, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print("Telegram send error:", e, "response:", getattr(r, "text", None))

def get_price_eur():
    r = requests.get(COINGECKO, timeout=10)
    r.raise_for_status()
    j = r.json()
    return float(j["bitcoin"]["eur"])

def load_state():
    p = Path(STATE_FILE)
    if not p.exists():
        state = {
            "capital": CAPITAL_EUR,
            "last_action": "SELL",   # pri prvom spustení pošle BUY
            "buy_price": None,
            "quantity": None,
            "min_target_price": None,
            "max_price": None,
            "history": []
        }
        p.write_text(json.dumps(state, indent=2))
        return state
    return json.loads(p.read_text())

def save_state(state):
    Path(STATE_FILE).write_text(json.dumps(state, indent=2))

def format_eur(x):
    return f"{x:.2f} €"

def main():
    state = load_state()
    try:
        price = get_price_eur()
    except Exception as e:
        print("Chyba pri načítaní ceny:", e)
        return

    print("BTC price (EUR):", price)
    last_action = state.get("last_action")

    # If last action was SELL -> send BUY signal
    if last_action is None or last_action == "SELL":
        capital = float(state.get("capital", CAPITAL_EUR))
        qty = capital / price  # množstvo BTC, ktoré kúpime za celý kapitál
        # minimálna cieľová cena aby profit >= MIN_PROFIT_EUR:
        min_target_price = price + (MIN_PROFIT_EUR / qty)
        state.update({
            "last_action": "AWAIT_SELL",
            "buy_price": price,
            "quantity": qty,
            "min_target_price": min_target_price,
            "max_price": price
        })
        save_state(state)

        text = (
            f"🔔 SIGNAL: BUY (manuálne cez XTB)\n\n"
            f"Aktuálna cena: {format_eur(price)}\n"
            f"Navrhované množstvo: {qty:.6f} BTC (kapitál {format_eur(capital)})\n"
            f"Min. cieľová cena (profit ≥ {MIN_PROFIT_EUR:.2f}€): {format_eur(min_target_price)}\n\n"
            f"Po vykúpení manuálne v XTB aktualizuj stav (ak chceš) — systém bude čakať na SELL."
        )
        send_telegram(text)
        print("BUY signal sent.")
        return

    # If waiting for sell:
    if last_action == "AWAIT_SELL":
        qty = float(state.get("quantity"))
        buy_price = float(state.get("buy_price"))
        min_target = float(state.get("min_target_price"))
        max_price = float(state.get("max_price", buy_price))

        # update max price if new high
        if price > max_price:
            max_price = price
            state["max_price"] = max_price
            save_state(state)
            print("Updated max_price:", max_price)

        # Check if we've reached minimal target profit
        if price >= min_target:
            # Sell condition: price dropped from max by TRAIL_DROP OR price significantly above buy (optionally immediate)
            dropped_from_max = price <= max_price * (1.0 - TRAIL_DROP)
            # If price reached min target but hasn't trailed, do NOT sell yet (we wait for trailing)
            if dropped_from_max:
                proceeds = qty * price
                profit = proceeds - (qty * buy_price)
                # update state: we assume manual sell will happen; we store new capital as proceeds for next cycle
                state.update({
                    "last_action": "SELL",
                    "sell_price": price,
                    "last_profit": profit,
                    "capital": proceeds
                })
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
                    f"Nový kapitál (ak predáš): {format_eur(proceeds)}\n\n"
                    f"Postup: predaj manuálne v XTB za ~{format_eur(price)}."
                )
                send_telegram(text)
                print("SELL signal sent.")
                return
            else:
                # reached min target but still climbing (no trailing drop yet) -> do nothing
                print(f"Price >= min_target ({format_eur(min_target)}), but no trailing drop yet. max_price={format_eur(max_price)}")
                return
        else:
            # not reached min profit yet -> do nothing
            print(f"Waiting: current {format_eur(price)}, need min target {format_eur(min_target)}")
            return

if __name__ == "__main__":
    main()

