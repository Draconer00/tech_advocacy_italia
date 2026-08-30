"""
Scraper per le principali testate tech italiane: aggrega i feed RSS e
scarta gli articoli non pertinenti a privacy, AI e diritti digitali
tramite un filtro per parole chiave.
"""
import os
import sys
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import feedparser
import pandas as pd
from bs4 import BeautifulSoup

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from utils.logger_config import setup_logger

logger = setup_logger(__name__)

# Testate tech italiane con copertura su privacy, AI e diritti digitali.
# Tutte le fonti hanno feed RSS pubblici e gratuiti.
FONTI_TECH_NEWS: dict[str, str] = {
    "Wired Italia":           "https://www.wired.it/rss/",
    "Punto Informatico":      "https://punto-informatico.it/feed/",
    "Agenda Digitale":        "https://www.agendadigitale.eu/feed/",
    "Corriere Comunicazioni": "https://www.corrierecomunicazioni.it/feed/",
    "Data Manager Online":    "https://datamanager.it/feed/",
    "Cybersecurity360":       "https://www.cybersecurity360.it/feed/",
    "Innovation Post":        "https://www.innovationpost.it/feed/",
    "StartupItalia":          "https://startupitalia.eu/feed",
}

# Articoli che NON contengono almeno una di queste parole chiave vengono scartati.
# L'obiettivo è tenere solo i contenuti pertinenti ai diritti digitali e
# alla governance della tecnologia, escludendo hardware, gaming, consumer tech.
KEYWORD_RILEVANZA: frozenset[str] = frozenset({
    "privacy", "gdpr", "dati personali", "trattamento dati",
    "intelligenza artificiale", "ai act", "algoritmo", "machine learning",
    "sorveglianza", "riconoscimento facciale", "biometrico",
    "cybersecurity", "sicurezza informatica", "ransomware", "data breach",
    "dsa", "dma", "nis2", "regolamento", "normativa", "direttiva",
    "diritti digitali", "libertà digitale", "censura", "agcom",
    "garante", "sanzione", "multa", "data protection",
    "fake news", "disinformazione", "moderazione contenuti",
    "open source", "trasparenza algoritmica", "bias",
})


def pulisci_html(testo: str) -> str:
    if not testo:
        return ""
    return BeautifulSoup(testo, "html.parser").get_text(separator=" ").strip()


def is_rilevante(testo: str) -> bool:
    """Restituisce True se il testo contiene almeno una keyword di rilevanza."""
    testo_lower = testo.lower()
    return any(kw in testo_lower for kw in KEYWORD_RILEVANZA)


def _processa_fonte(nome_testata: str, url_feed: str) -> list[dict]:
    """Scarica un feed RSS e restituisce solo gli articoli rilevanti."""
    try:
        feed = feedparser.parse(url_feed)
        if not feed.entries:
            logger.warning("Nessuna entry: %s", nome_testata)
            return []

        risultati = []
        for entry in feed.entries[:20]:  # max 20 per run per testata
            titolo = pulisci_html(entry.get("title", ""))
            sommario = pulisci_html(
                entry.get("summary", entry.get("description", ""))
            )
            if not titolo:
                continue

            testo_completo = f"{titolo} {sommario}".strip()

            # Scarta articoli non pertinenti ai diritti digitali
            if not is_rilevante(testo_completo):
                continue

            hash_contenuto = hashlib.sha256(
                testo_completo.encode("utf-8")
            ).hexdigest()

            risultati.append({
                "id_univoco":         hash_contenuto,
                "fonte":              "tech_news",
                "nome_testata":       nome_testata,
                "data_pubblicazione": entry.get("published", entry.get("updated", "")),
                "data_scraping":      datetime.now().isoformat(),
                "titolo":             titolo,
                "url":                entry.get("link", ""),
                "tipo_contenuto":     "articolo",
                "lingua":             "it",
                "testo_completo":     testo_completo,
                "hash_contenuto":     hash_contenuto,
            })

        logger.debug("%s: %d articoli rilevanti su %d totali",
                     nome_testata, len(risultati), len(feed.entries))
        return risultati

    except Exception as e:
        logger.warning("Errore %s: %s", nome_testata, e)
        return []


def scarica_tech_news() -> pd.DataFrame:
    """Aggrega RSS da tutte le testate tech italiane, filtrando per rilevanza."""
    logger.info("Avvio scraper Tech News Italia (%d fonti)", len(FONTI_TECH_NEWS))
    tutti_articoli: list[dict] = []

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(_processa_fonte, nome, url): nome
            for nome, url in FONTI_TECH_NEWS.items()
        }
        for future in as_completed(futures):
            tutti_articoli.extend(future.result())

    df = pd.DataFrame(tutti_articoli)
    logger.info("Tech News: %d articoli rilevanti raccolti", len(df))
    return df


if __name__ == "__main__":
    df_tech = scarica_tech_news()

    if not df_tech.empty:
        cartella_script = os.path.dirname(os.path.abspath(__file__))
        cartella_raw = os.path.join(cartella_script, "..", "data", "raw")
        os.makedirs(cartella_raw, exist_ok=True)

        percorso = os.path.join(cartella_raw, "tech_news_sample.csv")

        if os.path.exists(percorso):
            df_esistente = pd.read_csv(percorso)
            df_unito = pd.concat([df_esistente, df_tech], ignore_index=True)
            df_finale = df_unito.drop_duplicates(subset=["hash_contenuto"], keep="last")
        else:
            df_finale = df_tech

        df_finale.to_csv(percorso, index=False)
        logger.info("Salvato: %s (%d record totali)", percorso, len(df_finale))
    else:
        logger.warning("Nessun articolo rilevante raccolto dalle testate tech.")
