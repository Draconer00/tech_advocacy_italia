import os
import sys
import hashlib
import time
from datetime import datetime

import feedparser
import pandas as pd
from bs4 import BeautifulSoup

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from utils.logger_config import setup_logger

logger = setup_logger(__name__)

# Feed RSS pubblici AGCOM (Autorità per le Garanzie nelle Comunicazioni).
# AGCOM regola telecomunicazioni, media, piattaforme digitali e servizi postali.
# Tutti i testi sono già in italiano — nessuna traduzione necessaria.
FONTI_AGCOM: dict[str, dict] = {
    "AGCOM Comunicati Stampa": {
        "url": "https://www.agcom.it/comunicati-stampa?format=feed&type=rss",
        "tipo_contenuto": "comunicato_stampa",
    },
    "AGCOM Delibere": {
        "url": "https://www.agcom.it/delibere-agcom?format=feed&type=rss",
        "tipo_contenuto": "delibera",
    },
    "AGCOM Consultazioni Pubbliche": {
        "url": "https://www.agcom.it/consultazioni-pubbliche?format=feed&type=rss",
        "tipo_contenuto": "consultazione",
    },
    "AGCOM News": {
        "url": "https://www.agcom.it/news?format=feed&type=rss",
        "tipo_contenuto": "news",
    },
}

# Timeout per ogni fetch RSS (secondi)
_FEED_TIMEOUT = 10


def pulisci_html(testo: str) -> str:
    if not testo:
        return ""
    return BeautifulSoup(testo, "html.parser").get_text(separator=" ").strip()


def scarica_feed_agcom() -> pd.DataFrame:
    """Scarica e normalizza tutti i feed RSS AGCOM."""
    logger.info("Avvio scraper AGCOM (%d fonti)", len(FONTI_AGCOM))
    documenti: list[dict] = []

    for nome_fonte, config in FONTI_AGCOM.items():
        url = config["url"]
        tipo = config["tipo_contenuto"]
        logger.info("Connessione a: %s", nome_fonte)
        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})

            # feedparser segnala bozo=True per XML malformato ma restituisce
            # comunque le entries se riesce a fare parsing parziale.
            if not feed.entries:
                logger.warning("Nessuna entry trovata per: %s", nome_fonte)
                continue

            for entry in feed.entries[:10]:
                titolo = pulisci_html(entry.get("title", ""))
                sommario = pulisci_html(
                    entry.get("summary", entry.get("description", ""))
                )
                link = entry.get("link", "")
                data_raw = entry.get("published", entry.get("updated", ""))

                if not titolo:
                    continue

                testo_completo = f"{titolo} {sommario}".strip()
                hash_contenuto = hashlib.sha256(
                    testo_completo.encode("utf-8")
                ).hexdigest()

                documenti.append({
                    "id_univoco":         hash_contenuto,
                    "fonte":              "agcom",
                    "ente_origine":       nome_fonte,
                    "data_pubblicazione": data_raw,
                    "data_scraping":      datetime.now().isoformat(),
                    "titolo":             titolo,
                    "url":                link,
                    "tipo_contenuto":     tipo,
                    "lingua":             "it",
                    "testo_completo":     testo_completo,
                    "hash_contenuto":     hash_contenuto,
                })
                logger.debug("Trovato: %s", titolo[:70])

            time.sleep(0.5)  # cortesia verso il server AGCOM

        except Exception as e:
            logger.error("Errore su %s: %s", nome_fonte, e)

    df = pd.DataFrame(documenti)
    logger.info("AGCOM: %d documenti scaricati", len(df))
    return df


if __name__ == "__main__":
    df_agcom = scarica_feed_agcom()

    if not df_agcom.empty:
        cartella_script = os.path.dirname(os.path.abspath(__file__))
        cartella_raw = os.path.join(cartella_script, "..", "data", "raw")
        os.makedirs(cartella_raw, exist_ok=True)

        percorso = os.path.join(cartella_raw, "agcom_sample.csv")

        if os.path.exists(percorso):
            df_esistente = pd.read_csv(percorso)
            df_unito = pd.concat([df_esistente, df_agcom], ignore_index=True)
            df_finale = df_unito.drop_duplicates(subset=["hash_contenuto"], keep="last")
        else:
            df_finale = df_agcom

        df_finale.to_csv(percorso, index=False)
        logger.info("Salvato: %s (%d record totali)", percorso, len(df_finale))
    else:
        logger.warning("Nessun dato AGCOM raccolto.")
