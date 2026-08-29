"""
Scraper per la Gazzetta Ufficiale della Repubblica Italiana — feed RSS
ufficiali per serie, verificati live il 2026-08-29.

Serie monitorate (rilevanti per il perimetro del progetto: privacy, AI
governance, diritti digitali):
  SG — Serie Generale (leggi, decreti; volume alto e tutte le materie,
       per questo filtrata con KEYWORD_DIGITALE_STRETTO)
  S1 — Corte Costituzionale (sentenze; perimetro già ristretto, non filtrata)
  S2 — Unione Europea (recepimenti e atti UE pubblicati in GU; perimetro
       già ristretto, non filtrata)

Serie escluse perché fuori perimetro del progetto: S3 (Regioni), S4
(Concorsi ed Esami), S5 (Contratti pubblici), P2 (Parte II — annunci e
avvisi amministrativi).

Nota sull'URL: il sito espone i link RSS come percorsi relativi
(es. "rss/SG") nella sezione "Ultime Gazzette pubblicate" della homepage;
quel percorso relativo NON risolve se chiamato direttamente (redirige a una
pagina d'errore). L'URL assoluto sotto è stato verificato con una richiesta
live che ha restituito RSS 2.0 valido con il sommario del giorno corrente.
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

FONTI_GU: dict[str, str] = {
    "Serie Generale":       "https://www.gazzettaufficiale.it/rss/SG",
    "Corte Costituzionale": "https://www.gazzettaufficiale.it/rss/S1",
    "Unione Europea":       "https://www.gazzettaufficiale.it/rss/S2",
}

# Serie a perimetro già ristretto: nessun filtro di rilevanza aggiuntivo.
SERIE_NON_FILTRATE = frozenset({"Corte Costituzionale", "Unione Europea"})


def pulisci_html(testo: str) -> str:
    """Rimuove tag HTML dal testo RSS."""
    if not testo:
        return ""
    return BeautifulSoup(testo, "html.parser").get_text(separator=" ").strip()


def _hash(testo: str) -> str:
    return hashlib.sha256(testo.encode("utf-8")).hexdigest()


def scarica_gazzetta_ufficiale() -> pd.DataFrame:
    """Scarica i sommari RSS della Gazzetta Ufficiale, filtrati per rilevanza tematica."""
    logger.info("Avvio scraper Gazzetta Ufficiale (%d serie)", len(FONTI_GU))
    atti = []

    for serie, url in FONTI_GU.items():
        logger.info("Connessione a: %s", serie)
        try:
            feed = feedparser.parse(url)
            if feed.bozo != 0 and not hasattr(feed, "entries"):
                logger.warning("Feed non leggibile: %s", serie)
                continue
            if not feed.entries:
                logger.warning("Nessuna entry nel feed: %s", serie)
                continue

            esaminati = 0
            rilevanti = 0

            for entry in feed.entries:
                titolo = pulisci_html(entry.get("title", ""))
                if not titolo:
                    continue
                esaminati += 1

                contenuto_raw = entry.get("content")
                if contenuto_raw:
                    testo_atto = pulisci_html(contenuto_raw[0].get("value", ""))
                else:
                    testo_atto = pulisci_html(
                        entry.get("summary", entry.get("description", ""))
                    )

                testo_completo = f"{titolo} {testo_atto}".strip()

                if serie not in SERIE_NON_FILTRATE and not is_rilevante(
                    testo_completo, KEYWORD_DIGITALE_STRETTO
                ):
                    continue

                rilevanti += 1
                atti.append({
                    # Schema unificato (allineato a gnews, gpdp, ong, rss_eu)
                    'id_univoco':         _hash(testo_completo),
                    'fonte':              'gazzetta_ufficiale',
                    'data_pubblicazione': entry.get("published", entry.get("updated", "")),
                    'data_scraping':      datetime.now().isoformat(),
                    'titolo':             titolo,
                    'url':                entry.get("link", ""),
                    'tipo_contenuto':     'atto_normativo',
                    'lingua':             'it',
                    'testo_completo':     testo_completo,
                    'hash_contenuto':     _hash(testo_completo),
                    # Campo aggiuntivo specifico Gazzetta Ufficiale
                    'serie':              serie,
                })
                logger.debug("Trovato: %s", titolo[:60])

            logger.info("%s: %d esaminati, %d rilevanti", serie, esaminati, rilevanti)

        except Exception as e:
            logger.error("Errore su %s: %s", serie, e)

    df = pd.DataFrame(atti)
    logger.info("Totale: %d atti raccolti", len(df))
    return df


if __name__ == "__main__":
    df_gu = scarica_gazzetta_ufficiale()

    if not df_gu.empty:
        cartella_script = os.path.dirname(os.path.abspath(__file__))
        cartella_raw = os.path.join(cartella_script, '..', 'data', 'raw')
        os.makedirs(cartella_raw, exist_ok=True)

        percorso_salvataggio = os.path.join(cartella_raw, 'gazzetta_ufficiale_sample.csv')

        if os.path.exists(percorso_salvataggio):
            df_esistente = pd.read_csv(percorso_salvataggio)
            df_unito = pd.concat([df_esistente, df_gu], ignore_index=True)
            df_finale = df_unito.drop_duplicates(subset=['hash_contenuto'], keep='last')
        else:
            df_finale = df_gu

        df_finale.to_csv(percorso_salvataggio, index=False)
        logger.info("Dati salvati in: %s (%d record totali)", percorso_salvataggio, len(df_finale))
    else:
        logger.warning("Nessun atto rilevante raccolto dalla Gazzetta Ufficiale in questo run.")
