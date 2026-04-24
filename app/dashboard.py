import streamlit as st
import pandas as pd
import os
import ast
import sqlite3
import plotly.express as px
from collections import Counter
from datetime import datetime

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

@st.cache_data
def carica_dati_unificati():
    """Unisce tutti i dati da TUTTE le fonti in un singolo dataframe standardizzato"""
    df_gpdp = carica_dati_garante()
    df_ong = carica_dati_ong()
    
    dati_unificati = []
    
    # Normalizza dati GPDP
    for _, row in df_gpdp.iterrows():
        dati_unificati.append({
            'data': row.get('data_pubblicazione', datetime.now().date().isoformat()),
            'titolo': row.get('titolo', ''),
            'fonte': 'Garante Privacy',
            'tipo': 'Provvedimento',
            'url': row.get('url', ''),
            'sentiment': row.get('Sentiment_Direzione', 'NEUTRALE'),
            'ambito_geografico': row.get('Ambito_Geografico', 'Italia'),
            'livello_allarme': 2
        })
    
    # Normalizza dati ONG
    for _, row in df_ong.iterrows():
        # Supporto sia nuovo schema che vecchio schema ONG
        nome_ong = row.get('nome_organizzazione', row.get('nome_organizzazione', 'Organizzazione'))
        
        dati_unificati.append({
            'data': row.get('data_pubblicazione', row.get('Data', datetime.now().date().isoformat())),
            'titolo': row.get('titolo', row.get('Titolo', '')),
            'fonte': nome_ong,
            'tipo': 'Comunicato ONG',
            'url': row.get('url', row.get('Link', '')),
            'sentiment': 'NEUTRALE',
            'ambito_geografico': row.get('area_geografica', 'Italia'),
            'livello_allarme': row.get('livello_allarme', 1)
        })

    df = pd.DataFrame(dati_unificati)

    df['data'] = pd.to_datetime(df['data'], errors='coerce').dt.date
    return df.sort_values('data', ascending=False).reset_index(drop=True)


df_unificato = carica_dati_unificati()
df_ong = carica_dati_ong()
df_gpdp = carica_dati_garante()

# --- CREAZIONE DELLE SCHEDE (TABS) ---
tab_home, tab_ong, tab_garante = st.tabs(["🏠 Home Radar", "📢 Campagne ONG", "⚖️ Provvedimenti Garante"])

# ==========================================
# SCHEDA 0: HOME RADAR UNIFICATO
# ==========================================
with tab_home:
    st.header("📊 Panoramica Generale")
    
    # --- KPI PRINCIPALI ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📄 Documenti ultimi 7 giorni", len(df_unificato[df_unificato['data'] >= (datetime.now().date() - pd.Timedelta(days=7))]))
    col2.metric("🔍 Fonti monitorate", df_unificato['fonte'].nunique())
    col3.metric("🌍 Aree geografiche", df_unificato['ambito_geografico'].nunique())
    col4.metric("⚠️ Livello allarme medio", round(df_unificato['livello_allarme'].mean(), 1))
    
    st.divider()
    
    # --- FILTRI UNIVERSALI ---
    st.subheader("🔍 Filtri")
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        fonti_selezionate = st.multiselect("Fonte", options=df_unificato['fonte'].unique(), default=df_unificato['fonte'].unique())
    with col_f2:
        aree_selezionate = st.multiselect("Area Geografica", options=df_unificato['ambito_geografico'].unique(), default=df_unificato['ambito_geografico'].unique())
    with col_f3:
        livello_allarme = st.slider("Livello Allarme Minimo", min_value=1, max_value=3, value=1)
    
    # Applica filtri
    df_filtrato = df_unificato[
        df_unificato['fonte'].isin(fonti_selezionate) &
        df_unificato['ambito_geografico'].isin(aree_selezionate) &
        (df_unificato['livello_allarme'] >= livello_allarme)
    ]
    
    st.divider()
    
    # --- TIMELINE GENERALE ---
    st.subheader("📅 Timeline Tutti gli Eventi")
    
    eventi_per_giorno = df_filtrato.groupby('data').size().reset_index(name='conteggio')
    
    # Forziamo l'asse X come data giornaliera, evitiamo la formattazione automatica in secondi
    fig_timeline = px.line(
        eventi_per_giorno, 
        x='data', 
        y='conteggio', 
        title='Eventi per giorno', 
        markers=True,
        labels={'conteggio': 'Numero eventi'}
    )
    
    # ✅ Correzione asse orizzontale: forza formato data e nascondi ore/minuti/secondi
    fig_timeline.update_layout(
        xaxis=dict(
            type='date',
            tickformat='%d/%m/%Y',
            dtick='D1', # Un tick al giorno
            tickmode='linear',
            showgrid=True
        ),
        hovermode='x unified'
    )
    
    st.plotly_chart(fig_timeline, width='stretch')
    
    st.divider()
    
    # --- ULTIMI EVENTI ---
    st.subheader("📌 Ultimi 20 Eventi")
    st.dataframe(
        df_filtrato[['data', 'fonte', 'tipo', 'titolo', 'livello_allarme']].head(20),
        hide_index=True,
        width='stretch'
    )

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
                options=df_ong['nome_organizzazione'].unique(),
                default=df_ong['nome_organizzazione'].unique()
            )
        
        df_filtrato_ong = df_ong[df_ong['nome_organizzazione'].isin(ong_selezionate)]
        
        with col_metriche:
            col1, col2 = st.columns(2)
            col1.metric("Comunicati Analizzati", len(df_filtrato_ong))
            col2.metric("Organizzazioni Attive", len(ong_selezionate))
        
        st.subheader("Ultimi Aggiornamenti ONG")
        st.dataframe(df_filtrato_ong[['Data', 'nome_organizzazione', 'Titolo', 'Link']], width='stretch')

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