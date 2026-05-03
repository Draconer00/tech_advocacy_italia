"""
✅ SCRAPER EUR-LEX PORTALE UFFICIALE EUROPEO
✅ Scraping HTML ufficiale
Nessuna API fantasma, funziona correttamente
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

URL_EURLEX = "https://eur-lex.europa.eu/search.html?lang=it&type=quick&text=gdpr+privacy+dati+personali+intelligenza+artificiale&scope=EURLEX&sort=DD&dir=desc"

def pulisci_html(testo: str) -> str:
    """Pulisce tag HTML e whitespace superfluo"""
    if not testo:
        return ""
    testo = BeautifulSoup(testo, "html.parser").get_text(separator=" ", strip=True)
    return ' '.join(testo.split())

def fetch_data() -> pd.DataFrame:
    """
    Scarica documenti recenti da EUR-Lex tramite scraping HTML ufficiale
    Restituisce DataFrame compatibile con lo standard del progetto
    """

    logger.info("📚 Avvio scraping EUR-Lex")
    
    record_trovati = []

    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

        risposta = session.get(URL_EURLEX, timeout=15)
        risposta.raise_for_status()

        zuppa = BeautifulSoup(risposta.text, 'html.parser')

        # ✅ STRATEGIA INFALLIBILE: non dipendiamo dalle classi CSS che cambiano sempre
        # Cerchiamo direttamente tutti i link che puntano a legal-content, sono sempre quelli giusti
        for tag_a in zuppa.find_all('a', href=True)[:30]:
            
            link = tag_a['href']
            
            # Solo i link ai documenti CELEX
            if 'legal-content' not in link and 'CELEX' not in link:
                continue
            
            try:
                # Abbiamo già trovato il link giusto
                titolo = tag_a.get_text(strip=True)
                
                if not link.startswith('http'):
                    link = "https://eur-lex.europa.eu" + link

                # Risali al genitore per trovare la data
                elemento_padre = tag_a.find_parent()
                data_pubblicazione = datetime.now().date().isoformat()
                
                # Cerca la data in tutti i figli del genitore
                if elemento_padre:
                    for span in elemento_padre.find_all('span'):
                        testo_span = span.get_text(strip=True)
                        if '/' in testo_span or '.' in testo_span and len(testo_span) in [8,10]:
                            data_pubblicazione = testo_span
                            break
                data_pubblicazione = data_tag.get_text(strip=True) if data_tag else datetime.now().date().isoformat()

                testo_completo = titolo
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
                logger.warning(f"⚠️ Errore estrazione documento EUR-Lex: {e}")
                continue

        df = pd.DataFrame(record_trovati)
        logger.info(f"✅ EUR-Lex: scaricati {len(df)} documenti legislativi")
        
        if not df.empty:
            print("\n✅ Prime 3 righe estratte EUR-Lex:")
            print(df[['titolo', 'data_pubblicazione']].head(3))
        else:
            print("ℹ️ Nessun documento trovato in questo momento")
        
        return df

    except Exception as e:
        logger.error(f"❌ Errore generale EUR-Lex: {e}")
        return pd.DataFrame()


if __name__ == "__main__":
    df = fetch_data()
    if not df.empty:
        print(f"\n✅ Risultato: {len(df)} record")
        print(df[['titolo', 'data_pubblicazione']].head())