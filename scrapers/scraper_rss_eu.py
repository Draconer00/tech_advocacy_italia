import os
import sys
import hashlib
import time
from datetime import datetime

import feedparser
import pandas as pd
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from utils.logger_config import setup_logger

logger = setup_logger(__name__)

# Feed RSS degli enti regolatori europei sulla privacy.
#
# AEPD (Spagna) e ICO (Regno Unito) sono stati rimossi il 2026-08-29: nessun
# feed RSS attivo trovato dopo verifica diretta. AEPD ha un solo feed live
# (https://www.aepd.es/press-releases/feed.xml) ma è abbandonato, fermo al
# 2020. ICO dichiara sulla propria pagina ufficiale (ico.org.uk/global/rss-feeds/)
# che il feed news è "currently unavailable" dopo un redesign del sito; tutti
# gli endpoint provati (news-and-blogs, decision-notices, enforcement, rss.xml)
# restituiscono HTML o 404 al posto di XML. Riprovare periodicamente, o valutare
# scraping HTML della pagina notizie se questi enti diventano prioritari.
#
# EDPS (European Data Protection Supervisor) valutato e NON aggiunto il
# 2026-08-29: nessun feed RSS raggiungibile via richiesta diretta. Ogni
# percorso provato (/rss.xml, /rss_en.xml, /node/feed, i percorsi sotto
# press-publications/press-news) restituisce 404 pulito oppure 202 con body
# vuoto — il dominio edps.europa.eu è dietro un bot-challenge che non
# risponde a richieste non browser. Da riverificare con un browser reale
# (o headless) se questa fonte diventa prioritaria; per ora nessun URL
# aggiunto per evitare di fare affidamento su un endpoint mai confermato.
FONTI_RSS: dict[str, str] = {
    "EDPB (Unione Europea)": "https://www.edpb.europa.eu/rss.xml",
    "CNIL (Francia)":        "https://www.cnil.fr/fr/rss.xml",
}


def pulisci_html(testo_sporco: str) -> str:
    """Rimuove tag HTML dal testo RSS."""
    if not testo_sporco:
        return ""
    return BeautifulSoup(testo_sporco, "html.parser").text.strip()


def traduci_in_italiano(testo: str, lingua_origine: str = 'auto') -> str:
    """Traduce il testo in italiano via Google Translate (max 4999 caratteri)."""
    if not testo or len(testo) < 3:
        return testo
    try:
        traduttore = GoogleTranslator(source=lingua_origine, target='it')
        return traduttore.translate(testo[:4999])
    except Exception as e:
        logger.warning("Errore traduzione: %s", e)
        return testo


def caccia_rss_istituzionali() -> pd.DataFrame:
    """Scarica e traduce le ultime notizie dagli RSS dei regolatori europei."""
    logger.info("Avvio RSS scraper europeo (%d fonti)", len(FONTI_RSS))
    notizie = []

    for ente, url in FONTI_RSS.items():
        logger.info("Connessione a: %s", ente)
        try:
            feed = feedparser.parse(url)
            if feed.bozo != 0 and not hasattr(feed, 'entries'):
                logger.warning("Feed non leggibile: %s", ente)
                continue

            for notizia in feed.entries[:5]:
                titolo_orig = pulisci_html(notizia.get('title', ''))
                sommario_orig = pulisci_html(
                    notizia.get('summary', notizia.get('description', ''))
                )
                link = notizia.get('link', '')
                data_raw = notizia.get('published', notizia.get('updated', ''))

                time.sleep(1)  # evita rate-limit Google Translate
                titolo_ita = traduci_in_italiano(titolo_orig)
                sommario_ita = traduci_in_italiano(sommario_orig)

                testo_completo = f"{titolo_ita} {sommario_ita}"
                hash_contenuto = hashlib.sha256(testo_completo.encode('utf-8')).hexdigest()

                notizie.append({
                    # Schema unificato (allineato a gnews, gpdp, ong)
                    'id_univoco':         hash_contenuto,
                    'fonte':              'rss_eu',
                    'data_pubblicazione': data_raw,
                    'data_scraping':      datetime.now().isoformat(),
                    'titolo':             titolo_ita,
                    'url':                link,
                    'tipo_contenuto':     'comunicato_istituzionale',
                    'lingua':             'it',
                    'testo_completo':     testo_completo,
                    'hash_contenuto':     hash_contenuto,
                    # Campi aggiuntivi specifici RSS EU
                    'ente_origine':       ente,
                    'titolo_originale':   titolo_orig,
                    'sommario_italiano':  sommario_ita,
                })
                logger.debug("Trovata: %s", titolo_orig[:60])

        except Exception as e:
            logger.error("Errore su %s: %s", ente, e)

    df = pd.DataFrame(notizie)
    logger.info("Totale: %d notizie scaricate e tradotte", len(df))
    return df


if __name__ == "__main__":
    df_europa = caccia_rss_istituzionali()

    if not df_europa.empty:
        cartella_script = os.path.dirname(os.path.abspath(__file__))
        cartella_raw = os.path.join(cartella_script, '..', 'data', 'raw')
        os.makedirs(cartella_raw, exist_ok=True)

        percorso_salvataggio = os.path.join(cartella_raw, 'rss_eu_sample.csv')

        if os.path.exists(percorso_salvataggio):
            df_esistente = pd.read_csv(percorso_salvataggio)
            df_unito = pd.concat([df_esistente, df_europa], ignore_index=True)
            df_finale = df_unito.drop_duplicates(subset=['hash_contenuto'], keep='last')
        else:
            df_finale = df_europa

        df_finale.to_csv(percorso_salvataggio, index=False)
        logger.info("Dati salvati in: %s (%d record totali)", percorso_salvataggio, len(df_finale))
