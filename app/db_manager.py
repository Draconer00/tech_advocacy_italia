import streamlit as st
import pandas as pd
import os
import sqlite3
import json
from datetime import datetime
import plotly.graph_objects as go

# Configurazione pagina
st.set_page_config(
    page_title="Database Manager - Tech Advocacy Radar",
    page_icon="🗄️",
    layout="wide"
)

st.title("🗄️ Database Manager")
st.markdown("Gestisci, visualizza e interroga tutti i dati del progetto")

# ==============================================
# CARICAMENTO DATI E CONFIGURAZIONE
# ==============================================

@st.cache_data(ttl=300)
def get_available_tables():
    """Ritorna lista di tutte le tabelle e file disponibili"""
    cartella_script = os.path.dirname(os.path.abspath(__file__))
    cartella_data = os.path.join(cartella_script, '..', 'data')
    
    tabelle = []
    
    # Database SQLite
    percorso_db = os.path.join(cartella_data, 'tech_advocacy.db')
    if os.path.exists(percorso_db):
        conn = sqlite3.connect(percorso_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        sqlite_tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        tabelle.extend([("sqlite", t, percorso_db) for t in sqlite_tables])
    
    # File CSV nella cartella raw
    cartella_raw = os.path.join(cartella_data, 'raw')
    if os.path.exists(cartella_raw):
        for file in os.listdir(cartella_raw):
            if file.endswith('.csv'):
                tabelle.append(("csv", file, os.path.join(cartella_raw, file)))
    
    # File CSV nella cartella processed
    cartella_processed = os.path.join(cartella_data, 'processed')
    if os.path.exists(cartella_processed):
        for file in os.listdir(cartella_processed):
            if file.endswith('.csv'):
                tabelle.append(("csv", file, os.path.join(cartella_processed, file)))
    
    return tabelle

@st.cache_data(ttl=60)
def load_table(table_info):
    tipo, nome, percorso = table_info
    
    if tipo == 'sqlite':
        conn = sqlite3.connect(percorso)
        df = pd.read_sql(f"SELECT * FROM `{nome}`", conn)
        conn.close()
        return df
    elif tipo == 'csv':
        try:
            return pd.read_csv(
                percorso,
                on_bad_lines='skip',
                engine='python',
                quoting=3,
                sep=None
            )
        except Exception as e:
            # Modalità permissiva massima
            return pd.read_csv(
                percorso,
                on_bad_lines='skip',
                engine='python',
                error_bad_lines=False,
                warn_bad_lines=False
            )
    else:
        return pd.DataFrame()

@st.cache_data(ttl=60)
def get_table_schema(table_info):
    df = load_table(table_info)
    
    schema = []
    for colonna in df.columns:
        tipo = str(df[colonna].dtype)
        valori_unici = df[colonna].nunique()
        valori_null = df[colonna].isnull().sum()
        
        schema.append({
            'nome': colonna,
            'tipo': tipo,
            'valori_unici': valori_unici,
            'valori_null': valori_null,
            'percentuale_null': round( (valori_null / len(df)) * 100, 1)
        })
    
    return pd.DataFrame(schema), len(df)


# ==============================================
# INTERFACCIA UTENTE
# ==============================================

tab_schema, tab_tabelle, tab_query, tab_relazioni = st.tabs([
    "📋 Schema Database",
    "📊 Visualizza Tabelle",
    "⚡ Esegui Query SQL",
    "🔗 Relazioni e Struttura"
])

# ==============================================
# TAB 1: SCHEMA DATABASE
# ==============================================
with tab_schema:
    st.subheader("Schema completo del database")
    
    tabelle = get_available_tables()
    
    col_stats1, col_stats2, col_stats3, col_stats4 = st.columns(4)
    col_stats1.metric("Tabelle Totali", len(tabelle))
    
    totale_righe = 0
    totale_colonne = 0
    
    for tabella in tabelle:
        df = load_table(tabella)
        totale_righe += len(df)
        totale_colonne += len(df.columns)
    
    col_stats2.metric("Righe Totali", f"{totale_righe:,}")
    col_stats3.metric("Colonne Totali", totale_colonne)
    
    st.divider()
    
    st.subheader("Dettaglio tabelle")
    
    for tabella in tabelle:
        tipo, nome, percorso = tabella
        
        with st.expander(f"📋 {nome}"):
            schema, righe = get_table_schema(tabella)
            
            col1, col2 = st.columns([1, 3])
            col1.metric("Righe", righe)
            col1.metric("Colonne", len(schema))
            col1.metric("Tipo", tipo.upper())
            
            col2.dataframe(
                schema[['nome', 'tipo', 'valori_unici', 'valori_null', 'percentuale_null']],
                hide_index=True,
                width='stretch'
            )

# ==============================================
# TAB 2: VISUALIZZA TABELLE
# ==============================================
with tab_tabelle:
    st.subheader("Visualizza e filtra i dati")
    
    tabelle = get_available_tables()
    nome_tabelle = [nome for tipo, nome, percorso in tabelle]
    
    tabella_selezionata = st.selectbox("Scegli la tabella:", nome_tabelle)
    
    if tabella_selezionata:
        tabella_info = next(t for t in tabelle if t[1] == tabella_selezionata)
        df = load_table(tabella_info)
        
        st.subheader(f"Anteprima: {tabella_selezionata}")
        st.metric("Righe totali", len(df))
        
        # Filtro colonne
        colonne_visibili = st.multiselect(
            "Colonne da visualizzare:",
            options=df.columns,
            default=list(df.columns[:8])
        )
        
        st.dataframe(
            df[colonne_visibili].head(100),
            hide_index=True,
            width='stretch'
        )
        
        # Download
        st.download_button(
            label="📥 Scarica CSV completo",
            data=df.to_csv(index=False).encode('utf-8'),
            file_name=f"{tabella_selezionata}.csv",
            mime='text/csv'
        )

# ==============================================
# TAB 3: ESEGUI QUERY SQL
# ==============================================
with tab_query:
    st.subheader("Interrogazione SQL diretta")
    
    cartella_script = os.path.dirname(os.path.abspath(__file__))
    percorso_db = os.path.join(cartella_script, '..', 'data', 'tech_advocacy.db')
    
    if os.path.exists(percorso_db):
        st.info("✅ Connesso al database SQLite")
        
        query_default = """
SELECT * 
FROM provvedimenti_analyzed
LIMIT 10
        """
        
        query = st.text_area(
            "Inserisci la tua query SQL:",
            value=query_default,
            height=150
        )
        
        if st.button("🚀 Esegui Query", type="primary"):
            try:
                conn = sqlite3.connect(percorso_db)
                df_query = pd.read_sql(query, conn)
                conn.close()
                
                st.success(f"✅ Query eseguita con successo: {len(df_query)} risultati")
                st.dataframe(df_query, hide_index=True, width='stretch')
                
                st.download_button(
                    label="📥 Scarica risultati",
                    data=df_query.to_csv(index=False).encode('utf-8'),
                    file_name="risultati_query.csv",
                    mime='text/csv'
                )
                
            except Exception as e:
                st.error(f"❌ Errore nella query: {str(e)}")
    else:
        st.warning("⚠️ Database SQLite non trovato")

# ==============================================
# TAB 4: RELAZIONI E STRUTTURA
# ==============================================
with tab_relazioni:
    st.subheader("Schema Relazionale del Progetto")
    
    st.markdown("""
### 🗺️ Struttura Logica del Database:

| Tipo | Tabella | Chiave Primaria | Descrizione |
|---|---|---|---|
| ✅ | `provvedimenti_analyzed` | `id_univoco` | Tutti i provvedimenti del Garante Privacy analizzati con NLP |
| ✅ | `gpdp_sample.csv` | `url` | Dati grezzi scaricati dallo scraper GPDP |
| ✅ | `ong_sample.csv` | `url` | Tutti i comunicati dalle organizzazioni |
| ✅ | `gnews_sample.csv` | `url` | Articoli di stampa |
| ✅ | `rss_eu_sample.csv` | `url` | Feed RSS dalle istituzioni europee |

---

### 🔑 Chiavi comuni e campi standardizzati:

Tutte le tabelle condividono questi campi:
```
✅ id_univoco        - Hash SHA256 univoco globale
✅ data_pubblicazione  - Data ISO 8601
✅ titolo           - Titolo documento
✅ url              - Link originale
✅ fonte            - Fonte del dato
✅ testo_completo   - Contenuto testuale completo
✅ hash_contenuto   - Hash per deduplicazione
```

---

### 🔗 Relazioni:
Tutte le tabelle sono collegate tramite la **chiave univoca globale `id_univoco`** che è identica per lo stesso documento in qualsiasi tabella.

Questo permette di unire qualsiasi dato da qualsiasi fonte con una semplice query SQL.
    """)

st.divider()
st.caption(f"Ultimo aggiornamento: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")