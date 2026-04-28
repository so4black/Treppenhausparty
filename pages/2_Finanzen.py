import json
import math
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
PLANNED_EXPENSE_TYPE = "Geplante Ausgabe"
TRANSACTION_TYPES = [
    "Ausgabe/Einkauf",
    "Einzahlung auf das Haus",
    "Rueckerstattung vom Haus",
    "Einnahmen (Party)",
    "Verrechnung (Warenübernahme)",
]
CATEGORY_OPTIONS = [
    "Getraenke",
    "Deko",
    "Musik/Technik",
    "Location",
    "Umlage/Einzahlung",
    "Einnahmen",
    "Sonstiges",
]
GETRAENKE_ZAHLUNGSART = ["Vorkasse", "Auf Kommission"]
MUSIK_ZAHLUNGSTYP = ["Normaler Betrag", "Kaution", "Kaution + Betrag"]
STANDARD_NAMES = [
    HOUSE_PAYER,
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
HOUSE_NAME_ALIASES = {
    HOUSE_PAYER,
    "Altes Polizeipraesidium (Kassenstand Anfang)",
    "Altes Polizeipräsidum (Kassenstand Anfang)",
    "Altes Polizeipräsidium (Kassenstand Anfang)",
}
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
    "Kostenbezeichnung",
    "Anzahl",
    "Einheit",
    "Ist_Investition",
    "Status",
    "Referenz_ID",
    "Getraenk_Name",
    "Getraenk_Anzahl",
    "Getraenk_Preis_Stueck",
    "Getraenk_Zahlungsart",
    "Musik_Zahlungstyp",
    "Kaution_Betrag",
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


def parse_quantity(value):
    text = str(value).strip()
    if not text:
        return 0.0
    text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def parse_bool(value) -> bool:
    return str(value).strip().lower() in {"1", "true", "ja", "yes", "y"}


def format_quantity(value) -> str:
    if value is None or pd.isna(value) or float(value) == 0:
        return "-"
    value = float(value)
    if value.is_integer():
        return str(int(value))
    return f"{value:.2f}".replace(".", ",")


def build_cost_label(row: pd.Series) -> str:
    for column in ["Kostenbezeichnung", "Getraenk_Name", "Beschreibung"]:
        value = str(row.get(column, "")).strip()
        if value:
            return value
    return "Ohne Bezeichnung"


def format_date_value(value) -> str:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return ""
    if isinstance(value, pd.Timestamp):
        return value.strftime("%d.%m.%Y")
    return str(value)


def to_sheet_value(value):
    if value is None:
        return ""
    if isinstance(value, pd.Timestamp):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, (datetime, date)):
        return value.strftime("%d.%m.%Y")
    if pd.isna(value):
        return ""
    if isinstance(value, bool):
        return "Ja" if value else ""
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return ""
        return value
    return value


def column_index_to_letter(index: int) -> str:
    letters = []
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters.append(chr(65 + remainder))
    return "".join(reversed(letters))


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
        col_letter = column_index_to_letter(len(HEADER_ROW))
        worksheet.update(f"A1:{col_letter}1", [HEADER_ROW])


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
    for col in ["Anzahl", "Getraenk_Anzahl"]:
        if col in df.columns:
            df[col] = df[col].apply(parse_quantity)
    if "Ist_Investition" in df.columns:
        df["Ist_Investition"] = df["Ist_Investition"].apply(parse_bool)
    else:
        df["Ist_Investition"] = False
    for col in ["Erfasst_Am", "Faellig_Am", "Bezahlt_Am"]:
        df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
    if "Kostenbezeichnung" not in df.columns:
        df["Kostenbezeichnung"] = ""
    if "Anzahl" not in df.columns:
        df["Anzahl"] = 0.0
    if "Einheit" not in df.columns:
        df["Einheit"] = ""
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


def update_transaction(sheet_row: int, record: dict):
    worksheet = get_worksheet()
    current_values = worksheet.row_values(sheet_row)
    padded_values = current_values[: len(HEADER_ROW)] + [""] * (len(HEADER_ROW) - len(current_values))
    row_record = dict(zip(HEADER_ROW, padded_values))
    for field, value in record.items():
        if field in row_record:
            row_record[field] = to_sheet_value(value)
    row_values = [row_record.get(column, "") for column in HEADER_ROW]
    end_col = column_index_to_letter(len(HEADER_ROW))
    worksheet.update(
        f"A{sheet_row}:{end_col}{sheet_row}",
        [row_values],
        value_input_option="USER_ENTERED",
    )
    load_transactions.clear()


def delete_transaction(sheet_row: int):
    worksheet = get_worksheet()
    worksheet.delete_rows(sheet_row)
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
    people_df = people_df[~people_df["Name"].astype(str).isin(HOUSE_NAME_ALIASES)]
    if people_df.empty:
        return pd.DataFrame(
            columns=[
                "Name",
                "Einzahlungen",
                "Privat_vorgelegt_Party",
                "Privat_vorgelegt_Investition",
                "Privat_vorgelegt_Gesamt",
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
    private_party_spend = (
        people_df[
            (people_df["Transaktions_Typ"] == "Ausgabe/Einkauf")
            & (people_df["Bezahlt_Von"] == PRIVATE_PAYER)
            & (~people_df["Ist_Investition"].fillna(False))
        ]
        .groupby("Name")["Betrag"]
        .sum()
    )
    private_investment_spend = (
        people_df[
            (people_df["Transaktions_Typ"] == "Ausgabe/Einkauf")
            & (people_df["Bezahlt_Von"] == PRIVATE_PAYER)
            & (people_df["Ist_Investition"].fillna(False))
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
    summary["Privat_vorgelegt_Party"] = private_party_spend
    summary["Privat_vorgelegt_Investition"] = private_investment_spend
    summary["Rueckerstattungen"] = refunds
    summary["Geplante_Ausgaben"] = planned
    summary = summary.fillna(0.0)
    summary["Privat_vorgelegt_Gesamt"] = (
        summary["Privat_vorgelegt_Party"] + summary["Privat_vorgelegt_Investition"]
    )
    # Erstattungen decken zuerst offene Auslagen, dann die Einzahlung (Guthaben)
    raw_auslagen = summary["Privat_vorgelegt_Gesamt"] - summary["Rueckerstattungen"]
    summary["Offene_Auslagen"] = raw_auslagen.clip(lower=0.0)
    # Überschuss-Erstattungen (mehr erstattet als vorgelegt) mindern das Guthaben
    ueberschuss_erstattung = (-raw_auslagen).clip(lower=0.0)
    summary["Guthaben_im_Haus"] = (summary["Einzahlungen"] - ueberschuss_erstattung).clip(lower=0.0)
    summary["Gesamtanspruch_gegen_Haus"] = summary["Guthaben_im_Haus"] + summary["Offene_Auslagen"]
    summary = summary.reset_index().rename(columns={"index": "Name"})
    return summary.sort_values(["Gesamtanspruch_gegen_Haus", "Privat_vorgelegt_Gesamt"], ascending=[False, False])


def party_expense_mask(df: pd.DataFrame) -> pd.Series:
    is_party_spend = (
        (df["Transaktions_Typ"] == "Ausgabe/Einkauf")
        | (
            (df["Transaktions_Typ"] == "Geplante Ausgabe")
            & (df["Status"] == STATUS_PAID_BY_HOUSE)
        )
    )
    return is_party_spend & (~df["Ist_Investition"].fillna(False))


def planned_party_mask(df: pd.DataFrame) -> pd.Series:
    is_planned_party = (
        (df["Transaktions_Typ"] == "Geplante Ausgabe")
        & (df["Status"] == STATUS_PLANNED)
    )
    return is_planned_party & (~df["Ist_Investition"].fillna(False))


def investment_expense_mask(df: pd.DataFrame) -> pd.Series:
    is_investment_spend = (
        (df["Transaktions_Typ"] == "Ausgabe/Einkauf")
        | (
            (df["Transaktions_Typ"] == PLANNED_EXPENSE_TYPE)
            & (df["Status"] == STATUS_PAID_BY_HOUSE)
        )
    )
    return is_investment_spend & (df["Ist_Investition"].fillna(False))


def initial_house_funding_mask(df: pd.DataFrame) -> pd.Series:
    return (
        (df["Transaktions_Typ"] == "Einzahlung auf das Haus")
        & (df["Name"].astype(str).isin(HOUSE_NAME_ALIASES))
    )


st.set_page_config(page_title="Treppenhausparty - Finanzen", page_icon="EUR", layout="wide")
st.title("Treppenhausparty - Finanzuebersicht")
st.caption("Einzahlungen, Ausgaben, offene Erstattungen und geplante Kosten an einem Ort.")

transactions_df = load_transactions()
name_options = build_name_options(transactions_df)

entry_tab, edit_tab, overview_tab = st.tabs(
    ["Eintragen", "Bearbeiten / Löschen", "Übersicht"]
)

# ---------------------------------------------------------------------------
# EINTRAGEN-TAB
# ---------------------------------------------------------------------------
with entry_tab:
    st.subheader("Neue Transaktion")

    # Typ-Auswahl außerhalb des Forms (steuert sichtbare Felder)
    ENTRY_TYPES = {
        "Ausgabe": "Ausgabe/Einkauf",
        "Einzahlung": "Einzahlung auf das Haus",
        "Erstattung": "Rueckerstattung vom Haus",
        "Einnahme (Party)": "Einnahmen (Party)",
        "Verrechnung": "Verrechnung (Warenübernahme)",
    }
    entry_type_label = st.radio(
        "Was möchtest du eintragen?",
        list(ENTRY_TYPES.keys()),
        horizontal=True,
        key="entry_type_label",
    )
    entry_type = ENTRY_TYPES[entry_type_label]

    # Kategorie nur für Ausgaben & Verrechnung sinnvoll
    needs_category = entry_type_label in ("Ausgabe", "Verrechnung")
    needs_person = entry_type_label != "Einnahme (Party)"  # Einnahme → immer "Das Haus"

    if needs_category:
        entry_kategorie = st.selectbox("Kategorie", CATEGORY_OPTIONS, key="entry_kategorie")
    else:
        entry_kategorie = "Sonstiges"

    with st.form("transaktion_form", clear_on_submit=True):

        # Person
        if needs_person:
            name_col, new_col = st.columns([2, 1])
            with name_col:
                name_auswahl = st.selectbox("Person", name_options)
            with new_col:
                neuer_name = st.text_input("Neuer Name (falls oben letzte Option)")
        else:
            name_auswahl = HOUSE_PAYER
            neuer_name = ""

        # Betrag & Bezeichnung
        bez_col, amt_col = st.columns([2, 1])
        with bez_col:
            kostenbezeichnung = st.text_input(
                "Bezeichnung",
                placeholder="z.B. Bier, Kabelbinder, Kuehlschrank",
            )
        with amt_col:
            betrag = st.number_input("Betrag in EUR", min_value=0.0, step=0.5, format="%.2f")

        # Menge (nur bei Ausgabe)
        if entry_type_label == "Ausgabe":
            mq1, mq2, mq3, mq4 = st.columns([1, 1, 1, 1.2])
            with mq1:
                anzahl = st.number_input("Anzahl", min_value=0.0, step=1.0, format="%.2f")
            with mq2:
                einheit = st.text_input("Einheit", placeholder="z.B. Stk., Kisten")
            with mq3:
                ist_geplant = st.checkbox("Geplant (noch nicht bezahlt)", help="Trägt die Ausgabe als geplante Kosten ein.")
            with mq4:
                ist_investition = st.checkbox("Investition", help="Investitionen tauchen nicht als Partykosten auf.")
            if ist_geplant:
                due_date = st.date_input("Fällig am", value=date.today())
            else:
                due_date = None
        else:
            anzahl = 0.0
            einheit = ""
            ist_geplant = False
            ist_investition = False
            due_date = None

        # Wer hat gezahlt? (nur bei Ausgabe relevant)
        if entry_type_label == "Ausgabe":
            bezahlt_von = st.radio("Wer hat gezahlt?", [HOUSE_PAYER, PRIVATE_PAYER], horizontal=True)
        else:
            bezahlt_von = HOUSE_PAYER

        # Getränke-Details
        getraenk_name = ""
        getraenk_anzahl = 0
        getraenk_preis_stueck = 0.0
        getraenk_zahlungsart = ""
        musik_zahlungstyp = ""
        kaution_betrag = 0.0

        if needs_category and entry_kategorie == "Getraenke":
            st.markdown("**Getränke-Details**")
            gcol1, gcol2, gcol3 = st.columns(3)
            with gcol1:
                getraenk_name = st.text_input("Getränk", placeholder="z.B. Bier, Mate")
            with gcol2:
                getraenk_anzahl = st.number_input("Anzahl (Fl./Kästen)", min_value=0, step=1)
            with gcol3:
                getraenk_preis_stueck = st.number_input("Preis/Stück EUR", min_value=0.0, step=0.05, format="%.2f")
            getraenk_zahlungsart = st.selectbox("Zahlungsart", GETRAENKE_ZAHLUNGSART)

        elif needs_category and entry_kategorie == "Musik/Technik":
            st.markdown("**Musik/Technik-Details**")
            musik_zahlungstyp = st.selectbox("Art der Zahlung", MUSIK_ZAHLUNGSTYP)
            if musik_zahlungstyp in ("Kaution", "Kaution + Betrag"):
                kaution_betrag = st.number_input("Kautionsbetrag EUR", min_value=0.0, step=10.0, format="%.2f")

        beschreibung = st.text_area("Beschreibung / Notiz", placeholder="z.B. Becher, Kabel, Deko")
        submitted = st.form_submit_button("💾 Speichern", type="primary")

    if submitted:
        final_name = resolve_name(name_auswahl, neuer_name) if needs_person else HOUSE_PAYER

        # Betrag auto-berechnen aus Getränke-Details
        final_betrag = float(betrag)
        if entry_kategorie == "Getraenke" and getraenk_anzahl > 0 and getraenk_preis_stueck > 0 and betrag == 0:
            final_betrag = getraenk_anzahl * getraenk_preis_stueck

        if not final_name:
            st.error("Bitte wähle eine Person aus oder trage einen neuen Namen ein.")
        elif final_betrag <= 0 and not (entry_kategorie == "Musik/Technik" and kaution_betrag > 0):
            st.error("Bitte gib einen Betrag größer als 0 ein.")
        elif entry_type == "Verrechnung (Warenübernahme)":
            tx_id = make_transaction_id()
            paid_at = date.today().strftime("%d.%m.%Y")
            base = {
                "Erfasst_Am": paid_at, "Faellig_Am": "", "Bezahlt_Am": paid_at,
                "Betrag": final_betrag, "Kategorie": entry_kategorie,
                "Beschreibung": beschreibung, "Kostenbezeichnung": kostenbezeichnung,
                "Anzahl": anzahl, "Einheit": einheit, "Ist_Investition": "",
                "Status": STATUS_DONE,
                "Getraenk_Name": getraenk_name,
                "Getraenk_Anzahl": getraenk_anzahl if entry_kategorie == "Getraenke" else "",
                "Getraenk_Preis_Stueck": getraenk_preis_stueck if entry_kategorie == "Getraenke" else "",
                "Getraenk_Zahlungsart": getraenk_zahlungsart if entry_kategorie == "Getraenke" else "",
                "Musik_Zahlungstyp": "", "Kaution_Betrag": "",
            }
            append_transaction({**base, "ID": tx_id, "Name": HOUSE_PAYER, "Transaktions_Typ": "Einnahmen (Party)", "Bezahlt_Von": HOUSE_PAYER, "Referenz_ID": tx_id})
            append_transaction({**base, "ID": make_transaction_id(), "Name": final_name, "Transaktions_Typ": "Rueckerstattung vom Haus", "Bezahlt_Von": HOUSE_PAYER, "Referenz_ID": tx_id})
            st.success(f"Verrechnung über {format_euro(final_betrag)} für {final_name} gespeichert.")
            st.rerun()
        else:
            paid_at = date.today().strftime("%d.%m.%Y")
            if ist_geplant:
                tx_typ = PLANNED_EXPENSE_TYPE
                status = STATUS_PLANNED
                paid_by = ""
                paid_at_val = ""
                faellig = due_date.strftime("%d.%m.%Y") if due_date else ""
            else:
                tx_typ = entry_type
                faellig = ""
                paid_at_val = paid_at
                if entry_type == "Ausgabe/Einkauf" and bezahlt_von == PRIVATE_PAYER:
                    status = STATUS_OPEN
                    paid_by = PRIVATE_PAYER
                elif entry_type == "Einzahlung auf das Haus":
                    status = STATUS_DONE
                    paid_by = final_name
                else:
                    status = STATUS_DONE
                    paid_by = HOUSE_PAYER

            record = {
                "ID": make_transaction_id(),
                "Erfasst_Am": paid_at,
                "Faellig_Am": faellig,
                "Bezahlt_Am": paid_at_val,
                "Name": final_name,
                "Transaktions_Typ": tx_typ,
                "Betrag": final_betrag,
                "Kategorie": entry_kategorie,
                "Bezahlt_Von": paid_by,
                "Beschreibung": beschreibung,
                "Kostenbezeichnung": kostenbezeichnung,
                "Anzahl": anzahl,
                "Einheit": einheit,
                "Ist_Investition": "Ja" if ist_investition else "",
                "Status": status,
                "Referenz_ID": "",
                "Getraenk_Name": getraenk_name,
                "Getraenk_Anzahl": getraenk_anzahl if entry_kategorie == "Getraenke" else "",
                "Getraenk_Preis_Stueck": getraenk_preis_stueck if entry_kategorie == "Getraenke" else "",
                "Getraenk_Zahlungsart": getraenk_zahlungsart if entry_kategorie == "Getraenke" else "",
                "Musik_Zahlungstyp": musik_zahlungstyp if entry_kategorie == "Musik/Technik" else "",
                "Kaution_Betrag": kaution_betrag if entry_kategorie == "Musik/Technik" else "",
            }
            append_transaction(record)
            anzeige_betrag = final_betrag if final_betrag > 0 else kaution_betrag
            label = "Geplante Ausgabe" if ist_geplant else entry_type_label
            st.success(f"{label}: {format_euro(anzeige_betrag)} für {final_name} gespeichert.")
            st.rerun()

    # --- Offene geplante Ausgaben als Übersicht + Als-bezahlt-markieren ---
    planned_open_df = transactions_df[
        (transactions_df["Transaktions_Typ"] == PLANNED_EXPENSE_TYPE)
        & (transactions_df["Status"] == STATUS_PLANNED)
    ].copy()

    if not planned_open_df.empty:
        st.markdown("---")
        st.markdown("#### Offene geplante Ausgaben")
        planned_display = planned_open_df[
            ["Name", "Faellig_Am", "Kategorie", "Kostenbezeichnung", "Anzahl", "Einheit", "Beschreibung", "Betrag", "Ist_Investition"]
        ].copy()
        planned_display["Faellig_Am"] = planned_display["Faellig_Am"].dt.strftime("%d.%m.%Y").fillna("-")
        planned_display["Betrag"] = planned_display["Betrag"].map(format_euro)
        planned_display["Anzahl"] = planned_display["Anzahl"].map(format_quantity)
        planned_display["Ist_Investition"] = planned_display["Ist_Investition"].map(lambda v: "Ja" if v else "")
        st.dataframe(planned_display, use_container_width=True, hide_index=True)

        selection_labels = {
            row["_sheet_row"]: (
                f"{row['Name']} | {format_euro(row['Betrag'])} | {build_cost_label(row)} | "
                f"fällig {row['Faellig_Am'].strftime('%d.%m.%Y') if pd.notna(row['Faellig_Am']) else '-'}"
            )
            for _, row in planned_open_df.iterrows()
        }
        selected_rows = st.multiselect(
            "Als vom Haus bezahlt markieren:",
            options=list(selection_labels.keys()),
            format_func=lambda row_id: selection_labels[row_id],
        )
        payment_date = st.date_input("Bezahlt am", value=date.today(), key="planned_payment_date")
        if st.button("Als bezahlt markieren", type="primary"):
            if not selected_rows:
                st.warning("Bitte wähle mindestens eine geplante Ausgabe aus.")
            else:
                for sheet_row in selected_rows:
                    mark_planned_as_paid(sheet_row, payment_date)
                st.success("Markiert als vom Haus bezahlt.")
                st.rerun()

with edit_tab:
    st.subheader("Transaktion bearbeiten oder loeschen")

    if transactions_df.empty:
        st.info("Noch keine Transaktionen vorhanden.")
    else:
        # --- Suche / Auswahl ---
        st.markdown("**Schritt 1: Transaktion auswaehlen**")
        ecol1, ecol2 = st.columns(2)
        with ecol1:
            edit_filter_person = st.selectbox(
                "Nach Person filtern",
                ["Alle"] + sorted(transactions_df["Name"].dropna().astype(str).unique()),
                key="edit_filter_person",
            )
        with ecol2:
            edit_filter_cat = st.selectbox(
                "Nach Kategorie filtern",
                ["Alle"] + sorted(transactions_df["Kategorie"].dropna().astype(str).unique()),
                key="edit_filter_cat",
            )

        filtered_edit = transactions_df.copy()
        if edit_filter_person != "Alle":
            filtered_edit = filtered_edit[filtered_edit["Name"].astype(str) == edit_filter_person]
        if edit_filter_cat != "Alle":
            filtered_edit = filtered_edit[filtered_edit["Kategorie"].astype(str) == edit_filter_cat]

        if filtered_edit.empty:
            st.info("Keine Transaktionen fuer diese Filterauswahl.")
        else:
            tx_labels = {
                row["_sheet_row"]: (
                    f"{row['Erfasst_Am'].strftime('%d.%m.%Y') if pd.notna(row['Erfasst_Am']) else '-'}"
                    f" | {row['Name']} | {row['Kategorie']} | {format_euro(row['Betrag'])} | {row['Beschreibung'] or '-'}"
                )
                for _, row in filtered_edit.sort_values("Erfasst_Am", ascending=False).iterrows()
            }

            selected_sheet_row = st.selectbox(
                "Transaktion auswaehlen",
                options=list(tx_labels.keys()),
                format_func=lambda r: tx_labels[r],
                key="edit_selected_row",
            )

            tx = transactions_df[transactions_df["_sheet_row"] == selected_sheet_row].iloc[0]

            st.markdown("---")
            st.markdown("**Schritt 2: Felder bearbeiten**")

            # Kategorie außerhalb des Forms für live Felder
            edit_kat_idx = CATEGORY_OPTIONS.index(tx["Kategorie"]) if tx["Kategorie"] in CATEGORY_OPTIONS else 0
            edit_kategorie = st.selectbox("Kategorie", CATEGORY_OPTIONS, index=edit_kat_idx, key="edit_kategorie")

            if tx["Transaktions_Typ"] == "Verrechnung (Warenübernahme)":
                st.info("Verrechnungen bestehen aus zwei verknüpften Transaktionen (Einnahme + Erstattung). Bitte lösche und korrigiere beide Einträge einzeln im Transaktionsprotokoll.")

            with st.form("edit_form"):
                ecf1, ecf2 = st.columns(2)
                edit_type_options = TRANSACTION_TYPES + [PLANNED_EXPENSE_TYPE]
                with ecf1:
                    edit_typ_idx = edit_type_options.index(tx["Transaktions_Typ"]) if tx["Transaktions_Typ"] in edit_type_options else 0
                    edit_typ = st.selectbox("Transaktionstyp", edit_type_options, index=edit_typ_idx)
                with ecf2:
                    name_opts = build_name_options(transactions_df)
                    edit_name_idx = name_opts.index(tx["Name"]) if tx["Name"] in name_opts else 0
                    edit_name = st.selectbox("Person", name_opts, index=edit_name_idx)

                amount_col1, amount_col2 = st.columns(2)
                with amount_col1:
                    edit_kostenbezeichnung = st.text_input(
                        "Bezeichnung",
                        value=str(tx.get("Kostenbezeichnung", "") or ""),
                    )
                with amount_col2:
                    edit_betrag = st.number_input(
                        "Betrag in EUR",
                        min_value=0.0,
                        step=0.5,
                        format="%.2f",
                        value=float(tx["Betrag"]) if pd.notna(tx["Betrag"]) else 0.0,
                    )

                qty_col1, qty_col2, qty_col3 = st.columns([1, 1, 1.2])
                with qty_col1:
                    edit_anzahl = st.number_input(
                        "Anzahl",
                        min_value=0.0,
                        step=1.0,
                        format="%.2f",
                        value=float(tx.get("Anzahl", 0.0) or 0.0),
                    )
                with qty_col2:
                    edit_einheit = st.text_input("Einheit", value=str(tx.get("Einheit", "") or ""))
                with qty_col3:
                    edit_ist_investition = st.checkbox(
                        "Als Investition markieren",
                        value=bool(tx.get("Ist_Investition", False)),
                    )

                # Kategorie-spezifische Felder
                edit_getraenk_name = ""
                edit_getraenk_anzahl = 0
                edit_getraenk_preis = 0.0
                edit_getraenk_za = ""
                edit_musik_typ = ""
                edit_kaution = 0.0

                if edit_kategorie == "Getraenke":
                    st.markdown("**Getraenke-Details**")
                    gec1, gec2, gec3 = st.columns(3)
                    with gec1:
                        edit_getraenk_name = st.text_input("Getraenk (Name)", value=str(tx.get("Getraenk_Name", "") or ""))
                    with gec2:
                        edit_getraenk_anzahl = st.number_input("Anzahl", min_value=0, step=1, value=int(parse_quantity(tx.get("Getraenk_Anzahl", 0) or 0)))
                    with gec3:
                        edit_getraenk_preis = st.number_input("Preis/Stueck", min_value=0.0, step=0.05, format="%.2f", value=parse_amount(tx.get("Getraenk_Preis_Stueck", 0.0) or 0.0))
                    za_idx = GETRAENKE_ZAHLUNGSART.index(tx.get("Getraenk_Zahlungsart", "")) if tx.get("Getraenk_Zahlungsart", "") in GETRAENKE_ZAHLUNGSART else 0
                    edit_getraenk_za = st.selectbox("Zahlungsart", GETRAENKE_ZAHLUNGSART, index=za_idx)

                elif edit_kategorie == "Musik/Technik":
                    st.markdown("**Musik/Technik-Details**")
                    mt_idx = MUSIK_ZAHLUNGSTYP.index(tx.get("Musik_Zahlungstyp", "")) if tx.get("Musik_Zahlungstyp", "") in MUSIK_ZAHLUNGSTYP else 0
                    edit_musik_typ = st.selectbox("Art der Zahlung", MUSIK_ZAHLUNGSTYP, index=mt_idx)
                    if edit_musik_typ in ("Kaution", "Kaution + Betrag"):
                        edit_kaution = st.number_input("Kautionsbetrag", min_value=0.0, step=10.0, format="%.2f", value=float(tx.get("Kaution_Betrag", 0.0) or 0.0))

                edit_planned_status = STATUS_PLANNED
                if edit_typ == PLANNED_EXPENSE_TYPE:
                    planned_status_options = [STATUS_PLANNED, STATUS_PAID_BY_HOUSE]
                    current_planned_status = tx["Status"] if tx["Status"] in planned_status_options else STATUS_PLANNED
                    edit_planned_status = st.radio(
                        "Status der geplanten Ausgabe",
                        planned_status_options,
                        index=planned_status_options.index(current_planned_status),
                        horizontal=True,
                    )
                    st.caption("Geplante Ausgaben bleiben geplant, bis du sie hier oder im Tab oben als vom Haus bezahlt markierst.")
                    edit_bezahlt_von = ""
                else:
                    bv_options = [HOUSE_PAYER, PRIVATE_PAYER]
                    bv_idx = bv_options.index(tx["Bezahlt_Von"]) if tx["Bezahlt_Von"] in bv_options else 0
                    edit_bezahlt_von = st.radio("Wer hat gezahlt?", bv_options, index=bv_idx, horizontal=True)
                edit_beschreibung = st.text_area("Beschreibung", value=str(tx["Beschreibung"] or ""))

                save_col, del_col = st.columns([3, 1])
                with save_col:
                    save_btn = st.form_submit_button("Aenderungen speichern", type="primary")
                with del_col:
                    delete_btn = st.form_submit_button("Loeschen", type="secondary")

            if save_btn:
                new_status = STATUS_DONE
                new_paid_by = edit_bezahlt_von
                new_paid_at = format_date_value(tx.get("Bezahlt_Am"))
                if edit_typ == PLANNED_EXPENSE_TYPE:
                    new_status = edit_planned_status
                    new_paid_by = HOUSE_PAYER if edit_planned_status == STATUS_PAID_BY_HOUSE else ""
                    if edit_planned_status == STATUS_PAID_BY_HOUSE:
                        new_paid_at = new_paid_at or date.today().strftime("%d.%m.%Y")
                    else:
                        new_paid_at = ""
                elif edit_typ == "Ausgabe/Einkauf" and edit_bezahlt_von == PRIVATE_PAYER:
                    new_status = STATUS_OPEN
                elif edit_typ == "Einzahlung auf das Haus":
                    new_paid_by = edit_name
                elif edit_typ == "Rueckerstattung vom Haus":
                    new_paid_by = HOUSE_PAYER

                update_transaction(selected_sheet_row, {
                    "Name": edit_name,
                    "Transaktions_Typ": edit_typ,
                    "Betrag": float(edit_betrag),
                    "Kategorie": edit_kategorie,
                    "Bezahlt_Am": new_paid_at,
                    "Bezahlt_Von": new_paid_by,
                    "Beschreibung": edit_beschreibung,
                    "Kostenbezeichnung": edit_kostenbezeichnung,
                    "Anzahl": edit_anzahl,
                    "Einheit": edit_einheit,
                    "Ist_Investition": "Ja" if edit_ist_investition else "",
                    "Status": new_status,
                    "Getraenk_Name": edit_getraenk_name if edit_kategorie == "Getraenke" else "",
                    "Getraenk_Anzahl": edit_getraenk_anzahl if edit_kategorie == "Getraenke" else "",
                    "Getraenk_Preis_Stueck": edit_getraenk_preis if edit_kategorie == "Getraenke" else "",
                    "Getraenk_Zahlungsart": edit_getraenk_za if edit_kategorie == "Getraenke" else "",
                    "Musik_Zahlungstyp": edit_musik_typ if edit_kategorie == "Musik/Technik" else "",
                    "Kaution_Betrag": edit_kaution if edit_kategorie == "Musik/Technik" else "",
                })
                st.success("Transaktion wurde aktualisiert.")
                st.rerun()

            if delete_btn:
                if st.session_state.get("delete_confirmed") != selected_sheet_row:
                    st.session_state["delete_confirmed"] = selected_sheet_row
                    st.warning("Nochmal auf 'Loeschen' klicken um zu bestaetigen.")
                else:
                    delete_transaction(selected_sheet_row)
                    st.session_state.pop("delete_confirmed", None)
                    st.success("Transaktion wurde geloescht.")
                    st.rerun()


with overview_tab:
    st.subheader("Transparente Uebersicht")

    # --- Berechnungen ---
    initial_house_funding = transactions_df.loc[initial_house_funding_mask(transactions_df), "Betrag"].sum()
    people_deposits = transactions_df.loc[
        (transactions_df["Transaktions_Typ"] == "Einzahlung auf das Haus")
        & (~initial_house_funding_mask(transactions_df)),
        "Betrag",
    ].sum()
    party_income = transactions_df.loc[
        transactions_df["Transaktions_Typ"] == "Einnahmen (Party)", "Betrag"
    ].sum()
    house_income = initial_house_funding + people_deposits + party_income
    party_direct_spend = transactions_df.loc[
        party_expense_mask(transactions_df) & (transactions_df["Bezahlt_Von"] == HOUSE_PAYER),
        "Betrag",
    ].sum()
    investment_direct_spend = transactions_df.loc[
        investment_expense_mask(transactions_df) & (transactions_df["Bezahlt_Von"] == HOUSE_PAYER),
        "Betrag",
    ].sum()
    reimbursements_paid = transactions_df.loc[
        transactions_df["Transaktions_Typ"] == "Rueckerstattung vom Haus", "Betrag"
    ].sum()
    house_total_paid = party_direct_spend + investment_direct_spend + reimbursements_paid
    planned_total = transactions_df.loc[
        planned_party_mask(transactions_df),
        "Betrag",
    ].sum()
    planned_investment_total = transactions_df.loc[
        (transactions_df["Transaktions_Typ"] == PLANNED_EXPENSE_TYPE)
        & (transactions_df["Status"] == STATUS_PLANNED)
        & (transactions_df["Ist_Investition"].fillna(False)),
        "Betrag",
    ].sum()
    party_total = transactions_df.loc[party_expense_mask(transactions_df), "Betrag"].sum()
    investment_total = transactions_df.loc[investment_expense_mask(transactions_df), "Betrag"].sum()

    person_summary = build_person_summary(transactions_df)
    open_to_people = person_summary["Gesamtanspruch_gegen_Haus"].sum() if not person_summary.empty else 0.0
    private_party_total = person_summary["Privat_vorgelegt_Party"].sum() if not person_summary.empty else 0.0
    private_investment_total = person_summary["Privat_vorgelegt_Investition"].sum() if not person_summary.empty else 0.0
    liquide_mittel = house_income - house_total_paid
    house_balance_after_obligations = liquide_mittel - open_to_people - planned_total

    # --- Metriken: Zeile 1 (Liquidität) ---
    st.markdown("#### Hauskasse auf einen Blick")
    ohne_anfang = st.toggle(
        "Anfangsbestand herausrechnen (Gewinn/Verlust-Sicht)",
        value=False,
        help="Blendet den Anfangsbestand (Altes Polizeipräsidium) aus der Berechnung aus, "
             "um nur den durch die Party erzielten Gewinn/Verlust zu sehen.",
    )
    if ohne_anfang:
        income_basis = people_deposits + party_income
        liquide_mittel_angepasst = income_basis - house_total_paid
        balance_angepasst = liquide_mittel_angepasst - open_to_people - planned_total
    else:
        income_basis = house_income
        liquide_mittel_angepasst = liquide_mittel
        balance_angepasst = house_balance_after_obligations

    row1 = st.columns(4)
    row1[0].metric("Startbestand Haus", format_euro(initial_house_funding))
    row1[1].metric("Einzahlungen Personen", format_euro(people_deposits))
    row1[2].metric("Einnahmen Party", format_euro(party_income))
    liq_delta = f"{'+' if liquide_mittel_angepasst >= 0 else ''}{liquide_mittel_angepasst:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", ".")
    row1[3].metric(
        "Liquide Mittel (Kasse)" if not ohne_anfang else "Liquide Mittel (ohne Anfangsbestand)",
        format_euro(liquide_mittel_angepasst),
        delta=liq_delta,
        delta_color="normal" if liquide_mittel_angepasst >= 0 else "inverse",
    )

    # --- Metriken: Zeile 2 (Verpflichtungen & Endstand) ---
    row2 = st.columns(3)
    row2[0].metric("Partykosten gesamt", format_euro(party_total))
    row2[1].metric("Investitionen gesamt", format_euro(investment_total))
    row2[2].metric("Erstattungen gezahlt", format_euro(reimbursements_paid))

    row3 = st.columns(4)
    row3[0].metric("Ansprueche gesamt", format_euro(open_to_people))
    row3[1].metric("Privat vorgelegt Party", format_euro(private_party_total))
    row3[2].metric("Privat vorgelegt Invest.", format_euro(private_investment_total))
    balance_color = "normal" if balance_angepasst >= 0 else "inverse"
    bal_delta = f"{'+' if balance_angepasst >= 0 else ''}{balance_angepasst:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", ".")
    row3[3].metric(
        "Hausbestand nach allem" if not ohne_anfang else "Gewinn/Verlust (ohne Anfangsbestand)",
        format_euro(balance_angepasst),
        delta=bal_delta,
        delta_color=balance_color,
    )
    st.caption(
        f"Noch offen: geplante Partykosten {format_euro(planned_total)} | geplante Investitionen {format_euro(planned_investment_total)}"
    )
    st.caption(
        "Investitionen erscheinen nicht als Partykosten, privat vorgelegte Investitionen bleiben aber als Rueckzahlungsanspruch bestehen."
    )

    # --- Wasserfalldiagramm ---
    st.markdown("### Geldfluss")
    if ohne_anfang:
        wf_labels   = ["Einzahlungen Personen", "Einnahmen Party", "Ausgaben", "Liquide Mittel", "Auslagen offen", "Geplante Kosten", "Endbestand"]
        wf_measures = ["absolute", "relative", "relative", "total", "relative", "relative", "total"]
        wf_y        = [people_deposits, party_income, -house_total_paid, liquide_mittel_angepasst, -open_to_people, -planned_total, balance_angepasst]
        wf_text     = [format_euro(people_deposits), format_euro(party_income), format_euro(-house_total_paid), format_euro(liquide_mittel_angepasst), format_euro(-open_to_people), format_euro(-planned_total), format_euro(balance_angepasst)]
    else:
        wf_labels   = ["Anfangsbestand", "Einzahlungen Personen", "Einnahmen Party", "Ausgaben", "Liquide Mittel", "Auslagen offen", "Geplante Kosten", "Endbestand"]
        wf_measures = ["absolute", "relative", "relative", "relative", "total", "relative", "relative", "total"]
        wf_y        = [initial_house_funding, people_deposits, party_income, -house_total_paid, liquide_mittel_angepasst, -open_to_people, -planned_total, balance_angepasst]
        wf_text     = [format_euro(initial_house_funding), format_euro(people_deposits), format_euro(party_income), format_euro(-house_total_paid), format_euro(liquide_mittel_angepasst), format_euro(-open_to_people), format_euro(-planned_total), format_euro(balance_angepasst)]

    waterfall_fig = go.Figure(
        go.Waterfall(
            name="Hauskonto",
            orientation="v",
            measure=wf_measures,
            x=wf_labels,
            customdata=wf_labels,
            y=wf_y,
            text=wf_text,
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
        clickmode="event",
    )
    wf_event = st.plotly_chart(waterfall_fig, use_container_width=True, on_select="rerun", key="waterfall_chart")

    # Tabelle bei Balken-Klick
    selected_points = (wf_event or {}).get("selection", {}).get("points", [])
    if selected_points:
        clicked_label = selected_points[0].get("x") or selected_points[0].get("label", "")
        detail_df = None
        detail_title = ""

        if clicked_label == "Anfangsbestand":
            detail_df = transactions_df[initial_house_funding_mask(transactions_df)].copy()
            detail_title = "Anfangsbestand"
        elif clicked_label == "Einzahlungen Personen":
            detail_df = transactions_df[
                (transactions_df["Transaktions_Typ"] == "Einzahlung auf das Haus")
                & (~initial_house_funding_mask(transactions_df))
            ].copy()
            detail_title = "Einzahlungen Personen"
        elif clicked_label == "Einnahmen Party":
            detail_df = transactions_df[
                transactions_df["Transaktions_Typ"] == "Einnahmen (Party)"
            ].copy()
            detail_title = "Einnahmen Party"
        elif clicked_label == "Ausgaben":
            detail_df = transactions_df[
                party_expense_mask(transactions_df) | investment_expense_mask(transactions_df)
                | (transactions_df["Transaktions_Typ"] == "Rueckerstattung vom Haus")
            ].copy()
            detail_title = "Ausgaben & Erstattungen"
        elif clicked_label == "Auslagen offen":
            # Guthaben: Einzahlungen die noch im Haus liegen (pro Person)
            guthaben_df = person_summary[person_summary["Guthaben_im_Haus"] > 0][["Name", "Guthaben_im_Haus"]].copy()
            guthaben_df = guthaben_df.rename(columns={"Guthaben_im_Haus": "Betrag"})
            guthaben_df["Typ"] = "Guthaben im Haus (Einzahlung)"
            # Offene private Auslagen
            auslagen_df = transactions_df[
                (transactions_df["Transaktions_Typ"] == "Ausgabe/Einkauf")
                & (transactions_df["Bezahlt_Von"] == PRIVATE_PAYER)
                & (transactions_df["Status"] == STATUS_OPEN)
            ][["Name", "Kategorie", "Beschreibung", "Betrag"]].copy()
            auslagen_df["Typ"] = "Offene Auslage (privat vorgestreckt)"
            combined = pd.concat([
                guthaben_df[["Name", "Typ", "Betrag"]],
                auslagen_df[["Name", "Typ", "Kategorie", "Beschreibung", "Betrag"]],
            ], ignore_index=True)
            combined["Betrag"] = combined["Betrag"].map(format_euro)
            st.markdown("#### Ansprüche gegen das Haus")
            st.dataframe(combined, use_container_width=True, hide_index=True)
            detail_title = None  # schon gerendert
        elif clicked_label == "Geplante Kosten":
            detail_df = transactions_df[
                planned_party_mask(transactions_df)
            ].copy()
            detail_title = "Geplante Kosten (noch nicht bezahlt)"
        elif clicked_label in ("Liquide Mittel", "Endbestand"):
            st.info(f"**{clicked_label}** ist ein berechneter Wert – keine einzelnen Transaktionen dahinter.")

        if detail_df is not None:
            st.markdown(f"#### {detail_title}")
            if detail_df.empty:
                st.info("Keine Transaktionen vorhanden.")
            else:
                show_cols = ["Erfasst_Am", "Name", "Transaktions_Typ", "Kategorie", "Beschreibung", "Betrag", "Status"]
                show_cols = [c for c in show_cols if c in detail_df.columns]
                detail_df = detail_df.copy()
                detail_df["Erfasst_Am"] = detail_df["Erfasst_Am"].dt.strftime("%d.%m.%Y").fillna("-")
                detail_df["Betrag"] = detail_df["Betrag"].map(format_euro)
                st.dataframe(detail_df[show_cols], use_container_width=True, hide_index=True)

    # --- Einnahmen vs. Ausgaben Pie + Ansprüche pro Person ---
    if not person_summary.empty or party_income > 0 or people_deposits > 0:
        pie_col, bar_col = st.columns(2)

        with pie_col:
            st.markdown("### Einnahmen vs. Ausgaben")
            pie_labels = ["Einzahlungen Personen", "Einnahmen Party", "Partykosten", "Investitionen", "Erstattungen"]
            pie_values = [people_deposits, party_income, party_direct_spend, investment_direct_spend, reimbursements_paid]
            pie_colors = ["#15803d", "#22c55e", "#b91c1c", "#f97316", "#6366f1"]
            # nur Einträge > 0 zeigen
            filtered = [(l, v, c) for l, v, c in zip(pie_labels, pie_values, pie_colors) if v > 0]
            if filtered:
                fl, fv, fc = zip(*filtered)
                pie_fig = go.Figure(go.Pie(
                    labels=fl,
                    values=fv,
                    marker={"colors": fc},
                    textinfo="label+percent",
                    hovertemplate="%{label}<br>%{value:,.2f} EUR<extra></extra>",
                    hole=0.35,
                ))
                pie_fig.update_layout(
                    height=320,
                    margin={"l": 10, "r": 10, "t": 10, "b": 10},
                    showlegend=False,
                )
                st.plotly_chart(pie_fig, use_container_width=True)

        with bar_col:
            st.markdown("### Ansprüche pro Person")
            anspruch_df = person_summary[person_summary["Gesamtanspruch_gegen_Haus"] > 0].copy()
            if anspruch_df.empty:
                st.info("Alle Ansprüche beglichen.")
            else:
                anspruch_fig = go.Figure(go.Bar(
                    x=anspruch_df["Gesamtanspruch_gegen_Haus"],
                    y=anspruch_df["Name"],
                    orientation="h",
                    text=[format_euro(v) for v in anspruch_df["Gesamtanspruch_gegen_Haus"]],
                    textposition="outside",
                    customdata=list(zip(
                        anspruch_df["Einzahlungen"],
                        anspruch_df["Offene_Auslagen"],
                    )),
                    hovertemplate=(
                        "<b>%{y}</b><br>"
                        "Anspruch gesamt: %{x:,.2f} EUR<br>"
                        "davon Einzahlung: %{customdata[0]:,.2f} EUR<br>"
                        "davon offene Auslagen: %{customdata[1]:,.2f} EUR"
                        "<extra></extra>"
                    ),
                    marker_color="#7c3aed",
                ))
                anspruch_fig.update_layout(
                    height=320,
                    margin={"l": 10, "r": 60, "t": 10, "b": 10},
                    xaxis_title="EUR",
                    yaxis_title="",
                    showlegend=False,
                    yaxis={"categoryorder": "total ascending"},
                )
                st.plotly_chart(anspruch_fig, use_container_width=True)

    # --- Ausgaben-Timeline ---
    all_expense_df = transactions_df[
        party_expense_mask(transactions_df) | investment_expense_mask(transactions_df)
    ].copy()
    if not all_expense_df.empty and all_expense_df["Erfasst_Am"].notna().any():
        st.markdown("### Ausgaben über Zeit")
        timeline_df = all_expense_df.dropna(subset=["Erfasst_Am"]).copy()
        timeline_df["Datum"] = timeline_df["Erfasst_Am"].dt.date
        timeline_agg = (
            timeline_df.groupby(["Datum", "Kategorie"])["Betrag"]
            .sum()
            .reset_index()
            .sort_values("Datum")
        )
        kategorie_colors = {
            "Getraenke": "#1d4ed8",
            "Deko": "#db2777",
            "Musik/Technik": "#7c3aed",
            "Location": "#b45309",
            "Umlage/Einzahlung": "#15803d",
            "Einnahmen": "#22c55e",
            "Sonstiges": "#64748b",
        }
        timeline_fig = go.Figure()
        for kat in timeline_agg["Kategorie"].unique():
            df_k = timeline_agg[timeline_agg["Kategorie"] == kat]
            timeline_fig.add_trace(go.Bar(
                x=df_k["Datum"].astype(str),
                y=df_k["Betrag"],
                name=kat,
                marker_color=kategorie_colors.get(kat, "#94a3b8"),
                hovertemplate=f"<b>{kat}</b><br>%{{x}}<br>%{{y:,.2f}} EUR<extra></extra>",
            ))
        timeline_fig.update_layout(
            barmode="stack",
            height=320,
            margin={"l": 20, "r": 20, "t": 10, "b": 20},
            yaxis_title="EUR",
            xaxis_title="",
            legend={"orientation": "h", "y": -0.2},
        )
        st.plotly_chart(timeline_fig, use_container_width=True)

    # --- Ausgaben nach Kategorie ---
    st.markdown("### Ausgaben nach Kategorie")
    ausgaben_df = transactions_df[
        party_expense_mask(transactions_df)
    ].copy()
    if ausgaben_df.empty:
        st.info("Noch keine Ausgaben vorhanden.")
    else:
        cat_sum = ausgaben_df.groupby("Kategorie")["Betrag"].sum().reset_index().sort_values("Betrag", ascending=False)
        cat_fig = go.Figure(go.Bar(
            x=cat_sum["Kategorie"],
            y=cat_sum["Betrag"],
            text=[format_euro(v) for v in cat_sum["Betrag"]],
            textposition="outside",
            marker_color="#1d4ed8",
            hovertemplate="<b>%{x}</b><br>%{y:,.2f} EUR<extra></extra>",
        ))
        cat_fig.update_layout(
            height=340,
            margin={"l": 20, "r": 20, "t": 10, "b": 20},
            yaxis_title="EUR",
            showlegend=False,
            xaxis_title="",
        )
        cat_event = st.plotly_chart(cat_fig, use_container_width=True, on_select="rerun", key="cat_chart")
        cat_points = (cat_event or {}).get("selection", {}).get("points", [])
        if cat_points:
            clicked_kat = cat_points[0].get("x", "")
            if clicked_kat:
                kat_detail = ausgaben_df[ausgaben_df["Kategorie"].astype(str) == clicked_kat].copy()
                st.markdown(f"#### Einzelposten: {clicked_kat}")
                kat_detail["Erfasst_Am"] = kat_detail["Erfasst_Am"].dt.strftime("%d.%m.%Y").fillna("-")
                kat_detail["Betrag"] = kat_detail["Betrag"].map(format_euro)
                show = ["Erfasst_Am", "Name", "Kategorie", "Kostenbezeichnung", "Beschreibung", "Betrag", "Bezahlt_Von", "Status"]
                show = [c for c in show if c in kat_detail.columns]
                st.dataframe(kat_detail[show], use_container_width=True, hide_index=True)

        st.markdown("### Kosten nach Bezeichnung")
        detail_df = ausgaben_df.copy()
        detail_df["Bezeichnung"] = detail_df.apply(build_cost_label, axis=1)
        detail_df["Effektive_Anzahl"] = detail_df["Anzahl"]
        getraenke_mask = (detail_df["Effektive_Anzahl"] <= 0) & (detail_df["Getraenk_Anzahl"] > 0)
        detail_df.loc[getraenke_mask, "Effektive_Anzahl"] = detail_df.loc[getraenke_mask, "Getraenk_Anzahl"]

        available_categories = sorted(detail_df["Kategorie"].dropna().astype(str).unique())
        selected_detail_category = st.selectbox(
            "Kategorie fuer Einzelkosten",
            options=["Alle Kategorien"] + available_categories,
            key="detail_chart_category",
        )
        if selected_detail_category != "Alle Kategorien":
            detail_df = detail_df[detail_df["Kategorie"].astype(str) == selected_detail_category]

        detail_summary = (
            detail_df.groupby("Bezeichnung", dropna=False)
            .agg(
                Anzahl=("Effektive_Anzahl", "sum"),
                Betrag=("Betrag", "sum"),
            )
            .reset_index()
            .sort_values("Betrag", ascending=False)
        )

        detail_fig = go.Figure(
            go.Bar(
                x=detail_summary["Betrag"],
                y=detail_summary["Bezeichnung"],
                orientation="h",
                text=[
                    (
                        f"{format_euro(amount)}"
                        + (f" | {format_quantity(quantity)}" if quantity and quantity > 0 else "")
                    )
                    for amount, quantity in zip(detail_summary["Betrag"], detail_summary["Anzahl"])
                ],
                textposition="outside",
                marker_color="#0f766e",
                hovertemplate="<b>%{y}</b><br>%{x:,.2f} EUR<extra></extra>",
            )
        )
        detail_fig.update_layout(
            height=max(320, 70 + len(detail_summary) * 42),
            margin={"l": 20, "r": 40, "t": 10, "b": 20},
            xaxis_title="EUR",
            yaxis_title="",
            showlegend=False,
            yaxis={"categoryorder": "total ascending"},
        )
        st.plotly_chart(detail_fig, use_container_width=True)

    # --- Personensalden ---
    st.markdown("### Personensalden")
    if person_summary.empty:
        st.info("Noch keine Personendaten vorhanden.")
    else:
        # Tabelle mit lesbaren Spaltennamen
        display_person_summary = person_summary.rename(columns={
            "Einzahlungen": "Eingezahlt",
            "Privat_vorgelegt_Party": "Privat vorgelegt Party",
            "Privat_vorgelegt_Investition": "Privat vorgelegt Investition",
            "Privat_vorgelegt_Gesamt": "Privat vorgelegt gesamt",
            "Rueckerstattungen": "Erstattet",
            "Guthaben_im_Haus": "Guthaben im Haus",
            "Offene_Auslagen": "Auslage offen",
            "Gesamtanspruch_gegen_Haus": "Anspruch gesamt",
            "Geplante_Ausgaben": "Geplant",
        }).copy()
        for col in [
            "Eingezahlt",
            "Privat vorgelegt Party",
            "Privat vorgelegt Investition",
            "Privat vorgelegt gesamt",
            "Erstattet",
            "Guthaben im Haus",
            "Auslage offen",
            "Anspruch gesamt",
            "Geplant",
        ]:
            display_person_summary[col] = display_person_summary[col].map(format_euro)
        st.dataframe(display_person_summary, use_container_width=True, hide_index=True)

        # Detailkarten pro Person
        st.markdown("#### Details pro Person")
        cols_per_row = 5
        people_list = person_summary["Name"].tolist()
        for row_start in range(0, len(people_list), cols_per_row):
            row_people = people_list[row_start : row_start + cols_per_row]
            card_cols = st.columns(cols_per_row)
            for col_idx, person_name in enumerate(row_people):
                row_data = person_summary[person_summary["Name"] == person_name].iloc[0]
                person_tx = transactions_df[transactions_df["Name"].astype(str) == person_name]
                eingezahlt = row_data["Einzahlungen"]
                vorgelegt = row_data["Privat_vorgelegt_Gesamt"]
                vorgelegt_party = row_data["Privat_vorgelegt_Party"]
                vorgelegt_invest = row_data["Privat_vorgelegt_Investition"]
                erstattet = row_data["Rueckerstattungen"]
                offen = row_data["Offene_Auslagen"]
                anspruch = row_data["Gesamtanspruch_gegen_Haus"]

                if eingezahlt == 0 and vorgelegt == 0:
                    status_color = "#7a6000"
                    status_text = "Noch nichts eingetragen"
                elif anspruch > 0:
                    status_color = "#7a6000"
                    status_text = f"Offen: {format_euro(anspruch)}"
                else:
                    status_color = "#1a6b2f"
                    status_text = "Alles beglichen"

                with card_cols[col_idx]:
                    with st.container(border=True):
                        st.markdown(
                            f"<div style='font-size:0.85rem;font-weight:600;margin-bottom:4px'>{person_name}</div>"
                            f"<div style='background:{status_color};padding:3px 6px;border-radius:4px;"
                            f"font-size:0.75rem;margin-bottom:6px'>{status_text}</div>",
                            unsafe_allow_html=True,
                        )
                        st.markdown(
                            f"<div style='font-size:0.7rem;color:#aaa;margin-bottom:1px'>Eingezahlt</div>"
                            f"<div style='font-size:0.85rem;margin-bottom:4px'>{format_euro(eingezahlt)}</div>"
                            f"<div style='font-size:0.7rem;color:#aaa;margin-bottom:1px'>Privat vorgelegt gesamt</div>"
                            f"<div style='font-size:0.85rem;margin-bottom:4px'>{format_euro(vorgelegt)}</div>"
                            f"<div style='font-size:0.7rem;color:#aaa;margin-bottom:1px'>davon Party / Invest.</div>"
                            f"<div style='font-size:0.85rem;margin-bottom:4px'>{format_euro(vorgelegt_party)} / {format_euro(vorgelegt_invest)}</div>"
                            f"<div style='font-size:0.7rem;color:#aaa;margin-bottom:1px'>Erstattet</div>"
                            f"<div style='font-size:0.85rem;margin-bottom:4px'>{format_euro(erstattet)}</div>"
                            f"<div style='font-size:0.7rem;color:#aaa;margin-bottom:1px'>Anspruch gesamt</div>"
                            f"<div style='font-size:0.85rem;font-weight:600'>{format_euro(anspruch)}</div>",
                            unsafe_allow_html=True,
                        )
                        recent = person_tx.sort_values("Erfasst_Am", ascending=False).head(2)
                        if not recent.empty:
                            st.markdown("<div style='font-size:0.7rem;color:#aaa;margin-top:6px;margin-bottom:2px'><b>Letzte Transaktionen:</b></div>", unsafe_allow_html=True)
                            for _, tx in recent.iterrows():
                                datum = tx["Erfasst_Am"].strftime("%d.%m.") if pd.notna(tx["Erfasst_Am"]) else "-"
                                st.caption(
                                    f"{datum} · {tx['Kategorie']} · {format_euro(tx['Betrag'])}"
                                )

    # --- Rückzahlungs-Checkliste ---
    with st.expander("Rückzahlungen abhaken", expanded=False):
        st.caption("Hier kannst du festhalten, wem das Darlehen (Einzahlung) und offene Auslagen bereits zurückgezahlt wurden.")
        if person_summary.empty:
            st.info("Keine Personen vorhanden.")
        else:
            rueckzahl_cols = st.columns(3)
            for i, (_, row_data) in enumerate(person_summary.iterrows()):
                pname = row_data["Name"]
                panspruch = row_data["Gesamtanspruch_gegen_Haus"]
                if panspruch <= 0:
                    continue
                col = rueckzahl_cols[i % 3]
                key = f"rueckzahlung_{pname}"
                already = st.session_state.get(key, False)
                checked = col.checkbox(
                    f"{pname} – {format_euro(panspruch)}",
                    value=already,
                    key=key,
                )
            bezahlt = [
                row_data["Name"]
                for _, row_data in person_summary.iterrows()
                if row_data["Gesamtanspruch_gegen_Haus"] > 0
                and st.session_state.get(f"rueckzahlung_{row_data['Name']}", False)
            ]
            offen_personen = [
                row_data["Name"]
                for _, row_data in person_summary.iterrows()
                if row_data["Gesamtanspruch_gegen_Haus"] > 0
                and not st.session_state.get(f"rueckzahlung_{row_data['Name']}", False)
            ]
            st.markdown("---")
            if bezahlt:
                st.success(f"Bereits zurückgezahlt: {', '.join(bezahlt)}")
            if offen_personen:
                st.warning(f"Noch offen: {', '.join(offen_personen)}")

    # --- Privat vorgelegte Ausgaben (eingeklappt) ---
    with st.expander("Privat vorgelegte Ausgaben", expanded=False):
        st.caption("Ausgaben die eine Person privat vorgestreckt hat und vom Haus erstattet werden muessen.")
        open_private_df = transactions_df[
            (transactions_df["Transaktions_Typ"] == "Ausgabe/Einkauf")
            & (transactions_df["Bezahlt_Von"] == PRIVATE_PAYER)
        ].copy()
        if open_private_df.empty:
            st.info("Aktuell gibt es keine privat vorgelegten Ausgaben.")
        else:
            open_private_df["Erfasst_Am"] = open_private_df["Erfasst_Am"].dt.strftime("%d.%m.%Y").fillna("-")
            open_private_df["Betrag"] = open_private_df["Betrag"].map(format_euro)
            open_private_df["Anzahl"] = open_private_df["Anzahl"].map(format_quantity)
            open_private_df["Ist_Investition"] = open_private_df["Ist_Investition"].map(lambda value: "Ja" if value else "")
            st.dataframe(
                open_private_df[["Erfasst_Am", "Name", "Kategorie", "Kostenbezeichnung", "Anzahl", "Einheit", "Beschreibung", "Betrag", "Status", "Ist_Investition"]],
                use_container_width=True,
                hide_index=True,
            )

    # --- Ausgaben des Hauses (eingeklappt) ---
    with st.expander("Ausgaben des Hauses", expanded=False):
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
            house_spend_df["Anzahl"] = house_spend_df["Anzahl"].map(format_quantity)
            house_spend_df["Erfasst_Am"] = house_spend_df["Erfasst_Am"].dt.strftime("%d.%m.%Y").fillna("-")
            house_spend_df["Bezahlt_Am"] = house_spend_df["Bezahlt_Am"].dt.strftime("%d.%m.%Y").fillna("-")
            house_spend_df["Ist_Investition"] = house_spend_df["Ist_Investition"].map(lambda value: "Ja" if value else "")
            st.dataframe(
                house_spend_df[["Erfasst_Am", "Bezahlt_Am", "Name", "Transaktions_Typ", "Kategorie", "Kostenbezeichnung", "Anzahl", "Einheit", "Beschreibung", "Betrag", "Status", "Ist_Investition"]],
                use_container_width=True,
                hide_index=True,
            )

    # --- Komplettes Transaktionsprotokoll (eingeklappt, mit Filter) ---
    with st.expander("Komplettes Transaktionsprotokoll", expanded=False):
        if transactions_df.empty:
            st.info("Noch keine Transaktionen vorhanden.")
        else:
            fcol1, fcol2 = st.columns(2)
            with fcol1:
                filter_person = st.multiselect(
                    "Nach Person filtern",
                    options=sorted(transactions_df["Name"].dropna().astype(str).unique()),
                    key="ledger_filter_person",
                )
            with fcol2:
                filter_cat = st.multiselect(
                    "Nach Kategorie filtern",
                    options=sorted(transactions_df["Kategorie"].dropna().astype(str).unique()),
                    key="ledger_filter_cat",
                )
            ledger_df = transactions_df.copy()
            if filter_person:
                ledger_df = ledger_df[ledger_df["Name"].astype(str).isin(filter_person)]
            if filter_cat:
                ledger_df = ledger_df[ledger_df["Kategorie"].astype(str).isin(filter_cat)]
            for date_col in ["Erfasst_Am", "Faellig_Am", "Bezahlt_Am"]:
                ledger_df[date_col] = ledger_df[date_col].dt.strftime("%d.%m.%Y").fillna("-")
            ledger_df["Betrag"] = ledger_df["Betrag"].map(format_euro)
            ledger_df["Anzahl"] = ledger_df["Anzahl"].map(format_quantity)
            ledger_df["Ist_Investition"] = ledger_df["Ist_Investition"].map(lambda value: "Ja" if value else "")
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
                        "Kostenbezeichnung",
                        "Anzahl",
                        "Einheit",
                        "Beschreibung",
                        "Betrag",
                        "Ist_Investition",
                        "Status",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )
