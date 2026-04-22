import json
from pathlib import Path
from datetime import datetime

import gspread
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

SPREADSHEET_ID = "1z6pVOSBNUcrWAdmgQfuqfNpvlwBYUkPmd58Xu29kj-U"
SHEET_NAME = "Backend_Kasse"
HEADER = ["ID", "Zeitstempel", "Produkte", "Anzahl_Gesamt",
          "Betrag_Gesamt", "Erhalten", "Rueckgeld", "Rabatt", "Kassierer"]

KASSIERER_LIST = ["Freddy", "Divin", "Chrissi", "Jan", "Leul", "Sohrab",
                  "Aldar", "Lorena", "Anna K.", "Michelle", "Finn"]

PRODUCTS = [
    {"name": "Bier",            "price": 2.0,  "category": "🍺 Classics",    "color": "#00b894"},
    {"name": "Aeppler 0,33",    "price": 3.0,  "category": "🍺 Classics",    "color": "#0984e3"},
    {"name": "+Pfand",          "price": 0.5,  "category": "🍺 Classics",    "color": "#b6b904"},
    {"name": "Shot",            "price": 1.5,  "category": "🥃 Shots",       "color": "#0984e3"},
    {"name": "Surprise Shot",   "price": 0.5,  "category": "🥃 Shots",       "color": "#6c5ce7"},
    {"name": "Happy Hour Shot", "price": 1.0,  "category": "🥃 Shots",       "color": "#00cec9"},
    {"name": "Spezi",           "price": 2.0,  "category": "🧃 alkoholfrei", "color": "#00b894"},
    {"name": "Mate",            "price": 3.0,  "category": "🧃 alkoholfrei", "color": "#00b894"},
    {"name": "+Pfand",          "price": 0.5,  "category": "🧃 alkoholfrei", "color": "#b6b904"},
    {"name": "Limo 0,33",       "price": 1.5,  "category": "🧃 alkoholfrei", "color": "#0984e3"},
    {"name": "Red Bull",        "price": 3.0,  "category": "🧃 alkoholfrei", "color": "#0984e3"},
    {"name": "Sekt Mate",       "price": 4.0,  "category": "🍹 Mischen",     "color": "#00b894"},
    {"name": "Vodka Mate",      "price": 4.0,  "category": "🍹 Mischen",     "color": "#00b894"},
    {"name": "+Pfand",          "price": 0.5,  "category": "🍹 Mischen",     "color": "#b6b904"},
    {"name": "Koks Mische",     "price": 5.0,  "category": "🍹 Mischen",     "color": "#0984e3"},
    {"name": "Flasche Pfeffi",  "price": 15.0, "category": "⭐ Specials",    "color": "#6c5ce7"},
    {"name": "Golfclub",        "price": 15.0, "category": "⭐ Specials",    "color": "#6c5ce7"},
    {"name": "ACAB",            "price": 110.0,"category": "⭐ Specials",    "color": "#d63031"},
    {"name": "Bierpong",        "price": 15.0, "category": "⭐ Specials",    "color": "#6c5ce7"},
    {"name": "Mischkonsum",     "price": 15.0, "category": "⭐ Specials",    "color": "#6c5ce7"},
    {"name": "Schmeisse Runde", "price": 16.0, "category": "⭐ Specials",    "color": "#e17055"},
]

PRODUCT_ICONS = {
    "Bier": "🍺", "Aeppler 0,33": "🍏", "+Pfand": "♻️", "Shot": "🥃",
    "Surprise Shot": "🎲", "Happy Hour Shot": "⏰", "Spezi": "🥤", "Mate": "🧉",
    "Limo 0,33": "🍋", "Red Bull": "🐂", "Sekt Mate": "🥂", "Vodka Mate": "🍸",
    "Koks Mische": "🥃", "Flasche Pfeffi": "🌿", "Golfclub": "⛳", "ACAB": "🚨",
    "Bierpong": "🏓", "Mischkonsum": "🍹", "Schmeisse Runde": "🎉",
}

SERVICE_ACCOUNT_CANDIDATES = [
    Path("service_account.json"),
    Path(".streamlit/service_account.json"),
    Path(r"C:\Users\leul.zewdie\Downloads\party-dashboard-491808-a0ddf9a20e45.json"),
]


# ── Google Sheets ────────────────────────────────────────────────────────────

def get_gspread_client():
    try:
        secrets = dict(st.secrets)
    except StreamlitSecretNotFoundError:
        secrets = {}
    if "gcp_service_account" in secrets:
        return gspread.service_account_from_dict(dict(secrets["gcp_service_account"]))
    for candidate in SERVICE_ACCOUNT_CANDIDATES:
        if not candidate.exists():
            continue
        try:
            if candidate.suffix.lower() == ".json":
                return gspread.service_account(filename=str(candidate))
            credentials = json.loads(candidate.read_text(encoding="utf-8").strip())
            return gspread.service_account_from_dict(credentials)
        except Exception as exc:
            st.warning(f"Anmeldedatei konnte nicht genutzt werden: {candidate} ({exc})")
    raise FileNotFoundError("Keine Google-Service-Account-Datei gefunden.")


@st.cache_resource
def get_worksheet():
    client = get_gspread_client()
    ss = client.open_by_key(SPREADSHEET_ID)
    try:
        ws = ss.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=SHEET_NAME, rows=2000, cols=len(HEADER))
        ws.append_row(HEADER)
        ws.freeze(rows=1)
    return ws


def append_kasse_row(data: dict):
    ws = get_worksheet()
    now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    tx_id = "KS-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    ws.append_row([
        tx_id,
        data.get("zeitstempel", now),
        data.get("produkte", ""),
        data.get("anzahl_gesamt", 0),
        data.get("betrag", 0),
        data.get("erhalten", 0),
        data.get("rueckgeld", 0),
        data.get("rabatt", ""),
        data.get("kassierer", ""),
    ], value_input_option="USER_ENTERED")
    load_kasse.clear()


@st.cache_data(ttl=30)
def load_kasse():
    ws = get_worksheet()
    rows = ws.get_all_values()
    if len(rows) <= 1:
        return pd.DataFrame(columns=HEADER)
    data = []
    for row in rows[1:]:
        padded = row[:len(HEADER)] + [""] * (len(HEADER) - len(row))
        if not any(str(c).strip() for c in padded):
            continue
        data.append(dict(zip(HEADER, padded)))
    if not data:
        return pd.DataFrame(columns=HEADER)
    df = pd.DataFrame(data)
    df["Betrag_Gesamt"] = pd.to_numeric(df["Betrag_Gesamt"], errors="coerce").fillna(0.0)
    df["Anzahl_Gesamt"] = pd.to_numeric(df["Anzahl_Gesamt"], errors="coerce").fillna(0)
    df["Zeitstempel"] = pd.to_datetime(df["Zeitstempel"], format="%d.%m.%Y %H:%M:%S", errors="coerce")
    return df


def format_euro(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "-"
    return f"{v:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", ".")


# ── Session state helpers ────────────────────────────────────────────────────

def init_state():
    defaults = {
        "cart": {},           # key -> {name, price, category, quantity}
        "pay_amount": "",     # string being typed on numpad
        "discount": "",       # discount string e.g. "10%" or "2.50"
        "free": False,        # gratis toggle
        "history": [],        # list of display strings
        "quantity": 1,        # selected quantity multiplier
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def cart_total_base() -> float:
    return sum(v["price"] * v["quantity"] for v in st.session_state.cart.values())


def cart_total() -> float:
    base = cart_total_base()
    disc = st.session_state.discount
    if st.session_state.free:
        return 0.0
    if disc:
        if disc.endswith("%"):
            pct = float(disc[:-1] or 0) / 100
            return max(0.0, base - base * pct)
        else:
            try:
                return max(0.0, base - float(disc.replace(",", ".")))
            except ValueError:
                return base
    return base


def add_to_cart(product: dict):
    key = product["category"] + "::" + product["name"]
    if key not in st.session_state.cart:
        st.session_state.cart[key] = {**product, "quantity": 0}
    st.session_state.cart[key]["quantity"] += st.session_state.quantity
    st.session_state.quantity = 1


def numpad_press(val: str):
    cur = st.session_state.pay_amount
    if val == "C":
        st.session_state.pay_amount = ""
    elif val == "⌫":
        st.session_state.pay_amount = cur[:-1]
    else:
        st.session_state.pay_amount = cur + val


# ── Page setup ───────────────────────────────────────────────────────────────

st.set_page_config(page_title="THP - Kasse", page_icon="🍺", layout="wide")
init_state()

st.markdown("""
<style>
/* ── Global ── */
[data-testid="stAppViewContainer"] { background: #0f1117; }
[data-testid="stSidebar"] { background: #1a1d27; }

/* ── Alle Columns: kein Gap ── */
[data-testid="stHorizontalBlock"] { gap: 6px !important; }
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { padding: 0 !important; }
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"] > div { margin-bottom: 6px !important; }

/* ── Produkt-Buttons: farbige Kacheln ── */
.prod-btn button {
    width: 100% !important;
    height: 54px !important;
    min-height: 54px !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    padding: 0 6px !important;
    border-radius: 8px !important;
    border: none !important;
    background: #1e2130 !important;
    color: #e0e0e0 !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    transition: background 0.15s !important;
}
.prod-btn button:hover { filter: brightness(1.2) !important; }

/* ── Numpad-Buttons ── */
.numpad button {
    width: 100% !important;
    height: 52px !important;
    min-height: 52px !important;
    font-size: 18px !important;
    font-weight: 700 !important;
    border-radius: 8px !important;
    background: #1e2130 !important;
    color: #fff !important;
    border: 1px solid #2d3148 !important;
}
.numpad button:hover { background: #2a2f45 !important; }

/* ── Quantity-Buttons ── */
.qty-btn button {
    height: 38px !important;
    min-height: 38px !important;
    font-size: 14px !important;
    font-weight: 700 !important;
    border-radius: 6px !important;
    background: #1e2130 !important;
    color: #aaa !important;
    border: 1px solid #2d3148 !important;
    padding: 0 !important;
}

/* ── Action-Buttons ── */
.action-btn button {
    height: 46px !important;
    min-height: 46px !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
}

/* ── Checkout/Cancel ── */
.checkout-btn button {
    height: 56px !important;
    min-height: 56px !important;
    font-size: 16px !important;
    font-weight: 700 !important;
    border-radius: 10px !important;
}

/* ── Warenkorb-Box ── */
.cart-box {
    background: #1a1d27;
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 10px;
    min-height: 80px;
}
.cart-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 4px 0;
    border-bottom: 1px solid #2d3148;
    font-size: 14px;
    color: #e0e0e0;
}
.cart-row:last-child { border-bottom: none; }
.cart-empty { color: #555; font-style: italic; font-size: 14px; text-align: center; padding: 16px 0; }

/* ── Totals-Box ── */
.totals-box {
    background: #1a1d27;
    border-radius: 10px;
    padding: 12px 14px;
    margin: 8px 0;
    border: 1px solid #2d3148;
}
.totals-box .total-line {
    display: flex;
    justify-content: space-between;
    font-size: 14px;
    color: #aaa;
    padding: 2px 0;
}
.totals-box .total-main {
    display: flex;
    justify-content: space-between;
    font-size: 22px;
    font-weight: 700;
    color: #fff;
    padding: 6px 0 2px;
}
.totals-box .change-pos { color: #00b894 !important; }
.totals-box .change-neg { color: #d63031 !important; }

/* ── Kategorie-Label ── */
.cat-label {
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #666;
    margin: 10px 0 4px;
}

/* ── Kassierer-Bar ── */
.kass-bar {
    background: #1d4ed8;
    border-radius: 10px;
    padding: 10px 16px;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 12px;
    color: white;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

st.markdown("<h2 style='margin-bottom:4px'>🍺 Touch-Kasse</h2>", unsafe_allow_html=True)

kasse_tab, auswertung_tab = st.tabs(["Kasse", "Auswertung"])

# ── KASSE TAB ────────────────────────────────────────────────────────────────
with kasse_tab:

    # ── Kassierer-Bar + Anzahl ───────────────────────────────────────────────
    bar1, bar2 = st.columns([2, 5])
    with bar1:
        kassierer = st.selectbox("Kassierer", KASSIERER_LIST, key="kassierer",
                                 label_visibility="collapsed")
        st.markdown(f"<div style='color:#666;font-size:12px;margin-top:-8px'>Kassierer: <b style='color:#1d4ed8'>{kassierer}</b></div>", unsafe_allow_html=True)
    with bar2:
        st.markdown("<div style='color:#888;font-size:12px;margin-bottom:2px'>ANZAHL</div>", unsafe_allow_html=True)
        qcols = st.columns(11)
        for i, q in enumerate(range(1, 11)):
            with qcols[i]:
                st.markdown('<div class="qty-btn">', unsafe_allow_html=True)
                active = st.session_state.quantity == q
                if st.button(str(q), key=f"q_{q}", use_container_width=True,
                             type="primary" if active else "secondary"):
                    st.session_state.quantity = q
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
        with qcols[10]:
            st.markdown('<div class="qty-btn">', unsafe_allow_html=True)
            if st.button("C", key="q_c", use_container_width=True):
                st.session_state.quantity = 1
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(f"<div style='font-size:13px;color:#1d4ed8;font-weight:700;margin:-4px 0 8px'>Anzahl: {st.session_state.quantity}x</div>", unsafe_allow_html=True)
    st.divider()

    # ── Produkte links | Kasse rechts ───────────────────────────────────────
    prod_col, cart_col = st.columns([3, 2], gap="large")

    with prod_col:
        categories: dict = {}
        for p in PRODUCTS:
            categories.setdefault(p["category"], []).append(p)

        for cat, items in categories.items():
            st.markdown(f"<div class='cat-label'>{cat}</div>", unsafe_allow_html=True)
            cols = st.columns(3)
            for idx, p in enumerate(items):
                with cols[idx % 3]:
                    st.markdown('<div class="prod-btn">', unsafe_allow_html=True)
                    label = f"{p['name']}\n{p['price']:.2f} €"
                    if st.button(label, key=f"prod_{cat}_{p['name']}_{idx}", use_container_width=True):
                        add_to_cart(p)
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

    with cart_col:
        # ── Warenkorb ───────────────────────────────────────────────────────
        st.markdown("<div style='font-size:16px;font-weight:700;color:#fff;margin-bottom:6px'>Warenkorb</div>", unsafe_allow_html=True)

        if not st.session_state.cart:
            st.markdown("<div class='cart-box'><div class='cart-empty'>Warenkorb leer</div></div>", unsafe_allow_html=True)
        else:
            cart_html = "<div class='cart-box'>"
            for item in st.session_state.cart.values():
                cart_html += f"<div class='cart-row'><span>{item['quantity']}x {item['name']}</span><span style='color:#fff;font-weight:600'>{item['quantity']*item['price']:.2f} €</span></div>"
            cart_html += "</div>"
            st.markdown(cart_html, unsafe_allow_html=True)

            # +/- buttons per cart item
            for key, item in list(st.session_state.cart.items()):
                c1, c2, c3 = st.columns([4, 1, 1])
                c1.markdown(f"<div style='font-size:13px;padding-top:6px;color:#aaa'>{item['name']}</div>", unsafe_allow_html=True)
                if c2.button("+", key=f"plus_{key}", use_container_width=True):
                    st.session_state.cart[key]["quantity"] += 1
                    st.rerun()
                if c3.button("−", key=f"minus_{key}", use_container_width=True):
                    st.session_state.cart[key]["quantity"] -= 1
                    if st.session_state.cart[key]["quantity"] <= 0:
                        del st.session_state.cart[key]
                    st.rerun()

        # ── Aktionen ────────────────────────────────────────────────────────
        ac1, ac2 = st.columns(2)
        with ac1:
            st.markdown('<div class="action-btn">', unsafe_allow_html=True)
            if st.button("Gratis" if not st.session_state.free else "Gratis ✓",
                         type="primary" if st.session_state.free else "secondary",
                         use_container_width=True):
                st.session_state.free = not st.session_state.free
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        with ac2:
            st.markdown('<div class="action-btn">', unsafe_allow_html=True)
            if st.button("Leeren", use_container_width=True):
                st.session_state.cart = {}
                st.session_state.discount = ""
                st.session_state.free = False
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        new_disc = st.text_input("Rabatt", value=st.session_state.discount, key="disc_input",
                                 label_visibility="collapsed", placeholder="Rabatt: 10% oder 2.50 EUR")
        if new_disc != st.session_state.discount:
            st.session_state.discount = new_disc

        # ── Totals ──────────────────────────────────────────────────────────
        base = cart_total_base()
        total = cart_total()
        try:
            pay_val = float(st.session_state.pay_amount.replace(",", ".")) if st.session_state.pay_amount else 0.0
        except ValueError:
            pay_val = 0.0
        change = pay_val - total
        change_class = "change-pos" if change >= 0 else "change-neg"
        disc_line = ""
        if st.session_state.free:
            disc_line = "<div class='total-line'><span>Rabatt</span><span style='color:#e17055'>100% (Gratis)</span></div>"
        elif st.session_state.discount:
            disc_line = f"<div class='total-line'><span>Rabatt</span><span style='color:#e17055'>{st.session_state.discount}</span></div>"

        st.markdown(f"""
        <div class='totals-box'>
          <div class='total-line'><span>Summe</span><span>{base:.2f} €</span></div>
          {disc_line}
          <div class='total-main'><span>Gesamt</span><span>{total:.2f} €</span></div>
          <div class='total-line'><span>Erhalten</span><span>{pay_val:.2f} €</span></div>
          <div class='total-line'><span>Rückgeld</span><span class='{change_class}'><b>{change:.2f} €</b></span></div>
        </div>
        """, unsafe_allow_html=True)

        # ── Schnellzahlung ───────────────────────────────────────────────────
        st.markdown("<div style='color:#888;font-size:11px;margin:4px 0 2px'>SCHNELLZAHLUNG</div>", unsafe_allow_html=True)
        qp_cols = st.columns(4)
        for i, amt in enumerate([5, 10, 20, 50]):
            if qp_cols[i].button(f"{amt} €", key=f"qp_{amt}", use_container_width=True):
                st.session_state.pay_amount = str(amt)
                st.rerun()

        # ── Numpad ──────────────────────────────────────────────────────────
        st.markdown("<div style='color:#888;font-size:11px;margin:6px 0 2px'>BETRAG EINGEBEN</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:28px;font-weight:700;color:#fff;background:#1a1d27;border-radius:8px;padding:10px 14px;margin-bottom:6px;text-align:right'>{st.session_state.pay_amount or '0'} €</div>", unsafe_allow_html=True)

        pad_rows = [["7","8","9"], ["4","5","6"], ["1","2","3"], ["0",".","<"]]
        for row in pad_rows:
            rcols = st.columns(3)
            for i, val in enumerate(row):
                with rcols[i]:
                    st.markdown('<div class="numpad">', unsafe_allow_html=True)
                    if st.button(val, key=f"pad_{val}_{row}", use_container_width=True):
                        numpad_press("⌫" if val == "<" else val)
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

        pc1, pc2 = st.columns(2)
        with pc1:
            st.markdown('<div class="numpad">', unsafe_allow_html=True)
            if st.button("C", key="pad_C", use_container_width=True):
                numpad_press("C")
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        with pc2:
            if st.button("Passend", key="pad_passend", use_container_width=True):
                st.session_state.pay_amount = f"{total:.2f}"
                st.rerun()

        # ── Checkout ────────────────────────────────────────────────────────
        st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)
        ch1, ch2 = st.columns([3, 2])
        with ch1:
            st.markdown('<div class="checkout-btn">', unsafe_allow_html=True)
            checkout_clicked = st.button("Zahlung abschliessen", type="primary", use_container_width=True, key="checkout")
            st.markdown('</div>', unsafe_allow_html=True)
        with ch2:
            st.markdown('<div class="checkout-btn">', unsafe_allow_html=True)
            cancel_clicked = st.button("Stornieren", use_container_width=True, key="cancel")
            st.markdown('</div>', unsafe_allow_html=True)

        if cancel_clicked:
            st.session_state.cart = {}
            st.session_state.pay_amount = ""
            st.session_state.discount = ""
            st.session_state.free = False
            st.rerun()

        if checkout_clicked:
            if not st.session_state.cart:
                st.error("Warenkorb ist leer!")
            elif not st.session_state.free and pay_val < total:
                st.error(f"Betrag zu gering — noch {total - pay_val:.2f} € fehlen.")
            else:
                items_list = list(st.session_state.cart.values())
                produkte_str = ", ".join(f"{x['quantity']}x {x['name']}" for x in items_list)
                anzahl = sum(x["quantity"] for x in items_list)
                now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
                entry = f"{datetime.now().strftime('%H:%M:%S')} [{kassierer}] — {total:.2f} € | {produkte_str}"
                try:
                    append_kasse_row({
                        "zeitstempel": now_str,
                        "produkte": produkte_str,
                        "anzahl_gesamt": anzahl,
                        "betrag": total,
                        "erhalten": pay_val,
                        "rueckgeld": round(change, 2),
                        "rabatt": "100%" if st.session_state.free else st.session_state.discount,
                        "kassierer": kassierer,
                    })
                    st.session_state.history.insert(0, entry)
                    st.success(f"Gespeichert: {format_euro(total)} von {kassierer}")
                except Exception as e:
                    st.error(f"Fehler: {e}")
                st.session_state.cart = {}
                st.session_state.pay_amount = ""
                st.session_state.discount = ""
                st.session_state.free = False
                st.rerun()

        # ── History ─────────────────────────────────────────────────────────
        if st.session_state.history:
            st.markdown("<div style='margin-top:12px;color:#888;font-size:11px'>LETZTE TRANSAKTIONEN</div>", unsafe_allow_html=True)
            for entry in st.session_state.history[:5]:
                st.markdown(f"<div style='font-size:12px;color:#aaa;padding:3px 0;border-bottom:1px solid #2d3148'>{entry}</div>", unsafe_allow_html=True)

        try:
            df_hist = load_kasse()
            if not df_hist.empty:
                kass_hist = df_hist[df_hist["Kassierer"] == kassierer].dropna(subset=["Zeitstempel"])
                kass_hist = kass_hist.sort_values("Zeitstempel", ascending=False).head(5)
                if not kass_hist.empty and not st.session_state.history:
                    st.markdown("<div style='margin-top:12px;color:#888;font-size:11px'>AUS SHEET</div>", unsafe_allow_html=True)
                    for _, row in kass_hist.iterrows():
                        ts = row["Zeitstempel"].strftime("%d.%m %H:%M")
                        st.markdown(f"<div style='font-size:12px;color:#666;padding:3px 0'>{ts} — {row['Betrag_Gesamt']:.2f} € | {row['Produkte']}</div>", unsafe_allow_html=True)
        except Exception:
            pass


# ── AUSWERTUNG TAB ───────────────────────────────────────────────────────────
with auswertung_tab:
    if st.button("🔄 Daten neu laden"):
        load_kasse.clear()
        st.rerun()

    df = load_kasse()

    if df.empty:
        st.info("Noch keine Kassendaten vorhanden.")
        st.stop()

    gesamtumsatz = df["Betrag_Gesamt"].sum()
    transaktionen = len(df)
    schnitt = gesamtumsatz / transaktionen if transaktionen > 0 else 0
    stueck_gesamt = df["Anzahl_Gesamt"].sum()

    m = st.columns(4)
    m[0].metric("Gesamtumsatz", format_euro(gesamtumsatz))
    m[1].metric("Transaktionen", str(transaktionen))
    m[2].metric("Durchschnitt", format_euro(schnitt))
    m[3].metric("Artikel verkauft", str(int(stueck_gesamt)))

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Umsatz pro Transaktion")
        time_df = df.dropna(subset=["Zeitstempel"]).sort_values("Zeitstempel")
        if not time_df.empty:
            fig = px.bar(time_df, x="Zeitstempel", y="Betrag_Gesamt", color="Kassierer",
                         labels={"Betrag_Gesamt": "Betrag (EUR)", "Zeitstempel": "Zeit"}, height=300)
            fig.update_layout(margin={"l": 10, "r": 10, "t": 10, "b": 10})
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("### Umsatz pro Kassierer")
        kass_df = (df.groupby("Kassierer")["Betrag_Gesamt"].sum()
                   .reset_index().sort_values("Betrag_Gesamt", ascending=False))
        fig2 = go.Figure(go.Bar(
            x=kass_df["Kassierer"], y=kass_df["Betrag_Gesamt"],
            text=[format_euro(v) for v in kass_df["Betrag_Gesamt"]],
            textposition="outside", marker_color="#1d4ed8"))
        fig2.update_layout(height=300, margin={"l": 10, "r": 10, "t": 10, "b": 10}, yaxis_title="EUR")
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("### Meistverkaufte Produkte")
    product_counts: dict = {}
    for _, row in df.iterrows():
        for teil in str(row["Produkte"]).split(","):
            teil = teil.strip()
            if not teil or "x " not in teil:
                continue
            try:
                menge, name = teil.split("x ", 1)
                product_counts[name.strip()] = product_counts.get(name.strip(), 0) + int(menge.strip())
            except ValueError:
                continue

    if product_counts:
        prod_df = pd.DataFrame(
            sorted(product_counts.items(), key=lambda x: x[1], reverse=True),
            columns=["Produkt", "Stueck"])
        fig3 = go.Figure(go.Bar(
            x=prod_df["Produkt"], y=prod_df["Stueck"],
            text=prod_df["Stueck"], textposition="outside", marker_color="#16a34a"))
        fig3.update_layout(height=340, margin={"l": 10, "r": 10, "t": 10, "b": 10}, yaxis_title="Stueck")
        st.plotly_chart(fig3, use_container_width=True)

    with st.expander("Alle Buchungen", expanded=False):
        display = df.copy()
        display["Zeitstempel"] = display["Zeitstempel"].dt.strftime("%d.%m.%Y %H:%M").fillna("-")
        display["Betrag_Gesamt"] = display["Betrag_Gesamt"].map(format_euro)
        st.dataframe(
            display[["Zeitstempel", "Kassierer", "Produkte", "Anzahl_Gesamt", "Betrag_Gesamt", "Rabatt"]],
            use_container_width=True, hide_index=True)
