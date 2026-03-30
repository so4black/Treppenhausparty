import base64
import json
import os
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError
from plotly.subplots import make_subplots
import gspread

st.title("Barkalkulation")
st.markdown("Live-Daten aus Google Sheets laden und interaktive Dashboards anzeigen.")

BACKGROUND_IMAGE_PATH = r"C:\Users\leul.zewdie\Desktop\privat\THP\Nordfluegelerweitert.jpg"

if os.path.exists(BACKGROUND_IMAGE_PATH):
    def get_base64_image(image_path: str) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode()

    background_base64 = get_base64_image(BACKGROUND_IMAGE_PATH)
    st.markdown(
        f"""
        <style>
        html, body {{
            min-height: 100%;
            background-image:
                linear-gradient(to bottom, rgba(0,0,0,0) 45%, rgba(0,0,0,0.95) 100%),
                url('data:image/jpeg;base64,{background_base64}');
            background-size: 100% auto;
            background-position: top center;
            background-repeat: no-repeat;
            background-attachment: scroll;
            background-color: #000;
        }}
        [data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] .main {{
            min-height: 100%;
            background-color: transparent;
        }}
        [data-testid="stAppViewContainer"] .main,
        [data-testid="stAppViewContainer"] .block-container,
        [data-testid="stAppViewContainer"] .appview-container {{
            background-color: rgba(15, 23, 42, 0.18) !important;
            backdrop-filter: blur(8px);
            box-shadow: none !important;
        }}
        .st-c8 {{ background-color: rgba(255,255,255,0.85) !important; }}
        </style>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        """
        <style>
        html, body, [data-testid="stAppViewContainer"] {
            min-height: 100%;
            background-image:
                radial-gradient(circle at top left, rgba(129,140,248,0.35), transparent 20%),
                linear-gradient(180deg, #0f172a 0%, #020617 100%) !important;
            background-size: cover;
            background-attachment: fixed;
            background-repeat: no-repeat;
            background-color: #020617;
        }
        [data-testid="stAppViewContainer"] .main,
        [data-testid="stAppViewContainer"] .block-container,
        [data-testid="stAppViewContainer"] .appview-container {
            background-color: rgba(15, 23, 42, 0.18) !important;
            backdrop-filter: blur(8px);
            box-shadow: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

SHEET_ID = "1z6pVOSBNUcrWAdmgQfuqfNpvlwBYUkPmd58Xu29kj-U"
WORKSHEET_NAME = "THP26"
PUBLIC_SHEET_NAME = "THP26_Preisberechnung"
SERVICE_ACCOUNT_CANDIDATES = [
    Path("service_account.json"),
    Path(".streamlit/service_account.json"),
    Path(".streamlit/secrets.toml.txt"),
]


def normalize_number(value):
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "n/a"}:
        return pd.NA
    text = re.sub(r"[€\s\u00A0]", "", text)
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif text.count(",") == 1 and text.count(".") == 0:
        text = text.replace(",", ".")
    elif text.count(".") > 1 and text.count(",") == 0:
        text = text.replace(".", "")
    return text


def clean_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).apply(normalize_number), errors="coerce")


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
        except Exception as error:
            st.warning(f"Anmeldedatei konnte nicht verwendet werden: {candidate} ({error})")

    return None


@st.cache_data(ttl=600)
def load_google_sheet():
    df_raw = None
    client = get_gspread_client()
    if client is not None:
        try:
            sheet = client.open_by_key(SHEET_ID)
            try:
                worksheet = sheet.worksheet(WORKSHEET_NAME)
            except gspread.WorksheetNotFound:
                worksheet = sheet.sheet1
            values = worksheet.get_all_values()
            df_raw = pd.DataFrame(values)
        except Exception as error:
            st.warning(f"Service Account konnte nicht verwendet werden: {error}")

    if df_raw is None:
        gviz_csv_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={PUBLIC_SHEET_NAME}"
        try:
            df_raw = pd.read_csv(gviz_csv_url, header=None, dtype=str)
        except Exception:
            csv_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
            df_raw = pd.read_csv(csv_url, header=None, dtype=str)

    def normalize_header(cell):
        text = str(cell).strip().lower()
        text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
        text = text.replace(" ", "").replace("\"", "").replace("'", "")
        return text

    header_row = None
    for idx, row in df_raw.iterrows():
        cells = [normalize_header(cell) for cell in row.values]
        if any(pattern in cell for cell in cells if cell for pattern in ["getraenk", "metric", "spalte1"]):
            header_row = idx
            break

    if header_row is None:
        raise ValueError("Die Tabelle konnte nicht analysiert werden. Die Zeile mit 'Getränk' wurde nicht gefunden.")

    df_sheet = df_raw.iloc[header_row + 1 :].copy()
    header_columns = df_raw.iloc[header_row].astype(str).str.strip().tolist()
    if len(header_columns) >= 2:
        header_columns[0] = "Metric"
        header_columns[1] = "Unit"
    df_sheet.columns = header_columns
    df_sheet.columns.name = None
    df_sheet = df_sheet[df_sheet["Metric"].notna()].copy()

    drink_cols = [col for col in df_sheet.columns if col not in ["Metric", "Unit"]]
    if not drink_cols:
        raise ValueError("Keine Getränkespalten gefunden. Prüfe die Tabellenstruktur.")

    df_long = df_sheet.melt(
        id_vars=["Metric", "Unit"],
        value_vars=drink_cols,
        var_name="Getränk",
        value_name="Value"
    )
    df_long = df_long[df_long["Getränk"].notna()].copy()
    df_long["Value_clean"] = df_long["Value"].astype(str).apply(normalize_number)
    df_long["Value_num"] = pd.to_numeric(df_long["Value_clean"], errors="coerce")

    metric_units = (df_sheet.set_index("Metric")["Unit"].astype(str).str.strip().replace({"nan": ""}).to_dict())
    df_wide = df_long.pivot_table(
        index="Getränk",
        columns="Metric",
        values="Value_num",
        aggfunc="first"
    ).reset_index()

    # Spaltennamen um Einheiten erweitern
    new_columns = []
    for col in df_wide.columns:
        if col == "Getränk":
            new_columns.append(col)
        else:
            unit = metric_units.get(str(col).strip(), "")
            if unit:
                new_columns.append(f"{col} ({unit})")
            else:
                new_columns.append(str(col).strip())
    df_wide.columns = new_columns

    return df_wide


def find_column(df: pd.DataFrame, patterns):
    for pattern in patterns:
        for col in df.columns:
            if pattern.lower() in col.lower():
                return col
    return None


def get_total_from_totals_row(totals_df: pd.DataFrame, patterns, fallback=None):
    if totals_df is not None and not totals_df.empty:
        col = find_column(totals_df, patterns)
        if col:
            value = totals_df.iloc[0].get(col)
            if pd.notna(value):
                return value
    if fallback is not None:
        try:
            return fallback.sum()
        except Exception:
            return None
    return None


try:
    df = load_google_sheet()
except Exception as exc:
    st.error(f"Daten konnten nicht geladen werden: {exc}")
    st.stop()

st.success("✅ Daten erfolgreich aus Google Sheets geladen.")

mask_total = df["Getränk"].astype(str).str.contains("Gesamt|gesamt|Total|TOTAL", regex=True, na=False)
df_totals = df[mask_total].copy()
df = df[~mask_total].copy()
df = df[df["Getränk"].astype(str).str.strip() != ""].copy()

cost_col = find_column(df, ["Einkaufspreis je Flasche", "Einkaufspreis je Liter", "Kosten im Einkauf", "Kosten Shotbecher"])
sell_col = find_column(df, ["Verkaufspreis je Getränk", "Verkaufspreis/Einkaufspreis"])
qty_col = find_column(df, ["Anzahl Flaschen", "Getränke gesamt", "Geschätzer Verkauf"])
profit_col = find_column(df, ["Gewinn ([€])", "Gewinn je Getränk", "Gewinn je Flasche", "Gewinn"])
revenue_col = find_column(df, ["Umsatz (Fall", "Umsatz je Flasche", "kalkulierter Umsatz", "Umsatz nach Kasse", "Umsatz"])
canonical_revenue_col = "Umsatz (Fall: Komplettverkauf)"

if cost_col and sell_col:
    df["Deckungsbeitrag"] = df[sell_col] - df[cost_col]
if qty_col and sell_col:
    df["Umsatz"] = df[qty_col] * df[sell_col]

if revenue_col is None:
    if qty_col and sell_col:
        df[canonical_revenue_col] = df[qty_col] * df[sell_col]
        revenue_col = canonical_revenue_col
else:
    if revenue_col != canonical_revenue_col and canonical_revenue_col not in df.columns:
        df[canonical_revenue_col] = df[revenue_col]
        revenue_col = canonical_revenue_col
    else:
        revenue_col = canonical_revenue_col

if profit_col is None and qty_col and sell_col and cost_col:
    df["Gewinn berechnet"] = df[qty_col] * (df[sell_col] - df[cost_col])
    profit_col = "Gewinn berechnet"

if sell_col:
    price_df = df[["Getränk", sell_col]].copy()
    price_df[sell_col] = price_df[sell_col].apply(lambda v: f"{v:,.2f} €" if pd.notna(v) else "-")
    st.subheader("Verkaufspreise der Getränke")
    if len(price_df) <= 8:
        cols = st.columns(len(price_df))
        for col_block, (_, row) in zip(cols, price_df.iterrows()):
            drink_name = row["Getränk"]
            price_value = row[sell_col]
            card_html = f"""
                <div style=\"border:1px solid #d1d5db; border-radius:18px; padding:14px; text-align:center; background:#ffffff; box-shadow:0 4px 12px rgba(0,0,0,0.05);\">
                    <div style=\"font-size:16px; font-weight:700; color:#111827; margin-bottom:8px;\">{drink_name}</div>
                    <div style=\"font-size:22px; font-weight:700; color:#0f766e;\">{price_value}</div>
                </div>
            """
            col_block.markdown(card_html, unsafe_allow_html=True)
    else:
        st.dataframe(price_df, use_container_width=True)

# Top-KPIs von der Sheet-Gesamtzeile übernehmen, wenn vorhanden
if df_totals is not None and not df_totals.empty:
    total_bottles = get_total_from_totals_row(df_totals, ["Anzahl Flaschen", "Getränke gesamt", "Geschätzer Verkauf"], fallback=df[qty_col] if qty_col in df.columns else None)
    total_revenue = get_total_from_totals_row(df_totals, ["Umsatz (Fall", "Umsatz je Flasche", "kalkulierter Umsatz", "Umsatz nach Kasse", "Umsatz"], fallback=df["Umsatz"] if "Umsatz" in df.columns else None)
    total_profit = get_total_from_totals_row(df_totals, ["Gewinn ([€])", "Gewinn je Getränk", "Gewinn je Flasche", "Gewinn"], fallback=df[profit_col] if profit_col in df.columns else None)
else:
    total_bottles = None
    total_revenue = None
    total_profit = None

selected_drinks = st.sidebar.multiselect(
    "Getränke auswählen:",
    options=df["Getränk"].tolist(),
    default=df["Getränk"].tolist()
)
if not selected_drinks:
    selected_drinks = df["Getränk"].tolist()

available_metrics = [col for col in df.columns if col != "Getränk"]
metric_defaults = [c for c in [profit_col, qty_col, sell_col, revenue_col, "Deckungsbeitrag"] if c in available_metrics]
selected_chart_metrics = st.sidebar.multiselect(
    "Metriken für das kombinierte Diagramm:",
    options=available_metrics,
    default=metric_defaults[:3] if metric_defaults else available_metrics[:3]
)
if len(selected_chart_metrics) < 3:
    for option in available_metrics:
        if option not in selected_chart_metrics:
            selected_chart_metrics.append(option)
        if len(selected_chart_metrics) >= 3:
            break
    st.sidebar.warning("Mindestens 3 Metriken erforderlich – es wurden automatisch zusätzliche Metriken ausgewählt.")

chart_type_options = ["Line", "Bar", "Area", "Scatter"]
axis_options = ["Primäre Achse", "Sekundäre Achse"]
chart_type_by_metric = {}
axis_by_metric = {}
with st.sidebar.expander("Diagrammoptionen pro Metrik", expanded=True):
    for idx, metric in enumerate(selected_chart_metrics):
        chart_type_by_metric[metric] = st.selectbox(
            f"Diagrammtyp für {metric}:",
            options=chart_type_options,
            index=0,
            key=f"chart_type_{idx}"
        )
        axis_by_metric[metric] = st.selectbox(
            f"Achse für {metric}:",
            options=axis_options,
            index=0,
            key=f"chart_axis_{idx}"
        )

selected_metrics = st.sidebar.multiselect(
    "Metriken anzeigen:",
    options=available_metrics,
    default=metric_defaults[:6] if metric_defaults else available_metrics[:6]
)
if not selected_metrics:
    selected_metrics = available_metrics[:6]

st.sidebar.markdown("---")
st.sidebar.markdown("**Zu allen Kennzahlen im Sheet:**")
for col in available_metrics:
    st.sidebar.write(f"- {col}")

st.sidebar.markdown("---")
st.sidebar.write("**Hinweis:** Die Spalte 'Spalte 1' wird als Einheit in den Spaltennamen dargestellt.")

# Filter

if selected_drinks:
    df_selected = df[df["Getränk"].isin(selected_drinks)].copy()
else:
    df_selected = df.copy()

st.markdown("### Filter für das kombinierte Diagramm")
selected_chart_drinks = st.multiselect(
    "Getränke für das kombinierte Diagramm:",
    options=df["Getränk"].tolist(),
    default=df_selected["Getränk"].tolist(),
    key="combined_chart_drinks"
)
if not selected_chart_drinks:
    selected_chart_drinks = df["Getränk"].tolist()

df_chart = df_selected[df_selected["Getränk"].isin(selected_chart_drinks)].copy()


# KPIs

total_bottles = df_selected[qty_col].sum() if qty_col and qty_col in df_selected.columns else None
total_revenue = df_selected[revenue_col].sum() if revenue_col and revenue_col in df_selected.columns else None
total_profit = df_selected[profit_col].sum() if profit_col and profit_col in df_selected.columns else None

st.markdown("### Top KPIs")
col1, col2, col3 = st.columns(3)
card_style = "border:1px solid #cbd5e1; border-radius:24px; background:#ffffff; padding:24px; text-align:center; box-shadow:0 16px 40px rgba(15, 23, 42, 0.12);"
value_style = "font-size:36px; font-weight:800; color:#0f766e; margin:0;"
label_style = "font-size:14px; font-weight:700; color:#334155; margin-bottom:10px; text-transform:uppercase; letter-spacing:0.08em;"

for col, label, value in [
    (col1, "Flaschen gesamt", f"{int(total_bottles):,}" if total_bottles is not None and not pd.isna(total_bottles) else "-"),
    (col2, "Umsatz (Fall: Komplettverkauf)", f"{total_revenue:,.2f} €" if total_revenue is not None and not pd.isna(total_revenue) else "-"),
    (col3, "Gewinn (Fall: Komplettverkauf)", f"{total_profit:,.2f} €" if total_profit is not None and not pd.isna(total_profit) else "-"),
]:
    col.markdown(f"<div style='{card_style}'><div style='{label_style}'>{label}</div><div style='{value_style}'>{value}</div></div>", unsafe_allow_html=True)

st.divider()

# Charts

chart_type_options = ["Line", "Bar", "Area", "Scatter"]
selected_chart_types = st.sidebar.multiselect("Diagrammtypen wählen:", chart_type_options, default=["Line"])
if not selected_chart_types:
    selected_chart_types = ["Line"]

chart_metric_options = [col for col in available_metrics if col != "Getränk"]
if not chart_metric_options:
    chart_metric_options = []

selected_chart_metric = st.sidebar.selectbox(
    "Hauptvariable für das Diagramm:",
    chart_metric_options,
    index=chart_metric_options.index(profit_col) if profit_col in chart_metric_options else 0
)

secondary_metric_candidates = [col for col in chart_metric_options if "gewinn/umsatz" in col.lower() or "verkaufspreis/einkaufspreis" in col.lower()]
secondary_metric_options = [None] + secondary_metric_candidates
selected_secondary_metric = st.sidebar.selectbox("Zweite Achse (optional):", secondary_metric_options, index=0)

st.sidebar.markdown("---")

chart_title = f"Kombiniertes Diagramm: {', '.join(selected_chart_metrics)}"
fig = make_subplots(specs=[[{"secondary_y": any(axis_by_metric[m] == "Sekundäre Achse" for m in selected_chart_metrics)}]])

for metric in selected_chart_metrics:
    if metric not in df_chart.columns:
        continue
    chart_type = chart_type_by_metric.get(metric, "Line")
    use_secondary = axis_by_metric.get(metric, "Primäre Achse") == "Sekundäre Achse"
    trace_name = f"{metric} ({chart_type})"
    x = df_chart["Getränk"]
    y = df_chart[metric]

    if chart_type == "Bar":
        trace = go.Bar(name=trace_name, x=x, y=y)
    elif chart_type == "Line":
        trace = go.Scatter(name=trace_name, x=x, y=y, mode="lines+markers")
    elif chart_type == "Area":
        trace = go.Scatter(name=trace_name, x=x, y=y, fill="tozeroy", mode="none")
    else:
        trace = go.Scatter(name=trace_name, x=x, y=y, mode="markers+lines")

    fig.add_trace(trace, secondary_y=use_secondary)

fig.update_layout(title=chart_title, legend_title_text="Metrik", xaxis_title="Getränk")
fig.update_yaxes(title_text="Primäre Achse", secondary_y=False)
if any(axis_by_metric[m] == "Sekundäre Achse" for m in selected_chart_metrics):
    fig.update_yaxes(title_text="Sekundäre Achse", secondary_y=True)

st.plotly_chart(fig, use_container_width=True)

# Zusätzliche Diagramme
profit_variants = [col for col in available_metrics if "gewinn" in col.lower() and col != selected_chart_metric]
if profit_variants:
    fig_profit_variants = px.bar(
        df_selected,
        x="Getränk",
        y=profit_variants,
        title="Gewinnarten pro Getränk",
        barmode="group"
    )
    st.plotly_chart(fig_profit_variants, use_container_width=True)

if cost_col and sell_col:
    fig_price = px.bar(
        df_selected,
        x="Getränk",
        y=[cost_col, sell_col],
        barmode="group",
        title="Einkaufspreis vs. Verkaufspreis",
        labels={"value": "Euro", "variable": "Preis"}
    )
    st.plotly_chart(fig_price, use_container_width=True)

if qty_col and qty_col in df_selected.columns:
    fig_qty = px.pie(
        df_selected,
        names="Getränk",
        values=qty_col,
        title="Verteilung der Flaschenanzahl",
        hole=0.3
    )
    st.plotly_chart(fig_qty, use_container_width=True)

st.subheader("Detailtabelle")

format_dict = {}
for col in selected_metrics:
    if "anzahl" in col.lower() or "gesamt" in col.lower() or "menge" in col.lower() or "flaschen" in col.lower():
        format_dict[col] = "{:.0f}"
    else:
        format_dict[col] = "{:.2f}"

try:
    display_df = df_selected[["Getränk"] + selected_metrics].set_index("Getränk")
    st.dataframe(display_df.style.format(format_dict))
except Exception:
    st.dataframe(df_selected.set_index("Getränk"))

if not df_totals.empty:
    with st.expander("Gesamtwerte aus dem Sheet"):
        st.dataframe(df_totals.set_index("Getränk").style.format({
            c: "{:.2f}" for c in df_totals.columns if c != "Getränk"
        }))

party_patterns = ["Restbestand", "kalkulierter Umsatz", "Kassenbestand", "Umsatz nach Kasse", "(monetär) Selbsttrinker", "Anteilig selbst getrunken"]
party_cols = [col for col in df.columns if any(pat.lower() in col.lower() for pat in party_patterns)]
if party_cols:
    with st.expander("Auswertung nach der Party"):
        try:
            party_df = df_selected[["Getränk"] + party_cols].set_index("Getränk")
            st.dataframe(party_df.style.format({col: "{:.2f}" for col in party_cols}))
        except Exception:
            st.dataframe(df_selected[["Getränk"] + party_cols])

        if not df_totals.empty:
            source_col = find_column(df_totals, ["kalkulierter Umsatz"])
            loss_col = find_column(df_totals, ["Selbsttrinker", "offene Flaschen"])
            cash_col = find_column(df_totals, ["Umsatz nach Kasse"])

            if source_col and loss_col and cash_col:
                source_value = df_totals.iloc[0][source_col]
                loss_value = df_totals.iloc[0][loss_col]
                cash_value = df_totals.iloc[0][cash_col]

                if pd.notna(source_value) and pd.notna(loss_value) and pd.notna(cash_value):
                    waterfall_fig = go.Figure(go.Waterfall(
                        name="Party-Kalkulation",
                        orientation="v",
                        measure=["absolute", "relative", "total"],
                        x=["Kalkulierter Umsatz", "Selbsttrinker & offene Flaschen", "Umsatz nach Kasse"],
                        y=[source_value, -abs(loss_value), cash_value],
                        text=[f"{source_value:,.2f} €", f"-{abs(loss_value):,.2f} €", f"{cash_value:,.2f} €"],
                        textposition="outside",
                        decreasing={"marker": {"color": "#d62728"}},
                        increasing={"marker": {"color": "#2ca02c"}},
                        totals={"marker": {"color": "#1f77b4"}}
                    ))
                    waterfall_fig.update_layout(
                        title="Wasserfall: Auswertung nach der Party",
                        yaxis_title="Euro (€)",
                        xaxis_title="Schritt"
                    )
                    st.plotly_chart(waterfall_fig, use_container_width=True)
