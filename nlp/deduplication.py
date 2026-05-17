"""
Deduplicazione semantica via sentence-transformers + DBSCAN su coseno.
Modello: paraphrase-multilingual-MiniLM-L12-v2
"""

import os
import sys

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.cluster import DBSCAN

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from utils.logger_config import setup_logger

logger = setup_logger(__name__)

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
EPS_THRESHOLD = 0.15
MIN_SAMPLES = 2

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Caricamento modello deduplicazione: %s", MODEL_NAME)
        _model = SentenceTransformer(MODEL_NAME, device='cpu')
    return _model


def deduplica_dataframe(
    df: pd.DataFrame,
    colonna_testo: str = 'testo_completo',
) -> pd.DataFrame:
    """
    Deduplica un DataFrame tramite embedding semantico e clustering DBSCAN.

    Aggiunge colonne:
    - cluster_id:  ID del cluster (-1 = nessun cluster / rumore)
    - is_primary:  True se è il rappresentante principale del cluster
    """
    if df.empty:
        return df

    model = _get_model()
    logger.info("Inizio deduplicazione semantica: %d record", len(df))

    embeddings = model.encode(
        df[colonna_testo].tolist(),
        show_progress_bar=False,
        batch_size=32,
    )

    cluster_ids: np.ndarray = DBSCAN(
        eps=EPS_THRESHOLD,
        min_samples=MIN_SAMPLES,
        metric='cosine',
        n_jobs=-1,
    ).fit_predict(embeddings)

    df = df.copy()
    df['cluster_id'] = cluster_ids
    df['is_primary'] = False

    cluster_visti: set = set()
    for idx, cid in enumerate(cluster_ids):
        if cid == -1:
            df.at[idx, 'is_primary'] = True
        elif cid not in cluster_visti:
            df.at[idx, 'is_primary'] = True
            cluster_visti.add(cid)

    num_clusters = len(set(cluster_ids)) - (1 if -1 in cluster_ids else 0)
    num_rumore = int((cluster_ids == -1).sum())
    duplicati = len(df) - (num_rumore + num_clusters)

    logger.info(
        "Deduplicazione completata — cluster: %d | unici: %d | duplicati rimossi: %d",
        num_clusters, num_rumore + num_clusters, duplicati,
    )
    return df
