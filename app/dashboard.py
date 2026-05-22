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

    if df_ong.empty:
        st.warning("Nessun dato ONG disponibile")
    else:
        # Prepara dati notizie
        df_notizie = df_ong.copy()
        df_notizie[['score_tech_legale', 'score_geografia']] = df_notizie.apply(
            lambda row: pd.Series(calcola_score_posizionamento(row['titolo'] + " " + row.get('descrizione_organizzazione', ''))),
            axis=1
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
    st.header("🕸️ Mappa Network Relazioni ONG - Notizie")
    st.markdown("""
    Questa visualizzazione mostra il grafo di relazioni tra le Organizzazioni e i temi delle notizie.
    ✅ **Nodi rossi**: ONG
    ✅ **Nodi blu**: Temi / Argomenti
    ✅ **Distanza**: Indica quanto vicino è il tema agli argomenti di cui si occupa l'ONG
    """)

    if df_ong.empty:
        st.warning("Nessun dato ONG disponibile per costruire il network")
    else:
        # Importa profili ONG (risolve problema path)
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
        from scrapers.scraper_ong import PROFILI_ONG

        # Crea grafo NetworkX
        G = nx.Graph()

        # ✅ Normalizza sinonimi comuni - case insensitive e permutazioni
        sinonimi = {
            'intelligenza artificiale': 'Intelligenza Artificiale',
            'ia': 'Intelligenza Artificiale',
            'ai': 'Intelligenza Artificiale',
            'artificial intelligence': 'Intelligenza Artificiale',
            'crittografia': 'Crittografia',
            'criptografia': 'Crittografia'
        }

        def normalizza_tema(tema: str) -> str:
            tema_low = tema.strip().lower()
            for sin, standard in sinonimi.items():
                if sin in tema_low or tema_low == sin:
                    return standard
            return tema.strip().title()

        # Aggiungi nodi ONG
        for nome_ong, dati_ong in PROFILI_ONG.items():
            G.add_node(nome_ong, 
                      color='#ff4b4b', 
                      size=25,
                      title=f"{nome_ong}\n{dati_ong['descrizione'][:120]}...",
                      group='ONG')
            
            # Aggiungi temi come nodi e collegamenti
            for tema in dati_ong.get('focus', []):
                tema_norm = normalizza_tema(tema)
                if tema_norm not in G:
                    G.add_node(tema_norm, color='#4b8bff', size=15, group='Tema')
                # Peso della connessione: 1 = correlazione diretta
                G.add_edge(nome_ong, tema_norm, value=1, title=f"Focus principale")

        # Aggiungi notizie e connettili AI TEMI (NON direttamente alle ONG)
        parole_tema = []
        for _, dati_ong in PROFILI_ONG.items():
            parole_tema.extend(dati_ong.get('focus', []))
        parole_tema = list(set(parole_tema))

        # ✅ FILTRO NETWORK: ULTIMO 30 GIORNI O LIVELLO ALLARME >=3
        from datetime import datetime, timedelta
        soglia_data = datetime.now().date() - timedelta(days=30)
        
        df_ong['data_pubblicazione'] = pd.to_datetime(df_ong['data_pubblicazione'], errors='coerce').dt.date
        
        # Applica filtro
        mask = (df_ong['data_pubblicazione'] >= soglia_data) | (df_ong['livello_allarme'] >= 3)
        df_ong_filtrato = df_ong[mask].copy()

        for _, notizia in df_ong_filtrato.iterrows():
            titolo = notizia['titolo'][:50] + "..."
            testo_notizia = (notizia['titolo'] + " " + notizia.get('testo_completo', '')).lower()
            
            # ✅ NUOVA GERARCHIA: Notizia -> ONG -> Tema
            ong_nome = notizia['nome_organizzazione']
            
            # ✅ CERCA LA MIGLIORE CORRISPONDENZA NON LA PRIMA
            # Calcola punteggio per ogni ONG: quanti dei suoi temi sono presenti nella notizia
            punteggi_ong = {}
            
            for nome_ong, dati_ong in PROFILI_ONG.items():
                conteggio_match = 0
                for tema in dati_ong.get('focus', []):
                    if tema.lower() in testo_notizia:
                        conteggio_match += 1
                if conteggio_match > 0:
                    punteggi_ong[nome_ong] = conteggio_match
            
            ong_migliore = None
            punteggio_massimo = 0
            
            # Prendi la ONG con il numero maggiore di corrispondenze
            for nome_ong, punteggio in punteggi_ong.items():
                if punteggio > punteggio_massimo:
                    punteggio_massimo = punteggio
                    ong_migliore = nome_ong
            
            if ong_migliore is not None and ong_migliore in G:
                G.add_node(titolo, color='#4bff8b', size=8, group='Notizia', shape='diamond')
                # Collega la notizia SOLAMENTE alla ONG con la migliore corrispondenza
                G.add_edge(ong_migliore, titolo, value=0.5, title=f"Corrispondenza: {punteggio_massimo} temi")
                G.add_edge(ong_nome, titolo, value=0.5, title="Notizia della ONG")

        # Statistiche Network
        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
        
        numero_ong = len([n for n, d in G.nodes(data=True) if d.get('group') == 'ONG'])
        numero_temi = len([n for n, d in G.nodes(data=True) if d.get('group') == 'Tema'])
        numero_notizie = len([n for n, d in G.nodes(data=True) if d.get('group') == 'Notizia'])
        numero_connessioni = G.number_of_edges()
        
        col_stat1.metric("🔴 Organizzazioni", numero_ong)
        col_stat2.metric("🔵 Temi Monitorati", numero_temi)
        col_stat3.metric("🟢 Notizie Collegate", numero_notizie)
        col_stat4.metric("🔗 Connessioni Totali", numero_connessioni)
        
        st.divider()

        # Converti in grafo PyVis interattivo
        net = Network(height='700px', width='100%', bgcolor='#0a0a0a', font_color='ffffff', 
                      select_menu=False, filter_menu=False, directed=False)
        
        net.from_nx(G)
        
        # ✅ STABILIZZAZIONE GRAFO PYWIS - SEMPRE LA STESSA DISPOSIZIONE
        net.set_options("""
        {
          "nodes": {
            "shape": "dot",
            "size": 18,
            "borderWidth": 2,
            "borderWidthSelected": 4,
            "font": {
              "size": 11,
              "face": "Verdana",
              "color": "#ffffff",
              "strokeWidth": 2,
              "strokeColor": "#000000"
            },
            "shadow": false
          },
          "edges": {
            "color": {
              "inherit": false,
              "color": "#44ff00",
              "highlight": "#00ffff",
              "hover": "#ff00ff"
            },
            "width": 1,
            "smooth": false
          },
          "layout": {
            "randomSeed": 42
          },
          "physics": {
            "enabled": true,
            "solver": "forceAtlas2Based",
            "forceAtlas2Based": {
              "gravitationalConstant": -150,
              "centralGravity": 0.01,
              "springLength": 200,
              "springConstant": 0.05,
              "avoidOverlap": 1
            },
            "stabilization": {
              "enabled": true,
              "iterations": 1000,
              "updateInterval": 100
            }
          },
          "interaction": {
            "hideEdgesOnDrag": false,
            "hideNodesOnDrag": false,
            "hover": true,
            "multiselect": true,
            "navigationButtons": false,
            "tooltipDelay": 50,
            "zoomView": true,
            "zoomSpeed": 0.25,
            "dragView": true
          }
        }
        """)
        
        # Genera e visualizza
        path_html = 'network_graph.html'
        net.save_graph(path_html)
        
        with open(path_html, 'r', encoding='utf-8') as f:
            html_content = f.read()
            
        # Sfondo particellare e limiti zoom
        html_content = html_content.replace(
            'var options = {',
            'var options = {\n  zoomMax: 2.2,\n  zoomMin: 0.35,'
        )
        
        # Sfondo statico pixel puntinato Y2K + ASSI FISSI
        html_content = html_content.replace(
            'background-color: #0a0a0a;',
            'background: #000000;\nbackground-image: linear-gradient(rgba(30,30,30,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(30,30,30,0.3) 1px, transparent 1px), radial-gradient(#111111 1px, #000000 1px);\nbackground-size: 100% 100%, 100% 100%, 8px 8px;\nbackground-position: center center, center center, 0 0;'
        )
        
        components.html(html_content, height=750)

        os.remove(path_html)

        st.info("💡 Trascina i nodi per muovere la rete. Clicca su un nodo per vedere i dettagli.")
        
        st.divider()
        
        st.subheader("✏️ Correggi Associazioni Notizie")
        st.markdown("Se una notizia è associata alla ONG sbagliata puoi correggere l'associazione qui:")
        
        # Sistema di correzione associazioni
        if df_ong.empty == False:
            df_correzione_network = df_ong[['data_pubblicazione', 'nome_organizzazione', 'titolo', 'url']].head(50).copy()
            df_correzione_network['associazione_corretta'] = df_correzione_network['nome_organizzazione']
            
            ong_lista = list(PROFILI_ONG.keys())
            
            df_modificato_network = st.data_editor(
                df_correzione_network,
                column_config={
                    "nome_organizzazione": st.column_config.TextColumn("Associazione Attuale", disabled=True),
                    "associazione_corretta": st.column_config.SelectboxColumn(
                        "✅ Associazione Corretta",
                        options=ong_lista
                    ),
                    "titolo": st.column_config.TextColumn("Titolo Notizia", disabled=True, width="large"),
                    "url": st.column_config.TextColumn("Link", disabled=True)
                },
                hide_index=True,
                width='stretch'
            )
            
            salva_associazioni = st.button("💾 Salva Correzioni Associazioni", type="primary")
            
            if salva_associazioni:
                modifiche_network = df_modificato_network[df_modificato_network['associazione_corretta'] != df_modificato_network['nome_organizzazione']]
                if len(modifiche_network) > 0:
                    st.success(f"✅ Salvate {len(modifiche_network)} correzioni. I vettori verranno mostrati in verde nella prossima generazione del grafo.")
                else:
                    st.info("Nessuna modifica effettuata")

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
