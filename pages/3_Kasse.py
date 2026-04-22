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

# Custom CSS for product buttons
st.markdown("""
<style>
div[data-testid="column"] button {
    width: 100%;
    border-radius: 8px;
    font-size: 13px;
    padding: 6px 4px;
    min-height: 52px;
}
.stButton button { width: 100%; }
</style>
""", unsafe_allow_html=True)

st.title("🍺 Touch-Kasse")

kasse_tab, auswertung_tab = st.tabs(["Kasse", "Auswertung"])

# ── KASSE TAB ────────────────────────────────────────────────────────────────
with kasse_tab:

    # ── Top bar: kassierer + quantity selector ───────────────────────────────
    top1, top2, top3 = st.columns([2, 4, 2])
    with top1:
        kassierer = st.selectbox("👤 Kassierer", KASSIERER_LIST, key="kassierer")
    with top2:
        st.markdown("**🔢 Anzahl**")
        qcols = st.columns(11)
        for i, q in enumerate([1,2,3,4,5,6,7,8,9,10]):
            if qcols[i].button(str(q), key=f"q_{q}",
                               type="primary" if st.session_state.quantity == q else "secondary"):
                st.session_state.quantity = q
                st.rerun()
        if qcols[10].button("C", key="q_c"):
            st.session_state.quantity = 1
            st.rerun()
    with top3:
        st.metric("Anzahl", st.session_state.quantity)

    st.divider()

    # ── Product grid + Cart side by side ────────────────────────────────────
    prod_col, cart_col = st.columns([3, 2])

    with prod_col:
        # Group products by category
        categories: dict = {}
        for p in PRODUCTS:
            categories.setdefault(p["category"], []).append(p)

        for cat, items in categories.items():
            st.markdown(f"**{cat}**")
            cols = st.columns(3)
            for idx, p in enumerate(items):
                label = f"{p['name']} — {p['price']:.2f} €"
                if cols[idx % 3].button(label, key=f"prod_{cat}_{p['name']}_{idx}"):
                    add_to_cart(p)
                    st.rerun()

    with cart_col:
        st.markdown("### 🛒 Warenkorb")

        if not st.session_state.cart:
            st.caption("_Warenkorb leer_")
        else:
            for key, item in list(st.session_state.cart.items()):
                c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 1])
                c1.write(f"{item['quantity']}x **{item['name']}**")
                c2.write(f"{item['price']:.2f}")
                c3.write(f"= {item['quantity']*item['price']:.2f}")
                if c4.button("➕", key=f"plus_{key}"):
                    st.session_state.cart[key]["quantity"] += 1
                    st.rerun()
                if c5.button("➖", key=f"minus_{key}"):
                    st.session_state.cart[key]["quantity"] -= 1
                    if st.session_state.cart[key]["quantity"] <= 0:
                        del st.session_state.cart[key]
                    st.rerun()

        # Discount
        disc_col1, disc_col2 = st.columns([3, 1])
        new_disc = disc_col1.text_input("💸 Rabatt (z.B. 10% oder 2.50)", value=st.session_state.discount,
                                         key="disc_input", label_visibility="collapsed",
                                         placeholder="Rabatt: 10% oder 2.50 EUR")
        if new_disc != st.session_state.discount:
            st.session_state.discount = new_disc

        free_cols = st.columns(2)
        if free_cols[0].button("🎁 Gratis" if not st.session_state.free else "🎁 Gratis ✓",
                               type="primary" if st.session_state.free else "secondary"):
            st.session_state.free = not st.session_state.free
            st.rerun()
        if free_cols[1].button("🗑️ Warenkorb leeren"):
            st.session_state.cart = {}
            st.session_state.discount = ""
            st.session_state.free = False
            st.rerun()

        st.divider()

        # Totals
        base = cart_total_base()
        total = cart_total()
        st.markdown(f"**Summe:** {base:.2f} EUR")
        if st.session_state.free:
            st.markdown("**Rabatt:** 100% (Gratis)")
        elif st.session_state.discount:
            st.markdown(f"**Rabatt:** {st.session_state.discount}")
        st.markdown(f"### Gesamt: **{total:.2f} EUR**")

        # Payment numpad
        st.markdown("**💶 Betrag eingeben:**")
        try:
            pay_val = float(st.session_state.pay_amount.replace(",", ".")) if st.session_state.pay_amount else 0.0
        except ValueError:
            pay_val = 0.0
        change = pay_val - total

        st.markdown(f"**Erhalten:** {pay_val:.2f} EUR")
        if pay_val > 0:
            color = "green" if change >= 0 else "red"
            st.markdown(f"**Rückgeld:** :{color}[**{change:.2f} EUR**]")

        # Quick pay buttons
        qp_cols = st.columns(4)
        for i, amt in enumerate([5, 10, 20, 50]):
            if qp_cols[i].button(f"{amt} €", key=f"qp_{amt}"):
                st.session_state.pay_amount = str(amt)
                st.rerun()

        # Numpad
        pad_rows = [["7","8","9"], ["4","5","6"], ["1","2","3"], ["0",".","<"], ["C","",""]]
        for row in pad_rows:
            rcols = st.columns(3)
            for i, val in enumerate(row):
                if val and rcols[i].button(val, key=f"pad_{val}_{row}"):
                    numpad_press("⌫" if val == "<" else val)
                    st.rerun()

        # Passend button
        if st.button("Passend", use_container_width=True):
            st.session_state.pay_amount = f"{total:.2f}"
            st.rerun()

        st.divider()

        # Checkout + Cancel
        ch_col1, ch_col2 = st.columns(2)
        checkout_clicked = ch_col1.button("✅ Zahlung abschliessen", type="primary", use_container_width=True)
        cancel_clicked = ch_col2.button("❌ Stornieren", use_container_width=True)

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
                st.error(f"Betrag zu gering! Noch {total - pay_val:.2f} EUR fehlen.")
            else:
                items_list = list(st.session_state.cart.values())
                produkte_str = ", ".join(f"{x['quantity']}x {x['name']}" for x in items_list)
                anzahl = sum(x["quantity"] for x in items_list)
                now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
                entry = f"{datetime.now().strftime('%H:%M:%S')} [{kassierer}] - {total:.2f} EUR | {produkte_str}"
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
                    st.success(f"✅ {format_euro(total)} von {kassierer} gespeichert!")
                except Exception as e:
                    st.error(f"Fehler beim Speichern: {e}")

                # Reset cart
                st.session_state.cart = {}
                st.session_state.pay_amount = ""
                st.session_state.discount = ""
                st.session_state.free = False
                st.rerun()

    st.divider()

    # ── History ──────────────────────────────────────────────────────────────
    if st.session_state.history:
        st.markdown("**📋 Letzte Transaktionen (diese Sitzung):**")
        for entry in st.session_state.history[:8]:
            st.caption(entry)

    # Sheet history for selected kassierer
    try:
        df_hist = load_kasse()
        if not df_hist.empty:
            kass_hist = df_hist[df_hist["Kassierer"] == kassierer].dropna(subset=["Zeitstempel"])
            kass_hist = kass_hist.sort_values("Zeitstempel", ascending=False).head(5)
            if not kass_hist.empty:
                with st.expander(f"📄 Letzte Sheet-Einträge von {kassierer}"):
                    for _, row in kass_hist.iterrows():
                        ts = row["Zeitstempel"].strftime("%d.%m %H:%M")
                        st.caption(f"{ts} - {row['Betrag_Gesamt']:.2f} EUR | {row['Produkte']}")
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
