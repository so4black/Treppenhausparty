# Treppenhausparty Dashboard

Gemeinsames Streamlit-Dashboard fuer Barkalkulation, Finanzen und weitere Module rund um die Treppenhausparty.

## Lokal starten

```powershell
python -m streamlit run app.py
```

## Seiten

- `pages/1_Barkalkulation.py`
- `pages/2_Finanzen.py`

## Deployment

Das Repo kann direkt ueber Streamlit Community Cloud deployed werden.

Startdatei:

```text
app.py
```

## Secrets

Google-Credentials bitte nicht committen. Lokal in `.streamlit/secrets.toml` ablegen und im Deployment unter `App settings > Secrets` hinterlegen.
