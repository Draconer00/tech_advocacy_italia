"""
✅ SCRAPER EUR-LEX OPEN DATA UFFICIALE
Cellar API ufficiale: https://eur-lex.europa.eu/api/
Nessun scraping HTML, nessun Cloudflare, sempre funzionante
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import requests
from datetime import datetime
from scrapers.scraper_open_data_utils import normalizza_df, logger

API_URL = "https://eur-lex.europa.eu/api/search"

def fetch_data(max_results: int = 20) -> pd.DataFrame:
    """
    Scarica documenti recenti da EUR-Lex tramite API ufficiale Cellar
    """

    logger.info("📚 Avvio Open Data EUR-Lex Commissione Europea")
    
    try:
        risposta = requests.get(
            API_URL,
            params={
                'query': 'gdpr OR privacy OR "dati personali" OR "intelligenza artificiale"',
                'lang': 'it',
                'pageSize': max_results,
                'sort': 'date',
                'dir': 'desc'
            },
            timeout=15
        )
        risposta.raise_for_status()
        dati = risposta.json()
        
        record = []
        
        for documento in dati.get('results', []):
            record.append({
                'titolo': documento.get('title', ''),
                'testo_completo': documento.get('abstract', documento.get('title', '')),
                'data_pubblicazione': documento.get('date', datetime.now().date().isoformat()),
                'url': documento.get('uri', '')
            })
        
        df = pd.DataFrame(record)
        df_normalizzato = normalizza_df(df, 'eurlex')
        
        return df_normalizzato

    except Exception as e:
        logger.error(f"❌ Errore API EUR-Lex: {e}")
        return pd.DataFrame()


if __name__ == "__main__":
    df = fetch_data()
    print(f"\n✅ EUR-Lex: {len(df)} record scaricati")
    if not df.empty:
        print(df[['titolo', 'data_pubblicazione']].head())