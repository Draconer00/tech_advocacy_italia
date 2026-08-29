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


# Keyword per filtrare per rilevanza tematica digitale/privacy/AI.
# Tarato originariamente su scraper_eu_parl.py per il feed comunicati stampa
# delle commissioni EP, già di per sé a perimetro legislativo/digitale.
KEYWORD_DIGITALE: frozenset[str] = frozenset({
    "privacy", "dati", "intelligenza artificiale", "ai act", "dsa", "dma",
    "digitale", "cybersecurity", "algoritmo", "sorveglianza", "biometrico",
    "gdpr", "protezione dati", "piattaforme", "libertà", "diritti digitali",
    "nis2", "dora", "eidas", "sicurezza informatica",
})

# Versione più restrittiva per corpora eterogenei (giurisprudenza CJEU su
# tutte le materie, legislazione italiana generale in Gazzetta Ufficiale).
# KEYWORD_DIGITALE usa parole singole generiche ("libertà", "sicurezza",
# "digitale") che su un corpus generalista producono falsi positivi
# verificati: sul feed CJEU, "libertà" ha intercettato cause di estradizione
# solo perché rientrano nell'area "Spazio di libertà, sicurezza e
# giustizia" (verificato live il 2026-08-29). Qui si richiedono termini
# specifici del dominio privacy/AI/digitale, non parole isolate.
KEYWORD_DIGITALE_STRETTO: frozenset[str] = frozenset({
    "protezione dei dati", "protezione dati", "dati personali",
    "intelligenza artificiale", "ai act", "servizi digitali",
    "mercati digitali", "gdpr", "cybersicurezza", "sicurezza informatica",
    "dati biometrici", "dato biometrico", "sorveglianza digitale",
    "sorveglianza di massa", "piattaforme digitali", "piattaforma online",
    "diritti digitali", "algoritmo decisionale", "algoritmi decisionali",
    "nis2", "eidas", "dora",
})


def is_rilevante(testo: str, keywords: frozenset[str] = KEYWORD_DIGITALE) -> bool:
    """
    Filtro di rilevanza tematica su un blob di testo.
    Default KEYWORD_DIGITALE (feed già a perimetro legislativo/digitale,
    es. commissioni EP). Passare keywords=KEYWORD_DIGITALE_STRETTO per
    corpora generalisti dove le parole singole generano falsi positivi
    (es. CJEU, Gazzetta Ufficiale Serie Generale).
    """
    tl = testo.lower()
    return any(kw in tl for kw in keywords)


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