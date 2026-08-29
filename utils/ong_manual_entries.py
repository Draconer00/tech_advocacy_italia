"""
Documenti ONG inseriti manualmente dalla dashboard (tab "Campagne ONG").

Tenuti in un file SEPARATO da data/processed/ong_analyzed.csv perché quel file
viene rigenerato integralmente dalla pipeline NLP (nlp/text_analysis.py::main(),
dedup su 'titolo') — scrivere righe manuali lì le esporrebbe a essere
cancellate silenziosamente al prossimo run della pipeline, violando la regola
"mantieni archivi storici permanenti" di CLAUDE.md.

Questo file non viene mai toccato dalla pipeline: viene solo unito in lettura
a ong_analyzed.csv da app/dashboard.py::carica_dati_ong().
"""
import hashlib
import os
from datetime import datetime

import pandas as pd

from utils.logger_config import setup_logger

logger = setup_logger(__name__)

MANUAL_COLUMNS: list[str] = [
    "id_univoco",
    "nome_organizzazione",
    "titolo",
    "testo_completo",
    "data_pubblicazione",
    "url",
    "fonte",
    "data_scraping",
    "hash_contenuto",
    "livello_allarme",
    "tipo_contenuto",
]

DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "processed", "ong_manual_entries.csv"
)


def carica_documenti_manuali(path: str = DEFAULT_PATH) -> pd.DataFrame:
    """Carica i documenti ONG inseriti a mano. Ritorna un DataFrame vuoto (con le colonne canoniche) se il file non esiste."""
    if not os.path.exists(path):
        return pd.DataFrame(columns=MANUAL_COLUMNS)

    df = pd.read_csv(path)
    return df.reindex(columns=MANUAL_COLUMNS)


def salva_documento_manuale(
    nome_organizzazione: str,
    titolo: str,
    testo: str,
    data_pubblicazione,
    url: str,
    path: str = DEFAULT_PATH,
) -> None:
    """
    Aggiunge un documento ONG inserito a mano. Titolo, testo, data e url sono
    obbligatori: solleva ValueError se uno manca (mai inventare dati mancanti).

    Dedup idempotente su hash_contenuto: un doppio invio dello stesso form
    (stesso testo per la stessa ONG) non crea una riga duplicata.
    """
    campi_obbligatori = {
        "nome_organizzazione": nome_organizzazione,
        "titolo": titolo,
        "testo": testo,
        "data_pubblicazione": data_pubblicazione,
        "url": url,
    }
    mancanti = [nome for nome, valore in campi_obbligatori.items() if not str(valore or "").strip()]
    if mancanti:
        raise ValueError(f"Campi obbligatori mancanti: {', '.join(mancanti)}")

    hash_contenuto = hashlib.sha256(
        f"{nome_organizzazione}{titolo}{testo}".encode("utf-8")
    ).hexdigest()

    nuova_riga = pd.DataFrame([{
        "id_univoco": hash_contenuto,
        "nome_organizzazione": nome_organizzazione.strip(),
        "titolo": titolo.strip(),
        "testo_completo": testo.strip(),
        "data_pubblicazione": pd.to_datetime(data_pubblicazione).strftime("%Y-%m-%d"),
        "url": url.strip(),
        "fonte": "manuale",
        "data_scraping": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "hash_contenuto": hash_contenuto,
        "livello_allarme": 1,
        "tipo_contenuto": "Comunicato Manuale",
    }])

    esistenti = carica_documenti_manuali(path)
    if hash_contenuto in set(esistenti["hash_contenuto"]):
        logger.info("Documento manuale già presente (hash %s), invio ignorato.", hash_contenuto[:8])
        return

    unito = pd.concat([esistenti, nuova_riga], ignore_index=True)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    unito.to_csv(path, index=False)
    logger.info(
        "Documento manuale aggiunto per '%s': '%s' (totale documenti manuali: %d).",
        nome_organizzazione, titolo[:60], len(unito),
    )
