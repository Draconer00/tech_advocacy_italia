import os
from datetime import datetime

import pandas as pd
import requests

from utils.logger_config import setup_logger

logger = setup_logger(__name__)

from .gnews_config import DEFAULT_QUERY, GNEWS_URL


def _format_published_at(published_at: str) -> str:
    if not published_at:
        return ""
    try:
        # Prova a parsare come ISO 8601 e formatta come data
        dt_object = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        return dt_object.date().isoformat()
    except ValueError:
        # Se fallisce, prova a estrarre la parte della data se presente un 'T'
        if "T" in published_at:
            return published_at.split("T")[0]
        # Altrimenti, restituisci la stringa originale se non parsabile
        return published_at


def fetch_gnews(
    api_key: str,
    query: str = DEFAULT_QUERY,
    lang: str = "it",
    country: str = "it",
    max_results: int = 15,
    timeout: int = 10,
) -> pd.DataFrame:
    """Scarica articoli da GNews e restituisce un DataFrame."""

    if not api_key:
        raise ValueError("La chiave API GNews è richiesta")

    params = {
        "q": query,
        "lang": lang,
        "country": country,
        "max": max_results,
        "apikey": api_key,
    }

    logger.info("📰 Avvio ricerca GNews: lang=%s country=%s max=%s", lang, country, max_results)

    try:
        return _make_gnews_request(params, timeout)
    except ValueError as e:
        logger.error("Errore nella richiesta GNews: %s", e)
        return pd.DataFrame()
    except requests.RequestException as e:
        logger.error("Errore di connessione GNews: %s", e)
        return pd.DataFrame()

def _make_gnews_request(params: dict, timeout: int) -> dict:
    risposta = requests.get(GNEWS_URL, params=params, timeout=timeout)

    if risposta.status_code in {401, 403}:
        raise ValueError(f"Errore API {risposta.status_code}: chiave non valida o limite superato")

    risposta.raise_for_status()  # Solleva un HTTPError per altri codici di stato di errore
    return risposta.json()

        articoli = dati_json.get("articles", [])

        if not articoli:
            logger.warning("Nessun articolo trovato con la query fornita")
            return pd.DataFrame()

        notizie_estratte = []
        for articolo in articoli:
            source = articolo.get("source", {})
            notizie_estratte.append(
                {
                    "Testata": source.get("name", ""),
                    "Data": _format_published_at(articolo.get("publishedAt", "")),
                    "Titolo": articolo.get("title", ""),
                    "Riassunto": articolo.get("description", ""),
                    "Link": articolo.get("url", ""),
                }
            )
            logger.info("  - [%s] %s", source.get("name", ""), (articolo.get("title") or "")[:70])

        df_news = pd.DataFrame(notizie_estratte)
        logger.info("✅ Trovati %d articoli", len(df_news))
        return df_news

    except requests.RequestException as e:
        logger.error("Errore connessione GNews: %s", e)
        return pd.DataFrame()


if __name__ == "__main__":
    api_key = os.getenv("GNEWS_API_KEY")
    if not api_key:
        logger.error("Variabile d'ambiente GNEWS_API_KEY non impostata. Imposta la chiave API prima di eseguire.")
        raise SystemExit(1)

    df_stampa = fetch_gnews(api_key=api_key)

    if not df_stampa.empty:
        cartella_script = os.path.dirname(os.path.abspath(__file__))
        cartella_raw = os.path.normpath(os.path.join(cartella_script, "..", "data", "raw"))
        os.makedirs(cartella_raw, exist_ok=True)

        percorso_salvataggio = os.path.join(cartella_raw, "gnews_sample.csv")
        df_stampa.to_csv(percorso_salvataggio, index=False)
        logger.info("💾 Dati salvati in: %s", percorso_salvataggio)
