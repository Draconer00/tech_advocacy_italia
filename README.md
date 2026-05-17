# Tech Advocacy Italy — Digital Rights Radar

## About the Project

This project maps the ecosystem of digital rights, algorithmic accountability, and data privacy advocacy in Italy and Europe. It aggregates and semantically analyzes documents from institutional regulators, civil society organizations, and news sources, transforming raw text into a structured, queryable knowledge base.

The result is an interactive **Advocacy Radar**: a Streamlit dashboard that shows which organizations are active on which topics, how the regulatory landscape is evolving, and how Italian enforcement decisions compare with European counterparts.

## Architecture

```
tech_advocacy_italia/
│
├── .github/workflows/     ← CI/CD pipeline (runs daily at 02:00 UTC)
│
├── scrapers/              ← Data extraction layer
│   ├── scraper_gpdp.py    ← Italian Data Protection Authority (web scraper)
│   ├── scraper_ong.py     ← 22 civil society RSS feeds
│   ├── scraper_gnews.py   ← GNews API (requires GNEWS_API_KEY secret)
│   ├── scraper_rss_eu.py  ← 4 European regulators (EDPB, CNIL, AEPD, ICO)
│   ├── scraper_agcom.py   ← AGCOM (comunicati, delibere, consultazioni)
│   ├── scraper_tech_news.py ← 8 Italian tech outlets, relevance-filtered
│   └── scraper_eu_parl.py ← European Parliament (RSS + Open Data API)
│
├── nlp/                   ← Intelligence layer
│   ├── text_analysis.py   ← spaCy NER, BERT sentiment, TF-IDF, active learning
│   ├── deduplication.py   ← Semantic dedup via sentence-transformers + DBSCAN
│   ├── train_classifier.py     ← XLM-RoBERTa fine-tuning on user corrections
│   └── train_impact_model.py   ← Random Forest impact classifier
│
├── app/
│   ├── dashboard.py       ← Streamlit interactive dashboard (6 tabs)
│   └── db_manager.py      ← Database inspection and maintenance UI
│
├── data/
│   ├── raw/               ← Append-only raw CSV (never overwritten)
│   ├── processed/         ← NLP-enriched CSV + SQLite unified database
│   └── utils/             ← nlp_blacklist.csv (dynamic exclusion list)
│
├── utils/
│   └── logger_config.py   ← Shared logging setup
│
├── requirements.txt
└── .env                   ← Local secrets (git-ignored)
```

## Data Flow

```
GNews API    → gnews_sample.csv   ─┐
GPDP web     → gpdp_sample.csv    ─┤
22 ONG RSS   → ong_sample.csv     ─┤
4 EU RSS     → rss_eu_sample.csv  ─┼─→ text_analysis.py → *_analyzed.csv → SQLite
AGCOM RSS    → agcom_sample.csv   ─┤             ↑
8 Tech News  → tech_news_sample.csv┤    active learning feedback
EP RSS + API → eu_parl_sample.csv ─┘    (user corrections in dashboard)
```

All sources share a unified schema (`id_univoco`, `hash_contenuto`, `testo_completo`, ...). Raw files are append-only — data is never deleted, deduplication happens by hash.

## Running Locally

```bash
pip install -r requirements.txt
python -m spacy download it_core_news_md

# Set GNews API key (get one free at gnews.io)
# Windows:
$env:GNEWS_API_KEY="your_key"
# Linux/Mac:
export GNEWS_API_KEY="your_key"

# Run scrapers
python scrapers/scraper_gpdp.py
python scrapers/scraper_ong.py
python scrapers/scraper_gnews.py
python scrapers/scraper_rss_eu.py

# Run NLP pipeline
python nlp/text_analysis.py

# Launch dashboard
python -m streamlit run app/dashboard.py
```

## Automated Pipeline (GitHub Actions)

The workflow in `.github/workflows/update_data.yml` runs automatically every night at 02:00 UTC:

1. Four scraper jobs run in parallel
2. The NLP job waits for all scrapers, downloads their artifacts, runs analysis
3. Results are committed back to the repository

To enable GNews in CI: add `GNEWS_API_KEY` as a GitHub repository secret (Settings → Secrets and variables → Actions).

## Key Features

- **Multi-source normalization** — heterogeneous sources unified to one schema
- **Multi-level deduplication** — hash (scraper level) + fuzzy (NLP level) + semantic/DBSCAN
- **NLP pipeline** — NER (spaCy), sentiment (BERT), keywords (TF-IDF corpus-level), acronym recognition
- **Active learning** — user corrections in the dashboard retrain the impact classifier at each pipeline run
- **Stable visualizations** — network graph with fixed seed, ONG positions cached permanently
- **No cloud dependencies** — everything runs locally or on GitHub Actions with open-source models
