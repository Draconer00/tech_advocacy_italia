# Data Sources — Tech Advocacy Radar

Reference list of monitored sources and candidate sources for future integration.

---

## Currently Monitored Sources

### Italian Institutions
| Source | Type | Scraper |
|--------|------|---------|
| Garante Privacy (GPDP) | Enforcement decisions, rulings | `scraper_gpdp.py` |
| AGCOM | Press releases, deliberations | `scraper_agcom.py` |

### Italian Civil Society (23 organisations)
Aggregated via `scraper_ong.py`. Full list available in `PROFILI_ONG` within `scrapers/scraper_ong.py`.

Includes: Privacy Network, Hermes Center, The Good Lobby Italia, AlgorithmWatch Italy, Antigone, STRALI, Italiani Senza Cittadinanza, NINA, Slow Web, and others.

### European Regulators
| Source | Country | Scraper |
|--------|---------|---------|
| EDPB | European Union | `scraper_rss_eu.py` |
| CNIL | France | `scraper_rss_eu.py` |

AEPD (Spain) and ICO (United Kingdom) are **not currently monitored**: as of 2026-08-29 neither publishes a working general-news RSS feed (AEPD's only live feed is abandoned since 2020; ICO's official RSS page states the news feed is "currently unavailable" after a site redesign). Re-check periodically, or scrape their news pages directly if these become priority sources.

### European Parliament
RSS: all press releases, plenary press releases, and committee press releases (all committees, filtered to privacy/AI/digital-rights relevance — not restricted to LIBE/IMCO/ITRE by the feed itself). Open Data API: currently disabled — the EP migrated the API from v1 to v2 with a different response schema (ELI/JSON-LD), so the old integration 404s. Needs a schema rewrite, not just a URL fix — tracked as follow-up work, not yet done. Source: `scraper_eu_parl.py`.

### International Organisations
Included in `scraper_ong.py`: EDRi, Noyb, Access Now, Electronic Frontier Foundation, Privacy International, Open Rights Group, AlgorithmWatch, SOMO.

### Italian Tech Media (8 outlets)
Wired Italia, Punto Informatico, Agenda Digitale, Corriere Comunicazioni, Data Manager Online, Cybersecurity360, Innovation Post, StartupItalia. Source: `scraper_tech_news.py`.

### Italian Legislation
Gazzetta Ufficiale — Serie Generale (filtered to digital/privacy/AI relevance via `KEYWORD_DIGITALE_STRETTO`), Corte Costituzionale, and EU-related acts published in GU (both unfiltered — already narrow scope). RSS URLs verified live 2026-08-29 at `gazzettaufficiale.it/rss/{SG,S1,S2}`. Source: `scraper_gazzetta_ufficiale.py`.

### EU Case Law
Court of Justice of the European Union (CJEU) — single aggregated press-release feed (all subject areas, no topic-specific feed exists), filtered to digital/privacy/AI relevance via `KEYWORD_DIGITALE_STRETTO`. Feed verified live 2026-08-29 but intermittently returns HTTP 503 (~1 in 3 requests in testing; stabilizes on retry — no automatic retry implemented, next pipeline run picks it up). Source: `scraper_curia.py`.

> **NLP integration (2026-08-31):** both sources are now in `nlp/text_analysis.py`'s `FONTI` list, so they get the full NLP treatment (NER, keyword extraction, sentiment, entity linking, urgency scoring) and are written to `gazzetta_ufficiale_analyzed.csv` / `cjeu_analyzed.csv` and the SQLite table, and appear in the dashboard's Analisi Temporale tab alongside the other sources. Network Temi and Mappa Posizionamento stay ONG-specific by design, so these two institutional sources won't appear there.

---

## Candidate Sources for Future Integration

### Italian Institutions
- AGCM (Autorità Garante della Concorrenza e del Mercato) — antitrust and consumer protection. No open data/API found (2026-08-29 check); would require HTML scraping like `scraper_gpdp.py`, not RSS.
- Italian Parliament — `dati.camera.it` has downloadable datasets and a daily-updated SPARQL endpoint (verified to exist 2026-08-29, not load-tested); more complex than the RSS/CSV pattern used elsewhere in this project.
- Corte dei Conti — public spending oversight

### European Institutions
- EDPS (European Data Protection Supervisor) — evaluated and **not implemented** 2026-08-29: no RSS feed reachable via direct request (every path tried returns clean 404 or 202 with empty body; the domain sits behind a bot-challenge that doesn't respond to non-browser requests). See the note in `scraper_rss_eu.py`. Re-check with a real/headless browser if this becomes a priority.
- Council of Europe — Human Rights Commissioner
- European Commission DG Connect — digital strategy publications

### Public Datasets
- **GDPRhub full case database** — structured GDPR enforcement records worldwide (CC BY-SA 4.0), with fallback to enforcementtracker.com (CMS Law). Planned scraper: `scraper_gdpr_fines.py` (not yet implemented).
- **AI Act Monitor** — implementation tracking across EU member states
- **Digital Rights Tracker** — per-country digital rights status across Europe

---

## Adding New RSS Sources

New RSS feeds can be added by including them in the `PROFILI_ONG` dictionary in `scrapers/scraper_ong.py`. The scraper handles any standard RSS 2.0 or Atom feed without additional configuration.

For structured datasets (CSV, JSON, API), create a dedicated scraper following the conventions in any existing scraper file: SHA-256 hashing, append-only persistence, and unified schema output.
