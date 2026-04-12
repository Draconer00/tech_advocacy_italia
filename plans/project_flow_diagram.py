import streamlit as st
import pandas as pd
import os
import plotly.express as px  # Corretto da 'ploty' a 'plotly'!

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(
    page_title="Radar Diritti Digitali",
    page_icon="🛡️",
    layout="wide"
)

# --- 2. FUNZIONI DI SUPPORTO ---

def display_project_flow_diagram():
    """Mostra il diagramma di flusso del progetto usando Mermaid."""
    st.markdown("""
    ```mermaid
    graph TD
        subgraph Data_Sources ["1. Fonti Dati"]
            A[GNews API] --> S_GNews(scraper_gnews.py)
            B[Sito Garante Privacy] --> S_GPDP(scraper_gpdp.py)
            C[ONG RSS Feeds] --> S_ONG(scraper_ong.py)
            D[EU RSS Feeds] --> S_RSS_EU(scraper_rss_eu.py)
        end

        subgraph Scrapers ["2. Raccolta Dati"]
            S_GNews --> DR_GNews(data/raw/gnews_sample.csv)
            S_GPDP --> DR_GPDP(data/raw/gpdp_sample.csv)
            S_ONG --> DR_ONG(data/raw/ong_sample.csv)
            S_RSS_EU --> DR_RSS_EU(data/raw/rss_eu_sample.csv)
        end

        subgraph NLP_Processing ["3. Analisi IA"]
            DR_GPDP --> NLP_Text(nlp/text_analysis.py)
            NLP_Text -->|Entità & Geografia| DP_GPDP(data/processed/gpdp_analyzed.csv)
        end

        subgraph Dashboard ["4. Visualizzazione"]
            DR_ONG --> D_App(app/dashboard.py)
            DP_GPDP --> D_App
            DR_GNews --> D_App
            DR_RSS_EU --> D_App
            D_App -->|Interfaccia Streamlit| User((Utente Finale))
        end
    """)

def carica_dati(percorso):
    """Carica un file CSV se esiste, altrimenti restituisce un DataFrame vuoto."""
    if os.path.exists(percorso):
        return pd.read_csv(percorso)
    return pd.DataFrame()

# --- 3. LOGICA PRINCIPALE ---

st.title("🛡️ Radar Diritti Digitali & Privacy")
st.markdown("Monitoraggio automatico di Garante Privacy, Istituzioni Europee e ONG.")

# Creazione delle schede (Tabs)
tab_analisi, tab_rassegna, tab_europa, tab_architettura = st.tabs([
    "📊 Analisi Garante", 
    "📰 Stampa Italiana", 
    "🇪🇺 Osservatorio Europa", 
    "⚙️ Architettura Workflow"
])

# --- SCHEDA 1: ANALISI GARANTE ---
with tab_analisi:
    st.header("Analisi Provvedimenti Garante Privacy")
    df_gpdp = carica_dati("data/processed/gpdp_analyzed.csv")
    
    if not df_gpdp.empty:
        st.write(f"Trovati {len(df_gpdp)} provvedimenti analizzati.")
        # Esempio di grafico se hai la colonna Categoria
        if 'Categoria' in df_gpdp.columns:
            fig = px.pie(df_gpdp, names='Categoria', title="Distribuzione Entità Coinvolte")
            st.plotly_chart(fig)
        st.dataframe(df_gpdp, use_container_width=True)
    else:
        st.info("Nessun dato analizzato trovato. Esegui prima `nlp/text_analysis.py`.")

# --- SCHEDA 2: STAMPA ITALIANA ---
with tab_rassegna:
    st.header("Rassegna Stampa (GNews)")
    df_news = carica_dati("data/raw/gnews_sample.csv")
    
    if not df_news.empty:
        for idx, row in df_news.iterrows():
            with st.expander(f"[{row['Testata']}] {row['Titolo']}"):
                st.write(row['Riassunto'])
                st.link_button("Leggi Articolo", row['Link'])
    else:
        st.warning("Esegui `scrapers/scraper_gnews.py` per vedere le notizie.")

# --- SCHEDA 3: OSSERVATORIO EUROPA ---
with tab_europa:
    st.header("News Istituzionali Europee (Tradotte)")
    df_eu = carica_dati("data/raw/rss_eu_sample.csv")
    
    if not df_eu.empty:
        st.info("Queste notizie sono state tradotte automaticamente dall'IA in fase di scraping.")
        for idx, row in df_eu.iterrows():
            with st.container(border=True):
                st.subheader(row['Titolo_Italiano'])
                st.caption(f"Fonte: {row['Ente_Origine']} | Data: {row['Data']}")
                st.write(row['Sommario_Italiano'])
                st.link_button("Fonte Originale", row['Link'])
    else:
        st.warning("Esegui `scrapers/scraper_rss_eu.py` per scaricare i dati europei.")

# --- SCHEDA 4: ARCHITETTURA ---
with tab_architettura:
    st.header("Mappa del Flusso Dati")
    st.info("Questo diagramma mostra come le informazioni si muovono dalle API esterne fino a questa Dashboard.")
    display_project_flow_diagram()
    
    with st.expander("📝 Note sul Workflow"):
        st.markdown("""
        - **Scrapers:** Raccolgono dati grezzi (CSV) ogni notte.
        - **NLP Processing:** Spacy analizza il testo per estrarre aziende e istituzioni.
        - **Data Processing:** I dati vengono puliti e salvati in `data/processed/`.
        """)

# --- FOOTER ---
st.divider()
st.caption("Tech Advocacy Italia Radar - Creato per monitorare l'ecosistema privacy.")