import streamlit as st
import pandas as pd
import os
from collections import Counter
import ast

# --- CONFIGURAZIONE DELLA PAGINA ---
st.set_page_config(page_title="Radar Diritti Digitali", page_icon="⚖️", layout="wide")

st.title("⚖️ Tech Advocacy Radar - Italia & Europa")
st.markdown("""
Questa dashboard monitora in tempo reale le campagne delle principali organizzazioni civiche 
e le azioni del Garante Privacy, creando una mappa dell'ecosistema dei diritti digitali.
""")

# --- CARICAMENTO DATI ---
@st.cache_data # Questo comando rende l'app velocissima memorizzando i dati
def carica_dati():
    cartella_script = os.path.dirname(os.path.abspath(__file__))
    percorso_csv = os.path.join(cartella_script, '..', 'data', 'raw', 'ong_sample.csv')
    
    if os.path.exists(percorso_csv):
        df = pd.read_csv(percorso_csv)
        return df
    else:
        return pd.DataFrame()

df_ong = carica_dati()

if df_ong.empty:
    st.warning("Nessun dato trovato. Esegui prima lo scraper delle ONG!")
else:
    # --- BARRA LATERALE (FILTRI) ---
    st.sidebar.header("Filtra i Dati")
    ong_selezionate = st.sidebar.multiselect(
        "Scegli le Organizzazioni:", 
        options=df_ong['ONG'].unique(),
        default=df_ong['ONG'].unique()
    )
    
    # Filtriamo il dataframe
    df_filtrato = df_ong[df_ong['ONG'].isin(ong_selezionate)]
    
    # --- METRICHE PRINCIPALI ---
    col1, col2 = st.columns(2)
    col1.metric("Comunicati Analizzati", len(df_filtrato))
    col2.metric("Organizzazioni Attive", len(ong_selezionate))
    
    # --- TABELLA INTERATTIVA ---
    st.subheader("Ultimi Aggiornamenti")
    st.dataframe(df_filtrato[['Data', 'ONG', 'Titolo', 'Link']], use_container_width=True)
    
    st.info("💡 Suggerimento: Nelle prossime settimane collegheremo a questa tabella anche i dati del Garante e i grafici di Rete!")