"""
Scraper per la Corte di Giustizia dell'Unione Europea (CJEU) — comunicati
stampa su sentenze e conclusioni degli avvocati generali.

curia.europa.eu pubblica UN SOLO feed RSS aggregato (tutti i comunicati
stampa, ogni materia del diritto UE) — non feed dedicati per area tematica
come inizialmente ipotizzato. Verificato live il 2026-08-29. Si applica
quindi un filtro di rilevanza tematica sulle singole entry, sullo stesso
principio già usato in scraper_eu_parl.py per il feed commissioni EP.

Due differenze rispetto a quel caso, emerse dal test live, per cui questo
scraper NON riusa KEYWORD_DIGITALE tale quale:
  1. Il feed CJEU copre tutte le materie del diritto UE (concorrenza,
     immigrazione, diritto penale, tributario, ecc.), non solo la sfera
     legislativa/digitale come i comunicati delle commissioni EP. Le parole
     singole generiche di KEYWORD_DIGITALE ("libertà", "sicurezza",
     "digitale") hanno prodotto falsi positivi verificati: hanno intercettato
     cause di estradizione e asilo solo perché rientrano nell'area "Spazio
     di libertà, sicurezza e giustizia". Si usa quindi
     KEYWORD_DIGITALE_STRETTO (frasi/termini specifici del dominio
     privacy/AI/digitale) da scraper_open_data_utils.py.
  2. I titoli delle entry sono solo numeri di causa (es. "Sentenza della
     Corte nella causa C-523/24"): la materia è quasi sempre solo nella
     <description>, mai nel titolo. Il filtro va applicato al testo
     completo (titolo + description), mai al solo titolo.

Nota sull'affidabilità del feed: verificato live con richieste ripetute,
circa 1 su 3 ha restituito HTTP 503 (il servizio si è poi stabilizzato al
tentativo successivo). A differenza del caso dell'Open Data API del
Parlamento Europeo (vedi scraper_eu_parl.py, disattivata perché restituiva
dati sbagliati con status 200), qui il fallimento è un errore HTTP esplicito
e non silenzioso: il try/except sotto lo logga e salta il run, coerente con
il pattern già in uso negli altri scraper RSS del progetto (nessun retry
automatico, il prossimo run della pipeline riprova).

Feed nativo in italiano (?lang=it) — nessuna traduzione necessaria.
"""
import os
import sys
import hashlib
from datetime import datetime

import feedparser
import pandas as pd
from bs4 import BeautifulSoup

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from utils.logger_config import setup_logger
from scrapers.scraper_open_data_utils import KEYWORD_DIGITALE_STRETTO, is_rilevante

logger = setup_logger(__name__)

# Feed comunicati stampa CJEU, verificato live il 2026-08-29 (JCMS).
URL_CURIA_RSS = "https://curia.europa.eu/site/rss.jsp?lang=it"


def pulisci_html(testo: str) -> str:
    if not testo:
        return ""
    return BeautifulSoup(testo, "html.parser").get_text(separator=" ").strip()


def _hash(testo: str) -> str:
    return hashlib.sha256(testo.encode("utf-8")).hexdigest()


def scarica_giurisprudenza_cjeu() -> pd.DataFrame:
    """Scarica i comunicati stampa CJEU e li filtra per rilevanza tematica."""
    logger.info("Avvio scraper CJEU: %s", URL_CURIA_RSS)
    sentenze = []

    try:
        feed = feedparser.parse(URL_CURIA_RSS)
        if feed.bozo != 0 and not hasattr(feed, "entries"):
            logger.warning("Feed CJEU non leggibile (possibile errore HTTP transitorio)")
            return pd.DataFrame()
        if not feed.entries:
            logger.warning("Nessuna entry nel feed CJEU in questo run")
            return pd.DataFrame()

        esaminati = 0
        for entry in feed.entries:
            titolo = pulisci_html(entry.get("title", ""))
            if not titolo:
                continue
            esaminati += 1

            sommario = pulisci_html(entry.get("summary", entry.get("description", "")))
            testo_completo = f"{titolo} {sommario}".strip()

            if not is_rilevante(testo_completo, KEYWORD_DIGITALE_STRETTO):
                continue

            sentenze.append({
                # Schema unificato (allineato a gnews, gpdp, ong, rss_eu, eu_parl)
                'id_univoco':         _hash(testo_completo),
                'fonte':              'cjeu',
                'data_pubblicazione': entry.get("published", entry.get("updated", "")),
                'data_scraping':      datetime.now().isoformat(),
                'titolo':             titolo,
                'url':                entry.get("link", ""),
                'tipo_contenuto':     'sentenza_comunicato',
                'lingua':             'it',
                'testo_completo':     testo_completo,
                'hash_contenuto':     _hash(testo_completo),
            })
            logger.debug("Trovata: %s", titolo[:60])

        logger.info("CJEU: %d comunicati esaminati, %d rilevanti", esaminati, len(sentenze))

    except Exception as e:
        logger.error("Errore scraper CJEU: %s", e)
        return pd.DataFrame()

    return pd.DataFrame(sentenze)


if __name__ == "__main__":
    df_cjeu = scarica_giurisprudenza_cjeu()

    if not df_cjeu.empty:
        cartella_script = os.path.dirname(os.path.abspath(__file__))
        cartella_raw = os.path.join(cartella_script, '..', 'data', 'raw')
        os.makedirs(cartella_raw, exist_ok=True)

        percorso_salvataggio = os.path.join(cartella_raw, 'cjeu_sample.csv')

        if os.path.exists(percorso_salvataggio):
            df_esistente = pd.read_csv(percorso_salvataggio)
            df_unito = pd.concat([df_esistente, df_cjeu], ignore_index=True)
            df_finale = df_unito.drop_duplicates(subset=['hash_contenuto'], keep='last')
        else:
            df_finale = df_cjeu

        df_finale.to_csv(percorso_salvataggio, index=False)
        logger.info("Dati salvati in: %s (%d record totali)", percorso_salvataggio, len(df_finale))
    else:
        logger.warning("Nessun comunicato CJEU rilevante trovato in questo run.")
