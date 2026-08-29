"""
Scraper per il Parlamento Europeo — due fonti complementari:

1. RSS feed notizie EP (comunicati stampa in italiano, istantanei)
2. Open Data API EP (https://data.europarl.europa.eu/api/v1/)
   — atti legislativi strutturati, filtrabili per commissione e argomento

Le commissioni prioritarie per i diritti digitali sono:
  LIBE — Libertà civili, giustizia e affari interni
  IMCO — Mercato interno e protezione dei consumatori
  ITRE — Industria, ricerca ed energia (AI, DSA, DMA)
"""
import os
import sys
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
from scrapers.scraper_open_data_utils import KEYWORD_DIGITALE, is_rilevante

logger = setup_logger(__name__)

# RSS feed ufficiali del Parlamento Europeo (lingua italiana).
# Aggiornati il 2026-08-29: i 3 URL precedenti erano rotti (2 a 404, il terzo
# "top-stories" valido ma fermo a novembre 2023) o abbandonati. Trovati e
# verificati live i feed comunicati-stampa correnti, sostituiti qui.
FONTI_RSS_EP: dict[str, str] = {
    "EP Comunicati Stampa (Tutti)":     "https://www.europarl.europa.eu/rss/doc/press-releases/it.xml",
    "EP Comunicati Stampa Plenaria":    "https://www.europarl.europa.eu/rss/doc/press-releases-plenary/it.xml",
    "EP Comunicati Stampa Commissioni": "https://www.europarl.europa.eu/rss/doc/press-releases-committees/it.xml",
}

# Endpoint Open Data API EP
EP_API_BASE = "https://data.europarl.europa.eu/api/v1"

# Ricerche API filtrate per rilevanza tematica.
# Il parametro `work-type` filtra per tipologia di atto legislativo.
EP_API_QUERIES: list[dict] = [
    {
        "nome":        "Atti legislativi digitali",
        "endpoint":    f"{EP_API_BASE}/legislative-acts",
        "params":      {"lang": "it", "limit": 15, "offset": 0,
                        "format": "application/ld+json"},
    },
    {
        "nome":        "Attività commissione LIBE",
        "endpoint":    f"{EP_API_BASE}/documents",
        "params":      {"lang": "it", "limit": 10, "committee": "LIBE",
                        "format": "application/ld+json"},
    },
]

_HEADERS = {
    "User-Agent": "TechAdvocacyItaly/1.0 (research project; github.com/Draconer00)",
    "Accept":     "application/ld+json, application/json",
}


def pulisci_html(testo: str) -> str:
    if not testo:
        return ""
    return BeautifulSoup(testo, "html.parser").get_text(separator=" ").strip()


def _hash(testo: str) -> str:
    return hashlib.sha256(testo.encode("utf-8")).hexdigest()


def _scarica_rss() -> list[dict]:
    """Scarica le notizie dal RSS ufficiale EP (già in italiano)."""
    documenti = []
    for nome, url in FONTI_RSS_EP.items():
        logger.info("RSS EP: %s", nome)
        try:
            feed = feedparser.parse(url)
            if not feed.entries:
                logger.warning("Nessuna entry RSS: %s", nome)
                continue

            # 30 non 10: "Comunicati Stampa Commissioni" copre tutte le commissioni
            # del PE (non solo LIBE/IMCO/ITRE), serve un pool più ampio prima del
            # filtro di rilevanza tematica qui sotto.
            for entry in feed.entries[:30]:
                titolo = pulisci_html(entry.get("title", ""))
                sommario = pulisci_html(
                    entry.get("summary", entry.get("description", ""))
                )
                if not titolo:
                    continue

                testo_completo = f"{titolo} {sommario}".strip()
                if not is_rilevante(testo_completo):
                    continue

                documenti.append({
                    "id_univoco":         _hash(testo_completo),
                    "fonte":              "eu_parl",
                    "sotto_fonte":        nome,
                    "data_pubblicazione": entry.get("published", entry.get("updated", "")),
                    "data_scraping":      datetime.now().isoformat(),
                    "titolo":             titolo,
                    "url":                entry.get("link", ""),
                    "tipo_contenuto":     "notizia_parlamento",
                    "lingua":             "it",
                    "testo_completo":     testo_completo,
                    "hash_contenuto":     _hash(testo_completo),
                })

            time.sleep(0.5)

        except Exception as e:
            logger.error("Errore RSS EP %s: %s", nome, e)

    return documenti


def _scarica_open_data_api() -> list[dict]:
    """
    Interroga l'Open Data API del Parlamento Europeo.
    Restituisce atti legislativi e documenti di commissione,
    filtrando per rilevanza tematica digitale.
    """
    documenti = []

    for query in EP_API_QUERIES:
        logger.info("API EP: %s", query["nome"])
        try:
            resp = requests.get(
                query["endpoint"],
                params=query["params"],
                headers=_HEADERS,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            # L'API EP restituisce JSON-LD con campo "@graph" contenente i record
            items = data.get("@graph", data.get("data", []))
            if not items:
                logger.warning("API EP: risposta vuota per %s", query["nome"])
                continue

            for item in items:
                # Estrai campi con fallback per diversi naming convention dell'API
                titolo = (
                    item.get("label", item.get("title", item.get("rdfs:label", "")))
                )
                if isinstance(titolo, dict):
                    titolo = titolo.get("it", titolo.get("en", ""))
                titolo = str(titolo).strip()

                if not titolo or not is_rilevante(titolo):
                    continue

                url_doc = item.get("seeAlso", item.get("url", item.get("@id", "")))
                data_pub = item.get("date", item.get("created", ""))

                testo_completo = titolo
                sommario = item.get("description", item.get("abstract", ""))
                if sommario:
                    testo_completo = f"{titolo} {str(sommario)[:500]}"

                documenti.append({
                    "id_univoco":         _hash(testo_completo),
                    "fonte":              "eu_parl",
                    "sotto_fonte":        query["nome"],
                    "data_pubblicazione": str(data_pub),
                    "data_scraping":      datetime.now().isoformat(),
                    "titolo":             titolo,
                    "url":                str(url_doc),
                    "tipo_contenuto":     "atto_legislativo",
                    "lingua":             "it",
                    "testo_completo":     testo_completo,
                    "hash_contenuto":     _hash(testo_completo),
                })

            time.sleep(1)  # rispetto rate limit API pubblica

        except requests.HTTPError as e:
            logger.warning("API EP HTTP error %s: %s", query["nome"], e)
        except Exception as e:
            logger.error("Errore API EP %s: %s", query["nome"], e)

    return documenti


def scarica_eu_parlamento() -> pd.DataFrame:
    """Pipeline principale: RSS + Open Data API, deduplicazione per hash."""
    logger.info("Avvio scraper Parlamento Europeo")

    documenti_rss = _scarica_rss()
    # Open Data API disattivata deliberatamente (valutata e scartata il
    # 2026-08-29, non solo "da riscrivere"). Oltre al cambio di schema v1->v2
    # (ELI/JSON-LD annidato invece dei campi piatti label/date/description
    # usati qui sotto), l'endpoint v2 si è rivelato inaffidabile in modo da
    # rendere i dati non attendibili anche con retry perfetti:
    #  - ~50% delle richieste identiche restituisce HTTP 200 ma un body
    #    {"error": "404 Not Found from POST .../view=...-dsd&view-version=v2.0"}
    #    invece dei dati — raise_for_status() non lo intercetta.
    #  - Nessun parametro di ordinamento provato (sort=-document_date,
    #    "document_date desc", sort=-date) restituisce in modo affidabile i
    #    documenti più recenti prima: stessa chiamata, risultati diversi tra
    #    un tentativo e l'altro.
    #  - Il filtro year (es. year=2026) troncava a 1-3 risultati anche con
    #    limit=50, mentre senza filtro anno lo stesso endpoint restituisce
    #    correttamente 10-15 risultati per chiamata — bug del filtro/paginazione
    #    lato server, non dei parametri usati.
    # Costruirci sopra violerebbe i principi del progetto (evidence-based,
    # pipeline deterministiche): senza ordinamento/filtro affidabili non c'è
    # modo di sapere se un campione è davvero "i documenti più recenti" o un
    # sottoinsieme arbitrario. Il feed RSS "Comunicati Stampa" già coperto
    # sopra copre comunque gli sviluppi legislativi in modo affidabile.
    # Endpoint v2 (per riferimento, se l'API si stabilizza in futuro):
    # /adopted-texts, /committee-documents, /procedures (data.europarl.europa.eu/api/v2).
    # documenti_api = _scarica_open_data_api()
    documenti_api = []

    tutti = documenti_rss + documenti_api
    if not tutti:
        return pd.DataFrame()

    df = pd.DataFrame(tutti)
    df = df.drop_duplicates(subset=["hash_contenuto"], keep="last")
    logger.info("Parlamento EU: %d documenti totali (RSS: %d | API: %d)",
                len(df), len(documenti_rss), len(documenti_api))
    return df


if __name__ == "__main__":
    df_ep = scarica_eu_parlamento()

    if not df_ep.empty:
        cartella_script = os.path.dirname(os.path.abspath(__file__))
        cartella_raw = os.path.join(cartella_script, "..", "data", "raw")
        os.makedirs(cartella_raw, exist_ok=True)

        percorso = os.path.join(cartella_raw, "eu_parl_sample.csv")

        if os.path.exists(percorso):
            df_esistente = pd.read_csv(percorso)
            df_unito = pd.concat([df_esistente, df_ep], ignore_index=True)
            df_finale = df_unito.drop_duplicates(subset=["hash_contenuto"], keep="last")
        else:
            df_finale = df_ep

        df_finale.to_csv(percorso, index=False)
        logger.info("Salvato: %s (%d record totali)", percorso, len(df_finale))
    else:
        logger.warning("Nessun documento EP raccolto.")
