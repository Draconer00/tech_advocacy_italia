"""
✅ UTILITÀ COMUNI PER SCRAPER OPEN DATA
Funzioni condivise e normalizzazione standard
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import hashlib
from datetime import datetime

try:
    from utils.logger_config import setup_logger
    logger = setup_logger(__name__)
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)


def normalizza_df(df: pd.DataFrame, fonte_nome: str) -> pd.DataFrame:
    """
    Normalizza qualsiasi DataFrame allo standard del progetto
    Aggiunge tutte le colonne richieste e gestisce valori nulli
    """
    
    colonne_standard = [
        'id_univoco',
        'fonte',
        'data_pubblicazione',
        'data_scraping',
        'titolo',
        'url',
        'tipo_contenuto',
        'lingua',
        'testo_completo',
        'hash_contenuto'
    ]
    
    df_normalizzato = df.copy()
    
    # ✅ Aggiungi campi standard mancanti
    if 'fonte' not in df_normalizzato.columns:
        df_normalizzato['fonte'] = fonte_nome
    
    if 'data_scraping' not in df_normalizzato.columns:
        df_normalizzato['data_scraping'] = datetime.now().isoformat()
    
    if 'lingua' not in df_normalizzato.columns:
        df_normalizzato['lingua'] = 'it'
    
    if 'tipo_contenuto' not in df_normalizzato.columns:
        df_normalizzato['tipo_contenuto'] = 'documento'
    
    # ✅ Calcola hash e id univoco se mancanti
    if 'hash_contenuto' not in df_normalizzato.columns and 'testo_completo' in df_normalizzato.columns:
        df_normalizzato['hash_contenuto'] = df_normalizzato['testo_completo'].apply(
            lambda x: hashlib.sha256(str(x).encode('utf-8')).hexdigest()
        )
    
    if 'id_univoco' not in df_normalizzato.columns:
        df_normalizzato['id_univoco'] = df_normalizzato['hash_contenuto']
    
    # ✅ Riempi valori nulli
    df_normalizzato = df_normalizzato.fillna('')
    
    # ✅ Garantisci che esistano TUTTE le colonne standard
    for col in colonne_standard:
        if col not in df_normalizzato.columns:
            df_normalizzato[col] = ''
    
    # ✅ Rimuovi duplicati
    df_normalizzato = df_normalizzato.drop_duplicates(subset=['hash_contenuto'], keep='last')
    
    logger.info(f"✅ Normalizzato {fonte_nome}: {len(df_normalizzato)} record")
    
    return df_normalizzato[colonne_standard]