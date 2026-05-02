"""
✅ DEDUPLICAZIONE SEMANTICA AVANZATA
Modello: paraphrase-multilingual-MiniLM-L12-v2
Clustering DBSCAN su similarità coseno
"""

import os
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.cluster import DBSCAN

# Configurazione
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
EPS_THRESHOLD = 0.15
MIN_SAMPLES = 2

# Cache modello
model = None

def get_embedding_model():
    global model
    if model is None:
        print(f"✅ Caricamento modello deduplicazione: {MODEL_NAME}")
        model = SentenceTransformer(MODEL_NAME, device='cpu')
    return model


def deduplica_dataframe(df: pd.DataFrame, colonna_testo: str = 'testo_completo') -> pd.DataFrame:
    """
    Deduplica un dataframe tramite embedding semantico e clustering DBSCAN
    
    Aggiunge colonne:
    - cluster_id: identificatore cluster
    - is_primary: True se è il rappresentante principale del cluster
    """
    
    if len(df) == 0:
        return df
    
    model = get_embedding_model()
    
    print(f"🔍 Inizio deduplicazione semantica: {len(df)} record")
    
    # Calcola embeddings
    embeddings = model.encode(
        df[colonna_testo].tolist(),
        show_progress_bar=False,
        batch_size=32
    )
    
    # Clustering DBSCAN su distanza coseno
    clustering = DBSCAN(
        eps=EPS_THRESHOLD,
        min_samples=MIN_SAMPLES,
        metric='cosine',
        n_jobs=-1
    )
    
    cluster_ids = clustering.fit_predict(embeddings)
    
    df['cluster_id'] = cluster_ids
    
    # Segna il record principale per ogni cluster
    df['is_primary'] = False
    
    cluster_visti = set()
    
    for idx, cluster_id in enumerate(cluster_ids):
        if cluster_id == -1:
            # Rumore, non fa parte di nessun cluster, è primario
            df.at[idx, 'is_primary'] = True
        elif cluster_id not in cluster_visti:
            # Primo elemento del cluster, contrassegna come primario
            df.at[idx, 'is_primary'] = True
            cluster_visti.add(cluster_id)
    
    num_clusters = len(set(cluster_ids)) - (1 if -1 in cluster_ids else 0)
    num_rumore = list(cluster_ids).count(-1)
    
    print(f"✅ Deduplicazione completata")
    print(f"  📊 Cluster trovati: {num_clusters}")
    print(f"  📊 Record unici: {num_rumore + num_clusters}")
    print(f"  📊 Duplicati rimossi: {len(df) - (num_rumore + num_clusters)}")
    
    return df