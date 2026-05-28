# Project Overview — Tech Advocacy Radar

## Mission

Tech Advocacy Radar is an open-source civic intelligence platform that monitors, aggregates, and semantically analyses public-interest documents on digital rights, privacy regulation, and AI governance across Italy and Europe. The system is designed to be transparent, reproducible, and fully auditable: every classification traces back to a source document, and no model decision is treated as final.

---

## Module Structure

### `scrapers/` — Data Ingestion Layer

Eight independent scrapers collect documents from heterogeneous public sources. All scrapers follow a common persistence protocol: new records are appended to existing CSV files, deduplicated by SHA-256 hash, and never overwritten.

| Scraper | Source | Output |
|---------|--------|--------|
| `scraper_gpdp.py` | Italian Data Protection Authority (garanteprivacy.it) | `gpdp_sample.csv` |
| `scraper_ong.py` | 23 civil society organisations (RSS feeds) | `ong_sample.csv` |
| `scraper_gnews.py` | GNews API — Italian digital rights news | `gnews_sample.csv` |
| `scraper_rss_eu.py` | EDPB, CNIL, AEPD, ICO (auto-translated to Italian) | `rss_eu_sample.csv` |
| `scraper_agcom.py` | AGCOM communications authority | `agcom_sample.csv` |
| `scraper_tech_news.py` | 8 Italian tech media outlets (relevance-filtered) | `tech_news_sample.csv` |
| `scraper_eu_parl.py` | European Parliament RSS + Open Data API | `eu_parl_sample.csv` |
| `scraper_gdpr_fines.py` | GDPRhub enforcement database (CC BY-SA 4.0) | `gdpr_fines_sample.csv` |

All raw files share a unified schema: `id_univoco`, `hash_contenuto`, `titolo`, `testo_completo`, `url`, `data_pubblicazione`, `fonte`.

---

### `nlp/` — NLP Processing Layer

`text_analysis.py` processes all raw sources through a sequential pipeline:

1. **Text cleaning** — removes HTML artefacts, URLs, and domain-irrelevant tokens via a configurable blacklist (`data/utils/nlp_blacklist.csv`)
2. **Named Entity Recognition** — spaCy `it_core_news_md` extracts ORG, PER, LOC entities and maps them to domain categories (Company, Institution, NGO, Public Figure, Location)
3. **TF-IDF keyword extraction** — scikit-learn `TfidfVectorizer` fitted corpus-wide (max 200 features); output stored in `Parole_Chiave`
4. **Geographic classification** — rule-based classifier assigns `Italia`, `Europa`, or `USA / Internazionale` to each document
5. **Fuzzy deduplication** — `SequenceMatcher` merges near-duplicate entity strings above a 0.85 similarity threshold
6. **Entity linking** — keyword-overlap scoring against `PROFILI_ONG` assigns each document to the most relevant monitored organisation
7. **Urgency index** — sentence-transformers embeddings feed a classifier (retrained at each run on human corrections) to produce a 1–5 urgency score (`livello_allarme`)

---

### `app/` — Presentation Layer

An interactive Streamlit dashboard with seven tabs:

| Tab | Function |
|-----|----------|
| Home Radar | 14-day rolling overview, urgency-coded document feed, KPI metrics |
| ONG Campaigns | Aggregated feed from all monitored organisations, filterable |
| Network Themes | Force-directed graph: NGOs → focus topics → recent documents |
| Geographic Analysis | Cross-source unified view with geographic and source filters |
| Time Analysis | Monthly volume trends, keyword trajectories, GDPR fine amounts |
| Position Map | 2D positioning: Italy↔Global (X) × Technical↔Legal (Y) |
| Database Manager | SQL query interface, schema inspection, data retention controls |

---

### `data/` — Data Layer

```
data/
├── raw/                        ← Append-only ingestion output (git-ignored)
│   ├── gpdp_sample.csv
│   ├── ong_sample.csv
│   ├── gnews_sample.csv
│   ├── rss_eu_sample.csv
│   ├── agcom_sample.csv
│   ├── tech_news_sample.csv
│   ├── eu_parl_sample.csv
│   └── gdpr_fines_sample.csv
│
├── processed/                  ← NLP output (git-ignored)
│   ├── *_analyzed.csv          ← One file per source, NLP-enriched
│   ├── tech_advocacy.db        ← Unified SQLite database
│   ├── ong_posizioni_permanenti.csv  ← Cached NGO positions for Position Map
│   ├── embeddings_cache.pkl    ← Sentence-transformer embedding cache
│   └── training_data_feedback.csv   ← Human correction ground truth
│
└── utils/
    └── nlp_blacklist.csv       ← Configurable token exclusion list
```

#### Processed columns (per document)

| Column | Description |
|--------|-------------|
| `titolo` | Document title |
| `testo_completo` | Full cleaned text |
| `data_pubblicazione` | Normalised publication date |
| `Parole_Chiave` | TF-IDF keyword list |
| `Entita_Coinvolte` | spaCy NER output: `"Entity \|\| Category"` |
| `Ambito_Geografico` | Geographic scope classification |
| `Sentiment_Direzione` | Document tone: Positivo / Negativo / Neutro |
| `livello_allarme` | Urgency score 1–5 |
| `nome_organizzazione` | Linked NGO or institution |

---

## Human-in-the-Loop

All model outputs are correctable from the dashboard. Corrections are appended to `training_data_feedback.csv` and used to retrain the urgency classifier on the next pipeline run. This creates a continuous improvement loop without requiring changes to the pipeline code.
