import json
from pathlib import Path

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

SERVICE_ACCOUNT_CANDIDATES = [
    Path("service_account.json"),
    Path(".streamlit/service_account.json"),
    Path(".streamlit/secrets.toml.txt"),
    Path(r"C:\Users\leul.zewdie\Downloads\party-dashboard-491808-a0ddf9a20e45.json"),
]


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
    if v is None or pd.isna(v):
        return "-"
    return f"{v:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", ".")


st.set_page_config(page_title="THP – Kassen-Auswertung", page_icon="🍺", layout="wide")
st.title("🍺 Kassen-Auswertung")
st.caption("Live-Daten aus dem Google Sheet Backend_Kasse — wird von der Touch-Kasse befüllt.")

df = load_kasse()

if df.empty:
    st.info("Noch keine Kassendaten vorhanden. Die Touch-Kasse schreibt nach jedem Checkout automatisch hierher.")
    st.stop()

# --- Metriken ---
gesamtumsatz = df["Betrag_Gesamt"].sum()
transaktionen = len(df)
schnitt = gesamtumsatz / transaktionen if transaktionen > 0 else 0
stueck_gesamt = df["Anzahl_Gesamt"].sum()

m = st.columns(4)
m[0].metric("Gesamtumsatz", format_euro(gesamtumsatz))
m[1].metric("Transaktionen", str(transaktionen))
m[2].metric("Ø pro Transaktion", format_euro(schnitt))
m[3].metric("Verkaufte Artikel", str(int(stueck_gesamt)))

st.markdown("---")

# --- Umsatz über Zeit ---
col1, col2 = st.columns(2)

with col1:
    st.markdown("### Umsatz pro Transaktion")
    time_df = df.dropna(subset=["Zeitstempel"]).sort_values("Zeitstempel")
    if not time_df.empty:
        fig = px.bar(
            time_df,
            x="Zeitstempel",
            y="Betrag_Gesamt",
            color="Kassierer",
            labels={"Betrag_Gesamt": "Betrag (€)", "Zeitstempel": "Zeit"},
            height=320,
        )
        fig.update_layout(margin={"l": 10, "r": 10, "t": 10, "b": 10}, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Keine Zeitstempel vorhanden.")

with col2:
    st.markdown("### Umsatz pro Kassierer")
    kass_df = df.groupby("Kassierer")["Betrag_Gesamt"].sum().reset_index().sort_values("Betrag_Gesamt", ascending=False)
    fig2 = go.Figure(go.Bar(
        x=kass_df["Kassierer"],
        y=kass_df["Betrag_Gesamt"],
        text=[format_euro(v) for v in kass_df["Betrag_Gesamt"]],
        textposition="outside",
        marker_color="#1d4ed8",
    ))
    fig2.update_layout(height=320, margin={"l": 10, "r": 10, "t": 10, "b": 10}, yaxis_title="EUR", xaxis_title="")
    st.plotly_chart(fig2, use_container_width=True)

# --- Meistverkaufte Produkte ---
st.markdown("### Meistverkaufte Produkte")
st.caption("Wird aus den Produktfeldern der Kassenbuchungen extrahiert.")

product_counts: dict = {}
for _, row in df.iterrows():
    for teil in str(row["Produkte"]).split(","):
        teil = teil.strip()
        if not teil:
            continue
        try:
            menge, name = teil.split("x ", 1)
            product_counts[name.strip()] = product_counts.get(name.strip(), 0) + int(menge.strip())
        except ValueError:
            continue

if product_counts:
    prod_df = pd.DataFrame(
        sorted(product_counts.items(), key=lambda x: x[1], reverse=True),
        columns=["Produkt", "Stueck"]
    )
    fig3 = go.Figure(go.Bar(
        x=prod_df["Produkt"],
        y=prod_df["Stueck"],
        text=prod_df["Stueck"],
        textposition="outside",
        marker_color="#16a34a",
    ))
    fig3.update_layout(height=360, margin={"l": 10, "r": 10, "t": 10, "b": 10}, yaxis_title="Stück", xaxis_title="")
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("Noch keine Produktdaten auswertbar.")

# --- Rohdaten ---
with st.expander("Alle Buchungen (Rohdaten)", expanded=False):
    display = df.copy()
    display["Zeitstempel"] = display["Zeitstempel"].dt.strftime("%d.%m.%Y %H:%M").fillna("-")
    display["Betrag_Gesamt"] = display["Betrag_Gesamt"].map(format_euro)
    st.dataframe(display[["Zeitstempel", "Kassierer", "Produkte", "Anzahl_Gesamt", "Betrag_Gesamt", "Rabatt"]], use_container_width=True, hide_index=True)
