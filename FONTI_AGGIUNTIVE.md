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
| AEPD | Spain | `scraper_rss_eu.py` |
| ICO | United Kingdom | `scraper_rss_eu.py` |

### European Parliament
Committees monitored: LIBE (civil liberties), IMCO (internal market), ITRE (industry/AI). Source: `scraper_eu_parl.py`.

### International Organisations
Included in `scraper_ong.py`: EDRi, Noyb, Access Now, Electronic Frontier Foundation, Privacy International, Open Rights Group, AlgorithmWatch, SOMO.

### Italian Tech Media (8 outlets)
Wired Italia, Punto Informatico, Agenda Digitale, Corriere Comunicazioni, Data Manager Online, Cybersecurity360, Innovation Post, StartupItalia. Source: `scraper_tech_news.py`.

### GDPR Enforcement Database
GDPRhub (noyb, CC BY-SA 4.0) with fallback to enforcementtracker.com (CMS Law). Source: `scraper_gdpr_fines.py`.

---

## Candidate Sources for Future Integration

### Italian Institutions
- AGCM (Autorità Garante della Concorrenza e del Mercato) — antitrust and consumer protection
- Italian Parliament — legislative monitoring via parlamento.it
- Corte dei Conti — public spending oversight

### European Institutions
- EDPS (European Data Protection Supervisor)
- Council of Europe — Human Rights Commissioner
- European Commission DG Connect — digital strategy publications

### Public Datasets
- **GDPRhub full case database** — structured GDPR enforcement records worldwide (CC BY-SA 4.0)
- **AI Act Monitor** — implementation tracking across EU member states
- **Digital Rights Tracker** — per-country digital rights status across Europe

---

## Adding New RSS Sources

New RSS feeds can be added by including them in the `PROFILI_ONG` dictionary in `scrapers/scraper_ong.py`. The scraper handles any standard RSS 2.0 or Atom feed without additional configuration.

For structured datasets (CSV, JSON, API), create a dedicated scraper following the conventions in any existing scraper file: SHA-256 hashing, append-only persistence, and unified schema output.
