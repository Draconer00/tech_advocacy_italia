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
    percorso_csv = os.path.join(cartella_script, '..', 'data', 'processed', 'ong_complete.csv')
    if os.path.exists(percorso_csv):
        return pd.read_csv(percorso_csv)
    # Fallback su sample se completo non disponibile
    percorso_csv_fallback = os.path.join(cartella_script, '..', 'data', 'raw', 'ong_sample.csv')
    if os.path.exists(percorso_csv_fallback):
        return pd.read_csv(percorso_csv_fallback)
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
            'sentiment': 'NEUTRALE',
            'ambito_geografico': row.get('area_geografica', 'Italia'),
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

# --- CREAZIONE DELLE SCHEDE (TABS) ---
tab_home, tab_ong, tab_garante, tab_network, tab_mappa_posizionamento = st.tabs(["🏠 Home Radar", "📢 Campagne ONG", "⚖️ Provvedimenti Garante", "🕸️ Network Temi", "📍 Mappa Posizionamento"])

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
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        fonti_selezionate = st.multiselect("Fonte", options=df_master['fonte'].unique(), default=df_master['fonte'].unique())
    with col_f2:
        aree_selezionate = st.multiselect("Area Geografica", options=df_master['ambito_geografico'].unique(), default=df_master['ambito_geografico'].unique())
    with col_f3:
        livello_allarme = st.slider("Livello Allarme Minimo", min_value=1, max_value=3, value=1)
    
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
                    
                st.dataframe(df_filtrato_gpdp[['titolo', 'Ambito_Geografico']], hide_index=True)
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

        # ✅ MOSTRA TUTTE LE ONG ANCHE QUELLE SENZA NOTIZIE
        # ✅ CENTROIDI ONG CALCOLATI SEMPRE SU TUTTO LO STORICO
        # ✅ PRIMA DI QUALSIASI FILTRO: posizione delle ONG è STABILE NEL TEMPO
        # ✅ Non cambia mai anche se filtriamo le notizie mostrate
        centroidi_ong = df_notizie.groupby('nome_organizzazione').agg({
            'score_tech_legale': 'mean',
            'score_geografia': 'mean',
            'titolo': 'count'
        }).reset_index()
        centroidi_ong.columns = ['nome', 'score_tech_legale', 'score_geografia', 'numero_articoli']
        
        # Aggiungi TUTTE le ONG da PROFILI_ONG anche se non hanno articoli
        tutte_ong = list(PROFILI_ONG.keys())
        ong_presenti = centroidi_ong['nome'].tolist()
        
        for ong_nome in tutte_ong:
            if ong_nome not in ong_presenti:
                # Posiziona al centro temporaneamente le ONG senza dati
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

        for _, notizia in df_ong.iterrows():
            titolo = notizia['titolo'][:50] + "..."
            testo_notizia = (notizia['titolo'] + " " + notizia.get('testo_completo', '')).lower()
            
            # ✅ NUOVA GERARCHIA: Notizia -> ONG -> Tema
            ong_nome = notizia['nome_organizzazione']
            
            # Cerca TUTTE le corrispondenze tematiche
            temi_corrispondenti = []
            for tema in parole_tema:
                if tema.lower() in testo_notizia:
                    tema_norm = normalizza_tema(tema)
                    if tema_norm not in temi_corrispondenti:
                        temi_corrispondenti.append(tema_norm)
            
            if ong_nome in G:
                G.add_node(titolo, color='#4bff8b', size=8, group='Notizia', shape='diamond')
                
                # ✅ Collegamento MULTIPLO: notizia a TUTTE le ONG che hanno i temi trovati
                for tema_norm in temi_corrispondenti:
                    # Per ogni tema trovato, collega la notizia a TUTTE le ONG che trattano questo tema
                    for nome_ong, dati_ong in PROFILI_ONG.items():
                        if any(normalizza_tema(t) == tema_norm for t in dati_ong.get('focus', [])):
                            if not G.has_edge(nome_ong, titolo):
                                G.add_edge(nome_ong, titolo, value=0.5, title=f"Tema: {tema_norm}")
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
        
        # Impostazioni stile Y2K BRUTALIST
        net.set_options("""
        {
          "physics": {
            "enabled": true,
            "barnesHut": {
              "gravitationalConstant": -3200,
              "centralGravity": 0.08,
              "springLength": 160,
              "springConstant": 0.009,
              "damping": 0.95,
              "avoidOverlap": 0.3
            },
            "minVelocity": 0.1,
            "stabilization": {
              "enabled": true,
              "iterations": 80,
              "fit": true,
              "onlyDynamicEdges": false,
              "updateInterval": 50
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
          },
          "nodes": {
            "borderWidth": 2,
            "borderWidthSelected": 4,
            "shape": "diamond",
            "size": 14,
            "font": {
              "size": 12,
              "face": "Verdana",
              "color": "#ffffff",
              "strokeWidth": 2,
              "strokeColor": "#000000"
            },
            "shadow": false,
            "labelHighlightBold": true
          },
          "edges": {
            "color": {
              "inherit": false,
              "color": "#44ff00",
              "highlight": "#00ffff",
              "hover": "#ff00ff"
            },
            "width": 1,
            "dashes": [5,3],
            "smooth": false
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
