import streamlit as st
import pandas as pd
import os
import ast
import sqlite3
import plotly.express as px

# --- CONFIGURAZIONE DELLA PAGINA ---
st.set_page_config(page_title="Radar Diritti Digitali", page_icon="⚖️", layout="wide")

st.title("⚖️ Tech Advocacy Radar - Italia & Europa")
st.markdown("""
Questa dashboard monitora in tempo reale le campagne delle principali organizzazioni civiche 
e le azioni del Garante Privacy, creando una mappa dell'ecosistema dei diritti digitali.
""")

# --- CARICAMENTO DATI ---
@st.cache_data 
def carica_dati_ong():
    cartella_script = os.path.dirname(os.path.abspath(__file__))
    percorso_csv = os.path.join(cartella_script, '..', 'data', 'raw', 'ong_sample.csv')
    if os.path.exists(percorso_csv):
        return pd.read_csv(percorso_csv)
    return pd.DataFrame()

@st.cache_data 
def carica_dati_garante():
    """Carica dati del Garante da SQLite (Priority 0: più veloce di CSV)."""
    cartella_script = os.path.dirname(os.path.abspath(__file__))
    percorso_db = os.path.join(cartella_script, '..', 'data', 'tech_advocacy.db')
    percorso_csv_fallback = os.path.join(cartella_script, '..', 'data', 'processed', 'gpdp_analyzed.csv')
    
    # Prova prima SQLite (più veloce)
    if os.path.exists(percorso_db):
        try:
            conn = sqlite3.connect(percorso_db)
            df = pd.read_sql('SELECT * FROM provvedimenti_analyzed', conn)
            conn.close()
            
            # Converti liste salvate come stringhe in liste Python
            if 'Entita_Coinvolte' in df.columns:
                df['Entita_Coinvolte'] = df['Entita_Coinvolte'].apply(
                    lambda x: ast.literal_eval(x) if isinstance(x, str) else []
                )
            return df
        except Exception as e:
            st.warning(f"⚠️ Errore lettura SQLite: {e}. Fallback su CSV...")
    
    # Fallback su CSV se SQLite non disponibile
    if os.path.exists(percorso_csv_fallback):
        df = pd.read_csv(percorso_csv_fallback)
        if 'Entita_Coinvolte' in df.columns:
            df['Entita_Coinvolte'] = df['Entita_Coinvolte'].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) else [])
        return df
    
    return pd.DataFrame()

df_ong = carica_dati_ong()
df_gpdp = carica_dati_garante()

# --- CREAZIONE DELLE SCHEDE (TABS) ---
tab_ong, tab_garante = st.tabs(["📢 Campagne ONG", "⚖️ Provvedimenti Garante"])

# ==========================================
# SCHEDA 1: ORGANIZZAZIONI CIVICHE (Il tuo codice originale)
# ==========================================
with tab_ong:
    if df_ong.empty:
        st.warning("Nessun dato trovato. Esegui prima lo scraper delle ONG!")
    else:
        # Layout a due colonne per filtri e metriche
        col_filtri, col_metriche = st.columns([1, 2])
        
        with col_filtri:
            st.subheader("Filtra i Dati")
            ong_selezionate = st.multiselect(
                "Scegli le Organizzazioni:", 
                options=df_ong['ONG'].unique(),
                default=df_ong['ONG'].unique()
            )
        
        df_filtrato_ong = df_ong[df_ong['ONG'].isin(ong_selezionate)]
        
        with col_metriche:
            col1, col2 = st.columns(2)
            col1.metric("Comunicati Analizzati", len(df_filtrato_ong))
            col2.metric("Organizzazioni Attive", len(ong_selezionate))
        
        st.subheader("Ultimi Aggiornamenti ONG")
        st.dataframe(df_filtrato_ong[['Data', 'ONG', 'Titolo', 'Link']], width='stretch')

# ==========================================
# SCHEDA 2: GARANTE PRIVACY (La nuova analisi geografica)
# ==========================================
with tab_garante:
    if df_gpdp.empty:
        st.warning("Nessun dato Garante trovato. Assicurati che il bot abbia salvato in data/processed/")
    else:
        # Metriche in alto
        col1, col2, col3 = st.columns(3)
        col1.metric("📄 Documenti Legali Analizzati", len(df_gpdp))
        
        # Controlliamo se esiste la colonna geografica prima di fare i conteggi
        if 'Ambito_Geografico' in df_gpdp.columns:
            col2.metric("🌍 Focus USA/Internazionale", len(df_gpdp[df_gpdp['Ambito_Geografico'] == 'USA / Internazionale']))
            col3.metric("🇪🇺 Focus Europeo", len(df_gpdp[df_gpdp['Ambito_Geografico'] == 'Europa']))

            st.divider()

            # --- ANALISI GEOGRAFICA ---
            st.subheader("📍 Distribuzione Geografica dei Provvedimenti")
            col_grafico, col_tabella = st.columns([2, 1])
            
            with col_grafico:
                conteggio_geo = df_gpdp['Ambito_Geografico'].value_counts().reset_index()
                conteggio_geo.columns = ['Area', 'Numero Provvedimenti']
                
                # Grafico a torta "a ciambella" (Donut chart) con Plotly
                fig = px.pie(conteggio_geo, values='Numero Provvedimenti', names='Area', hole=0.4,
                             color='Area', 
                             color_discrete_map={'Italia':'#2ca02c', 'Europa':'#1f77b4', 'USA / Internazionale':'#ff7f0e'})
                st.plotly_chart(fig, width='stretch')
                
            with col_tabella:
                st.markdown("**Filtra i documenti:**")
                filtro_geo = st.selectbox("Seleziona Area Geografica:", ["Tutte le aree", "Italia", "Europa", "USA / Internazionale"])
                
                if filtro_geo != "Tutte le aree":
                    df_filtrato_gpdp = df_gpdp[df_gpdp['Ambito_Geografico'] == filtro_geo]
                else:
                    df_filtrato_gpdp = df_gpdp
                    
                st.dataframe(df_filtrato_gpdp[['Titolo', 'Ambito_Geografico']], hide_index=True)
        else:
            st.info("Esegui text_analysis.py per abilitare la classificazione geografica.")
            df_filtrato_gpdp = df_gpdp # Fallback se manca la colonna

        # --- BERSAGLI (ENTITÀ) ---
        st.divider()
        st.subheader("🎯 Entità e Aziende più Citate")
        
        if 'Entita_Coinvolte' in df_filtrato_gpdp.columns:
            tutte_entita = [ent for lista in df_filtrato_gpdp['Entita_Coinvolte'] for ent in lista]
            if tutte_entita:
                dati_entita = pd.Series(tutte_entita).value_counts().head(10).reset_index()
                dati_entita.columns = ['Entità', 'Citazioni']
                
                # Grafico a barre orizzontali
                fig_bar = px.bar(dati_entita, x='Citazioni', y='Entità', orientation='h', text_auto=True)
                fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}) # Ordina dal basso all'alto
                st.plotly_chart(fig_bar, width='stretch')
            else:
                st.info("Nessuna entità trovata con i filtri attuali.")