"""
Profilo di parole chiave curate per ONG, usato per arricchire il matching
Notizia -> ONG nel grafo "Network Temi" della dashboard.

A differenza di `PROFILI_ONG['focus']` (in scrapers/scraper_ong.py, pensato
per generare i nodi Tema del grafo e modificabile solo via PR sul codice),
questo file è una tabella di configurazione piccola e umana, editabile da
chiunque usa la dashboard. Non è un dataset di evidenze grezze: per questo
è consentito sovrascriverla (con backup timestampato) invece di trattarla
come archivio append-only.
"""
import os
from datetime import datetime

import pandas as pd

from utils.logger_config import setup_logger

logger = setup_logger(__name__)

PROFILO_COLUMNS: list[str] = ["nome_organizzazione", "parola_chiave"]

DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "config", "ong_keywords_profilo.csv"
)


def carica_profilo_keywords_ong(path: str = DEFAULT_PATH) -> dict[str, list[str]]:
    """Legge il profilo e lo raggruppa per ONG. Ritorna {} se il file non esiste."""
    if not os.path.exists(path):
        return {}

    df = pd.read_csv(path)
    if df.empty or not set(PROFILO_COLUMNS).issubset(df.columns):
        return {}

    profilo: dict[str, list[str]] = {}
    for nome_ong, gruppo in df.groupby("nome_organizzazione"):
        parole = [
            str(p).strip()
            for p in gruppo["parola_chiave"].tolist()
            if str(p).strip()
        ]
        if parole:
            profilo[nome_ong] = sorted(set(parole))
    return profilo


def salva_profilo_keywords_ong(nome_organizzazione: str, parole_chiave: list[str], path: str = DEFAULT_PATH) -> None:
    """
    Sostituisce la lista di parole chiave dell'ONG indicata, preservando quelle
    delle altre ONG. Crea un backup timestampato del file esistente prima di
    sovrascriverlo (stesso pattern di app/db_manager.py).
    """
    profilo = carica_profilo_keywords_ong(path)

    parole_pulite = sorted({str(p).strip() for p in parole_chiave if str(p).strip()})
    if parole_pulite:
        profilo[nome_organizzazione] = parole_pulite
    else:
        profilo.pop(nome_organizzazione, None)

    righe = [
        {"nome_organizzazione": nome_ong, "parola_chiave": parola}
        for nome_ong, parole in profilo.items()
        for parola in parole
    ]
    df_nuovo = pd.DataFrame(righe, columns=PROFILO_COLUMNS)

    os.makedirs(os.path.dirname(path), exist_ok=True)

    if os.path.exists(path):
        percorso_backup = path + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        pd.read_csv(path).to_csv(percorso_backup, index=False)
        logger.info("Backup profilo ONG creato: %s", percorso_backup)

    df_nuovo.to_csv(path, index=False)
    logger.info(
        "Profilo parole chiave aggiornato per '%s': %d termini (%d ONG totali in profilo).",
        nome_organizzazione, len(parole_pulite), len(profilo),
    )
