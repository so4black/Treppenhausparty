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
GETRAENKE_ZAHLUNGSART = ["Vorkasse", "Auf Kommission"]
MUSIK_ZAHLUNGSTYP = ["Normaler Betrag", "Kaution", "Kaution + Betrag"]
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
        col_letter = chr(ord("A") + len(HEADER_ROW) - 1)
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


def update_transaction(sheet_row: int, record: dict):
    worksheet = get_worksheet()
    col_index = {column: idx + 1 for idx, column in enumerate(HEADER_ROW)}
    for field, value in record.items():
        if field in col_index:
            worksheet.update_cell(sheet_row, col_index[field], value)
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

entry_tab, planned_tab, edit_tab, overview_tab = st.tabs(
    ["Transaktion eintragen", "Geplante Ausgaben", "Bearbeiten / Loeschen", "Uebersicht"]
)

with entry_tab:
    st.subheader("Neue Transaktion")

    # Kategorie außerhalb des Forms, damit die Zusatzfelder live erscheinen
    kategorie = st.selectbox("Kategorie", CATEGORY_OPTIONS, key="entry_kategorie")

    with st.form("transaktion_form", clear_on_submit=True):
        transaktions_typ = st.selectbox("Was moechtest du eintragen?", TRANSACTION_TYPES)
        name_auswahl = st.selectbox("Wer traegt es ein / um wen geht es?", name_options)
        st.caption("Falls 'Neuen Namen hinzufuegen...' gewaehlt wurde:")
        neuer_name = st.text_input("Neuer Name")

        betrag = st.number_input("Betrag in EUR", min_value=0.0, step=0.5, format="%.2f")

        # --- Kategorie-spezifische Zusatzfelder ---
        getraenk_name = ""
        getraenk_anzahl = 0
        getraenk_preis_stueck = 0.0
        getraenk_zahlungsart = ""
        musik_zahlungstyp = ""
        kaution_betrag = 0.0

        if kategorie == "Getraenke":
            st.markdown("**Getraenke-Details**")
            gcol1, gcol2, gcol3 = st.columns(3)
            with gcol1:
                getraenk_name = st.text_input("Getraenk (Name)", placeholder="z.B. Bier, Mate, Prosecco")
            with gcol2:
                getraenk_anzahl = st.number_input("Anzahl (Flaschen/Kaesten)", min_value=0, step=1)
            with gcol3:
                getraenk_preis_stueck = st.number_input("Preis pro Stueck in EUR", min_value=0.0, step=0.05, format="%.2f")
            getraenk_zahlungsart = st.selectbox("Zahlungsart", GETRAENKE_ZAHLUNGSART)

        elif kategorie == "Musik/Technik":
            st.markdown("**Musik/Technik-Details**")
            musik_zahlungstyp = st.selectbox("Art der Zahlung", MUSIK_ZAHLUNGSTYP)
            if musik_zahlungstyp in ("Kaution", "Kaution + Betrag"):
                kaution_betrag = st.number_input(
                    "Kautionsbetrag in EUR",
                    min_value=0.0,
                    step=10.0,
                    format="%.2f",
                    help="Kaution wird separat erfasst und erscheint in der Uebersicht als rueckerstattbar.",
                )

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
        elif betrag <= 0 and kategorie not in ("Musik/Technik",) and not (kategorie == "Musik/Technik" and kaution_betrag > 0):
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

            # Betrag automatisch berechnen wenn Getraenke-Details ausgefuellt
            final_betrag = float(betrag)
            if kategorie == "Getraenke" and getraenk_anzahl > 0 and getraenk_preis_stueck > 0 and betrag == 0:
                final_betrag = getraenk_anzahl * getraenk_preis_stueck

            record = {
                "ID": make_transaction_id(),
                "Erfasst_Am": date.today().strftime("%d.%m.%Y"),
                "Faellig_Am": "",
                "Bezahlt_Am": paid_at,
                "Name": final_name,
                "Transaktions_Typ": transaktions_typ,
                "Betrag": final_betrag,
                "Kategorie": kategorie,
                "Bezahlt_Von": paid_by,
                "Beschreibung": beschreibung,
                "Status": status,
                "Referenz_ID": "",
                "Getraenk_Name": getraenk_name,
                "Getraenk_Anzahl": getraenk_anzahl if kategorie == "Getraenke" else "",
                "Getraenk_Preis_Stueck": getraenk_preis_stueck if kategorie == "Getraenke" else "",
                "Getraenk_Zahlungsart": getraenk_zahlungsart if kategorie == "Getraenke" else "",
                "Musik_Zahlungstyp": musik_zahlungstyp if kategorie == "Musik/Technik" else "",
                "Kaution_Betrag": kaution_betrag if kategorie == "Musik/Technik" else "",
            }
            append_transaction(record)
            anzeige_betrag = final_betrag if final_betrag > 0 else kaution_betrag
            st.success(f"{format_euro(anzeige_betrag)} fuer {final_name} wurde gespeichert.")
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

            with st.form("edit_form"):
                ecf1, ecf2 = st.columns(2)
                with ecf1:
                    edit_typ_idx = TRANSACTION_TYPES.index(tx["Transaktions_Typ"]) if tx["Transaktions_Typ"] in TRANSACTION_TYPES else 0
                    edit_typ = st.selectbox("Transaktionstyp", TRANSACTION_TYPES, index=edit_typ_idx)
                with ecf2:
                    name_opts = build_name_options(transactions_df)
                    edit_name_idx = name_opts.index(tx["Name"]) if tx["Name"] in name_opts else 0
                    edit_name = st.selectbox("Person", name_opts, index=edit_name_idx)

                edit_betrag = st.number_input(
                    "Betrag in EUR",
                    min_value=0.0,
                    step=0.5,
                    format="%.2f",
                    value=float(tx["Betrag"]) if pd.notna(tx["Betrag"]) else 0.0,
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
                        edit_getraenk_anzahl = st.number_input("Anzahl", min_value=0, step=1, value=int(tx.get("Getraenk_Anzahl", 0) or 0))
                    with gec3:
                        edit_getraenk_preis = st.number_input("Preis/Stueck", min_value=0.0, step=0.05, format="%.2f", value=float(tx.get("Getraenk_Preis_Stueck", 0.0) or 0.0))
                    za_idx = GETRAENKE_ZAHLUNGSART.index(tx.get("Getraenk_Zahlungsart", "")) if tx.get("Getraenk_Zahlungsart", "") in GETRAENKE_ZAHLUNGSART else 0
                    edit_getraenk_za = st.selectbox("Zahlungsart", GETRAENKE_ZAHLUNGSART, index=za_idx)

                elif edit_kategorie == "Musik/Technik":
                    st.markdown("**Musik/Technik-Details**")
                    mt_idx = MUSIK_ZAHLUNGSTYP.index(tx.get("Musik_Zahlungstyp", "")) if tx.get("Musik_Zahlungstyp", "") in MUSIK_ZAHLUNGSTYP else 0
                    edit_musik_typ = st.selectbox("Art der Zahlung", MUSIK_ZAHLUNGSTYP, index=mt_idx)
                    if edit_musik_typ in ("Kaution", "Kaution + Betrag"):
                        edit_kaution = st.number_input("Kautionsbetrag", min_value=0.0, step=10.0, format="%.2f", value=float(tx.get("Kaution_Betrag", 0.0) or 0.0))

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
                if edit_typ == "Ausgabe/Einkauf" and edit_bezahlt_von == PRIVATE_PAYER:
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
                    "Bezahlt_Von": new_paid_by,
                    "Beschreibung": edit_beschreibung,
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
    liquide_mittel = house_income - house_total_paid
    house_balance_after_obligations = liquide_mittel - open_to_people - planned_total

    # --- Metriken: Zeile 1 (Liquidität) ---
    st.markdown("#### Hauskasse auf einen Blick")
    row1 = st.columns(3)
    row1[0].metric("Eingezahlt (gesamt)", format_euro(house_income))
    row1[1].metric("Ausgegeben (gesamt)", format_euro(house_total_paid))
    liq_delta = f"{'+' if liquide_mittel >= 0 else ''}{liquide_mittel:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", ".")
    row1[2].metric(
        "Liquide Mittel (Kasse)",
        format_euro(liquide_mittel),
        delta=liq_delta,
        delta_color="normal" if liquide_mittel >= 0 else "inverse",
    )

    # --- Metriken: Zeile 2 (Verpflichtungen & Endstand) ---
    row2 = st.columns(3)
    row2[0].metric("Offene Auslagen (Personen)", format_euro(open_to_people))
    row2[1].metric("Geplante Kosten noch offen", format_euro(planned_total))
    balance_color = "normal" if house_balance_after_obligations >= 0 else "inverse"
    bal_delta = f"{'+' if house_balance_after_obligations >= 0 else ''}{house_balance_after_obligations:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", ".")
    row2[2].metric(
        "Hausbestand nach allem",
        format_euro(house_balance_after_obligations),
        delta=bal_delta,
        delta_color=balance_color,
    )

    # --- Wasserfalldiagramm ---
    st.markdown("### Geldfluss")
    waterfall_fig = go.Figure(
        go.Waterfall(
            name="Hauskonto",
            orientation="v",
            measure=["absolute", "relative", "total", "relative", "relative", "total"],
            x=[
                "Einzahlungen",
                "Ausgaben",
                "Liquide Mittel",
                "Auslagen offen",
                "Geplante Kosten",
                "Endbestand",
            ],
            y=[
                house_income,
                -house_total_paid,
                liquide_mittel,
                -open_to_people,
                -planned_total,
                house_balance_after_obligations,
            ],
            text=[
                format_euro(house_income),
                format_euro(-house_total_paid),
                format_euro(liquide_mittel),
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

    # --- Ausgaben nach Kategorie ---
    st.markdown("### Ausgaben nach Kategorie")
    ausgaben_df = transactions_df[
        (transactions_df["Transaktions_Typ"] == "Ausgabe/Einkauf")
        | (
            (transactions_df["Transaktions_Typ"] == "Geplante Ausgabe")
            & (transactions_df["Status"] == STATUS_PAID_BY_HOUSE)
        )
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
        ))
        cat_fig.update_layout(
            height=340,
            margin={"l": 20, "r": 20, "t": 10, "b": 20},
            yaxis_title="EUR",
            showlegend=False,
            xaxis_title="",
        )
        st.plotly_chart(cat_fig, use_container_width=True)

    # --- Personensalden ---
    st.markdown("### Personensalden")
    if person_summary.empty:
        st.info("Noch keine Personendaten vorhanden.")
    else:
        # Tabelle mit lesbaren Spaltennamen
        display_person_summary = person_summary.rename(columns={
            "Einzahlungen": "Eingezahlt",
            "Privat_vorgelegt": "Privat vorgelegt",
            "Rueckerstattungen": "Erstattet",
            "Guthaben_im_Haus": "Guthaben im Haus",
            "Offene_Auslagen": "Auslage offen",
            "Gesamtanspruch_gegen_Haus": "Anspruch gesamt",
            "Geplante_Ausgaben": "Geplant",
        }).copy()
        for col in ["Eingezahlt", "Privat vorgelegt", "Erstattet", "Guthaben im Haus", "Auslage offen", "Anspruch gesamt", "Geplant"]:
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
                vorgelegt = row_data["Privat_vorgelegt"]
                erstattet = row_data["Rueckerstattungen"]
                offen = row_data["Offene_Auslagen"]
                anspruch = row_data["Gesamtanspruch_gegen_Haus"]

                if eingezahlt == 0 and vorgelegt == 0:
                    status_color = "#7a6000"
                    status_text = "Noch nichts eingetragen"
                elif offen > 0:
                    status_color = "#7a6000"
                    status_text = f"Offen: {format_euro(offen)}"
                else:
                    status_color = "#1a6b2f"
                    status_text = "Erstattet"

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
                            f"<div style='font-size:0.7rem;color:#aaa;margin-bottom:1px'>Privat vorgelegt</div>"
                            f"<div style='font-size:0.85rem;margin-bottom:4px'>{format_euro(vorgelegt)}</div>"
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
            st.dataframe(
                open_private_df[["Erfasst_Am", "Name", "Kategorie", "Beschreibung", "Betrag", "Status"]],
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
            house_spend_df["Erfasst_Am"] = house_spend_df["Erfasst_Am"].dt.strftime("%d.%m.%Y").fillna("-")
            house_spend_df["Bezahlt_Am"] = house_spend_df["Bezahlt_Am"].dt.strftime("%d.%m.%Y").fillna("-")
            st.dataframe(
                house_spend_df[["Erfasst_Am", "Bezahlt_Am", "Name", "Transaktions_Typ", "Kategorie", "Beschreibung", "Betrag", "Status"]],
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
