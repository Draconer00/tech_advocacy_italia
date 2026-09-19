"""
Scraper RSS generico e guidato da configurazione.

A differenza degli scraper dedicati (tech_news, agcom, rss_eu...), questo legge
l'elenco dei feed da data/utils/feeds.csv: aggiungere un blog, una newsletter
Substack o un feed istituzionale diventa una riga di CSV, non un nuovo file.

Ogni feed dichiara: nome, url, tipo_fonte, trust_tier (1=istituzionale,
2=media/blog, 3=opinione), filtro_rilevanza (si/no), lingua, attivo.
I contenuti non italiani vengono tradotti; i feed rumorosi passano per il filtro
keyword condiviso con lo scraper tech_news.

Regole CLAUDE.md rispettate: timeout sulle richieste, snapshot grezzo su
fallimento estrazione, nessuno scarto silenzioso (le esclusioni per rilevanza
sono loggate e conteggiate), tipo_fonte/trust_tier propagati fino alla dashboard
per separare i fatti (atti ufficiali) dall'opinione (blog/newsletter).
"""
import os
import sys
import csv
import hashlib
import time
from datetime import datetime

import feedparser
import pandas as pd
import requests
from bs4 import BeautifulSoup

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from utils.logger_config import setup_logger
# Riuso di componenti già testati (DRY): filtro rilevanza e traduzione robusta.
from scrapers.scraper_tech_news import is_rilevante
from scrapers.scraper_rss_eu import traduci_in_italiano

logger = setup_logger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_SCRIPT_DIR, '..', 'data', 'utils', 'feeds.csv')
SNAPSHOT_DIR = os.path.join(_SCRIPT_DIR, '..', 'data', 'snapshots')
MAX_ENTRY_PER_FEED = 15
_TIMEOUT = 15
_USER_AGENT = "Mozilla/5.0 (compatible; AdvocacyRadar/1.0)"

_VERO = ('si', 'sì', 'true', '1', 'yes')


def pulisci_html(testo: str) -> str:
    if not testo:
        return ""
    return BeautifulSoup(testo, "html.parser").get_text(separator=" ").strip()


def carica_config(percorso: str = CONFIG_PATH) -> list[dict]:
    """Legge l'elenco dei feed dal CSV di configurazione (solo righe attive)."""
    if not os.path.exists(percorso):
        logger.error("Config feed non trovata: %s", percorso)
        return []
    feeds = []
    with open(percorso, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if str(row.get('attivo', 'si')).strip().lower() in _VERO:
                feeds.append(row)
    logger.info("Config feed caricata: %d feed attivi", len(feeds))
    return feeds


def _salva_snapshot(nome: str, url: str) -> None:
    """Salva il contenuto grezzo del feed quando l'estrazione fallisce (regola CLAUDE.md:
    'Save raw HTML snapshots when extraction fails')."""
    try:
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        r = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=_TIMEOUT)
        slug = "".join(c if c.isalnum() else "_" for c in nome)[:40]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        percorso = os.path.join(SNAPSHOT_DIR, f"feeds_{slug}_{ts}.html")
        with open(percorso, 'w', encoding='utf-8') as fh:
            fh.write(r.text)
        logger.warning("Snapshot salvato per '%s' (estrazione fallita): %s", nome, percorso)
    except Exception as e:
        logger.warning("Impossibile salvare snapshot per '%s': %s", nome, e)


def _processa_feed(cfg: dict) -> list[dict]:
    nome = str(cfg.get('nome', '')).strip()
    url = str(cfg.get('url', '')).strip()
    tipo_fonte = str(cfg.get('tipo_fonte', 'blog_newsletter')).strip()
    trust_tier = str(cfg.get('trust_tier', '2')).strip()
    lingua = str(cfg.get('lingua', 'it')).strip().lower()
    applica_filtro = str(cfg.get('filtro_rilevanza', 'si')).strip().lower() in _VERO

    if not url:
        logger.warning("Feed '%s' senza url, saltato", nome)
        return []

    logger.info("Connessione a: %s", nome)
    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": _USER_AGENT})
    except Exception as e:
        logger.error("Errore parsing feed '%s': %s", nome, e)
        _salva_snapshot(nome, url)
        return []

    if not feed.entries:
        logger.warning("Nessuna entry per '%s'", nome)
        _salva_snapshot(nome, url)
        return []

    risultati = []
    scartati = 0
    for entry in feed.entries[:MAX_ENTRY_PER_FEED]:
        titolo = pulisci_html(entry.get('title', ''))
        sommario = pulisci_html(entry.get('summary', entry.get('description', '')))
        if not titolo:
            continue

        if lingua != 'it':
            time.sleep(1)  # cortesia verso l'endpoint di traduzione (rate-limit)
            titolo = traduci_in_italiano(titolo)
            sommario = traduci_in_italiano(sommario)

        testo_completo = f"{titolo} {sommario}".strip()

        # Scarto per rilevanza: loggato e conteggiato, mai silenzioso.
        if applica_filtro and not is_rilevante(testo_completo):
            scartati += 1
            continue

        hash_contenuto = hashlib.sha256(testo_completo.encode('utf-8')).hexdigest()
        risultati.append({
            # Schema unificato (allineato agli altri scraper)
            'id_univoco':         hash_contenuto,
            'fonte':              'feeds',
            'nome_testata':       nome,
            'data_pubblicazione': entry.get('published', entry.get('updated', '')),
            'data_scraping':      datetime.now().isoformat(),
            'titolo':             titolo,
            'url':                entry.get('link', ''),
            'tipo_contenuto':     tipo_fonte,
            'lingua':             'it',
            'testo_completo':     testo_completo,
            'hash_contenuto':     hash_contenuto,
            # Metadati per separare fatti da opinione a valle
            'tipo_fonte':         tipo_fonte,
            'trust_tier':         trust_tier,
        })

    logger.info("%s: %d rilevanti, %d scartati su %d esaminati",
                nome, len(risultati), scartati,
                min(len(feed.entries), MAX_ENTRY_PER_FEED))
    return risultati


def scarica_feeds() -> pd.DataFrame:
    """Scarica tutti i feed attivi dalla configurazione."""
    feeds = carica_config()
    tutti: list[dict] = []
    for cfg in feeds:
        tutti.extend(_processa_feed(cfg))
    df = pd.DataFrame(tutti)
    logger.info("Feeds: %d contenuti raccolti da %d feed attivi", len(df), len(feeds))
    return df


if __name__ == "__main__":
    df_feeds = scarica_feeds()

    if not df_feeds.empty:
        cartella_raw = os.path.join(_SCRIPT_DIR, '..', 'data', 'raw')
        os.makedirs(cartella_raw, exist_ok=True)
        percorso = os.path.join(cartella_raw, 'feeds_sample.csv')

        if os.path.exists(percorso):
            df_esistente = pd.read_csv(percorso)
            df_unito = pd.concat([df_esistente, df_feeds], ignore_index=True)
            df_finale = df_unito.drop_duplicates(subset=['hash_contenuto'], keep='last')
        else:
            df_finale = df_feeds

        df_finale.to_csv(percorso, index=False)
        logger.info("Salvato: %s (%d record totali)", percorso, len(df_finale))
    else:
        logger.warning("Nessun contenuto raccolto dai feed configurati.")
