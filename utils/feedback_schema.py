"""
Schema canonico per il file di feedback human-in-the-loop.

Unica fonte di verità condivisa tra il *writer* (la dashboard, che salva le
correzioni) e i *reader* (gli script di training che le consumano). Prima di
questo modulo writer e reader divergevano: la dashboard scriveva 12 colonne in
append con header=False su un file legacy a 8 colonne, producendo un CSV con
righe di lunghezza variabile che i trainer non riuscivano a leggere
(le correzioni di urgenza venivano scartate da on_bad_lines='skip').

Le funzioni qui sotto garantiscono che il file resti sempre allineato allo
schema canonico e migrano in modo trasparente i file legacy.
"""
import os

import pandas as pd

from utils.logger_config import setup_logger

logger = setup_logger(__name__)

# Ordine canonico delle colonne, identico a quello prodotto dalla dashboard.
FEEDBACK_COLUMNS: list[str] = [
    "data",
    "fonte",
    "titolo",
    "ambito_geografico",
    "livello_allarme",            # punteggio urgenza predetto dall'AI
    "errore_segnalato",           # True se l'operatore ha segnalato la riga
    "categoria_corretta",         # correzione geografica (o "Non modificato")
    "livello_allarme_corretto",   # urgenza reale assegnata dall'operatore (label)
    "ong_collegata_corretta",     # ONG associata corretta a mano
    "timestamp_correzione",
    "utente",
    "tipo_correzione",
]

# Schema storico (pre-fix): la dashboard salvava solo queste 8 colonne, senza
# alcuna informazione di urgenza. Serve a riconoscere e migrare le righe legacy.
LEGACY_COLUMNS: list[str] = [
    "data",
    "fonte",
    "titolo",
    "ambito_geografico",
    "errore_segnalato",
    "categoria_corretta",
    "timestamp_correzione",
    "utente",
]


def _normalizza(df: pd.DataFrame) -> pd.DataFrame:
    """Reindex al set canonico: colonne mancanti -> NA, ordine fisso, niente extra."""
    return df.reindex(columns=FEEDBACK_COLUMNS)


def load_feedback(path: str) -> pd.DataFrame:
    """
    Carica il file di feedback in modo robusto, tollerando file legacy o misti.

    Ogni riga viene parsata con il modulo csv (gestisce correttamente le virgole
    dentro i campi quotati) e classificata in base al numero di campi:
    12 -> schema canonico, 8 -> schema legacy. Le righe di lunghezza diversa
    vengono loggate e saltate invece di corrompere il DataFrame.

    Restituisce sempre un DataFrame con le colonne FEEDBACK_COLUMNS
    (vuoto se il file non esiste).
    """
    if not os.path.exists(path):
        return pd.DataFrame(columns=FEEDBACK_COLUMNS)

    import csv

    righe_canoniche: list[dict] = []
    saltate = 0
    with open(path, "r", encoding="utf-8", newline="") as f:
        for i, campi in enumerate(csv.reader(f)):
            if not campi:
                continue
            # Salta eventuali righe header (canonico o legacy)
            if campi[0] == "data" and ("fonte" in campi or "titolo" in campi):
                continue
            if len(campi) == len(FEEDBACK_COLUMNS):
                righe_canoniche.append(dict(zip(FEEDBACK_COLUMNS, campi)))
            elif len(campi) == len(LEGACY_COLUMNS):
                righe_canoniche.append(dict(zip(LEGACY_COLUMNS, campi)))
            else:
                saltate += 1
                logger.warning(
                    "Riga feedback %d ignorata: %d campi (attesi %d o %d)",
                    i + 1, len(campi), len(FEEDBACK_COLUMNS), len(LEGACY_COLUMNS),
                )

    if saltate:
        logger.warning("Totale righe feedback saltate per formato non valido: %d", saltate)

    if not righe_canoniche:
        return pd.DataFrame(columns=FEEDBACK_COLUMNS)

    return _normalizza(pd.DataFrame(righe_canoniche))


def append_correzioni(modifiche: pd.DataFrame, path: str) -> None:
    """
    Aggiunge nuove correzioni al file di feedback mantenendolo allineato allo
    schema canonico.

    - Se il file non esiste: lo crea con header canonico.
    - Se l'header esistente combacia con lo schema canonico: append senza header.
    - Altrimenti (file legacy/misto): lo ri-normalizza interamente — carica il
      contenuto esistente con load_feedback(), concatena le nuove righe e
      riscrive il file pulito. Operazione di self-healing una tantum.

    `modifiche` può avere colonne in più o in meno: viene reindicizzato.
    """
    modifiche_norm = _normalizza(modifiche)

    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        modifiche_norm.to_csv(path, mode="w", header=True, index=False)
        logger.info("Creato nuovo file feedback: %s", path)
        return

    # Confronta l'header esistente con lo schema canonico.
    with open(path, "r", encoding="utf-8", newline="") as f:
        prima_riga = f.readline().strip()
    header_esistente = [c.strip() for c in prima_riga.split(",")]

    if header_esistente == FEEDBACK_COLUMNS:
        modifiche_norm.to_csv(path, mode="a", header=False, index=False)
        logger.info("Aggiunte %d correzioni a %s", len(modifiche_norm), path)
    else:
        logger.warning(
            "Header feedback non canonico in %s: ri-normalizzo l'intero file.", path
        )
        esistenti = load_feedback(path)
        unito = pd.concat([esistenti, modifiche_norm], ignore_index=True)
        unito.to_csv(path, mode="w", header=True, index=False)
        logger.info(
            "File feedback ri-normalizzato: %d righe totali (%d nuove).",
            len(unito), len(modifiche_norm),
        )
