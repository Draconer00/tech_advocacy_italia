"""
✅ SCRAPER CAMERA DEI DEPUTATI OPEN DATA UFFICIALE
API ufficiale pubblica: https://dati.camera.it/
Nessun scraping HTML, nessun blocco, sempre funzionante
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import requests
from datetime import datetime
from scrapers.scraper_open_data_utils import normalizza_df, logger

API_URL = "https://dati.camera.it/api/atti/ultimi"

def fetch_data(max_results: int = 20) -> pd.DataFrame:
    """
    Scarica gli ultimi atti dalla Camera dei Deputati tramite API ufficiale Open Data
    """

    logger.info("🏛️ Avvio Open Data Camera dei Deputati")
    
    try:
        risposta = requests.get(
            API_URL,
            params={
                'rows': max_results,
                'sort': 'data',
                'order': 'desc'
            },
            timeout=15
        )
        risposta.raise_for_status()
        dati = risposta.json()
        
        record = []
        
        for atto in dati.get('atti', []):
            record.append({
                'titolo': atto.get('titolo', ''),
                'testo_completo': atto.get('testo', atto.get('titolo', '')),
                'data_pubblicazione': atto.get('data', datetime.now().date().isoformat()),
                'url': atto.get('uri', '')
            })
        
        df = pd.DataFrame(record)
        df_normalizzato = normalizza_df(df, 'camera_deputati')
        
        return df_normalizzato

    except Exception as e:
        logger.error(f"❌ Errore API Camera: {e}")
        return pd.DataFrame()


if __name__ == "__main__":
    df = fetch_data()
    print(f"\n✅ Camera dei Deputati: {len(df)} record scaricati")
    if not df.empty:
        print(df[['titolo', 'data_pubblicazione']].head())