# Tech Advocacy Italy: Legal & Civic Tech Radar ⚖️🔍

## About the Project
This project maps the ecosystem of digital rights, algorithmic fairness, and data privacy advocacy in Italy. It transitions from analyzing isolated cases (such as predictive policing tools like SARI) to providing a systemic view of the ongoing "legal battles" and civic campaigns regarding technology.

The goal is to create a dynamic **Positional Map** and an **Advocacy Radar**. By transforming qualitative text (e.g., GDPR enforcement decisions, NGO press releases, FOIA requests) into quantitative metrics through Natural Language Processing (NLP), this tool helps citizens, journalists, and researchers understand which organizations to turn to based on their specific digital rights issues.

## Project Architecture & Components

The repository is structured to ensure reproducibility and clean data engineering practices:

tech_advocacy_italia/
│
├── data/                  <-- The storage layer.
│   ├── raw/               <-- Untouched, freshly scraped CSV data from institutional sources & RSS.
│   └── processed/         <-- Clean data, enriched with NLP labels (e.g., NER tags, sentiment).
│
├── scrapers/              <-- The data extraction engines.
│   ├── scraper_gpdp.py    <-- Custom web scraper targeting the Garante Privacy (enforcement actions).
│   └── scraper_ong.py     <-- RSS/HTML scraper monitoring Italian digital rights NGOs & civic networks.
│
├── nlp/                   <-- The intelligence layer.
│   └── text_analysis.py   <-- Scripts using models like spaCy to extract entities and classify text.
│
├── app/                   <-- The frontend.
│   └── dashboard.py       <-- Streamlit dashboard code for interactive positional maps and timelines.
│
├── notebooks/
│   └── esplorazione.ipynb <-- Jupyter notebooks for initial data exploration and algorithm testing.
│
├── .gitignore             <-- Files and folders ignored by Git (e.g., .venv/ and data/raw/).
└── requirements.txt       <-- List of project dependencies (e.g., pandas, spacy, streamlit, bs4).

## Future Developments
* Automated daily data ingestion via GitHub Actions.
* Dynamic Topic Modeling to automatically detect emerging tech-rights issues in Italy.
* Public deployment of the Streamlit dashboard via Community Cloud.