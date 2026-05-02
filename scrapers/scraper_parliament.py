"""
✅ SCRAPER PARLAMENTO ITALIANO
Scarica atti e comunicati recenti dal sito ufficiale della Camera dei Deputati
Compatibile al 100% con il resto della pipeline
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hashlib
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from utils.logger_config import setup_logger

logger = setup_logger(__name__)

URL_PARLAMENTO = "https://www.camera.it/leg19/124?lang=it"

def pulisci_html(testo: str) -> str:
    """Pulisce tag HTML e whitespace superfluo"""
    if not testo:
        return ""
    testo = BeautifulSoup(testo, "html.parser").get_text(separator=" ", strip=True)
    return ' '.join(testo.split())

def fetch_data() -> pd.DataFrame:
    """
    Scarica documenti recenti dal Parlamento italiano
    Restituisce DataFrame compatibile con lo standard del progetto
    
    Colonne output:
    - id_univoco
    - fonte
    - data_pubblicazione
    - data_scraping
    - titolo
    - url
    - tipo_contenuto
    - lingua
    - testo_completo
    - hash_contenuto
    """

    logger.info("🏛️ Avvio scraping Parlamento italiano")
    
    record_trovati = []

    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        risposta = session.get(URL_PARLAMENTO, timeout=15)
        risposta.raise_for_status()

        zuppa = BeautifulSoup(risposta.content, 'html.parser')

        for elemento in zuppa.select('.lista_atti li')[:15]:
            
            try:
                tag_a = elemento.find('a')
                if not tag_a:
                    continue
                
                titolo = tag_a.get_text(strip=True)
                link = tag_a['href']
                
                if not link.startswith('http'):
                    link = "https://www.camera.it" + link
                
                data_elemento = elemento.find(class_='data')
                data_pubblicazione = data_elemento.get_text(strip=True) if data_elemento else datetime.now().date().isoformat()
                
                testo_completo = titolo
                hash_contenuto = hashlib.sha256(testo_completo.encode('utf-8')).hexdigest()

                record_trovati.append({
                    'id_univoco': hash_contenuto,
                    'fonte': 'parlamento_italiano',
                    'data_pubblicazione': data_pubblicazione,
                    'data_scraping': datetime.now().isoformat(),
                    'titolo': titolo,
                    'url': link,
                    'tipo_contenuto': 'atto_parlamentare',
                    'lingua': 'it',
                    'testo_completo': pulisci_html(testo_completo),
                    'hash_contenuto': hash_contenuto
                })

            except Exception as e:
                logger.warning(f"⚠️ Errore estrazione elemento Parlamento: {e}")
                continue

        df = pd.DataFrame(record_trovati)
        logger.info(f"✅ Parlamento italiano: scaricati {len(df)} atti")
        
        # ✅ Log dettagliato come negli altri scraper
        print("\n✅ Prime 3 righe estratte Parlamento Italiano:")
        print(df[['titolo', 'data_pubblicazione']].head(3))
        
        return df

    except Exception as e:
        logger.error(f"❌ Errore generale scraping Parlamento: {e}")
        return pd.DataFrame()


if __name__ == "__main__":
    df = fetch_data()
    if not df.empty:
        print(f"\n✅ Risultato: {len(df)} record")
        print(df[['titolo', 'data_pubblicazione']].head())