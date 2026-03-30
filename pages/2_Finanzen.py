import json
from datetime import date, datetime
from pathlib import Path

import gspread
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError


SPREADSHEET_ID = "1z6pVOSBNUcrWAdmgQfuqfNpvlwBYUkPmd58Xu29kj-U"
WORKSHEET_NAME = "Backend_Transaktionen"
NAME_ADD_OPTION = "Neuen Namen hinzufuegen..."
HOUSE_PAYER = "Das Haus"
PRIVATE_PAYER = "Privat vorgelegt"
STATUS_OPEN = "Offen"
STATUS_DONE = "Erledigt"
STATUS_PLANNED = "Geplant"
STATUS_PAID_BY_HOUSE = "Vom Haus bezahlt"
TRANSACTION_TYPES = [
    "Ausgabe/Einkauf",
    "Einzahlung auf das Haus",
    "Rueckerstattung vom Haus",
]
CATEGORY_OPTIONS = [
    "Getraenke",
    "Deko",
    "Musik/Technik",
    "Location",
    "Umlage/Einzahlung",
    "Sonstiges",
]
STANDARD_NAMES = [
    "Freddy",
    "Divin",
    "Chrissi",
    "Jan",
    "Leul",
    "Sohrab",
    "Aldar",
    "Lorena",
    "Anna K.",
    "Michelle",
    "Finn",
]
HEADER_ROW = [
    "ID",
    "Erfasst_Am",
    "Faellig_Am",
    "Bezahlt_Am",
    "Name",
    "Transaktions_Typ",
    "Betrag",
    "Kategorie",
    "Bezahlt_Von",
    "Beschreibung",
    "Status",
    "Referenz_ID",
]
SERVICE_ACCOUNT_CANDIDATES = [
    Path("service_account.json"),
    Path(".streamlit/service_account.json"),
    Path(".streamlit/secrets.toml.txt"),
    Path(r"C:\Users\leul.zewdie\Downloads\party-dashboard-491808-a0ddf9a20e45.json"),
]


def make_transaction_id() -> str:
    return datetime.now().strftime("TX-%Y%m%d-%H%M%S-%f")


def format_euro(value) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{value:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", ".")


def parse_amount(value):
    text = str(value).strip()
    if not text:
        return 0.0
    text = text.replace("EUR", "").replace("eur", "").replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


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

    raise FileNotFoundError(
        "Keine Google-Service-Account-Datei gefunden. "
        "Lege 'service_account.json' im Projekt ab oder nutze Streamlit-Secrets."
    )


@st.cache_resource
def get_worksheet():
    client = get_gspread_client()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    try:
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=WORKSHEET_NAME, rows=2000, cols=len(HEADER_ROW))

    ensure_header(worksheet)
    return worksheet


def ensure_header(worksheet):
    current_header = worksheet.row_values(1)
    if current_header[: len(HEADER_ROW)] != HEADER_ROW:
        worksheet.update("A1:L1", [HEADER_ROW])


@st.cache_data(ttl=30)
def load_transactions():
    worksheet = get_worksheet()
    rows = worksheet.get_all_values()
    if len(rows) <= 1:
        return pd.DataFrame(columns=HEADER_ROW + ["_sheet_row"])

    data_rows = []
    for row_index, row in enumerate(rows[1:], start=2):
        padded = row[: len(HEADER_ROW)] + [""] * (len(HEADER_ROW) - len(row))
        if not any(str(cell).strip() for cell in padded):
            continue
        record = dict(zip(HEADER_ROW, padded))
        record["_sheet_row"] = row_index
        data_rows.append(record)

    if not data_rows:
        return pd.DataFrame(columns=HEADER_ROW + ["_sheet_row"])

    df = pd.DataFrame(data_rows)
    df["Betrag"] = df["Betrag"].apply(parse_amount)
    for col in ["Erfasst_Am", "Faellig_Am", "Bezahlt_Am"]:
        df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
    return df


def append_transaction(record):
    worksheet = get_worksheet()
    worksheet.append_row([record.get(column, "") for column in HEADER_ROW], value_input_option="USER_ENTERED")
    load_transactions.clear()


def mark_planned_as_paid(sheet_row: int, payment_date: date):
    worksheet = get_worksheet()
    col_index = {column: idx + 1 for idx, column in enumerate(HEADER_ROW)}
    worksheet.update_cell(sheet_row, col_index["Bezahlt_Am"], payment_date.strftime("%d.%m.%Y"))
    worksheet.update_cell(sheet_row, col_index["Bezahlt_Von"], HOUSE_PAYER)
    worksheet.update_cell(sheet_row, col_index["Status"], STATUS_PAID_BY_HOUSE)
    load_transactions.clear()


def resolve_name(name_choice: str, new_name: str) -> str:
    if name_choice == NAME_ADD_OPTION:
        return new_name.strip()
    return name_choice.strip()


def build_name_options(df: pd.DataFrame):
    known_names = [name for name in df.get("Name", pd.Series(dtype=str)).dropna().astype(str).tolist() if name.strip()]
    ordered_names = []
    for name in STANDARD_NAMES + sorted(set(known_names)):
        if name not in ordered_names:
            ordered_names.append(name)
    ordered_names.append(NAME_ADD_OPTION)
    return ordered_names


def build_person_summary(df: pd.DataFrame) -> pd.DataFrame:
    people_df = df[df["Name"].astype(str).str.strip() != ""].copy()
    if people_df.empty:
        return pd.DataFrame(
            columns=[
                "Name",
                "Einzahlungen",
                "Privat_vorgelegt",
                "Rueckerstattungen",
                "Guthaben_im_Haus",
                "Offene_Auslagen",
                "Gesamtanspruch_gegen_Haus",
                "Geplante_Ausgaben",
            ]
        )

    income = (
        people_df[people_df["Transaktions_Typ"] == "Einzahlung auf das Haus"]
        .groupby("Name")["Betrag"]
        .sum()
    )
    private_spend = (
        people_df[
            (people_df["Transaktions_Typ"] == "Ausgabe/Einkauf")
            & (people_df["Bezahlt_Von"] == PRIVATE_PAYER)
        ]
        .groupby("Name")["Betrag"]
        .sum()
    )
    refunds = (
        people_df[people_df["Transaktions_Typ"] == "Rueckerstattung vom Haus"]
        .groupby("Name")["Betrag"]
        .sum()
    )
    planned = (
        people_df[
            (people_df["Transaktions_Typ"] == "Geplante Ausgabe")
            & (people_df["Status"] == STATUS_PLANNED)
        ]
        .groupby("Name")["Betrag"]
        .sum()
    )

    summary = pd.DataFrame(index=sorted(people_df["Name"].dropna().unique()))
    summary["Einzahlungen"] = income
    summary["Privat_vorgelegt"] = private_spend
    summary["Rueckerstattungen"] = refunds
    summary["Geplante_Ausgaben"] = planned
    summary = summary.fillna(0.0)
    summary["Guthaben_im_Haus"] = summary["Einzahlungen"]
    summary["Offene_Auslagen"] = summary["Privat_vorgelegt"] - summary["Rueckerstattungen"]
    summary["Offene_Auslagen"] = summary["Offene_Auslagen"].clip(lower=0.0)
    summary["Gesamtanspruch_gegen_Haus"] = summary["Guthaben_im_Haus"] + summary["Offene_Auslagen"]
    summary = summary.reset_index().rename(columns={"index": "Name"})
    return summary.sort_values(["Gesamtanspruch_gegen_Haus", "Privat_vorgelegt"], ascending=[False, False])


st.set_page_config(page_title="Treppenhausparty - Finanzen", page_icon="EUR", layout="wide")
st.title("Treppenhausparty - Finanzuebersicht")
st.caption("Einzahlungen, Ausgaben, offene Erstattungen und geplante Kosten an einem Ort.")

transactions_df = load_transactions()
name_options = build_name_options(transactions_df)

entry_tab, planned_tab, overview_tab = st.tabs(
    ["Transaktion eintragen", "Geplante Ausgaben", "Uebersicht"]
)

with entry_tab:
    st.subheader("Neue Transaktion")
    with st.form("transaktion_form", clear_on_submit=True):
        transaktions_typ = st.selectbox("Was moechtest du eintragen?", TRANSACTION_TYPES)
        name_auswahl = st.selectbox("Wer traegt es ein / um wen geht es?", name_options)
        st.caption("Falls 'Neuen Namen hinzufuegen...' gewaehlt wurde:")
        neuer_name = st.text_input("Neuer Name")

        col1, col2 = st.columns(2)
        with col1:
            betrag = st.number_input("Betrag in EUR", min_value=0.0, step=0.5, format="%.2f")
        with col2:
            kategorie = st.selectbox("Kategorie", CATEGORY_OPTIONS)

        bezahlt_von = st.radio(
            "Wer hat gezahlt?",
            [HOUSE_PAYER, PRIVATE_PAYER],
            horizontal=True,
        )
        beschreibung = st.text_area("Beschreibung", placeholder="z.B. Becher, Kabel, Deko")
        submitted = st.form_submit_button("Transaktion speichern")

    if submitted:
        final_name = resolve_name(name_auswahl, neuer_name)

        if not final_name:
            st.error("Bitte waehle einen Namen aus oder trage einen neuen Namen ein.")
        elif betrag <= 0:
            st.error("Bitte gib einen Betrag groesser als 0 ein.")
        else:
            status = STATUS_DONE
            paid_by = bezahlt_von
            paid_at = date.today().strftime("%d.%m.%Y")

            if transaktions_typ == "Ausgabe/Einkauf" and bezahlt_von == PRIVATE_PAYER:
                status = STATUS_OPEN
            elif transaktions_typ == "Einzahlung auf das Haus":
                paid_by = final_name
            elif transaktions_typ == "Rueckerstattung vom Haus":
                paid_by = HOUSE_PAYER

            record = {
                "ID": make_transaction_id(),
                "Erfasst_Am": date.today().strftime("%d.%m.%Y"),
                "Faellig_Am": "",
                "Bezahlt_Am": paid_at,
                "Name": final_name,
                "Transaktions_Typ": transaktions_typ,
                "Betrag": float(betrag),
                "Kategorie": kategorie,
                "Bezahlt_Von": paid_by,
                "Beschreibung": beschreibung,
                "Status": status,
                "Referenz_ID": "",
            }
            append_transaction(record)
            st.success(f"{format_euro(betrag)} fuer {final_name} wurde gespeichert.")
            st.rerun()

with planned_tab:
    st.subheader("Zukuenftige Ausgaben erfassen")
    st.caption("Geplante Kosten bleiben sichtbar, bis sie spaeter vom Haus bezahlt werden.")

    with st.form("planned_expense_form", clear_on_submit=True):
        planned_name = st.selectbox("Wer meldet die geplante Ausgabe?", name_options, key="planned_name")
        st.caption("Falls 'Neuen Namen hinzufuegen...' gewaehlt wurde:")
        planned_new_name = st.text_input("Neuer Name fuer geplante Ausgabe")

        col1, col2, col3 = st.columns(3)
        with col1:
            planned_amount = st.number_input(
                "Geplanter Betrag in EUR",
                min_value=0.0,
                step=0.5,
                format="%.2f",
                key="planned_amount",
            )
        with col2:
            planned_category = st.selectbox("Kategorie", CATEGORY_OPTIONS, key="planned_category")
        with col3:
            due_date = st.date_input("Faellig am", value=date.today(), key="planned_due_date")

        planned_description = st.text_area(
            "Beschreibung der geplanten Ausgabe",
            placeholder="z.B. Restgetraenke, Leihtechnik, Reinigung",
            key="planned_description",
        )
        planned_submit = st.form_submit_button("Geplante Ausgabe speichern")

    if planned_submit:
        final_name = resolve_name(planned_name, planned_new_name)

        if not final_name:
            st.error("Bitte waehle einen Namen aus oder trage einen neuen Namen ein.")
        elif planned_amount <= 0:
            st.error("Bitte gib einen Betrag groesser als 0 ein.")
        else:
            record = {
                "ID": make_transaction_id(),
                "Erfasst_Am": date.today().strftime("%d.%m.%Y"),
                "Faellig_Am": due_date.strftime("%d.%m.%Y"),
                "Bezahlt_Am": "",
                "Name": final_name,
                "Transaktions_Typ": "Geplante Ausgabe",
                "Betrag": float(planned_amount),
                "Kategorie": planned_category,
                "Bezahlt_Von": "",
                "Beschreibung": planned_description,
                "Status": STATUS_PLANNED,
                "Referenz_ID": "",
            }
            append_transaction(record)
            st.success(f"Geplante Ausgabe ueber {format_euro(planned_amount)} wurde gespeichert.")
            st.rerun()

    planned_open_df = transactions_df[
        (transactions_df["Transaktions_Typ"] == "Geplante Ausgabe")
        & (transactions_df["Status"] == STATUS_PLANNED)
    ].copy()

    if planned_open_df.empty:
        st.info("Aktuell gibt es keine offenen geplanten Ausgaben.")
    else:
        planned_display = planned_open_df[
            ["Name", "Faellig_Am", "Kategorie", "Beschreibung", "Betrag"]
        ].copy()
        planned_display["Faellig_Am"] = planned_display["Faellig_Am"].dt.strftime("%d.%m.%Y").fillna("-")
        planned_display["Betrag"] = planned_display["Betrag"].map(format_euro)
        st.dataframe(planned_display, use_container_width=True, hide_index=True)

        selection_labels = {
            row["_sheet_row"]: (
                f"{row['Name']} | {format_euro(row['Betrag'])} | "
                f"{row['Beschreibung'] or row['Kategorie']} | "
                f"faellig {row['Faellig_Am'].strftime('%d.%m.%Y') if pd.notna(row['Faellig_Am']) else '-'}"
            )
            for _, row in planned_open_df.iterrows()
        }
        selected_rows = st.multiselect(
            "Welche geplanten Ausgaben wurden inzwischen vom Haus bezahlt?",
            options=list(selection_labels.keys()),
            format_func=lambda row_id: selection_labels[row_id],
        )
        payment_date = st.date_input("Bezahlt am", value=date.today(), key="planned_payment_date")
        if st.button("Ausgewaehlte Ausgaben als bezahlt markieren", type="primary"):
            if not selected_rows:
                st.warning("Bitte waehle mindestens eine geplante Ausgabe aus.")
            else:
                for sheet_row in selected_rows:
                    mark_planned_as_paid(sheet_row, payment_date)
                st.success("Die ausgewaehlten geplanten Ausgaben wurden als vom Haus bezahlt markiert.")
                st.rerun()

with overview_tab:
    st.subheader("Transparente Uebersicht")

    house_income = transactions_df.loc[
        transactions_df["Transaktions_Typ"] == "Einzahlung auf das Haus", "Betrag"
    ].sum()
    house_direct_spend = transactions_df.loc[
        (
            (transactions_df["Transaktions_Typ"] == "Ausgabe/Einkauf")
            & (transactions_df["Bezahlt_Von"] == HOUSE_PAYER)
        )
        | (
            (transactions_df["Transaktions_Typ"] == "Geplante Ausgabe")
            & (transactions_df["Status"] == STATUS_PAID_BY_HOUSE)
        ),
        "Betrag",
    ].sum()
    reimbursements_paid = transactions_df.loc[
        transactions_df["Transaktions_Typ"] == "Rueckerstattung vom Haus", "Betrag"
    ].sum()
    house_total_paid = house_direct_spend + reimbursements_paid
    planned_total = transactions_df.loc[
        (transactions_df["Transaktions_Typ"] == "Geplante Ausgabe")
        & (transactions_df["Status"] == STATUS_PLANNED),
        "Betrag",
    ].sum()

    person_summary = build_person_summary(transactions_df)
    open_to_people = person_summary["Gesamtanspruch_gegen_Haus"].sum() if not person_summary.empty else 0.0
    house_balance_now = house_income - house_total_paid
    house_balance_after_obligations = house_balance_now - open_to_people - planned_total

    metric_cols = st.columns(5)
    metric_cols[0].metric("Im Haus eingezahlt", format_euro(house_income))
    metric_cols[1].metric("Vom Haus bezahlt", format_euro(house_total_paid))
    metric_cols[2].metric("Gesamtanspruch gegen Haus", format_euro(open_to_people))
    metric_cols[3].metric("Geplante Kosten offen", format_euro(planned_total))
    metric_cols[4].metric("Hausbestand nach allem", format_euro(house_balance_after_obligations))

    st.markdown("### Wasserfalldiagramm")
    waterfall_fig = go.Figure(
        go.Waterfall(
            name="Hauskonto",
            orientation="v",
            measure=["absolute", "relative", "relative", "relative", "total"],
            x=[
                "Einzahlungen",
                "Vom Haus bezahlt",
                "Ansprueche gegen Haus",
                "Geplante Kosten",
                "Verbleibender Hausbestand",
            ],
            y=[
                house_income,
                -house_total_paid,
                -open_to_people,
                -planned_total,
                house_balance_after_obligations,
            ],
            text=[
                format_euro(house_income),
                format_euro(-house_total_paid),
                format_euro(-open_to_people),
                format_euro(-planned_total),
                format_euro(house_balance_after_obligations),
            ],
            textposition="outside",
            increasing={"marker": {"color": "#15803d"}},
            decreasing={"marker": {"color": "#b91c1c"}},
            totals={"marker": {"color": "#1d4ed8"}},
            connector={"line": {"color": "#94a3b8"}},
        )
    )
    waterfall_fig.update_layout(
        height=460,
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
        yaxis_title="EUR",
        showlegend=False,
    )
    st.plotly_chart(waterfall_fig, use_container_width=True)

    st.markdown("### Personensalden")
    if person_summary.empty:
        st.info("Noch keine Personendaten vorhanden.")
    else:
        display_person_summary = person_summary.copy()
        for column in [
            "Einzahlungen",
            "Privat_vorgelegt",
            "Rueckerstattungen",
            "Guthaben_im_Haus",
            "Offene_Auslagen",
            "Gesamtanspruch_gegen_Haus",
            "Geplante_Ausgaben",
        ]:
            display_person_summary[column] = display_person_summary[column].map(format_euro)
        st.dataframe(display_person_summary, use_container_width=True, hide_index=True)

    st.markdown("### Privat vorgelegte Ausgaben")
    st.caption("Die offene Gesamtschuld gegenueber Personen siehst du oben in der Personentabelle.")
    open_private_df = transactions_df[
        (transactions_df["Transaktions_Typ"] == "Ausgabe/Einkauf")
        & (transactions_df["Bezahlt_Von"] == PRIVATE_PAYER)
    ].copy()
    if open_private_df.empty:
        st.info("Aktuell gibt es keine privat vorgelegten Ausgaben.")
    else:
        open_private_df["Erfasst_Am"] = open_private_df["Erfasst_Am"].dt.strftime("%d.%m.%Y").fillna("-")
        open_private_df["Betrag"] = open_private_df["Betrag"].map(format_euro)
        st.dataframe(
            open_private_df[
                ["Erfasst_Am", "Name", "Kategorie", "Beschreibung", "Betrag", "Status"]
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("### Ausgaben des Hauses")
    house_spend_df = transactions_df[
        (
            (transactions_df["Transaktions_Typ"] == "Ausgabe/Einkauf")
            & (transactions_df["Bezahlt_Von"] == HOUSE_PAYER)
        )
        | (transactions_df["Transaktions_Typ"] == "Rueckerstattung vom Haus")
        | (
            (transactions_df["Transaktions_Typ"] == "Geplante Ausgabe")
            & (transactions_df["Status"] == STATUS_PAID_BY_HOUSE)
        )
    ].copy()
    if house_spend_df.empty:
        st.info("Bisher wurden noch keine Hausausgaben verbucht.")
    else:
        house_spend_df["Betrag"] = house_spend_df["Betrag"].map(format_euro)
        house_spend_df["Erfasst_Am"] = house_spend_df["Erfasst_Am"].dt.strftime("%d.%m.%Y").fillna("-")
        house_spend_df["Bezahlt_Am"] = house_spend_df["Bezahlt_Am"].dt.strftime("%d.%m.%Y").fillna("-")
        st.dataframe(
            house_spend_df[
                [
                    "Erfasst_Am",
                    "Bezahlt_Am",
                    "Name",
                    "Transaktions_Typ",
                    "Kategorie",
                    "Beschreibung",
                    "Betrag",
                    "Status",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("### Komplettes Transaktionsprotokoll")
    if transactions_df.empty:
        st.info("Noch keine Transaktionen vorhanden.")
    else:
        ledger_df = transactions_df.copy()
        for date_col in ["Erfasst_Am", "Faellig_Am", "Bezahlt_Am"]:
            ledger_df[date_col] = ledger_df[date_col].dt.strftime("%d.%m.%Y").fillna("-")
        ledger_df["Betrag"] = ledger_df["Betrag"].map(format_euro)
        st.dataframe(
            ledger_df[
                [
                    "Erfasst_Am",
                    "Faellig_Am",
                    "Bezahlt_Am",
                    "Name",
                    "Transaktions_Typ",
                    "Kategorie",
                    "Bezahlt_Von",
                    "Beschreibung",
                    "Betrag",
                    "Status",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )
