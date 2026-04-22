// Google Apps Script – als Web App deployen (Zugriff: Jeder)
// Spreadsheet ID: 1z6pVOSBNUcrWAdmgQfuqfNpvlwBYUkPmd58Xu29kj-U

const SPREADSHEET_ID = "1z6pVOSBNUcrWAdmgQfuqfNpvlwBYUkPmd58Xu29kj-U";
const SHEET_NAME     = "Backend_Kasse";

const HEADER = [
  "ID", "Zeitstempel", "Produkte", "Anzahl_Gesamt",
  "Betrag_Gesamt", "Erhalten", "Rueckgeld", "Rabatt", "Kassierer"
];

function getOrCreateSheet() {
  const ss    = SpreadsheetApp.openById(SPREADSHEET_ID);
  let   sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
    sheet.appendRow(HEADER);
    sheet.setFrozenRows(1);
  }
  // Header nachziehen falls Spalten fehlen
  const current = sheet.getRange(1, 1, 1, HEADER.length).getValues()[0];
  if (current.join("|") !== HEADER.join("|")) {
    sheet.getRange(1, 1, 1, HEADER.length).setValues([HEADER]);
  }
  return sheet;
}

function doPost(e) {
  try {
    const data   = JSON.parse(e.postData.contents);
    const sheet  = getOrCreateSheet();
    const now    = new Date();
    const id     = "KS-" + Utilities.formatDate(now, "Europe/Berlin", "yyyyMMdd-HHmmss");
    const ts     = Utilities.formatDate(now, "Europe/Berlin", "dd.MM.yyyy HH:mm:ss");

    sheet.appendRow([
      id,
      ts,
      data.produkte      || "",
      data.anzahl_gesamt || 0,
      data.betrag        || 0,
      data.erhalten      || 0,
      data.rueckgeld     || 0,
      data.rabatt        || "",
      data.kassierer     || "Kasse",
    ]);

    return ContentService
      .createTextOutput(JSON.stringify({ ok: true, id }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ ok: false, error: err.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// Zum Testen im Browser: gibt letzten Eintrag zurück
function doGet(e) {
  const sheet = getOrCreateSheet();
  return ContentService
    .createTextOutput(JSON.stringify({ ok: true, rows: sheet.getLastRow() - 1 }))
    .setMimeType(ContentService.MimeType.JSON);
}
