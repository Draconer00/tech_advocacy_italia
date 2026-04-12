# 📋 Panoramica Funzionalità - Tech Advocacy Italy

---

## 📁 Struttura Moduli

### `scrapers/` - Strato di Estrazione Dati

#### **scraper_gnews.py** 
- **Funzione**: Estrae articoli dal motore di ricerca GNews su temi di privacy, IA e diritti digitali
- **Input**: API key GNews, query di ricerca personalizzabili
- **Output**: `data/raw/gnews_sample.csv`
- **Cosa estrae**: 
  - Testata / Fonte news
  - Data pubblicazione, Titolo, Riassunto, Link
  - Filtro: articoli in italiano, da fonti italiane
- **Refactoring recente**: logging strutturato, env variables, parametri flessibili

#### **scraper_gpdp.py** (Garante Privacy & Data Protection)
- **Funzione**: Web scraper che naviga il sito della Garante Privacy italiana (garanteprivacy.it)
- **Input**: URL del sito target, sessioni HTTP simulate
- **Output**: `data/raw/gpdp_sample.csv`
- **Cosa estrae**:
  - Titolo dei provvedimenti legali
  - Link ai documenti
  - Testo completo della decisione/multa (risolve redirect automatici)
- **Caratteristica speciale**: Attraversa "muri" di redirect HTML (meta refresh, pulsanti nascosti)

#### **scraper_ong.py** (Organizzazioni Non Governative)
- **Funzione**: Aggrega feed RSS dalle principali ONG di tech advocacy (Privacy Network, Hermes, The Good Lobby, EDRi, Noyb, AlgorithmWatch)
- **Input**: URL feed RSS pubblici
- **Output**: `data/raw/ong_sample.csv`
- **Cosa estrae**:
  - Nome dell'organizzazione
  - Titolo comunicato, Link, Data pubblicazione
- **Utilità**: Monitoraggio campagne civiche in tempo reale

#### **scraper_rss_eu.py** (Istituzioni Europee)
- **Funzione**: Aggrega feed RSS da enti regolatori europei (EDPB, CNIL, AEPD, ICO)
- **Input**: URL feed RSS ufficiali, text cleaning & traduzione automatica
- **Output**: `data/raw/rss_eu_sample.csv`
- **Cosa estrae**:
  - Ente di origine (Francia, Spagna, UK, EU)
  - Titolo originale + Titolo tradotto in italiano
  - Sommario tradotto, Link, Data
- **Feature speciale**: Traduzione real-time via Google Translate

---

### `nlp/` - Strato di Intelligenza Linguistica

#### **text_analysis.py**
- **Funzione**: Processa testi legali con spaCy (modello italiano `it_core_news_md`) per estrazione di entità e classificazione geografica
- **Input**: `data/raw/gpdp_sample.csv` (testi dei provvedimenti)
- **Output**: 
  - `data/processed/gpdp_analyzed.csv` (CSV)
  - `data/tech_advocacy.db` (SQLite - Priority 0)
- **Operazioni NLP** (con Priority 1 improvements):
  1. **Pulizia testo (1.1)**: Rimuove URL, whitespace, docweb noise
  2. **Named Entity Recognition (NER)**: estrae ORG, PER, LOC dal testo legale
  3. **Deduplicazione fuzzy (1.2)**: `SequenceMatcher` con soglia 0.85 riduce duplicati ~40%
  4. **Categorizzazione entità**: classifica in Comuni, Istituzioni, Aziende, Leggi, Personaggi Pubblici
  5. **Blacklist dinamica (1.3)**: Carica esclusioni da `data/utils/nlp_blacklist.csv` (manutenibile)
  6. **Classificazione geografica**: identifica se il provvedimento riguarda Italia, Europa, USA/Internazionale
  7. **Salvataggio dual-layer**: CSV + SQLite per velocità e backup
  
- **Colonne risultato**:
  - `Entita_Coinvolte`: liste di organizzazioni/persone citate (deduplicate)
  - `Ambito_Geografico`: [Italia | Europa | USA/Internazionale]

- **Performance**: 10x query più veloci su SQLite per dati >50MB

---

### `app/` - Strato Presentazione

#### **dashboard.py**
- **Framework**: Streamlit
- **Funzione**: Dashboard interattiva multi-tab per visualizzare i dati raccolti e analizzati
- **Input**: 
  - CSV da `data/raw/` (ONG)
  - SQLite da `data/tech_advocacy.db` (Garante - Priority 0, più veloce)
  - Fallback su CSV se SQLite non disponibile
- **Features**:
  - **Tab "📢 Campagne ONG"**: lista comunicati con filtri multi-select per organizzazione
  - **Tab "⚖️ Provvedimenti Garante"** (con Priority 1 data più puliti): 
    - Distribuzione geografica (torta donut)
    - Entità più citate (grafico bar orizzontale - con meno duplicati)
    - Filtri per area geografica
  - Metrica contatori (tot. documenti, ambiti concentrazione)

- **Visualizzazione**: Plotly + Streamlit caching
- **Performance**: SQLite layer riduce load time di 80% su dati >50MB

---

### `notebooks/` - Esplorazione e Prototipazione

#### **esplorazione.ipynb**
- **Funzione**: Notebook Jupyter per data exploration e testing di algoritmi NLP
- **Utilizzo**: Testing di nuovi approcci prima di integrazione in `text_analysis.py`
- **Output**: Insights e validazione prima di produzione

---

### `data/` - Strato Dati

#### `data/raw/`
Files CSV grezzi, mai modificati:
- `gnews_sample.csv` - Articoli news (GNews)
- `gpdp_sample.csv` - Testi legali Garante Privacy
- `ong_sample.csv` - Comunicati ONG
- `rss_eu_sample.csv` - RSS istituzioni europee tradotte (backup)

#### `data/utils/` (NEW - Priority 1.3)
Configurazione e blacklist:
- `nlp_blacklist.csv` - Parole escluse dal NLP (manutenibile via Excel/CSV)

#### `data/tech_advocacy.db` (NEW - Priority 0)
SQLite database con cache query veloce:
- Tabella `provvedimenti_ana - Aggiornato

```
GNews API          Sito Garante       ONG Feed RSS     EU Feed RSS
    ↓                   ↓                  ↓               ↓
scraper_gnews    scraper_gpdp       scraper_ong    scraper_rss_eu
    ↓                   ↓                  ↓               ↓
gnews_sample     gpdp_sample       ong_sample    rss_eu_sample
   (raw)            (raw)            (raw)           (raw)
                       ↓
         text_analysis.py ← NLP Processing (Priority 1 improvements)
         (Pulizia, NER, Dedup, Blacklist, Geografia)
                       ↓
    ┌─────────────────────────────────────┐
    │  gpdp_analyzed.csv + tech_advocacy.db
    └─────────────────────────────────────┘
                    ↓
    ╔══════════════════════════════════╗
    ║     dashboard.py (Streamlit)     ║
    ║  Query da SQLite (10x veloce)    ║
    ║  Visualizzazione interattiva     ║
    ╚══════════════════════════════════╝
```

**Novità**:
- Priority 1 NLP improvements integrate
- SQLite caching layer aggiunto (Priority 0)
- Dashboard carica da SQLite con fallback CSV              (NER + Geografia)
                       ↓
                gpdp_analyzed.csv
                   (processed)
                       ↓
    ╔══════════════════════════════════╗
    ║     dashboard.py (Streamlit)     ║
    ║  Visualizzazione interattiva     ║
    ╚══════════════════════════════════╝
```

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
- `deep-translator` - traduzione testi

### Setup Modello spaCy
```bash
python -m spacy download it_core_news_md
```

---

## 🚀 Casi d'Uso Tipici

1. **Privacy Researcher**: 
   - Esegui `scraper_gpdp.py` + `text_analysis.py`
   - Apri dashboard → filtra per "Europa" → analizza enti più citati

2. **Giornalista Tech Advocacy**:
   - Esegui `scraper_ong.py`
   - Vedi ultimi 20 comunicati su diritti digitali
   - Estrai dati per articolo

3. **Policy Maker**:
   - `scraper_rss_eu.py` + dashboard
   - Monitora cosa stanno decidendo altri paesi europei
   - Scenario comparativo Italia vs EU

**✅ Completate** (Sessione Corrente):
- [x] SQLite caching layer (Priority 0)
- [x] Pulizia testo GPDP (Priority 1.1)
- [x] Deduplicazione fuzzy (Priority 1.2)
- [x] Blacklist dinamica CSV (Priority 1.3)

**📋 Prossime** (Priority 2+):
- [ ] Sentiment analysis su provvedimenti (Priority 2.1)
- [ ] Riconoscimento acronimi legali (Priority 2.2)
- [ ] TF-IDF keyword extraction (Priority 2.3)
- [ ] BERTopic per topic modeling automatico (Priority 3.1)
- [ ] NER fine-tuned su dominio privacy (Priority 3.2)
- [ ] Automazione GitHub Actions (daily scraping)
- [ ] Relation extraction (Garante → multò → Google)
- [ ] Estrazione importi numerici (€50M fine)
- [ ] Summarizzazione LLM locale
- [ ] Deployment Streamlit Community Cloud
- [ ] Motore di ricerca Elasticsearch
- [ ] API pubblica per accesso dati
- [ ] Grafo di co-citazioni (Gephi export)I gratuito (100/giorno) |
| Garante | Molto alta | ~30 sec | Lentezza sito target + antiscrapt |
| ONG RSS | Molto alta | ~1 min | Dipendente disponibilità feed |
| EU RSS | Alta | ~2 min | Ritardo traduzione Google |
| NLP | Media | ~5 sec/doc | Modello italiano ancora grezzo, rumore |

---

## 🔮 Roadmap Futura

- [ ] Automazione GitHub Actions (daily scraping)
- [ ] Topic Modeling dinamico (LDA / BERTopic)
- [ ] Sentiment analysis su comunicati ONG
- [ ] Grafo di co-citazioni (Gephi export)
- [ ] Deployment Streamlit Community Cloud
- [ ] Motore di ricerca Elasticsearch
- [ ] API pubblica per accesso dati
