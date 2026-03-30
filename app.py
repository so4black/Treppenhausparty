import streamlit as st


st.set_page_config(
    page_title="Treppenhausparty Dashboard",
    page_icon="🥳",
    layout="wide",
)

st.title("Treppenhausparty Dashboard")
st.caption("Zentrale Uebersicht fuer Barkalkulation, Finanzen und weitere Party-Module.")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### Barkalkulation")
    st.write("Preisberechnung, Mengenplanung und Auswertung fuer den Barverkauf.")

with col2:
    st.markdown("### Finanzen")
    st.write("Einzahlungen, Ausgaben, geplante Kosten und offene Ansprueche gegen das Haus.")

st.info("Nutze die Navigation links, um zwischen den Bereichen zu wechseln.")
