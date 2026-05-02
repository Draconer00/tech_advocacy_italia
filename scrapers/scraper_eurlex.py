"""
✅ SCRAPER EUR-LEX PORTALE UFFICIALE EUROPEO
Scarica atti legislativi recenti pubblicati sulla Gazzetta Ufficiale Europea
Compatibile al 100% con il resto della pipeline
"""

import hashlib
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from utils.logger_config import setup_logger

logger = setup_logger(__name__)

URL_EURLEX = "https://eur-lex.europa.eu/search.html?lang=it&type=quick&qid=1714691460666&scope=EURLEX&text=gdpr+privacy+dati"

def pulisci_html(testo: str) -> str:
    """Pulisce tag HTML e whitespace superfluo"""
    if not testo:
        return ""
    testo = BeautifulSoup(testo, "html.parser").get_text(separator=" ", strip=True)
    return ' '.join(testo.split())

def fetch_data() -> pd.DataFrame:
    """
    Scarica documenti recenti da EUR-Lex
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

    logger.info("📚 Avvio scraping EUR-Lex portale europeo")
    
    record_trovati = []

    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        risposta = session.get(URL_EURLEX, timeout=15)
        risposta.raise_for_status()

        zuppa = BeautifulSoup(risposta.content, 'html.parser')

        for elemento in zuppa.select('.SearchResult')[:10]:
            
            try:
                titolo = elemento.find('a', class_='title').get_text(strip=True)
                link = elemento.find('a', class_='title')['href']
                
                if not link.startswith('http'):
                    link = "https://eur-lex.europa.eu" + link
                
                data_pubblicazione = elemento.find(class_='date').get_text(strip=True) if elemento.find(class_='date') else datetime.now().date().isoformat()
                sommario = elemento.find(class_='abstract').get_text(strip=True) if elemento.find(class_='abstract') else ""
                
                testo_completo = f"{titolo} {sommario}"
                hash_contenuto = hashlib.sha256(testo_completo.encode('utf-8')).hexdigest()

                record_trovati.append({
                    'id_univoco': hash_contenuto,
                    'fonte': 'eurlex',
                    'data_pubblicazione': data_pubblicazione,
                    'data_scraping': datetime.now().isoformat(),
                    'titolo': titolo,
                    'url': link,
                    'tipo_contenuto': 'atto_legislativo',
                    'lingua': 'it',
                    'testo_completo': pulisci_html(testo_completo),
                    'hash_contenuto': hash_contenuto
                })

            except Exception as e:
                logger.warning(f"⚠️ Errore estrazione elemento EUR-Lex: {e}")
                continue

        df = pd.DataFrame(record_trovati)
        logger.info(f"✅ EUR-Lex: scaricati {len(df)} documenti legislativi")
        
        return df

    except Exception as e:
        logger.error(f"❌ Errore generale scraping EUR-Lex: {e}")
        return pd.DataFrame()


if __name__ == "__main__":
    df = fetch_data()
    if not df.empty:
        print(f"\n✅ Risultato: {len(df)} record")
        print(df[['titolo', 'data_pubblicazione']].head())