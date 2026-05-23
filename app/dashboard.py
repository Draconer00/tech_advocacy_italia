import streamlit as st
import pandas as pd
import os
import ast
import sqlite3
import plotly.express as px
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components
from collections import Counter
from datetime import datetime
import numpy as np
import sys

# Aggiungi cartella ROOT del progetto al path (risolve import scrapers)
cartella_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, cartella_root)

from scrapers.scraper_ong import PROFILI_ONG

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
    # Priorità: dati analizzati da NLP → dati grezzi come fallback
    for percorso in [
        os.path.join(cartella_script, '..', 'data', 'processed', 'ong_analyzed.csv'),
        os.path.join(cartella_script, '..', 'data', 'raw', 'ong_sample.csv'),
    ]:
        if os.path.exists(percorso):
            return pd.read_csv(percorso)
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
        nome_ong = row.get('nome_organizzazione', 'Organizzazione')
        
        dati_unificati.append({
            'data': row.get('data_pubblicazione', row.get('Data', datetime.now().date().isoformat())),
            'titolo': row.get('titolo', row.get('Titolo', '')),
            'fonte': nome_ong,
            'tipo': 'Comunicato ONG',
            'url': row.get('url', row.get('Link', '')),
            'sentiment': row.get('Sentiment_Direzione', 'NEUTRALE'),
            'ambito_geografico': row.get('Ambito_Geografico', row.get('area_geografica', 'Italia')),
            'livello_allarme': row.get('livello_allarme', 1)
        })

    df = pd.DataFrame(dati_unificati)

    df['data'] = pd.to_datetime(df['data'], errors='coerce').dt.date
    return df.sort_values('data', ascending=False).reset_index(drop=True)


# ✅ BUG 2: Carica anche GNews
@st.cache_data
def carica_dati_gnews():
    cartella_script = os.path.dirname(os.path.abspath(__file__))
    percorso_csv = os.path.join(cartella_script, '..', 'data', 'processed', 'gnews_analyzed.csv')
    if os.path.exists(percorso_csv):
        df = pd.read_csv(percorso_csv)
        df['ong_collegata'] = df.get('ong_collegata', "")
        df['fonte'] = 'GNews'
        return df
    return pd.DataFrame()

df_unificato = carica_dati_unificati()
df_ong = carica_dati_ong()
df_gpdp = carica_dati_garante()
df_gnews = carica_dati_gnews()

# Normalizza GNews prima della concatenazione con schema standard
df_gnews_normalizzato = pd.DataFrame()
if not df_gnews.empty:
    df_gnews_normalizzato = df_gnews.apply(lambda row: pd.Series({
        'data': row.get('publishedAt', row.get('data', datetime.now().date().isoformat())),
        'titolo': row.get('title', row.get('titolo', '')),
        'fonte': row.get('source', 'GNews'),
        'tipo': 'Notizia',
        'url': row.get('url', ''),
        'sentiment': row.get('sentiment', 'NEUTRALE'),
        'ambito_geografico': row.get('ambito_geografico', 'Italia'),
        'livello_allarme': row.get('impact_score', row.get('livello_allarme', 2))
    }), axis=1)

# Unisci TUTTE le fonti con lo stesso schema
df_master = pd.concat([df_unificato, df_gnews_normalizzato], ignore_index=True)

# Rimuovi duplicati per titolo e fonte
df_master = df_master.drop_duplicates(subset=['titolo', 'fonte'], keep='first')

# Conversione data finale e ordinamento
df_master['data'] = pd.to_datetime(df_master['data'], errors='coerce').dt.date
df_master = df_master.sort_values('data', ascending=False).reset_index(drop=True)

# --- CARICAMENTO DATI AGGIUNTIVI PER ANALISI TEMPORALE ---
@st.cache_data
def carica_dati_rss_eu():
    cartella_script = os.path.dirname(os.path.abspath(__file__))
    percorso_csv = os.path.join(cartella_script, '..', 'data', 'processed', 'rss_eu_analyzed.csv')
    if os.path.exists(percorso_csv):
        return pd.read_csv(percorso_csv)
    return pd.DataFrame()

@st.cache_data
def carica_dati_tech_news():
    cartella_script = os.path.dirname(os.path.abspath(__file__))
    percorso_csv = os.path.join(cartella_script, '..', 'data', 'processed', 'tech_news_analyzed.csv')
    if os.path.exists(percorso_csv):
        return pd.read_csv(percorso_csv)
    return pd.DataFrame()

@st.cache_data
def carica_dati_eu_parl():
    cartella_script = os.path.dirname(os.path.abspath(__file__))
    percorso_csv = os.path.join(cartella_script, '..', 'data', 'processed', 'eu_parl_analyzed.csv')
    if os.path.exists(percorso_csv):
        return pd.read_csv(percorso_csv)
    return pd.DataFrame()

@st.cache_data
def carica_dati_agcom():
    cartella_script = os.path.dirname(os.path.abspath(__file__))
    percorso_csv = os.path.join(cartella_script, '..', 'data', 'processed', 'agcom_analyzed.csv')
    if os.path.exists(percorso_csv):
        return pd.read_csv(percorso_csv)
    return pd.DataFrame()

def _estrai_data_pubblicazione(df: pd.DataFrame) -> pd.Series:
    """Tenta di leggere la data da colonne note, restituisce una Series datetime con NaT per date malformate."""
    for col in ['data_pubblicazione', 'Data', 'publishedAt']:
        if col in df.columns:
            return pd.to_datetime(df[col], errors='coerce')
    return pd.Series(pd.NaT, index=df.index)

@st.cache_data
def carica_dati_per_analisi_temporale():
    """Unifica tutti i dataset in un formato standard per l'analisi temporale."""
    df_gpdp = carica_dati_garante()
    df_ong_loc = carica_dati_ong()
    df_gnews_loc = carica_dati_gnews()
    df_rss = carica_dati_rss_eu()
    df_tech = carica_dati_tech_news()
    df_eu = carica_dati_eu_parl()
    df_agcom = carica_dati_agcom()

    fonti_config = [
        (df_gpdp,   'GPDP'),
        (df_ong_loc,'ONG'),
        (df_gnews_loc, 'GNews'),
        (df_rss,    'EU RSS'),
        (df_tech,   'Tech News'),
        (df_eu,     'Parlamento EU'),
        (df_agcom,  'AGCOM'),
    ]

    blocchi = []
    for df_src, etichetta in fonti_config:
        if df_src.empty:
            continue
        blocco = pd.DataFrame()
        blocco['data'] = _estrai_data_pubblicazione(df_src)
        blocco['fonte'] = etichetta
        # Parole chiave — colonna Parole_Chiave o keywords
        for col_kw in ['Parole_Chiave', 'keywords']:
            if col_kw in df_src.columns:
                blocco['parole_chiave_raw'] = df_src[col_kw].values
                break
        else:
            blocco['parole_chiave_raw'] = None
        # Topic label se presente
        for col_tp in ['Topic_Emergente', 'topic', 'topic_label']:
            if col_tp in df_src.columns:
                blocco['topic_label'] = df_src[col_tp].values
                break
        else:
            blocco['topic_label'] = None
        # Importo EUR (solo GPDP potrebbe averlo)
        if 'importo_eur' in df_src.columns:
            blocco['importo_eur'] = pd.to_numeric(df_src['importo_eur'], errors='coerce')
        else:
            blocco['importo_eur'] = float('nan')
        blocchi.append(blocco)

    if not blocchi:
        return pd.DataFrame(columns=['data', 'fonte', 'parole_chiave_raw', 'topic_label', 'importo_eur'])

    df_unione = pd.concat(blocchi, ignore_index=True)
    df_unione['data'] = pd.to_datetime(df_unione['data'], errors='coerce')
    df_unione = df_unione.dropna(subset=['data'])
    df_unione['mese'] = df_unione['data'].dt.to_period('M')
    return df_unione

def _parse_parole_chiave(valore) -> list:
    """Converte una stringa-lista Python in lista reale, con gestione degli errori."""
    if isinstance(valore, list):
        return valore
    if not isinstance(valore, str) or not valore.strip():
        return []
    try:
        parsed = ast.literal_eval(valore)
        if isinstance(parsed, list):
            return [str(p).strip() for p in parsed if str(p).strip()]
        return []
    except Exception:
        return []

# --- CREAZIONE DELLE SCHEDE (TABS) ---
tab_home, tab_ong, tab_garante, tab_network, tab_mappa_posizionamento, tab_analisi_temporale = st.tabs(["🏠 Home Radar", "📢 Campagne ONG", "⚖️ Provvedimenti Garante", "🕸️ Network Temi", "📍 Mappa Posizionamento", "📈 Analisi Temporale"])

# ==========================================
# SCHEDA 0: HOME RADAR UNIFICATO
# ==========================================
with tab_home:
    st.header("📊 Panoramica Generale")
    
    # --- KPI PRINCIPALI ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📄 Documenti ultimi 7 giorni", len(df_master[df_master['data'] >= (datetime.now().date() - pd.Timedelta(days=7))]))
    col2.metric("🔍 Fonti monitorate", df_master['fonte'].nunique())
    col3.metric("🌍 Aree geografiche", df_master['ambito_geografico'].nunique())
    col4.metric("⚠️ Livello allarme medio", round(df_master['livello_allarme'].mean(), 1))
    
    st.divider()
    
    # --- FILTRI UNIVERSALI ---
    st.subheader("🔍 Filtri")
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    
    with col_f1:
        fonti_selezionate = st.multiselect("Fonte", options=df_master['fonte'].unique(), default=df_master['fonte'].unique())
    with col_f2:
        aree_selezionate = st.multiselect("Area Geografica", options=df_master['ambito_geografico'].unique(), default=df_master['ambito_geografico'].unique())
    with col_f3:
        livello_allarme = st.slider("Livello Allarme Minimo", min_value=1, max_value=3, value=1)
    with col_f4:
        intervallo_giorni = st.selectbox(
            "📅 Intervallo Temporale",
            options=[
                ("Ultimi 7 giorni", 7),
                ("Ultimi 14 giorni", 14),
                ("Ultimi 30 giorni", 30),
                ("Ultimi 90 giorni", 90),
                ("Tutto lo storico", 9999)
            ],
            index=1, # ✅ DEFAULT: 14 GIORNI
            format_func=lambda x: x[0]
        )
    
    # Applica filtro data
    soglia_data = datetime.now().date() - pd.Timedelta(days=intervallo_giorni[1])
    if intervallo_giorni[1] != 9999:
        df_master_filtrato = df_master[df_master['data'] >= soglia_data]
    else:
        df_master_filtrato = df_master.copy()
    
    # Applica filtri
    df_filtrato = df_master[
        df_master['fonte'].isin(fonti_selezionate) &
        df_master['ambito_geografico'].isin(aree_selezionate) &
        (df_master['livello_allarme'] >= livello_allarme)
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
    
    # === SISTEMA HUMAN-IN-THE-LOOP ===
    st.subheader("🔧 Correggi Classificazione (Active Learning)")
    
    # ✅ FILTRO FONTE PER GOLDEN STANDARD
    col_filtro_gold1, col_filtro_gold2 = st.columns(2)
    with col_filtro_gold1:
        fonti_disponibili = ["Tutte le fonti"] + list(df_unificato['fonte'].unique())
        fonte_filtro = st.selectbox("Filtra per Fonte:", options=fonti_disponibili)
    with col_filtro_gold2:
        mostra_solo_non_corrette = st.checkbox("Mostra solo notizie non ancora corrette", value=False)
    
    # Applica filtri
    df_gold = df_master.copy()
    if fonte_filtro != "Tutte le fonti":
        df_gold = df_gold[df_gold['fonte'] == fonte_filtro]
    
    # Inizializza stato sessione per modifiche
    if 'modifiche_correzione' not in st.session_state:
        st.session_state.modifiche_correzione = []
    
    # Categorie disponibili per correzione
    CATEGORIE_GEOGRAFICHE = ["Italia", "Europa", "USA / Internazionale", "Asia", "Generico"]
    ong_lista = list(PROFILI_ONG.keys())
    
    # Prepara dataframe per editor - NESSUN LIMITE DI RIGHE
    df_correzione = df_gold[['data', 'fonte', 'titolo', 'ambito_geografico', 'livello_allarme']].copy()
    df_correzione['errore_segnalato'] = False
    df_correzione['categoria_corretta'] = "Non modificato"
    df_correzione['livello_allarme_corretto'] = df_correzione['livello_allarme']
    df_correzione['ong_collegata_corretta'] = ""
    
    # Usa data_editor invece di dataframe per modifiche interattive
    col_edit, col_save = st.columns([4,1])
    
    with col_edit:
        df_modificato = st.data_editor(
            df_correzione,
            column_config={
                "data": st.column_config.DateColumn("Data", disabled=True),
                "fonte": st.column_config.TextColumn("Fonte", disabled=True),
                "titolo": st.column_config.TextColumn("Titolo", disabled=True, width="large"),
                "ambito_geografico": st.column_config.TextColumn("Classificazione AI", disabled=True),
                "errore_segnalato": st.column_config.CheckboxColumn("✅ Segnala Errore"),
            "categoria_corretta": st.column_config.SelectboxColumn(
                "🎯 Categoria Corretta",
                options=CATEGORIE_GEOGRAFICHE
            ),
            "livello_allarme": st.column_config.NumberColumn("Livello AI", disabled=True, min_value=1, max_value=5),
            "livello_allarme_corretto": st.column_config.NumberColumn(
                "⚠️ Livello Allarme Reale",
                help="Modifica per assegnare l'importanza vera di questa notizia. 1 = Bassa, 5 = Molto Alta",
                min_value=1,
                max_value=5,
                step=1
            ),
            "ong_collegata_corretta": st.column_config.SelectboxColumn(
                "🔗 ONG Associata",
                options=ong_lista,
                help="Assegna manualmente quale ONG è citata in questa notizia"
            )
        },
            hide_index=True,
            width='stretch',
            disabled=["data", "fonte", "titolo", "ambito_geografico"]
        )
    
    with col_save:
        st.markdown("<br>", unsafe_allow_html=True)
        salva_correzioni = st.button("💾 Salva Correzioni", type="primary", use_container_width=True)
        
        if salva_correzioni:
            # Estrai solo le righe modificate
            modifiche = df_modificato[df_modificato['errore_segnalato'] == True].copy()
            
            if len(modifiche) > 0:
                # Aggiungi metadata
                modifiche['timestamp_correzione'] = datetime.now().isoformat()
                modifiche['utente'] = "Operatore"
                modifiche['tipo_correzione'] = "classificazione"
                
                # Percorso file feedback
                cartella_script = os.path.dirname(os.path.abspath(__file__))
                percorso_feedback = os.path.join(cartella_script, '..', 'data', 'processed', 'training_data_feedback.csv')
                
                # Append al file (o crea se non esiste)
                if os.path.exists(percorso_feedback):
                    modifiche.to_csv(percorso_feedback, mode='a', header=False, index=False)
                else:
                    modifiche.to_csv(percorso_feedback, mode='w', header=True, index=False)
                
                st.success(f"✅ Salvataggi {len(modifiche)} correzioni. Saranno usate per il prossimo fine-tuning del modello.")
                st.balloons()
            else:
                st.info("Nessuna modifica selezionata per il salvataggio.")
    
    st.divider()
    
    # --- ULTIMI EVENTI ---
    st.subheader("📌 Ultimi 50 Eventi")
    st.dataframe(
        df_filtrato[['data', 'fonte', 'tipo', 'titolo', 'livello_allarme']].head(50),
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
        st.dataframe(df_filtrato_ong[['data_pubblicazione', 'nome_organizzazione', 'titolo', 'url']], width='stretch')

# ==========================================
# SCHEDA 2: ANALISI GEOGRAFICA GLOBALE
# ==========================================
with tab_garante:
    st.header("🌍 Analisi Geografica Tutte le Fonti")
    
    # Unisci TUTTI i dati da TUTTI gli scraper
    df_geografia_totale = df_master.copy()
    
    # --- FILTRO TIPO FONTE ---
    st.subheader("🔍 Filtra per Tipo di Fonte")
    col_f1, col_f2 = st.columns(2)
    
    with col_f1:
        filtro_tipo = st.multiselect(
            "Tipo di Contenuto:",
            options=['Provvedimento', 'Comunicato ONG', 'Notizia'],
            default=['Provvedimento', 'Comunicato ONG', 'Notizia']
        )
    
    with col_f2:
        filtro_area = st.selectbox("Filtra per Area Geografica:", 
            ["Tutte le aree", "Italia", "Europa", "USA / Internazionale", "Asia"]
        )
    
    # Applica filtri
    df_geo_filtrato = df_geografia_totale[df_geografia_totale['tipo'].isin(filtro_tipo)]
    
    if filtro_area != "Tutte le aree":
        df_geo_filtrato = df_geo_filtrato[df_geo_filtrato['ambito_geografico'] == filtro_area]
    
    # --- METRICHE GENERALI ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📄 Totale Documenti Analizzati", len(df_geo_filtrato))
    col2.metric("🇮🇹 Italia", len(df_geo_filtrato[df_geo_filtrato['ambito_geografico'] == 'Italia']))
    col3.metric("🇪🇺 Europa", len(df_geo_filtrato[df_geo_filtrato['ambito_geografico'] == 'Europa']))
    col4.metric("🌍 Mondo", len(df_geo_filtrato[df_geo_filtrato['ambito_geografico'].isin(['USA / Internazionale', 'Asia'])]))

    st.divider()

    # --- ANALISI GEOGRAFICA ---
    st.subheader("📊 Distribuzione Geografica per Tipo")
    
    col_grafico, col_dettaglio = st.columns([2, 1])
    
    with col_grafico:
        # Raggruppa per Area e Tipo
        conteggio_geo = df_geo_filtrato.groupby(['ambito_geografico', 'tipo']).size().reset_index(name='conteggio')
        
        fig = px.bar(
            conteggio_geo,
            x='ambito_geografico',
            y='conteggio',
            color='tipo',
            barmode='stack',
            title='Distribuzione Geografica per Tipologia Contenuto',
            labels={'conteggio': 'Numero Documenti', 'ambito_geografico': 'Area Geografica'}
        )
        
        st.plotly_chart(fig, width='stretch')
    
    with col_dettaglio:
        st.markdown("**Dettaglio per Fonte:**")
        conteggio_fonte = df_geo_filtrato.groupby(['fonte', 'ambito_geografico']).size().reset_index(name='conteggio')
        st.dataframe(conteggio_fonte, hide_index=True, width='stretch')

    st.divider()

    # --- ELENCO COMPLETO ---
    st.subheader("📜 Elenco Tutti i Documenti")
    
    st.dataframe(
        df_geo_filtrato[['data', 'fonte', 'tipo', 'ambito_geografico', 'titolo', 'livello_allarme']],
        hide_index=True,
        width='stretch'
    )


# ==========================================
# SCHEDA 4: MAPPA DI POSIZIONAMENTO CARTESIANO
# ==========================================
with tab_mappa_posizionamento:
    st.header("📍 Mappa di Posizionamento")
    st.markdown("""
    Piano cartesiano bidimensionale dove ogni elemento viene posizionato in base a due assi:
    
    | Asse | Estremo Sinistro | Estremo Destro |
    |------|------------------|----------------|
    | 🡪 **Asse X Orizzontale** | `-1 = Italia 🇮🇹` | `+1 = Mondo 🌍` |
    | 🡩 **Asse Y Verticale** | `-1 = Legale ⚖️` | `+1 = Tecnico ⚙️` |
    
    ✅ Punti grigi piccoli = Singole notizie
    ✅ Punti colorati grandi = Centroidi delle ONG
    ✅ La dimensione del punto dipende dal numero di articoli pubblicati
    """)

    # Importa funzione calcolo score
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from nlp.text_analysis import calcola_score_posizionamento
    from scrapers.scraper_ong import PROFILI_ONG

    # Mapping Ambito_Geografico → score X già calcolato dal NLP pipeline
    _AMBITO_SCORE = {
        'Italia':              -0.65,
        'Europa':               0.15,
        'USA / Internazionale': 0.75,
        'Asia':                 0.55,
    }
    # Baseline geografica dal profilo ONG (area_geografica)
    _AREA_ONG_SCORE = {
        'italia':          -0.5,
        'europa':           0.1,
        'unione europea':   0.1,
        'internazionale':   0.6,
        'mondiale':         0.7,
    }
    # Parole chiave bilingui per asse Y (legale=positivo, tecnico=negativo)
    _KW_LEGALE = (
        # Italiano
        "legge", "normativa", "provvedimento", "multa", "sentenza", "regolamento",
        "tribunale", "avvocato", "giurisprudenza", "ricorso", "decreto", "sanzione",
        "violazione", "illecito", "procedimento", "delibera", "autorità", "gdpr",
        "direttiva", "codice privacy", "corte", "giudice", "contenziosi",
        # Inglese
        "regulation", "enforcement", "fine", "court", "compliance",
        "lawsuit", "ruling", "judgment", "penalty", "legislation",
        "infringement", "supervisory authority", "legal action", "appeal",
        "complaint", "sanction", "legal challenge", "gdpr article",
        "data protection authority", "dpa decision",
    )
    _KW_TECNICO = (
        # Italiano
        "algoritmo", "crittografia", "software", "hardware",
        "intelligenza artificiale", "machine learning", "dataset",
        "biometri", "cybersecurity", "exploit", "vulnerabilit", "hacker",
        "cifratura", "open source", "api", "rete neurale", "llm", "deepfake",
        # Inglese
        "algorithm", "encryption", "neural network", "biometric",
        "vulnerability", "open source software", "artificial intelligence",
        "surveillance technology", "fingerprinting", "large language model",
        "deepfake", "adversarial", "model training", "training data",
        "technical standard", "interoperability",
    )

    # Baseline Y derivata dal profilo PROFILI_ONG (focus dichiarato).
    # Negativo = orientamento tecnico, positivo = orientamento legale/policy.
    _BASELINE_Y_ONG = {
        "Hermes Center":                   -0.50,  # crittografia, anonimato, censura
        "AI Forensics":                    -0.45,  # audit IA, trasparenza algoritmica
        "AlgorithmWatch":                  -0.40,  # auditing algoritmico, trasparenza IA
        "Electronic Frontier Foundation":  -0.25,  # libertà digitale, crittografia, brevetti
        "Slow Web":                        -0.20,  # decentralizzazione, etica digitale
        "NINA":                            -0.20,  # critica IA, filosofia tecnologica
        "Privacy International":           -0.15,  # sorveglianza di massa, dati, AI
        "Access Now":                      -0.15,  # internet freedom, shutdown, sorveglianza
        "Privacy Network":                 -0.05,  # dati personali, sorveglianza, IA
        "Open Rights Group":                0.00,  # GDPR, sorveglianza, open data
        "EDRi (Europa)":                    0.15,  # policy europea, diritti civili, regolamentazione
        "Consiglio d'Europa":               0.25,  # diritti umani, governance AI, etica
        "The Good Lobby Italia":            0.20,  # democrazia, trasparenza istituzionale
        "Amnesty Italia":                   0.20,  # diritti umani, giustizia
        "Antigone":                         0.25,  # carceri, giustizia penale
        "SOMO (Multinazionali)":            0.15,  # corporate accountability, diritti economici
        "Italiani Senza Cittadinanza":      0.15,  # cittadinanza, migrazioni
        "STRALI":                           0.10,  # lavoro, economia
        "EDPS Garante Privacy UE":          0.30,  # GDPR, applicazione normativa, IA
        "Commissione Europea DG Connect":   0.35,  # AI Act, DSA, DMA
        "AI Act Monitor":                   0.40,  # AI Act, regolamentazione IA, conformità
        "Noyb (Privacy UE)":                0.50,  # GDPR, contenziosi strategici, multate
    }

    def _calcola_scores(row) -> pd.Series:
        # --- Asse X: geografia ---
        ambito = str(row.get('Ambito_Geografico', '')).strip()
        score_geo = _AMBITO_SCORE.get(ambito, 0.0)
        # Sfuma con baseline ONG (area_geografica dal profilo)
        area_ong = str(row.get('area_geografica', '')).lower()
        for k, v in _AREA_ONG_SCORE.items():
            if k in area_ong:
                score_geo = round((score_geo + v) / 2, 3)
                break

        # --- Asse Y: tech/legale ---
        # 40% baseline da profilo ONG (cosa fa l'org), 60% da testo (di cosa parla l'articolo)
        nome_ong = str(row.get('nome_organizzazione', ''))
        baseline_y = _BASELINE_Y_ONG.get(nome_ong, 0.0)

        # Analisi testuale bilingue: usa titolo + fino a 1500 char di testo
        testo = ' '.join(filter(None, [
            str(row.get('titolo', '')),
            str(row.get('testo_completo', ''))[:1500],
        ])).lower()
        punti_tl = 0.0
        for p in _KW_LEGALE:
            if p in testo:
                punti_tl += 0.1
        for p in _KW_TECNICO:
            if p in testo:
                punti_tl -= 0.1
        text_signal = max(-1.0, min(1.0, punti_tl))

        score_tl = round(max(-1.0, min(1.0, 0.6 * baseline_y + 0.4 * text_signal)), 3)

        return pd.Series([score_tl, score_geo])

    if df_ong.empty:
        st.warning("Nessun dato ONG disponibile")
    else:
        # Prepara dati notizie
        df_notizie = df_ong.copy()
        df_notizie[['score_tech_legale', 'score_geografia']] = df_notizie.apply(
            _calcola_scores, axis=1
        )
        df_notizie['tipo'] = 'Notizia'
        # ✅ Rinomina colonna per compatibilità
        df_notizie['data'] = df_notizie.get('data_pubblicazione', datetime.now().date().isoformat())
        df_notizie['livello_allarme'] = df_notizie.get('livello_allarme', 1)

        # ✅ SALVATAGGIO PERMANENTE POSIZIONE ONG
        # ✅ Posizione non si perde mai anche se le notizie scompaiono
        # ✅ Viene aggiornata solamente quando ci sono nuovi dati
        cartella_script = os.path.dirname(os.path.abspath(__file__))
        percorso_posizioni_ong = os.path.join(cartella_script, '..', 'data', 'processed', 'ong_posizioni_permanenti.csv')
        
        # Calcola nuovi centroidi dai dati attuali
        centroidi_nuovi = df_notizie.groupby('nome_organizzazione').agg({
            'score_tech_legale': 'mean',
            'score_geografia': 'mean',
            'titolo': 'count'
        }).reset_index()
        centroidi_nuovi.columns = ['nome', 'score_tech_legale', 'score_geografia', 'numero_articoli']
        
        # Carica posizioni salvate permanentemente se esistono
        if os.path.exists(percorso_posizioni_ong):
            centroidi_salvati = pd.read_csv(percorso_posizioni_ong)
            
            # Aggiorna solamente le ONG che hanno nuovi dati
            for _, riga_nuova in centroidi_nuovi.iterrows():
                nome_ong = riga_nuova['nome']
                # Se abbiamo nuovi dati per questa ONG aggiorniamo la posizione
                if nome_ong in centroidi_salvati['nome'].values:
                    indice = centroidi_salvati.index[centroidi_salvati['nome'] == nome_ong][0]
                    centroidi_salvati.at[indice, 'score_tech_legale'] = riga_nuova['score_tech_legale']
                    centroidi_salvati.at[indice, 'score_geografia'] = riga_nuova['score_geografia']
                    centroidi_salvati.at[indice, 'numero_articoli'] = riga_nuova['numero_articoli']
                else:
                    # Nuova ONG mai vista prima, aggiungila
                    centroidi_salvati = pd.concat([centroidi_salvati, pd.DataFrame([riga_nuova])], ignore_index=True)
            
            centroidi_ong = centroidi_salvati
        else:
            # Nessun salvataggio esistente, usa i centroidi nuovi
            centroidi_ong = centroidi_nuovi
        
        # Salva le posizioni aggiornate in modo permanente
        centroidi_ong.to_csv(percorso_posizioni_ong, index=False)
        
        # Aggiungi TUTTE le ONG da PROFILI_ONG anche se non hanno articoli
        tutte_ong = list(PROFILI_ONG.keys())
        ong_presenti = centroidi_ong['nome'].tolist()
        
        for ong_nome in tutte_ong:
            if ong_nome not in ong_presenti:
                # Posiziona al centro temporaneamente le ONG senza dati MAI VISTE
                centroidi_ong = pd.concat([centroidi_ong, pd.DataFrame([{
                    'nome': ong_nome,
                    'score_tech_legale': 0,
                    'score_geografia': 0,
                    'numero_articoli': 0
                }])], ignore_index=True)
        
        centroidi_ong['tipo'] = 'ONG'

        # Unisci i due dataframe
        df_plot = pd.concat([
            df_notizie[['score_tech_legale', 'score_geografia', 'titolo', 'tipo', 'data', 'livello_allarme']],
            centroidi_ong.rename(columns={'nome': 'titolo'})
        ])

        # Riempie valori NaN per le notizie con dimensione fissa piccola
        df_plot['numero_articoli'] = df_plot['numero_articoli'].fillna(3)

        # ✅ Dimensione punto dipende anche da livello di allarme
        # Notizie più importanti sono più grandi
        df_plot['dimensione_finale'] = df_plot['numero_articoli'] * 1.5

        # ✅ Scala FISSA ASSOLUTA - nessuna normalizzazione dinamica
        # I valori rimangono stabili nel tempo, comparabili tra esecuzioni diverse
        # Range: -1.0 / +1.0 definito una volta per sempre nel modello
        
        # ✅ FILTRO GLOBALE GRAFICI: solo ultime 30 giorni o allarme >=2
        from datetime import datetime, timedelta
        soglia_data = datetime.now().date() - timedelta(days=30)
        
        # Gestisci valori NaN per i centroidi ONG che non hanno dati
        df_plot['data'] = df_plot['data'].fillna(datetime.now().date().isoformat())
        df_plot['livello_allarme'] = df_plot['livello_allarme'].fillna(2)
        
        # ✅ LE ONG VENGONO SEMPRE MOSTRATE SEMPRE
        mask_ong = (df_plot['tipo'] == 'ONG')
        mask_notizie = (pd.to_datetime(df_plot['data'], errors='coerce', format='ISO8601').dt.date >= soglia_data) | (df_plot['livello_allarme'] >= 2)
        mask = mask_ong | mask_notizie
        
        df_plot_grafici = df_plot[mask].copy()
        
        # ✅ Jitter leggero per separare i punti sovrapposti
        # ✅ Seed FISSO per garantire riproducibilità: stesso risultato ad ogni lancio
        rng = np.random.RandomState(seed=42)
        df_plot_grafici['score_tech_legale'] += rng.normal(0, 0.025, size=len(df_plot_grafici))
        df_plot_grafici['score_geografia'] += rng.normal(0, 0.025, size=len(df_plot_grafici))

        # Separa ONG per aggiungere etichette direttamente sui punti
        df_notizie_solo = df_plot[df_plot['tipo'] == 'Notizia']
        df_ong_solo = df_plot[df_plot['tipo'] == 'ONG']

        # Crea scatter plot base per le notizie
        fig = px.scatter(
            df_notizie_solo,
            x='score_geografia',
            y='score_tech_legale',
            color_discrete_sequence=['#666666'],
            size='dimensione_finale' if 'dimensione_finale' in df_plot.columns else None,
            size_max=18,
            opacity=0.6,
            hover_data=['titolo'],
            range_x=[-1.1, 1.1],
            range_y=[-1.1, 1.1],
            title='Mappa di Posizionamento delle Organizzazioni e Notizie'
        )

        # ✅ Aggiungi punti ONG con NOME SCRITTO DIRETTAMENTE SUL PUNTO
        # Nessun offset, nessuna freccia, perfettamente allineato sempre
        fig.add_scatter(
            x=df_ong_solo['score_geografia'],
            y=df_ong_solo['score_tech_legale'],
            mode='markers+text',
            text=df_ong_solo['titolo'],
            textposition='top center',
            marker=dict(
                color='#ff4b4b',
                size=22,
                line=dict(width=3, color='#ffffff')
            ),
            textfont=dict(
                family='Verdana',
                size=11,
                color='#ffffff'
            ),
            hovertext=df_ong_solo['titolo'],
            name='ONG'
        )

        # Aggiungi linee degli assi al centro
        fig.add_hline(y=0, line_dash="dash", line_color="#ff00ff", line_width=2)
        fig.add_vline(x=0, line_dash="dash", line_color="#ff00ff", line_width=2)

        # ✅ Stile Y2K BRUTALIST
        fig.update_layout(
            xaxis_title="🌍 Geografia: Italia ↔ Mondo",
            yaxis_title="⚙️ Tipo: Legale ↔ Tecnico",
            showlegend=True,
            height=750,
            paper_bgcolor="#000000",
            plot_bgcolor="#000000",
            font_color="#ffffff",
            xaxis=dict(
                gridcolor="#330033",
                linecolor="#ff00ff",
                zerolinecolor="#ff00ff",
                tickfont_color="#ffffff"
            ),
            yaxis=dict(
                gridcolor="#330033",
                linecolor="#ff00ff",
                zerolinecolor="#ff00ff",
                tickfont_color="#ffffff"
            )
        )

        st.plotly_chart(fig, width='stretch')

        st.info("💡 Passa con il mouse sopra i punti per vedere i dettagli. Le ONG si trovano nella media della posizione di tutte le loro notizie.")


# ==========================================
# SCHEDA 3: NETWORK MAP ONG <-> TEMI
# ==========================================
with tab_network:
    st.header("🕸️ Mappa Network: Istituzioni, Temi ed Entità")
    st.markdown("""
    Grafo basato sugli output NLP reali — nessuna corrispondenza di parole chiave codificata.
    🔴 **Nodi rossi**: Istituzioni / Organizzazioni (dimensione = numero documenti)
    🔵 **Nodi blu**: Temi / Parole chiave (dimensione = frequenza totale)
    🟠 **Nodi arancioni**: Entità nominate (aziende, istituzioni) estratte da spaCy NER
    """)

    # ------------------------------------------------------------------
    # CARICAMENTO E AGGREGAZIONE DATI (cached)
    # ------------------------------------------------------------------
    @st.cache_data
    def _carica_dati_network():
        """Carica tutti i CSV/DB e restituisce un DataFrame unificato per il network."""
        cartella_script = os.path.dirname(os.path.abspath(__file__))
        base = os.path.join(cartella_script, '..', 'data', 'processed')
        db_path = os.path.join(cartella_script, '..', 'data', 'tech_advocacy.db')

        def _leggi_csv(nome_file):
            p = os.path.join(base, nome_file)
            if os.path.exists(p):
                try:
                    return pd.read_csv(p, low_memory=False)
                except Exception:
                    return pd.DataFrame()
            return pd.DataFrame()

        blocchi = []

        # --- GPDP ---
        df_src = _leggi_csv('gpdp_analyzed.csv')
        if df_src.empty and os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                df_src = pd.read_sql('SELECT * FROM provvedimenti_analyzed', conn)
                conn.close()
            except Exception:
                df_src = pd.DataFrame()
        if not df_src.empty:
            df_src['_istituzione'] = 'GPDP'
            cols = [c for c in ['_istituzione', 'Parole_Chiave', 'Entita_Coinvolte'] if c in df_src.columns or c == '_istituzione']
            blocchi.append(df_src[cols])

        # --- ONG ---
        df_src = _leggi_csv('ong_analyzed.csv')
        if not df_src.empty:
            if 'nome_organizzazione' in df_src.columns:
                df_src['_istituzione'] = df_src['nome_organizzazione'].fillna('ONG sconosciuta')
            else:
                df_src['_istituzione'] = 'ONG'
            cols = [c for c in ['_istituzione', 'Parole_Chiave', 'Entita_Coinvolte'] if c in df_src.columns or c == '_istituzione']
            blocchi.append(df_src[cols])

        # --- RSS EU ---
        df_src = _leggi_csv('rss_eu_analyzed.csv')
        if not df_src.empty:
            if 'ente_origine' in df_src.columns:
                df_src['_istituzione'] = df_src['ente_origine'].fillna('EU RSS')
            elif 'Ente_Origine' in df_src.columns:
                df_src['_istituzione'] = df_src['Ente_Origine'].fillna('EU RSS')
            else:
                df_src['_istituzione'] = 'EU RSS'
            cols = [c for c in ['_istituzione', 'Parole_Chiave', 'Entita_Coinvolte'] if c in df_src.columns or c == '_istituzione']
            blocchi.append(df_src[cols])

        # --- AGCOM ---
        df_src = _leggi_csv('agcom_analyzed.csv')
        if not df_src.empty:
            df_src['_istituzione'] = 'AGCOM'
            cols = [c for c in ['_istituzione', 'Parole_Chiave', 'Entita_Coinvolte'] if c in df_src.columns or c == '_istituzione']
            blocchi.append(df_src[cols])

        # --- Tech News ---
        df_src = _leggi_csv('tech_news_analyzed.csv')
        if not df_src.empty:
            if 'nome_testata' in df_src.columns:
                df_src['_istituzione'] = df_src['nome_testata'].fillna('Tech News')
            elif 'ente_origine' in df_src.columns:
                df_src['_istituzione'] = df_src['ente_origine'].fillna('Tech News')
            else:
                df_src['_istituzione'] = 'Tech News'
            cols = [c for c in ['_istituzione', 'Parole_Chiave', 'Entita_Coinvolte'] if c in df_src.columns or c == '_istituzione']
            blocchi.append(df_src[cols])

        # --- Parlamento EU ---
        df_src = _leggi_csv('eu_parl_analyzed.csv')
        if not df_src.empty:
            df_src['_istituzione'] = 'Parlamento EU'
            cols = [c for c in ['_istituzione', 'Parole_Chiave', 'Entita_Coinvolte'] if c in df_src.columns or c == '_istituzione']
            blocchi.append(df_src[cols])

        # --- GDPR Fines ---
        df_src = _leggi_csv('gdpr_fines_analyzed.csv')
        if not df_src.empty:
            if 'ente_origine' in df_src.columns:
                df_src['_istituzione'] = df_src['ente_origine'].fillna('DPA')
            else:
                df_src['_istituzione'] = 'DPA'
            cols = [c for c in ['_istituzione', 'Parole_Chiave', 'Entita_Coinvolte'] if c in df_src.columns or c == '_istituzione']
            blocchi.append(df_src[cols])

        if not blocchi:
            return pd.DataFrame(columns=['_istituzione', 'Parole_Chiave', 'Entita_Coinvolte'])

        df_unito = pd.concat(blocchi, ignore_index=True)
        for col in ['Parole_Chiave', 'Entita_Coinvolte']:
            if col not in df_unito.columns:
                df_unito[col] = None
        return df_unito

    @st.cache_data
    def _aggrega_network(max_topic: int, min_peso: int, fonti_incluse: tuple):
        """Aggrega istituzioni, topic ed entità dal DataFrame unificato."""
        stopwords = {
            'di', 'del', 'della', 'delle', 'degli', 'dei', 'la', 'il', 'le', 'lo',
            'un', 'una', 'e', 'in', 'per', 'da', 'a', 'con', 'non', 'si', 'su',
            'al', 'che', 'è', 'gli', 'i', 'o', 'ha', 'ma', 'se', 'più', 'tra',
            'nei', 'nel', 'alla', 'agli', 'col', 'sui', 'dai', 'fin', 'tra', 'fra',
            'sono', 'stato', 'stati', 'come', 'cui', 'suo', 'sua', 'suoi', 'sue',
            'loro', 'questo', 'questa', 'questi', 'queste', 'quando', 'anche',
            'già', 'dopo', 'prima', 'però', 'dove', 'mentre', 'tutti',
            'the', 'of', 'and', 'to', 'is', 'it', 'on', 'at', 'by', 'as',
            'an', 'or', 'be', 'we', 'are', 'this', 'that', 'was', 'has',
            'have', 'its', 'from', 'also', 'into', 'their', 'been', 'which',
            'with', 'for', 'not', 'but', 'they', 'he', 'she', 'his', 'her',
            'all', 'can', 'will', 'one', 'were', 'had', 'would', 'about',
            'more', 'other', 'than', 'any', 'who', 'may', 'public', 'new',
            'him', 'our', 'your', 'end', 'per', 'via', 'due',
            'accessnow', 'accessnoworg',
            'div', 'span', 'class', 'href', 'style', 'src', 'alt', 'type',
            'http', 'https', 'html', 'body', 'head', 'script', 'link', 'nbsp',
            'strong', 'table', 'tbody', 'thead', 'tr', 'td', 'th', 'ul', 'li',
            'org', 'com', 'www', 'amp',
            'company', 'controller', 'processor', 'decision', 'case',
            'authority', 'protection', 'right', 'rights', 'law', 'act',
            'article', 'regulation', 'complaint', 'fine', 'penalty',
            'personal', 'subject', 'information', 'national', 'european',
            'general', 'pursuant', 'accordance', 'therefore', 'however',
            'null', 'none', 'nan', 'true', 'false',
            'spain', 'france', 'germany', 'italy', 'austria', 'belgium', 'denmark',
            'netherlands', 'sweden', 'norway', 'finland', 'poland', 'romania',
            'greece', 'portugal', 'hungary', 'czechia', 'slovakia', 'croatia',
            'bulgaria', 'ireland', 'luxembourg', 'cyprus', 'malta', 'latvia',
            'lithuania', 'estonia', 'slovenia', 'liechtenstein', 'iceland',
            'united', 'kingdom', 'swiss', 'switzerland',
            'apd', 'gba', 'hdpa', 'eff', 'ecl', 'dpa', 'dpas',
        }
        _inst_words_lower: set = set()
        df_raw = _carica_dati_network()
        if df_raw.empty:
            return {
                'istituzione_docs': Counter(), 'inst_topic': Counter(),
                'topic_freq': Counter(), 'topic_cooccur': Counter(),
                'entity_freq': Counter(), 'entity_inst': Counter(),
                'fonti_disponibili': [],
            }

        fonti_disponibili = sorted(df_raw['_istituzione'].dropna().unique().tolist())
        if fonti_incluse:
            df_raw = df_raw[df_raw['_istituzione'].isin(fonti_incluse)]

        if df_raw.empty:
            return {
                'istituzione_docs': Counter(), 'inst_topic': Counter(),
                'topic_freq': Counter(), 'topic_cooccur': Counter(),
                'entity_freq': Counter(), 'entity_inst': Counter(),
                'fonti_disponibili': fonti_disponibili,
            }

        istituzione_docs: Counter = Counter()
        inst_topic: Counter = Counter()
        topic_freq: Counter = Counter()
        topic_cooccur: Counter = Counter()
        entity_freq: Counter = Counter()
        entity_inst: Counter = Counter()

        for _, row in df_raw.iterrows():
            istituzione = str(row.get('_istituzione', '')).strip()
            if not istituzione:
                continue
            istituzione_docs[istituzione] += 1

            import re as _re
            for _w in _re.split(r'[\s\(\)/\-_,\.]+', istituzione.lower()):
                if len(_w) >= 2:
                    _inst_words_lower.add(_w)

            kw_raw = row.get('Parole_Chiave', None)
            keywords: list = []
            if isinstance(kw_raw, list):
                keywords = kw_raw
            elif isinstance(kw_raw, str) and kw_raw.strip():
                try:
                    parsed = ast.literal_eval(kw_raw)
                    if isinstance(parsed, list):
                        keywords = [str(k).strip().lower() for k in parsed if str(k).strip()]
                except Exception:
                    pass
            keywords = [
                k.lower().strip() for k in keywords
                if len(k.strip()) >= 3
                and k.strip().lower() not in stopwords
                and k.strip().lower() not in _inst_words_lower
            ]
            keywords_unici = list(dict.fromkeys(keywords))
            for kw in keywords_unici:
                topic_freq[kw] += 1
                inst_topic[(istituzione, kw)] += 1
            for i in range(len(keywords_unici)):
                for j in range(i + 1, len(keywords_unici)):
                    coppia = tuple(sorted([keywords_unici[i], keywords_unici[j]]))
                    topic_cooccur[coppia] += 1

            ent_raw = row.get('Entita_Coinvolte', None)
            entita_doc: list = []
            if isinstance(ent_raw, list):
                entita_doc = ent_raw
            elif isinstance(ent_raw, str) and ent_raw.strip():
                try:
                    parsed = ast.literal_eval(ent_raw)
                    if isinstance(parsed, list):
                        entita_doc = [str(e) for e in parsed]
                except Exception:
                    pass
            for ent_str in entita_doc:
                nome_ent = str(ent_str).split(' || ')[0].strip()
                if nome_ent and len(nome_ent) >= 2:
                    entity_freq[nome_ent] += 1
                    entity_inst[(nome_ent, istituzione)] += 1

        return {
            'istituzione_docs': istituzione_docs, 'inst_topic': inst_topic,
            'topic_freq': topic_freq, 'topic_cooccur': topic_cooccur,
            'entity_freq': entity_freq, 'entity_inst': entity_inst,
            'fonti_disponibili': fonti_disponibili,
        }

    # ------------------------------------------------------------------
    # UI CONTROLS
    # ------------------------------------------------------------------
    _df_raw_preview = _carica_dati_network()
    _tutte_le_fonti = sorted(_df_raw_preview['_istituzione'].dropna().unique().tolist()) if not _df_raw_preview.empty else []

    if not _tutte_le_fonti:
        st.warning("Nessun dato disponibile. Assicurati che gli scraper abbiano prodotto i file CSV in data/processed/.")
    else:
        col_ctrl1, col_ctrl2 = st.columns(2)
        with col_ctrl1:
            peso_minimo = st.slider("Peso minimo connessione", 1, 10, 2,
                                    help="Rimuovi gli archi con peso inferiore a questa soglia")
            max_topic_nodi = st.slider("Max nodi topic", 10, 50, 30,
                                       help="Numero massimo di topic da mostrare nel grafo")
        with col_ctrl2:
            fonti_selezionate_net = st.multiselect(
                "Fonti da includere",
                options=_tutte_le_fonti,
                default=_tutte_le_fonti,
                help="Filtra il grafo per fonte di provenienza dei documenti"
            )

        dati_agg = _aggrega_network(
            max_topic=max_topic_nodi,
            min_peso=peso_minimo,
            fonti_incluse=tuple(sorted(fonti_selezionate_net)) if fonti_selezionate_net else tuple(_tutte_le_fonti),
        )

        istituzione_docs = dati_agg['istituzione_docs']
        inst_topic = dati_agg['inst_topic']
        topic_freq = dati_agg['topic_freq']
        topic_cooccur = dati_agg['topic_cooccur']
        entity_freq = dati_agg['entity_freq']
        entity_inst = dati_agg['entity_inst']

        top_topics = set(k for k, _ in topic_freq.most_common(max_topic_nodi))
        top_entities = set(k for k, _ in entity_freq.most_common(30))

        # ------------------------------------------------------------------
        # GRAFO
        # ------------------------------------------------------------------
        G = nx.Graph()

        max_docs = max(istituzione_docs.values()) if istituzione_docs else 1
        for inst, n_docs in istituzione_docs.items():
            size = 20 + int(30 * (n_docs / max_docs))
            G.add_node(inst, color='#ff4b4b', size=size,
                       title=f"{inst}\n{n_docs} documenti", group='Istituzione')

        max_freq_topic = max(topic_freq.values()) if topic_freq else 1
        for kw in top_topics:
            freq = topic_freq[kw]
            size = 10 + int(20 * (freq / max_freq_topic))
            G.add_node(kw, color='#4b8bff', size=size,
                       title=f"Tema: {kw}\nFrequenza: {freq}", group='Topic')

        max_freq_ent = max(entity_freq.values()) if entity_freq else 1
        for ent in top_entities:
            freq = entity_freq[ent]
            size = 8 + int(15 * (freq / max_freq_ent))
            G.add_node(ent, color='#ff9f40', size=size,
                       title=f"Entità: {ent}\nMenzioni: {freq}", group='Entita')

        for (inst, kw), peso in inst_topic.items():
            if inst in G and kw in top_topics and kw in G and peso >= peso_minimo:
                G.add_edge(inst, kw, value=peso, width=max(1, min(8, peso // 2)),
                           title=f"{inst} → {kw}: {peso} documenti", color='#44aa44')

        for (kw1, kw2), co_count in topic_cooccur.items():
            if kw1 in top_topics and kw2 in top_topics and kw1 in G and kw2 in G and co_count >= 3:
                G.add_edge(kw1, kw2, value=co_count, width=1,
                           title=f"Co-occorrenza: {co_count} documenti",
                           color='#336699', dashes=True)

        for (ent, inst), peso in entity_inst.items():
            if ent in top_entities and ent in G and inst in G and entity_freq.get(ent, 0) >= 3 and peso >= peso_minimo:
                G.add_edge(ent, inst, value=peso, width=max(1, min(5, peso // 2)),
                           title=f"{ent} → {inst}: {peso} documenti", color='#aa6600')

        if len(G.nodes) > 0:
            pos = nx.spring_layout(G, seed=42, k=2.5 / max(1, len(G.nodes) ** 0.5))
            for node, (x, y) in pos.items():
                G.nodes[node]['x'] = float(x) * 1000
                G.nodes[node]['y'] = float(y) * 1000

        # Statistiche
        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
        n_istituzioni = len([n for n, d in G.nodes(data=True) if d.get('group') == 'Istituzione'])
        n_temi = len([n for n, d in G.nodes(data=True) if d.get('group') == 'Topic'])
        n_entita = len([n for n, d in G.nodes(data=True) if d.get('group') == 'Entita'])
        n_connessioni = G.number_of_edges()
        col_stat1.metric("🔴 Organizzazioni", n_istituzioni)
        col_stat2.metric("🔵 Temi", n_temi)
        col_stat3.metric("🟠 Entità", n_entita)
        col_stat4.metric("🔗 Connessioni", n_connessioni)
        st.divider()

        if len(G.nodes) == 0:
            st.warning("Nessun nodo nel grafo con i filtri selezionati. Riduci il peso minimo o aggiungi più fonti.")
        else:
            net = Network(height='720px', width='100%', bgcolor='#0a0a0a',
                          font_color='#ffffff', select_menu=False, filter_menu=False, directed=False)
            net.from_nx(G)
            net.set_options("""
            {
              "nodes": {
                "shape": "dot",
                "borderWidth": 2,
                "borderWidthSelected": 4,
                "font": {"size": 11, "face": "Verdana", "color": "#ffffff",
                         "strokeWidth": 2, "strokeColor": "#000000"},
                "shadow": false
              },
              "edges": {"color": {"inherit": false}, "smooth": false},
              "layout": {"randomSeed": 42},
              "physics": {"enabled": false},
              "interaction": {
                "hideEdgesOnDrag": false, "hover": true, "multiselect": true,
                "navigationButtons": false, "tooltipDelay": 50,
                "zoomView": true, "zoomSpeed": 0.25, "dragView": true
              }
            }
            """)

            path_html = 'network_graph_nlp.html'
            net.save_graph(path_html)
            with open(path_html, 'r', encoding='utf-8') as f:
                html_content = f.read()
            html_content = html_content.replace(
                'var options = {',
                'var options = {\n  zoomMax: 2.5,\n  zoomMin: 0.2,'
            )
            html_content = html_content.replace(
                'background-color: #0a0a0a;',
                'background: #000000;\nbackground-image: radial-gradient(#111111 1px, #000000 1px);\nbackground-size: 8px 8px;'
            )
            components.html(html_content, height=750)
            os.remove(path_html)

            st.info("💡 Trascina i nodi per esplorare la rete. Passa il mouse sopra un nodo per i dettagli.")
            st.markdown("""
**Legenda:**
- 🔴 Nodo rosso = Istituzione/ONG (dimensione proporzionale al numero di documenti)
- 🔵 Nodo blu = Tema/Parola chiave estratta da TF-IDF (dimensione = frequenza)
- 🟠 Nodo arancione = Entità nominata da spaCy NER (aziende, istituzioni, persone)
- Arco verde = Istituzione pubblica quel tema
- Arco blu tratteggiato = Due temi co-occorrono in ≥3 documenti
- Arco arancione = Entità menzionata da quell'istituzione
""")


# ==========================================
# SCHEDA 6: ANALISI TEMPORALE
# ==========================================
with tab_analisi_temporale:
    st.header("📈 Analisi Temporale")
    st.markdown("""
    Questa sezione offre due viste analitiche sull'evoluzione nel tempo dei dati raccolti:
    - **Sezione A**: Andamento dei provvedimenti/documenti per mese, raggruppati per fonte
    - **Sezione B**: Tendenze dei temi principali nelle ultime settimane
    """)

    df_temporale = carica_dati_per_analisi_temporale()

    if df_temporale.empty:
        st.warning("Nessun dato temporale disponibile. Assicurati che gli scraper abbiano prodotto i file CSV analizzati in data/processed/.")
    else:
        # --- FILTRO INTERVALLO TEMPORALE (condiviso dalle due sezioni) ---
        st.subheader("🗓️ Intervallo Temporale")
        col_filtro_temp1, col_filtro_temp2 = st.columns([2, 2])

        data_min = df_temporale['data'].min().date()
        data_max = df_temporale['data'].max().date()

        with col_filtro_temp1:
            scelta_intervallo = st.selectbox(
                "Periodo di analisi",
                options=[
                    ("Ultimi 6 mesi", 180),
                    ("Ultimo anno", 365),
                    ("Tutto lo storico", 0),
                ],
                format_func=lambda x: x[0],
                index=0
            )

        giorni_intervallo = scelta_intervallo[1]
        if giorni_intervallo > 0:
            soglia_temporale = pd.Timestamp.now() - pd.Timedelta(days=giorni_intervallo)
            df_filtrato_temp = df_temporale[df_temporale['data'] >= soglia_temporale].copy()
        else:
            df_filtrato_temp = df_temporale.copy()

        with col_filtro_temp2:
            st.metric("Documenti nel periodo selezionato", len(df_filtrato_temp))

        st.divider()

        # ==========================================
        # SEZIONE A — TIMELINE PROVVEDIMENTI
        # ==========================================
        st.subheader("📊 Sezione A — Timeline Provvedimenti per Fonte")
        st.markdown(
            "Numero di documenti pubblicati ogni mese, suddivisi per fonte di provenienza. "
            "Consente di individuare periodi di maggiore attività regolatoria o giornalistica."
        )

        if df_filtrato_temp.empty:
            st.info("Nessun documento nel periodo selezionato.")
        else:
            # Raggruppa per mese e fonte
            conteggio_mensile = (
                df_filtrato_temp
                .groupby([df_filtrato_temp['data'].dt.to_period('M').astype(str), 'fonte'])
                .size()
                .reset_index(name='conteggio')
                .rename(columns={'data': 'mese'})
            )
            conteggio_mensile = conteggio_mensile.sort_values('mese')

            fig_timeline_fonti = px.bar(
                conteggio_mensile,
                x='mese',
                y='conteggio',
                color='fonte',
                barmode='stack',
                title='Documenti per mese, raggruppati per fonte',
                labels={
                    'mese': 'Mese',
                    'conteggio': 'Numero documenti',
                    'fonte': 'Fonte'
                }
            )
            fig_timeline_fonti.update_layout(
                xaxis_title="Mese",
                yaxis_title="Numero documenti",
                legend_title="Fonte",
                hovermode='x unified',
                xaxis=dict(tickangle=-45)
            )
            st.plotly_chart(fig_timeline_fonti, width='stretch')

            # Grafico secondario: importo EUR multo (solo se la colonna esiste con valori reali)
            ha_importo_eur = (
                'importo_eur' in df_filtrato_temp.columns
                and df_filtrato_temp['importo_eur'].notna().any()
                and (df_filtrato_temp['importo_eur'] > 0).any()
            )

            if ha_importo_eur:
                st.markdown("**Totale sanzioni (EUR) per mese — solo GPDP/AGCOM**")
                df_sanzioni = df_filtrato_temp[df_filtrato_temp['importo_eur'].notna() & (df_filtrato_temp['importo_eur'] > 0)].copy()
                sanzioni_mensili = (
                    df_sanzioni
                    .groupby(df_sanzioni['data'].dt.to_period('M').astype(str))['importo_eur']
                    .sum()
                    .reset_index()
                    .rename(columns={'data': 'mese'})
                    .sort_values('mese')
                )
                fig_sanzioni = px.line(
                    sanzioni_mensili,
                    x='mese',
                    y='importo_eur',
                    markers=True,
                    title='Totale sanzioni (EUR) per mese',
                    labels={'mese': 'Mese', 'importo_eur': 'Importo totale (€)'}
                )
                fig_sanzioni.update_layout(
                    xaxis_title="Mese",
                    yaxis_title="Importo totale (€)",
                    hovermode='x unified',
                    xaxis=dict(tickangle=-45)
                )
                st.plotly_chart(fig_sanzioni, width='stretch')
            else:
                st.info(
                    "ℹ️ La colonna `importo_eur` non è presente o non contiene valori nei dati attuali. "
                    "Il grafico delle sanzioni verrà mostrato automaticamente non appena i dati saranno disponibili."
                )

        st.divider()

        # ==========================================
        # SEZIONE B — TENDENZE TEMATICHE
        # ==========================================
        st.subheader("🔍 Sezione B — Tendenze dei Temi nel Tempo")
        st.markdown(
            "Evoluzione mensile delle parole chiave/temi più frequenti estratti dai documenti. "
            "Consente di identificare quali argomenti stanno crescendo o calando di importanza."
        )

        # Estrai parole chiave da tutti i documenti nel periodo, ignorando stopword banali
        STOPWORD_KW = {
            'di', 'del', 'la', 'il', 'le', 'lo', 'un', 'una', 'e', 'in', 'per', 'da',
            'dei', 'a', 'con', 'non', 'si', 'su', 'al', 'che', 'è', 'gli', 'i', 'o',
            'ha', 'ma', 'se', 'più', 'tra', 'nei', 'della', 'delle', 'degli', 'al',
            'i', 'ii', 'iii', 'iv', 'it', 'in', 'the', 'of', 'and', 'to', 'a',
        }

        righe_kw = []
        for _, riga in df_filtrato_temp.iterrows():
            kw_lista = _parse_parole_chiave(riga.get('parole_chiave_raw'))
            mese_str = riga['data'].to_period('M').strftime('%Y-%m')
            for kw in kw_lista:
                kw_norm = kw.lower().strip()
                if kw_norm and kw_norm not in STOPWORD_KW and len(kw_norm) > 2:
                    righe_kw.append({'mese': mese_str, 'parola': kw_norm})

        if not righe_kw:
            st.info(
                "Nessuna parola chiave trovata nel periodo selezionato. "
                "Verifica che i CSV analizzati contengano la colonna `Parole_Chiave`."
            )
        else:
            df_kw = pd.DataFrame(righe_kw)

            # Top 10 parole chiave globali nel periodo
            top_parole = (
                df_kw.groupby('parola')
                .size()
                .sort_values(ascending=False)
                .head(10)
                .index.tolist()
            )

            # Pivot: mesi × parole chiave
            df_kw_pivot = (
                df_kw[df_kw['parola'].isin(top_parole)]
                .groupby(['mese', 'parola'])
                .size()
                .reset_index(name='conteggio')
                .sort_values('mese')
            )

            fig_trend = px.line(
                df_kw_pivot,
                x='mese',
                y='conteggio',
                color='parola',
                markers=True,
                title='Top 10 temi — frequenza mensile',
                labels={
                    'mese': 'Mese',
                    'conteggio': 'Occorrenze',
                    'parola': 'Tema'
                }
            )
            fig_trend.update_layout(
                xaxis_title="Mese",
                yaxis_title="Occorrenze mensili",
                legend_title="Tema",
                hovermode='x unified',
                xaxis=dict(tickangle=-45)
            )
            st.plotly_chart(fig_trend, width='stretch')

            # --- Indicatori crescita/declino (ultimi 2 mesi vs 2 mesi precedenti) ---
            mesi_ordinati = sorted(df_kw_pivot['mese'].unique())

            if len(mesi_ordinati) >= 4:
                mesi_recenti = mesi_ordinati[-2:]
                mesi_precedenti = mesi_ordinati[-4:-2]

                def _freq_media(df_p, mesi_sel):
                    sub = df_p[df_p['mese'].isin(mesi_sel)]
                    return sub.groupby('parola')['conteggio'].mean()

                freq_recente = _freq_media(df_kw_pivot, mesi_recenti)
                freq_precedente = _freq_media(df_kw_pivot, mesi_precedenti)

                confronto = pd.DataFrame({
                    'freq_recente': freq_recente,
                    'freq_precedente': freq_precedente,
                }).fillna(0)

                confronto['variazione_pct'] = (
                    (confronto['freq_recente'] - confronto['freq_precedente'])
                    / confronto['freq_precedente'].replace(0, float('nan'))
                    * 100
                ).round(1)

                confronto = confronto.dropna(subset=['variazione_pct']).sort_values('variazione_pct', ascending=False)

                st.markdown(f"**Variazione % frequenza: {mesi_precedenti[0]}–{mesi_precedenti[1]} → {mesi_recenti[0]}–{mesi_recenti[1]}**")

                col_trend_su, col_trend_giu = st.columns(2)

                with col_trend_su:
                    st.markdown("📈 **In crescita**")
                    trending_up = confronto[confronto['variazione_pct'] > 0].head(5)
                    if trending_up.empty:
                        st.info("Nessun tema in crescita rilevato.")
                    else:
                        for parola, riga in trending_up.iterrows():
                            st.metric(
                                label=parola.title(),
                                value=f"{riga['freq_recente']:.1f} occ/mese",
                                delta=f"+{riga['variazione_pct']:.0f}%"
                            )

                with col_trend_giu:
                    st.markdown("📉 **In calo**")
                    trending_down = confronto[confronto['variazione_pct'] < 0].tail(5).sort_values('variazione_pct')
                    if trending_down.empty:
                        st.info("Nessun tema in calo rilevato.")
                    else:
                        for parola, riga in trending_down.iterrows():
                            st.metric(
                                label=parola.title(),
                                value=f"{riga['freq_recente']:.1f} occ/mese",
                                delta=f"{riga['variazione_pct']:.0f}%"
                            )
            else:
                st.info(
                    "Dati insufficienti per calcolare le tendenze di crescita/calo "
                    "(sono necessari almeno 4 mesi distinti di dati)."
                )

            st.divider()

            # Tabella di riepilogo parole chiave
            st.markdown("**Tabella dettagliata — occorrenze mensili per tema**")
            df_tabella = df_kw_pivot.pivot_table(
                index='mese', columns='parola', values='conteggio', fill_value=0
            ).reset_index()
            st.dataframe(df_tabella, hide_index=True, width='stretch')
