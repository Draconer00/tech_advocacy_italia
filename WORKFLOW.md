# Pipeline Workflow — Tech Advocacy Radar

Complete reference for running the data ingestion, NLP processing, and dashboard layers.

---

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   SCRAPERS  │────▶│   RAW DATA  │────▶│  NLP ENGINE │────▶│  DASHBOARD  │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
      │                    │                   │                    │
      ▼                    ▼                   ▼                    ▼
  35+ sources          CSV files         NER, TF-IDF,         7 analytical
  RSS + Web            SQLite DB         classification,       views, human
  Auto-translate       Append-only       active learning       feedback loop
```

---

## Setup (once)

```bash
pip install -r requirements.txt
python -m spacy download it_core_news_md
```

---

## Step 1 — Data Ingestion

Each scraper is independent and can be run in any order. All scrapers append to existing files without overwriting historical data.

### GPDP — Italian Data Protection Authority
```bash
python scrapers/scraper_gpdp.py
```
Extracts enforcement decisions and rulings from garanteprivacy.it. Resolves HTML meta-refresh redirects automatically. Output: `data/raw/gpdp_sample.csv`.

### NGOs and Civil Society
```bash
python scrapers/scraper_ong.py
```
Aggregates RSS feeds from 23 civil society organisations. Applies semantic deduplication via sentence-transformers. Output: `data/raw/ong_sample.csv`.

### News (GNews API)
```bash
# Windows
$env:GNEWS_API_KEY="your_key"
# Linux/Mac
export GNEWS_API_KEY="your_key"

python scrapers/scraper_gnews.py
```
Queries the GNews API for Italian-language articles on privacy, AI, and digital rights. Requires a free API key from gnews.io. Output: `data/raw/gnews_sample.csv`.

### European Regulators
```bash
python scrapers/scraper_rss_eu.py
```
Aggregates RSS feeds from EDPB, CNIL, ICO, and AEPD. All content is automatically translated to Italian via `deep-translator`. Output: `data/raw/rss_eu_sample.csv`.

### AGCOM
```bash
python scrapers/scraper_agcom.py
```
Collects press releases, rulings, and public consultations from the AGCOM communications authority. Output: `data/raw/agcom_sample.csv`.

### Italian Tech Media
```bash
python scrapers/scraper_tech_news.py
```
Monitors 8 Italian technology outlets (Wired Italia, Punto Informatico, Agenda Digitale, and others). Filters articles by relevance to privacy, AI, GDPR, and digital regulation. Output: `data/raw/tech_news_sample.csv`.

### European Parliament
```bash
python scrapers/scraper_eu_parl.py
```
Combines EP news RSS (in Italian) with the Open Data API for structured legislative acts. Priority committees: LIBE, IMCO, ITRE. Output: `data/raw/eu_parl_sample.csv`.

### GDPR Enforcement Database
```bash
python scrapers/scraper_gdpr_fines.py
```
Imports structured penalty records from GDPRhub (CC BY-SA 4.0) with fallback to enforcementtracker.com. Normalises fine amounts across European and US decimal formats. Output: `data/raw/gdpr_fines_sample.csv`.

---

## Step 2 — NLP Processing

```bash
python nlp/text_analysis.py
```

Processes all eight raw sources sequentially:

1. Text cleaning (HTML, URLs, blacklist filtering)
2. Named Entity Recognition — spaCy `it_core_news_md`
3. TF-IDF keyword extraction — scikit-learn corpus-wide
4. Geographic classification — Italy / Europe / International
5. Fuzzy deduplication — SequenceMatcher at 0.85 threshold
6. Entity linking — keyword-overlap scoring against NGO profiles
7. Urgency index — sentence-transformers + active learning classifier

Output: `data/processed/*_analyzed.csv` (one per source) and `data/tech_advocacy.db`.

---

## Step 3 — Dashboard

```bash
python -m streamlit run app/dashboard.py
```

Opens the interactive dashboard at `http://localhost:8501`.

---

## Full Pipeline (single command)

```bash
python run_pipeline.py
```

Executes all scrapers, the NLP pipeline, and launches the dashboard in sequence. The pipeline continues even if individual scrapers fail, ensuring the dashboard always opens with the most recent available data.

---

## Automated Scheduling

The pipeline is compatible with GitHub Actions. The workflow in `.github/workflows/` runs daily at 02:00 UTC. Add `GNEWS_API_KEY` as a repository secret to enable the news scraper in CI.

All data is appended to the historical record on each run — no conflicts, no data loss.

---

## Troubleshooting

| Error | Solution |
|-------|----------|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| `No module named 'scrapers'` | Use `python -m streamlit run app/dashboard.py` |
| spaCy model missing | Run `python -m spacy download it_core_news_md` |
| GPDP timeout | The site is slow; wait and retry |
| Port 8501 in use | Add `--server.port 8502` to the streamlit command |
| `UnicodeEncodeError` on Windows | Fixed: stdout/stderr forced to UTF-8 at startup |
