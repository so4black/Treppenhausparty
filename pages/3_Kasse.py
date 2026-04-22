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

# Farben pro Kategorie
CAT_COLOR = {
    "Classics":    "#00b894",
    "Shots":       "#e17055",
    "alkoholfrei": "#0984e3",
    "Mischen":     "#6c5ce7",
    "Specials":    "#fdcb6e",
}

PRODUCTS = [
    {"name": "Bier",            "price": 2.0,  "cat": "Classics"},
    {"name": "Aeppler 0,33",    "price": 3.0,  "cat": "Classics"},
    {"name": "+Pfand",          "price": 0.5,  "cat": "Classics"},
    {"name": "Shot",            "price": 1.5,  "cat": "Shots"},
    {"name": "Surprise Shot",   "price": 0.5,  "cat": "Shots"},
    {"name": "Happy Hour Shot", "price": 1.0,  "cat": "Shots"},
    {"name": "Spezi",           "price": 2.0,  "cat": "alkoholfrei"},
    {"name": "Mate",            "price": 3.0,  "cat": "alkoholfrei"},
    {"name": "+Pfand",          "price": 0.5,  "cat": "alkoholfrei"},
    {"name": "Limo 0,33",       "price": 1.5,  "cat": "alkoholfrei"},
    {"name": "Red Bull",        "price": 3.0,  "cat": "alkoholfrei"},
    {"name": "Sekt Mate",       "price": 4.0,  "cat": "Mischen"},
    {"name": "Vodka Mate",      "price": 4.0,  "cat": "Mischen"},
    {"name": "+Pfand",          "price": 0.5,  "cat": "Mischen"},
    {"name": "Koks Mische",     "price": 5.0,  "cat": "Mischen"},
    {"name": "Flasche Pfeffi",  "price": 15.0, "cat": "Specials"},
    {"name": "Golfclub",        "price": 15.0, "cat": "Specials"},
    {"name": "ACAB",            "price": 110.0,"cat": "Specials"},
    {"name": "Bierpong",        "price": 15.0, "cat": "Specials"},
    {"name": "Mischkonsum",     "price": 15.0, "cat": "Specials"},
    {"name": "Schmeisse Runde", "price": 16.0, "cat": "Specials"},
]

SERVICE_ACCOUNT_CANDIDATES = [
    Path("service_account.json"),
    Path(".streamlit/service_account.json"),
    Path(r"C:\Users\leul.zewdie\Downloads\party-dashboard-491808-a0ddf9a20e45.json"),
]


# ── Google Sheets ─────────────────────────────────────────────────────────────

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
            st.warning(f"Anmeldedatei: {candidate} ({exc})")
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


# ── Session state ─────────────────────────────────────────────────────────────

def init_state():
    for k, v in {
        "cart": {},
        "pay_amount": "",
        "discount": "",
        "free": False,
        "history": [],
        "quantity": 1,
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v


def cart_total_base() -> float:
    return sum(v["price"] * v["quantity"] for v in st.session_state.cart.values())


def cart_total() -> float:
    base = cart_total_base()
    if st.session_state.free:
        return 0.0
    disc = st.session_state.discount
    if disc:
        if disc.endswith("%"):
            pct = float(disc[:-1] or 0) / 100
            return max(0.0, base - base * pct)
        try:
            return max(0.0, base - float(disc.replace(",", ".")))
        except ValueError:
            pass
    return base


def add_to_cart(idx: int):
    p = PRODUCTS[idx]
    key = f"{p['cat']}::{p['name']}"
    if key not in st.session_state.cart:
        st.session_state.cart[key] = {**p, "quantity": 0}
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


# ── HTML helpers ──────────────────────────────────────────────────────────────

def product_grid_html() -> str:
    cats: dict = {}
    for i, p in enumerate(PRODUCTS):
        cats.setdefault(p["cat"], []).append((i, p))

    cat_icons = {"Classics": "🍺", "Shots": "🥃", "alkoholfrei": "🧃", "Mischen": "🍹", "Specials": "⭐"}

    html = ""
    for cat, items in cats.items():
        color = CAT_COLOR[cat]
        # dark text for bright yellow (Specials), white for others
        text_color = "#1a1d27" if cat == "Specials" else "#fff"
        html += f"<div style='font-size:11px;font-weight:700;letter-spacing:1px;color:{color};margin:10px 0 5px;text-transform:uppercase'>{cat_icons.get(cat,'')} {cat}</div>"
        html += "<div style='display:grid;grid-template-columns:repeat(3,1fr);gap:6px'>"
        for i, p in items:
            html += (
                f"<a href='?add={i}' style='text-decoration:none'>"
                f"<div style='background:{color};color:{text_color};border-radius:8px;"
                f"padding:10px 8px;font-size:13px;font-weight:600;text-align:center;"
                f"min-height:54px;display:flex;flex-direction:column;justify-content:center;"
                f"align-items:center;gap:2px;cursor:pointer;transition:filter .15s'>"
                f"<span>{p['name']}</span>"
                f"<span style='font-size:12px;opacity:.85'>{p['price']:.2f} €</span>"
                f"</div></a>"
            )
        html += "</div>"
    return html


# ── Page ──────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="THP - Kasse", page_icon="🍺", layout="wide")
init_state()

# Handle product click via query param
qp = st.query_params
if "add" in qp:
    try:
        add_to_cart(int(qp["add"]))
    except (ValueError, IndexError):
        pass
    st.query_params.clear()
    st.rerun()

st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #0f1117; }
[data-testid="stSidebar"] { background: #1a1d27; }
[data-testid="stHorizontalBlock"] { gap: 5px !important; }
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { padding: 0 !important; }
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"] > div { margin-bottom: 5px !important; }

/* Alle st.button gleich groß */
button[kind="secondary"], button[kind="primary"] {
    width: 100% !important;
    height: 48px !important;
    min-height: 48px !important;
    max-height: 48px !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    padding: 0 8px !important;
    border-radius: 8px !important;
}
/* Numpad größer */
.numpad-row button[kind="secondary"] {
    height: 56px !important;
    min-height: 56px !important;
    max-height: 56px !important;
    font-size: 20px !important;
    font-weight: 700 !important;
}
/* Checkout-Button */
.checkout-row button[kind="primary"] {
    height: 60px !important;
    min-height: 60px !important;
    max-height: 60px !important;
    font-size: 17px !important;
    font-weight: 700 !important;
    background: #00b894 !important;
    border-color: #00b894 !important;
}
.cancel-row button[kind="secondary"] {
    height: 60px !important;
    min-height: 60px !important;
    max-height: 60px !important;
    font-size: 15px !important;
}
/* Qty-Buttons klein */
.qty-row button {
    height: 36px !important;
    min-height: 36px !important;
    max-height: 36px !important;
    font-size: 13px !important;
    padding: 0 !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("<h2 style='margin-bottom:8px'>🍺 Touch-Kasse</h2>", unsafe_allow_html=True)

kasse_tab, auswertung_tab = st.tabs(["Kasse", "Auswertung"])

with kasse_tab:

    # Top bar
    t1, t2 = st.columns([2, 6])
    with t1:
        kassierer = st.selectbox("Kassierer", KASSIERER_LIST, key="kassierer", label_visibility="collapsed")
        st.markdown(f"<div style='color:#1d4ed8;font-size:12px;font-weight:700;margin-top:-6px'>👤 {kassierer}</div>", unsafe_allow_html=True)
    with t2:
        st.markdown("<div style='color:#666;font-size:11px;letter-spacing:1px;text-transform:uppercase;margin-bottom:3px'>Anzahl</div>", unsafe_allow_html=True)
        st.markdown('<div class="qty-row">', unsafe_allow_html=True)
        qcols = st.columns(11)
        for i, q in enumerate(range(1, 11)):
            if qcols[i].button(str(q), key=f"q_{q}", use_container_width=True,
                               type="primary" if st.session_state.quantity == q else "secondary"):
                st.session_state.quantity = q
                st.rerun()
        if qcols[10].button("✕", key="q_c", use_container_width=True):
            st.session_state.quantity = 1
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown(f"<div style='color:#1d4ed8;font-size:12px;font-weight:700;margin-top:-4px'>{st.session_state.quantity}x ausgewählt</div>", unsafe_allow_html=True)

    st.markdown("<hr style='border-color:#2d3148;margin:10px 0'>", unsafe_allow_html=True)

    prod_col, cart_col = st.columns([3, 2], gap="large")

    # ── Produktgitter als HTML ────────────────────────────────────────────────
    with prod_col:
        st.markdown(product_grid_html(), unsafe_allow_html=True)

    # ── Kassenansicht ─────────────────────────────────────────────────────────
    with cart_col:

        # Warenkorb-Anzeige
        st.markdown("<div style='font-size:15px;font-weight:700;color:#fff;margin-bottom:6px'>Warenkorb</div>", unsafe_allow_html=True)
        cart_html = "<div style='background:#1a1d27;border-radius:10px;padding:10px 14px;margin-bottom:8px;min-height:60px'>"
        if not st.session_state.cart:
            cart_html += "<div style='color:#555;font-style:italic;font-size:13px;padding:8px 0'>Warenkorb leer</div>"
        else:
            for item in st.session_state.cart.values():
                color = CAT_COLOR.get(item["cat"], "#aaa")
                cart_html += (
                    f"<div style='display:flex;justify-content:space-between;padding:5px 0;"
                    f"border-bottom:1px solid #2d3148;font-size:13px'>"
                    f"<span><span style='color:{color};font-weight:700'>{item['quantity']}×</span> {item['name']}</span>"
                    f"<span style='color:#fff;font-weight:600'>{item['quantity']*item['price']:.2f} €</span>"
                    f"</div>"
                )
        cart_html += "</div>"
        st.markdown(cart_html, unsafe_allow_html=True)

        # Warenkorb +/- Buttons
        if st.session_state.cart:
            for key, item in list(st.session_state.cart.items()):
                c1, c2, c3 = st.columns([5, 1, 1])
                c1.markdown(f"<div style='font-size:12px;color:#888;padding-top:8px'>{item['name']}</div>", unsafe_allow_html=True)
                if c2.button("+", key=f"p_{key}", use_container_width=True):
                    st.session_state.cart[key]["quantity"] += 1
                    st.rerun()
                if c3.button("−", key=f"m_{key}", use_container_width=True):
                    st.session_state.cart[key]["quantity"] -= 1
                    if st.session_state.cart[key]["quantity"] <= 0:
                        del st.session_state.cart[key]
                    st.rerun()

        # Aktionszeile
        a1, a2 = st.columns(2)
        if a1.button("Gratis" if not st.session_state.free else "Gratis ✓",
                     type="primary" if st.session_state.free else "secondary",
                     use_container_width=True):
            st.session_state.free = not st.session_state.free
            st.rerun()
        if a2.button("Leeren", use_container_width=True):
            st.session_state.cart = {}
            st.session_state.discount = ""
            st.session_state.free = False
            st.rerun()

        new_disc = st.text_input("Rabatt", value=st.session_state.discount, key="disc_input",
                                 label_visibility="collapsed", placeholder="Rabatt: 10% oder 2.50 EUR")
        if new_disc != st.session_state.discount:
            st.session_state.discount = new_disc

        # Totals-Box
        base = cart_total_base()
        total = cart_total()
        try:
            pay_val = float(st.session_state.pay_amount.replace(",", ".")) if st.session_state.pay_amount else 0.0
        except ValueError:
            pay_val = 0.0
        change = pay_val - total
        chg_color = "#00b894" if change >= 0 else "#d63031"
        disc_html = ""
        if st.session_state.free:
            disc_html = "<div style='display:flex;justify-content:space-between;font-size:13px;color:#e17055;padding:2px 0'><span>Rabatt</span><span>100% Gratis</span></div>"
        elif st.session_state.discount:
            disc_html = f"<div style='display:flex;justify-content:space-between;font-size:13px;color:#e17055;padding:2px 0'><span>Rabatt</span><span>{st.session_state.discount}</span></div>"

        st.markdown(f"""
        <div style='background:#1a1d27;border-radius:10px;padding:12px 14px;margin:6px 0;border:1px solid #2d3148'>
          <div style='display:flex;justify-content:space-between;font-size:13px;color:#888;padding:2px 0'><span>Summe</span><span>{base:.2f} €</span></div>
          {disc_html}
          <div style='display:flex;justify-content:space-between;font-size:24px;font-weight:700;color:#fff;padding:6px 0 4px'><span>Gesamt</span><span>{total:.2f} €</span></div>
          <div style='display:flex;justify-content:space-between;font-size:13px;color:#888;padding:2px 0'><span>Erhalten</span><span>{pay_val:.2f} €</span></div>
          <div style='display:flex;justify-content:space-between;font-size:16px;font-weight:700;color:{chg_color};padding:2px 0'><span>Rückgeld</span><span>{change:.2f} €</span></div>
        </div>
        """, unsafe_allow_html=True)

        # Schnellzahlung
        st.markdown("<div style='color:#666;font-size:11px;letter-spacing:1px;text-transform:uppercase;margin:6px 0 3px'>Schnellzahlung</div>", unsafe_allow_html=True)
        qp2 = st.columns(4)
        for i, amt in enumerate([5, 10, 20, 50]):
            if qp2[i].button(f"{amt} €", key=f"qp_{amt}", use_container_width=True):
                st.session_state.pay_amount = str(amt)
                st.rerun()

        # Numpad
        st.markdown("<div style='color:#666;font-size:11px;letter-spacing:1px;text-transform:uppercase;margin:8px 0 3px'>Betrag eingeben</div>", unsafe_allow_html=True)
        st.markdown(
            f"<div style='font-size:30px;font-weight:700;color:#fff;background:#1a1d27;"
            f"border-radius:8px;padding:10px 14px;margin-bottom:6px;text-align:right;"
            f"border:1px solid #2d3148'>{st.session_state.pay_amount or '0'} €</div>",
            unsafe_allow_html=True
        )
        for row in [["7","8","9"], ["4","5","6"], ["1","2","3"], ["0",".","<"]]:
            st.markdown('<div class="numpad-row">', unsafe_allow_html=True)
            rcols = st.columns(3)
            for i, val in enumerate(row):
                if rcols[i].button(val, key=f"np_{val}_{row[0]}", use_container_width=True):
                    numpad_press("⌫" if val == "<" else val)
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        bot1, bot2 = st.columns(2)
        if bot1.button("C  (löschen)", key="np_C", use_container_width=True):
            numpad_press("C")
            st.rerun()
        if bot2.button("Passend", key="np_passend", use_container_width=True):
            st.session_state.pay_amount = f"{total:.2f}"
            st.rerun()

        # Checkout
        st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)
        ch1, ch2 = st.columns([3, 2])
        st.markdown('<div class="checkout-row">', unsafe_allow_html=True)
        checkout_clicked = ch1.button("Zahlung abschliessen", type="primary", use_container_width=True, key="checkout")
        st.markdown('</div><div class="cancel-row">', unsafe_allow_html=True)
        cancel_clicked = ch2.button("Stornieren", use_container_width=True, key="cancel")
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

        # History
        if st.session_state.history:
            st.markdown("<div style='margin-top:12px;color:#666;font-size:11px;letter-spacing:1px;text-transform:uppercase'>Letzte Transaktionen</div>", unsafe_allow_html=True)
            for e in st.session_state.history[:5]:
                st.markdown(f"<div style='font-size:12px;color:#888;padding:3px 0;border-bottom:1px solid #2d3148'>{e}</div>", unsafe_allow_html=True)

        try:
            df_hist = load_kasse()
            if not df_hist.empty and not st.session_state.history:
                kh = df_hist[df_hist["Kassierer"] == kassierer].dropna(subset=["Zeitstempel"])
                kh = kh.sort_values("Zeitstempel", ascending=False).head(5)
                if not kh.empty:
                    st.markdown("<div style='margin-top:10px;color:#666;font-size:11px;letter-spacing:1px;text-transform:uppercase'>Aus Sheet</div>", unsafe_allow_html=True)
                    for _, row in kh.iterrows():
                        ts = row["Zeitstempel"].strftime("%d.%m %H:%M")
                        st.markdown(f"<div style='font-size:12px;color:#555;padding:3px 0'>{ts} — {row['Betrag_Gesamt']:.2f} € | {row['Produkte']}</div>", unsafe_allow_html=True)
        except Exception:
            pass


# ── AUSWERTUNG TAB ────────────────────────────────────────────────────────────
with auswertung_tab:
    if st.button("Daten neu laden"):
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
            fig.update_layout(margin={"l":10,"r":10,"t":10,"b":10})
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown("### Umsatz pro Kassierer")
        kass_df = df.groupby("Kassierer")["Betrag_Gesamt"].sum().reset_index().sort_values("Betrag_Gesamt", ascending=False)
        fig2 = go.Figure(go.Bar(x=kass_df["Kassierer"], y=kass_df["Betrag_Gesamt"],
                                text=[format_euro(v) for v in kass_df["Betrag_Gesamt"]],
                                textposition="outside", marker_color="#1d4ed8"))
        fig2.update_layout(height=300, margin={"l":10,"r":10,"t":10,"b":10}, yaxis_title="EUR")
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
        prod_df = pd.DataFrame(sorted(product_counts.items(), key=lambda x: x[1], reverse=True), columns=["Produkt", "Stueck"])
        fig3 = go.Figure(go.Bar(x=prod_df["Produkt"], y=prod_df["Stueck"],
                                text=prod_df["Stueck"], textposition="outside", marker_color="#16a34a"))
        fig3.update_layout(height=340, margin={"l":10,"r":10,"t":10,"b":10}, yaxis_title="Stueck")
        st.plotly_chart(fig3, use_container_width=True)

    with st.expander("Alle Buchungen", expanded=False):
        display = df.copy()
        display["Zeitstempel"] = display["Zeitstempel"].dt.strftime("%d.%m.%Y %H:%M").fillna("-")
        display["Betrag_Gesamt"] = display["Betrag_Gesamt"].map(format_euro)
        st.dataframe(display[["Zeitstempel","Kassierer","Produkte","Anzahl_Gesamt","Betrag_Gesamt","Rabatt"]],
                     use_container_width=True, hide_index=True)
