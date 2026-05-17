# 📋 Panoramica Funzionalità - Tech Advocacy Italy
Aggiornato al 02/05/2026

---

## 📁 Struttura Moduli

### `scrapers/` - Strato di Estrazione Dati

#### **✅ TUTTI GLI SCRAPER ADESSO HANNO STORICO PERMANENTE**
✅ Nessuna sovrascrittura ✅ Append automatico ✅ Deduplicazione ✅ Dati mantenuti per sempre

---

#### **scraper_gnews.py** 
- **Funzione**: Estrae articoli dal motore di ricerca GNews su temi di privacy, IA e diritti digitali
- **Input**: API key GNews, query di ricerca personalizzabili
- **Output**: `data/raw/gnews_sample.csv`
- **Cosa estrae**: 
  - Testata / Fonte news
  - Data pubblicazione, Titolo, Riassunto, Link
  - Filtro: articoli in italiano, da fonti italiane
- ✅ **✅ NOVITÀ 05/2026**: Storico permanente, rimosso limite 3 minuti

---

#### **scraper_gpdp.py** (Garante Privacy & Data Protection)
- **Funzione**: Web scraper che naviga il sito della Garante Privacy italiana (garanteprivacy.it)
- **Input**: URL del sito target, sessioni HTTP simulate
- **Output**: `data/raw/gpdp_sample.csv`
- **Cosa estrae**:
  - Titolo dei provvedimenti legali
  - Link ai documenti
  - Testo completo della decisione/multa (risolve redirect automatici)
- **Caratteristica speciale**: Attraversa "muri" di redirect HTML (meta refresh, pulsanti nascosti)
- ✅ **✅ NOVITÀ 05/2026**: Storico permanente

---

#### **scraper_ong.py** (Organizzazioni Non Governative)
- **Funzione**: Aggrega feed RSS dalle principali ONG di tech advocacy (Privacy Network, Hermes, The Good Lobby, EDRi, Noyb, AlgorithmWatch)
- **Input**: URL feed RSS pubblici
- **Output**: `data/raw/ong_sample.csv`
- **Cosa estrae**:
  - Nome dell'organizzazione
  - Titolo comunicato, Link, Data pubblicazione
- **Utilità**: Monitoraggio campagne civiche in tempo reale
- ✅ **✅ NOVITÀ 05/2026**: Storico permanente, deduplicazione semantica

---

#### **scraper_rss_eu.py** (Istituzioni Europee)
- **Funzione**: Aggrega feed RSS da enti regolatori europei (EDPB, CNIL, AEPD, ICO)
- **Input**: URL feed RSS ufficiali, text cleaning & traduzione automatica
- **Output**: `data/raw/rss_eu_sample.csv`
- **Cosa estrae**:
  - Ente di origine (Francia, Spagna, UK, EU)
  - Titolo originale + Titolo tradotto in italiano
  - Sommario tradotto, Link, Data
- **Feature speciale**: Traduzione real-time via Google Translate
- ✅ **✅ NOVITÀ 05/2026**: Storico permanente

---

### `nlp/` - Strato di Intelligenza Linguistica

#### **text_analysis.py**
- **Funzione**: Processa testi legali con spaCy (modello italiano `it_core_news_md`) per estrazione di entità e classificazione geografica
- **Input**: Tutti i file raw da tutti gli scraper
- **Output**: 
  - `data/processed/*.csv` (tutte le fonti)
  - `data/tech_advocacy.db` (SQLite - Database unificato)
- **Operazioni NLP**:
  1. **Pulizia testo**: Rimuove URL, whitespace, docweb noise
  2. **Named Entity Recognition (NER)**: estrae ORG, PER, LOC dal testo legale
  3. **Deduplicazione fuzzy**: `SequenceMatcher` con soglia 0.85 riduce duplicati ~40%
  4. **Categorizzazione entità**: classifica in Comuni, Istituzioni, Aziende, Leggi, Personaggi Pubblici
  5. **Blacklist dinamica**: Carica esclusioni da `data/utils/nlp_blacklist.csv`
  6. **Classificazione geografica**: identifica se il provvedimento riguarda Italia, Europa, USA/Internazionale
  7. **Active Learning**: Modello di predizione impatto che si allena sulle correzioni manuali

✅ **✅ NOVITÀ 05/2026**: Ora processa TUTTE le fonti automaticamente, non solamente il Garante

---

### `app/` - Strato Presentazione

#### **dashboard.py**
- **Framework**: Streamlit
- **Funzione**: Dashboard interattiva multi-tab per visualizzare i dati raccolti e analizzati
- **Input**: 
  - Tutti i file raw e processed
  - SQLite database unificato
- ✅ **✅ SCHEDE DISPONIBILI**:
  1. 🏠 **Home Radar** - Panoramica generale, timeline, sistema di correzione manuale
  2. 📢 **Campagne ONG** - Dati organizzazioni civiche
  3. ⚖️ **Analisi Geografica Globale** - Tutte le fonti unificate con filtri
  4. 🕸️ **Network Temi** - Grafo relazioni
  5. 📍 **Mappa Posizionamento** - Piano cartesiano bidimensionale
  6. 🗄️ **Database Manager** - Gestione completa dati

✅ **✅ NOVITÀ 05/2026**:
✅ Network Map stabile e sempre uguale ad ogni refresh
✅ Posizioni ONG permanenti salvate per sempre
✅ Filtro temporale home default 14 giorni
✅ Sistema di pulizia dati manuale
✅ Pipeline non si blocca più al primo errore

---

### `data/` - Strato Dati

#### `data/raw/`
Files CSV grezzi, storico permanente:
- `gnews_sample.csv` - Articoli news (GNews)
- `gpdp_sample.csv` - Testi legali Garante Privacy
- `ong_sample.csv` - Comunicati ONG
- `rss_eu_sample.csv` - RSS istituzioni europee tradotte

#### `data/processed/`
File analizzati con NLP:
- `gpdp_analyzed.csv` - Provvedimenti Garante con NLP
- `ong_analyzed.csv` - Comunicati ONG con NLP (sentiment, entità, keyword)
- `gnews_analyzed.csv` - Notizie GNews con NLP
- `rss_eu_analyzed.csv` - RSS europei con NLP
- `ong_posizioni_permanenti.csv` - Posizioni permanenti ONG sulla mappa
- `embeddings_cache.pkl` - Cache deduplicazione semantica
- `training_data_feedback.csv` - Golden Standard correzioni manuali

---

## 📊 Flusso Dati Aggiornato

```
GNews API          Sito Garante       ONG Feed RSS     EU Feed RSS
    ↓                   ↓                  ↓               ↓
scraper_gnews    scraper_gpdp       scraper_ong    scraper_rss_eu
    ↓                   ↓                  ↓               ↓
✅ STORICO PERMANENTE ✅  APPEND  ✅ DEDUPLICAZIONE ✅
    ↓                   ↓                  ↓               ↓
gnews_sample     gpdp_sample       ong_sample    rss_eu_sample
   (raw)            (raw)            (raw)           (raw)
    ↓                   ↓                  ↓               ↓
          text_analysis.py ← NLP Processing su TUTTE le fonti
          (Pulizia, NER, Sentiment, TF-IDF, Dedup, Active Learning)
                        ↓
     ┌──────────────────────────────────────────────┐
     │  gpdp_analyzed + ong_analyzed +              │
     │  gnews_analyzed + rss_eu_analyzed + SQLite   │
     └──────────────────────────────────────────────┘
                     ↓
     ╔══════════════════════════════════╗
     ║     dashboard.py (Streamlit)     ║
     ║  6 schede + Network Map Stabile  ║
     ║  Posizioni ONG Permanenti        ║
     ║  Database Manager + Pulizia Dati ║
     ╚══════════════════════════════════╝
```

---

## ✅ Funzionalità Completate Maggio 2026

| Funzionalità | Stato |
|---|---|
| ✅ Storico permanente tutti gli scraper | ✅ COMPLETATO |
| ✅ Network Map disposizione stabile | ✅ COMPLETATO |
| ✅ Posizioni ONG permanenti | ✅ COMPLETATO |
| ✅ Database Manager con pulizia dati | ✅ COMPLETATO |
| ✅ Pipeline non si blocca più | ✅ COMPLETATO |
| ✅ Bug apertura dashboard Windows | ✅ COMPLETATO |
| ✅ Bug associazione ONG prima corrispondenza | ✅ COMPLETATO |
| ✅ Filtro temporale home | ✅ COMPLETATO |
| ✅ Auto-pulizia righe CSV malformate | ✅ COMPLETATO |
| ✅ Compatibilità completa GitHub Actions | ✅ COMPLETATO |

---

## 🚀 Casi d'Uso Tipici

1. **Privacy Researcher**: 
   - Esegui `run_pipeline.py`
   - Apri dashboard → filtra per area geografica → analizza enti più citati

2. **Giornalista Tech Advocacy**:
   - Vedi tutti i comunicati ONG e notizie in un unico pannello
   - Usa la mappa di posizionamento per vedere gli orientamenti

3. **Policy Maker**:
   - Monitora cosa stanno decidendo altri paesi europei
   - Scenario comparativo Italia vs EU

---

## 🛠️ Configurazione e Dipendenze

### `requirements.txt`
Librerie principali:
- `pandas` - manipolazione dati
- `requests` - HTTP client per scraping
- `beautifulsoup4` - parsing HTML
- `feedparser` - parsing RSS
- `spacy` - NLP (modello italiano)
- `streamlit` - dashboard web
- `plotly` - visualizzazione interattiva
- `pyvis` - Network Graph
- `sentence-transformers` - Deduplicazione semantica
- `deep-translator` - traduzione testi

---

## 🔮 Roadmap Futura

- [ ] Sentiment analysis avanzata
- [ ] Topic Modeling dinamico BERTopic
- [ ] Estrazione automatica importi multe
- [ ] Alert cambiamento posizione ONG
- [ ] Export grafo Gephi
- [ ] Deployment pubblico

---

> Progetto Open Source, trasparente e auditabile. Nessuna dipendenza da servizi cloud proprietari.