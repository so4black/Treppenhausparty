import json
from pathlib import Path
from datetime import datetime

import gspread
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from streamlit.errors import StreamlitSecretNotFoundError

SPREADSHEET_ID = "1z6pVOSBNUcrWAdmgQfuqfNpvlwBYUkPmd58Xu29kj-U"
SHEET_NAME = "Backend_Kasse"
HEADER = ["ID", "Zeitstempel", "Produkte", "Anzahl_Gesamt",
          "Betrag_Gesamt", "Erhalten", "Rueckgeld", "Rabatt", "Kassierer"]

KASSIERER_LIST = ["Freddy","Divin","Chrissi","Jan","Leul","Sohrab",
                  "Aldar","Lorena","Anna K.","Michelle","Finn"]

SERVICE_ACCOUNT_CANDIDATES = [
    Path("service_account.json"),
    Path(".streamlit/service_account.json"),
    Path(".streamlit/secrets.toml.txt"),
    Path(r"C:\Users\leul.zewdie\Downloads\party-dashboard-491808-a0ddf9a20e45.json"),
]

# Custom component — bidirectional, so setComponentValue works
_component_dir = Path(__file__).parent.parent / "kasse_component"


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


def build_sheet_history(df: pd.DataFrame, n: int = 10) -> dict:
    result: dict = {}
    if df.empty:
        return result
    for kassierer, group in df.groupby("Kassierer"):
        group_sorted = group.dropna(subset=["Zeitstempel"]).sort_values("Zeitstempel", ascending=False)
        entries = []
        for _, row in group_sorted.head(n).iterrows():
            ts = row["Zeitstempel"].strftime("%d.%m %H:%M") if pd.notna(row["Zeitstempel"]) else "?"
            betrag = f"{row['Betrag_Gesamt']:.2f}"
            produkte = str(row["Produkte"])[:40]
            entries.append(f"{ts} - {betrag} EUR | {produkte}")
        result[str(kassierer)] = entries
    return result


def format_euro(v):
    if v is None or pd.isna(v):
        return "-"
    return f"{v:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", ".")


st.set_page_config(page_title="THP - Kasse", page_icon="🍺", layout="wide")
st.title("🍺 Touch-Kasse")

kasse_tab, auswertung_tab = st.tabs(["Kasse", "Auswertung"])

with kasse_tab:
    try:
        df_for_history = load_kasse()
        sheet_history = build_sheet_history(df_for_history, n=10)
    except Exception:
        sheet_history = {}

    _kasse = components.declare_component("kasse", path=str(_component_dir))

    checkout_data = _kasse(
        kassierer_list=KASSIERER_LIST,
        sheet_history=sheet_history,
        key="kasse_main",
    )

    # When checkout_data is set by JS, write to sheet
    if checkout_data and isinstance(checkout_data, dict) and checkout_data.get("type") == "checkout":
        # Deduplicate: skip if we already processed this exact checkout (same ts_epoch)
        last_epoch = st.session_state.get("last_checkout_epoch", 0)
        this_epoch = checkout_data.get("ts_epoch", 0)
        if this_epoch != last_epoch:
            st.session_state["last_checkout_epoch"] = this_epoch
            try:
                append_kasse_row(checkout_data)
                kassierer = checkout_data.get("kassierer", "")
                betrag = checkout_data.get("betrag", 0)
                st.success(f"✅ {format_euro(betrag)} von {kassierer} ins Sheet gespeichert.")
            except Exception as e:
                st.error(f"Fehler beim Speichern: {e}")

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
        prod_df = pd.DataFrame(sorted(product_counts.items(), key=lambda x: x[1], reverse=True),
                               columns=["Produkt", "Stueck"])
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
