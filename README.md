# Tech Advocacy Radar

An open-source civic intelligence platform for monitoring digital rights, privacy regulation, and AI governance in Italy and Europe.

---

## Overview

Tech Advocacy Radar aggregates and semantically analyses public-interest documents from institutional regulators, civil society organisations, and news sources. It transforms heterogeneous raw text into a structured, queryable knowledge base and presents the results through an interactive dashboard designed for journalists, researchers, policy professionals, and activists.

The system monitors over 35 sources continuously, processes documents in Italian and English, and provides six analytical views including network visualisation, geographic classification, temporal trend analysis, and a two-dimensional positioning map.

---

## Architecture

```
tech_advocacy_italia/
│
├── scrapers/                  ← Data ingestion layer (7 independent scrapers)
│   ├── scraper_gpdp.py        ← Italian Data Protection Authority (web scraper)
│   ├── scraper_ong.py         ← 23 civil society organisations (RSS feeds)
│   ├── scraper_gnews.py       ← GNews API (requires GNEWS_API_KEY)
│   ├── scraper_rss_eu.py      ← European regulators: EDPB, CNIL, AEPD, ICO
│   ├── scraper_agcom.py       ← AGCOM communications authority (RSS)
│   ├── scraper_tech_news.py   ← 8 Italian tech media outlets (relevance-filtered)
│   └── scraper_eu_parl.py     ← European Parliament (RSS + Open Data API)
│   # planned: scraper_gdpr_fines.py — structured GDPR sanctions layer (GDPRhub / enforcementtracker)
│
├── nlp/                       ← NLP processing layer
│   └── text_analysis.py       ← spaCy NER, TF-IDF, sentiment, active learning
│
├── app/
│   └── dashboard.py           ← Streamlit interactive dashboard (7 tabs)
│
├── data/
│   ├── raw/                   ← Append-only raw CSV files (git-ignored)
│   ├── processed/             ← NLP-enriched CSV + SQLite database (git-ignored)
│   └── utils/                 ← nlp_blacklist.csv
│
├── run_pipeline.py            ← Single-command full pipeline execution
└── requirements.txt
```

---

## Data Flow

```
GPDP (web)        →  gpdp_sample.csv       ─┐
23 NGO RSS feeds  →  ong_sample.csv         │
GNews API         →  gnews_sample.csv       │
EU regulators     →  rss_eu_sample.csv      ├─→ text_analysis.py → *_analyzed.csv → SQLite
AGCOM RSS         →  agcom_sample.csv       │         ↑
8 Tech outlets    →  tech_news_sample.csv   │  human-in-the-loop corrections
EU Parliament     →  eu_parl_sample.csv    ─┘  (dashboard feedback interface)

# planned: GDPRhub → gdpr_fines_sample.csv (structured sanctions layer, under development)
```

All sources share a unified schema. Raw files are append-only — records are never deleted, deduplication is performed by SHA-256 hash at ingestion time.

---

## NLP Pipeline

Each document is processed through the following stages:

1. **Text cleaning** — HTML removal, URL stripping, domain-specific blacklist filtering
2. **Named Entity Recognition** — spaCy `it_core_news_md`, categories: Organisation, Person, Location
3. **TF-IDF keyword extraction** — corpus-wide vectorisation (scikit-learn), top keywords per document
4. **Geographic classification** — rule-based: Italy / Europe / International
5. **Fuzzy deduplication** — `SequenceMatcher` at threshold 0.85
6. **Entity linking** — keyword-overlap scoring against NGO profile registry
7. **Urgency index** — 1–5 score via sentence-transformers embeddings + active learning classifier

---

## Dashboard

The Streamlit dashboard provides six analytical views:

| Tab | Description |
|-----|-------------|
| Home Radar | Rolling 14-day overview with urgency-coded document feed and correction interface |
| Campagne ONG | Aggregated feed from all monitored civil society organisations |
| Provvedimenti Garante | Italian Data Protection Authority decisions, filterable by geography and alert level |
| Network Temi | Force-directed graph: NGOs → focus topics → recent documents |
| Mappa Posizionamento | 2D Cartesian map: Italy↔Global (X) × Technical↔Legal (Y) |
| Analisi Temporale | Monthly document volume, keyword trends, GDPR fine amounts over time |

A standalone SQL utility (`app/db_manager.py`) provides direct database access and schema inspection; it is run separately and is not yet wired into the dashboard as a tab.

---

## Quick Start

```bash
pip install -r requirements.txt
python -m spacy download it_core_news_md

# Set GNews API key (free tier available at gnews.io)
# Windows:
$env:GNEWS_API_KEY="your_key"
# Linux/Mac:
export GNEWS_API_KEY="your_key"

# Run the full pipeline
python run_pipeline.py

# Or run steps individually
python scrapers/scraper_gpdp.py
python scrapers/scraper_ong.py
python nlp/text_analysis.py
python -m streamlit run app/dashboard.py
```

---

## Automated Scheduling

The pipeline is compatible with GitHub Actions and cron scheduling. The workflow in `.github/workflows/` runs daily at 02:00 UTC: scrapers execute, the NLP pipeline processes new documents, and the results are published as downloadable workflow **artifacts** (raw data, processed data, and SQLite database). Collected data is not versioned in the repository — each run is self-contained, and long-term persistence (if needed) is the operator's responsibility. Add `GNEWS_API_KEY` as a GitHub repository secret to enable the news scraper in CI.

---

## Key Design Principles

- **Append-only storage** — no historical data is ever overwritten or deleted
- **Full traceability** — every dashboard output traces back to a source document and URL
- **No cloud dependencies** — the entire pipeline runs locally or on GitHub Actions using open-source models
- **Human oversight** — all model predictions are inspectable and correctable through the dashboard
- **Reproducibility** — fixed random seeds, versioned dependencies, deterministic graph layouts

---

## License

This project is released under the [MIT License](LICENSE). Data collected by the scrapers is not included in the repository; users are responsible for running the ingestion pipeline against the original public sources.

---

## Related Publication

This platform is described in:

> *Tech Advocacy Radar: An NLP Pipeline for Monitoring Digital Rights in Italy and Europe* — [venue, year]
