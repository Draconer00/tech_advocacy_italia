"""
✅ SCRAPER SENATO DELLA REPUBBLICA OPEN DATA UFFICIALE
API ufficiale pubblica: https://dati.senato.it/
Nessun scraping HTML, nessun blocco, sempre funzionante
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import requests
from datetime import datetime
from scrapers.scraper_open_data_utils import normalizza_df, logger

API_URL = "https://dati.senato.it/api/atti"

def fetch_data(max_results: int = 20) -> pd.DataFrame:
    """
    Scarica gli ultimi atti dal Senato tramite API ufficiale Open Data
    """

    logger.info("🏛️ Avvio Open Data Senato della Repubblica")
    
    try:
        risposta = requests.get(
            API_URL,
            params={
                '$limit': max_results,
                '$orderby': 'dataInserimento desc'
            },
            timeout=15
        )
        risposta.raise_for_status()
        dati = risposta.json()
        
        record = []
        
        for atto in dati:
            record.append({
                'titolo': atto.get('titolo', ''),
                'testo_completo': atto.get('descrizione', atto.get('titolo', '')),
                'data_pubblicazione': atto.get('dataInserimento', datetime.now().date().isoformat()),
                'url': atto.get('url', '')
            })
        
        df = pd.DataFrame(record)
        df_normalizzato = normalizza_df(df, 'senato')
        
        return df_normalizzato

    except Exception as e:
        logger.error(f"❌ Errore API Senato: {e}")
        return pd.DataFrame()


if __name__ == "__main__":
    df = fetch_data()
    print(f"\n✅ Senato: {len(df)} record scaricati")
    if not df.empty:
        print(df[['titolo', 'data_pubblicazione']].head())