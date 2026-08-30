"""
Scraper per il sito del Garante per la protezione dei dati personali (GPDP):
estrae provvedimenti e comunicati, seguendo i redirect intermedi con cui il
sito pubblica il testo integrale dei documenti.
"""
import os
import sys
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import pandas as pd
import requests
from bs4 import BeautifulSoup

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from utils.logger_config import setup_logger

logger = setup_logger(__name__)


def estrai_testo_completo(url: str, session: requests.Session) -> str:
    """
    Naviga il redirect del Garante Privacy (pagine con 'clicca qui' o meta-refresh)
    e restituisce il testo legale della pagina di destinazione.
    """
    try:
        time.sleep(1)
        risposta = session.get(url, timeout=10)
        if risposta.status_code != 200:
            return "Errore di connessione"

        zuppa = BeautifulSoup(risposta.content, 'html.parser')
        testo_pagina = zuppa.text.lower()

        if "redirect automatico" in testo_pagina or "clicca qui" in testo_pagina:
            logger.debug("Redirect rilevato su %s", url)
            vero_link = None

            link_tag = zuppa.find('a', string=lambda t: t and "clicca qui" in t.lower())
            if link_tag and link_tag.has_attr('href'):
                vero_link = link_tag['href']
            else:
                meta = zuppa.find('meta', attrs={'http-equiv': lambda x: x and x.lower() == 'refresh'})
                if meta and 'url=' in meta.get('content', '').lower():
                    vero_link = meta['content'].lower().split('url=')[-1].strip('\'" ')

            if vero_link:
                if vero_link.startswith('/'):
                    vero_link = "https://www.garanteprivacy.it" + vero_link
                time.sleep(1)
                risposta = session.get(vero_link, timeout=10)
                zuppa = BeautifulSoup(risposta.content, 'html.parser')

        paragrafi = zuppa.find_all('p')
        testo = " ".join(p.text.strip() for p in paragrafi if len(p.text.strip()) > 20)
        if not testo or len(testo) < 50:
            testo = zuppa.text.strip()[:1000]
        return testo

    except Exception as e:
        logger.warning("Errore estrazione testo da %s: %s", url, e)
        return "Errore estrazione"


def scrape_provvedimenti_garante() -> pd.DataFrame:
    url_base = "https://www.garanteprivacy.it/"
    logger.info("Avvio scraping Garante Privacy: %s", url_base)

    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

    try:
        risposta = session.get(url_base, timeout=10)
        risposta.raise_for_status()
        zuppa = BeautifulSoup(risposta.content, 'html.parser')

        parole_escluse = {
            "agenda", "eventi", "newsletter", "convegno", "seminario",
            "podcast", "comunicato", "comunicati", "stampa", "notizia",
            "news", "avviso", "annuncio",
        }
        links_da_scaricare = []

        for tag_a in zuppa.find_all('a', href=True):
            link = tag_a['href']
            titolo = tag_a.text.strip()
            if "docweb" in link and len(titolo) > 10:
                if not any(p in titolo.lower() for p in parole_escluse):
                    if link.startswith("/"):
                        link = "https://www.garanteprivacy.it" + link
                    if link not in [p['link'] for p in links_da_scaricare]:
                        links_da_scaricare.append({'link': link, 'titolo': titolo})
                        if len(links_da_scaricare) >= 10:
                            break

        logger.info("Trovati %d provvedimenti. Inizio download parallelo...", len(links_da_scaricare))

        provvedimenti = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(estrai_testo_completo, item['link'], session): item
                for item in links_da_scaricare
            }
            for future in as_completed(futures):
                item = futures[future]
                try:
                    testo = future.result()
                    hash_contenuto = hashlib.sha256(testo.encode('utf-8')).hexdigest()
                    provvedimenti.append({
                        'id_univoco':        hash_contenuto,
                        'fonte':             'gpdp',
                        'data_pubblicazione': datetime.now().date().isoformat(),
                        'data_scraping':     datetime.now().isoformat(),
                        'titolo':            item['titolo'],
                        'url':               item['link'],
                        'tipo_contenuto':    'provvedimento',
                        'lingua':            'it',
                        'testo_completo':    testo,
                        'hash_contenuto':    hash_contenuto,
                    })
                    logger.debug("Download OK: %s", item['titolo'][:50])
                except Exception as e:
                    logger.error("Errore download %s: %s", item['link'], e)

        df_gpdp = pd.DataFrame(provvedimenti)
        logger.info("Scaricati %d provvedimenti completi.", len(df_gpdp))
        return df_gpdp

    except Exception as e:
        logger.error("Errore durante lo scraping GPDP: %s", e)
        return pd.DataFrame()


if __name__ == "__main__":
    df_test = scrape_provvedimenti_garante()

    if not df_test.empty:
        cartella_script = os.path.dirname(os.path.abspath(__file__))
        cartella_raw = os.path.join(cartella_script, '..', 'data', 'raw')
        os.makedirs(cartella_raw, exist_ok=True)

        percorso_salvataggio = os.path.join(cartella_raw, 'gpdp_sample.csv')

        if os.path.exists(percorso_salvataggio):
            df_esistente = pd.read_csv(percorso_salvataggio)
            df_unito = pd.concat([df_esistente, df_test], ignore_index=True)
            df_finale = df_unito.drop_duplicates(subset=['url'], keep='last')
        else:
            df_finale = df_test

        df_finale.to_csv(percorso_salvataggio, index=False)
        logger.info("Dati salvati in: %s (%d record totali)", percorso_salvataggio, len(df_finale))
