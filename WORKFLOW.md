# Pipeline Workflow — Tech Advocacy Radar

Detailed runbook for running each pipeline stage individually. For a quick start and architecture overview, see [README.md](README.md); this file only covers what the README doesn't: per-scraper notes and troubleshooting.

---

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   SCRAPERS  │────▶│   RAW DATA  │────▶│  NLP ENGINE │────▶│  DASHBOARD  │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
      │                    │                   │                    │
      ▼                    ▼                   ▼                    ▼
  35+ sources          CSV files         NER, TF-IDF,          7 analytical
  RSS + Web            SQLite DB         classification,       views, human
  Auto-translate       Append-only       active learning        feedback loop
```

---

## Step 1 — Data Ingestion

Each scraper is independent and can be run in any order. All scrapers append to existing files without overwriting historical data. See [README.md](README.md#quick-start) for setup.

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
python scrapers/scraper_gnews.py
```
Queries the GNews API for Italian-language articles on privacy, AI, and digital rights. Requires `GNEWS_API_KEY` (see README). Skips cleanly (exit 0) if the key isn't set. Output: `data/raw/gnews_sample.csv`.

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

### Gazzetta Ufficiale
```bash
python scrapers/scraper_gazzetta_ufficiale.py
```
Aggregates RSS feeds for series SG (Serie Generale, keyword-filtered), S1 (Corte Costituzionale), and S2 (EU acts published in GU). Output: `data/raw/gazzetta_ufficiale_sample.csv`.

### CJEU (Court of Justice of the EU)
```bash
python scrapers/scraper_curia.py
```
Aggregates the single CJEU press-release RSS feed (all subject areas), filtered to privacy/AI/digital-rights relevance. The feed intermittently returns HTTP 503 (~1 in 3 requests observed); no automatic retry — the next scheduled run picks it up. Output: `data/raw/cjeu_sample.csv`.

### Blogs, Newsletters & Extra Institutions (config-driven)
```bash
python scrapers/scraper_feeds.py
```
Generic RSS scraper driven entirely by `data/utils/feeds.csv` — one row per feed (`nome,url,tipo_fonte,trust_tier,filtro_rilevanza,lingua,attivo`). Adding a blog or Substack means adding a CSV row, not writing code. Reuses the tech-news relevance filter (when `filtro_rilevanza=si`) and the `rss_eu` translator for non-Italian feeds. `tipo_fonte`/`trust_tier` flow through the pipeline and drive the dashboard's source-category classification. Output: `data/raw/feeds_sample.csv`.

> Note on foreign-language feeds: EN/DE/FR feeds are translated to Italian before the relevance filter runs. The free Google Translate endpoint rate-limits under bursty local runs — when translation fails the text stays foreign and the Italian filter over-drops it, so such feeds yield little locally but recover in spaced CI runs. Pre-filter-then-translate is a noted follow-up.

> `scraper_gdpr_fines.py` (structured GDPR sanctions layer from GDPRhub) is planned but not yet implemented — see [FONTI_AGGIUNTIVE.md](FONTI_AGGIUNTIVE.md).

---

## Step 2 — NLP Processing

```bash
python nlp/text_analysis.py
```

Processes all ten raw sources sequentially through the stages described in the README's [NLP Pipeline](README.md#nlp-pipeline) section. Output: `data/processed/*_analyzed.csv` (one per source) and `data/tech_advocacy.db`.

---

## Step 3 — Dashboard

```bash
python -m streamlit run app/dashboard.py
```

Opens the interactive dashboard at `http://localhost:8501`.

---

## Step 4 — Topic Discovery (offline, periodic)

```bash
python nlp/topic_discovery.py
```

Runs unsupervised topic discovery (BERTopic: shared MiniLM embeddings → UMAP → HDBSCAN → c-TF-IDF) over all processed documents and writes `data/processed/topic_emergenti.csv` + `topic_emergenti_trend.csv`, which the dashboard's **Topic Emergenti** tab reads. Kept **separate from `run_pipeline.py`** on purpose: the clustering is statistical and can shift between runs, so it's a periodic exploratory pass, not a per-run step. Each topic is compared with the themes already assigned to its documents (✅ covered by a sub-theme / 🟡 inside a macro-theme, sub-theme candidate / 🔴 outside the lexicon). Promote a topic to a **sub-theme** from the dashboard tab (or edit `data/utils/temi.csv` by hand), then rerun `python nlp/text_analysis.py` to apply it — retroactively — to all documents. Options: `--min-topic N` (minimum documents per cluster, default 8).

---

## Full Pipeline (single command)

```bash
python run_pipeline.py
```

Executes all scrapers, the NLP pipeline, and launches the dashboard in sequence. The pipeline continues even if individual scrapers fail, ensuring the dashboard always opens with the most recent available data.

---

## Automated Scheduling

Same GitHub Actions workflow described in the README's [Automated Scheduling](README.md#automated-scheduling) section — daily at 02:00 UTC, results published as workflow artifacts, `GNEWS_API_KEY` required as a repository secret for the news scraper.

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
