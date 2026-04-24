import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import os
import hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

def estrai_testo_completo(url, session):
    """
    Simula l'azione umana: legge il testo del redirect e preme esattamente
    il link nascosto sotto la scritta 'clicca qui'.
    """
    try:
        time.sleep(1)
        risposta = session.get(url, timeout=10)
        
        if risposta.status_code != 200:
            return "Errore di connessione"
            
        zuppa = BeautifulSoup(risposta.content, 'html.parser')
        testo_pagina = zuppa.text.lower()
        
        # Se troviamo il muro...
        if "redirect automatico" in testo_pagina or "clicca qui" in testo_pagina:
            print("  [!] Muro rilevato. Cerco il pulsante esatto...")
            
            vero_link = None
            
            # 1. CERCHIAMO ESATTAMENTE LA PAROLA "clicca qui"
            link_clicca_qui = zuppa.find('a', string=lambda t: t and "clicca qui" in t.lower())
            
            if link_clicca_qui and link_clicca_qui.has_attr('href'):
                vero_link = link_clicca_qui['href']
            else:
                # 2. Piano B: Cerchiamo nel tag <meta> usato dai browser
                meta = zuppa.find('meta', attrs={'http-equiv': lambda x: x and x.lower() == 'refresh'})
                if meta and 'url=' in meta.get('content', '').lower():
                    contenuto = meta['content']
                    # Estraiamo brutalmente l'URL dal testo "1;url=/home..."
                    vero_link = contenuto.lower().split('url=')[-1].strip('\'" ')
            
            # Se abbiamo trovato il varco, ci entriamo!
            if vero_link:
                if vero_link.startswith('/'):
                    vero_link = "https://www.garanteprivacy.it" + vero_link
                
                print(f"  [>] Varco trovato! Entro in: {vero_link[-30:]}...")
                time.sleep(1)
                risposta = session.get(vero_link, timeout=10)
                zuppa = BeautifulSoup(risposta.content, 'html.parser')
        
        # Ora estraiamo la polpa legale
        paragrafi = zuppa.find_all('p')
        testo_completo = " ".join([p.text.strip() for p in paragrafi if len(p.text.strip()) > 20])
        
        # Se il testo è ancora vuoto, prendiamo tutto il testo visibile della pagina
        if not testo_completo or len(testo_completo) < 50:
             testo_completo = zuppa.text.strip()[:1000] # Prendiamo un pezzo per sicurezza
             
        return testo_completo
        
    except Exception as e:
        print(f"Errore nell'estrazione: {e}")
        return "Errore estrazione"

def scrape_provvedimenti_garante():
    url_base = "https://www.garanteprivacy.it/"
    print(f"Avvio esplorazione. Creazione lasciapassare (Sessione) in corso...")
    
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    
    try:
        risposta = session.get(url_base, timeout=10)
        risposta.raise_for_status() 
        zuppa = BeautifulSoup(risposta.content, 'html.parser')
        
        provvedimenti = []
        tutti_i_link = zuppa.find_all('a', href=True)
        
        parole_escluse = ["agenda", "eventi", "newsletter", "convegno", "seminario", "podcast"]
        link_trovati = 0
        links_da_scaricare = []

        for tag_a in tutti_i_link:
            link = tag_a['href']
            titolo = tag_a.text.strip()
            titolo_lower = titolo.lower()
            
            if "docweb" in link and len(titolo) > 10:
                if not any(parola in titolo_lower for parola in parole_escluse):
                    if link.startswith("/"):
                        link = "https://www.garanteprivacy.it" + link
                    
                    if link not in [p['link'] for p in links_da_scaricare]:
                        links_da_scaricare.append({'link': link, 'titolo': titolo})
                        link_trovati += 1
                        
                        if link_trovati >= 10: 
                            break

        print(f"Trovati {len(links_da_scaricare)} provvedimenti. Inizio download parallelo...")

        # ✅ PARALLELIZZAZIONE 4 WORKERS
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(estrai_testo_completo, item['link'], session): item
                for item in links_da_scaricare
            }

            for future in as_completed(futures):
                item = futures[future]
                try:
                    testo = future.result()

                    # ✅ HASH UNIVOCO E METADATI STANDARDIZZATI
                    hash_contenuto = hashlib.sha256(testo.encode('utf-8')).hexdigest()

                    provvedimenti.append({
                        'id_univoco': hash_contenuto,
                        'fonte': 'gpdp',
                        'data_pubblicazione': datetime.now().date().isoformat(),
                        'data_scraping': datetime.now().isoformat(),
                        'titolo': item['titolo'],
                        'url': item['link'],
                        'tipo_contenuto': 'provvedimento',
                        'lingua': 'it',
                        'testo_completo': testo,
                        'hash_contenuto': hash_contenuto
                    })
                    
                    print(f"✅ Download completato: {item['titolo'][:45]}...")
                    
                except Exception as e:
                    print(f"❌ Errore download {item['link']}: {str(e)}")
                            
        df_gpdp = pd.DataFrame(provvedimenti)
        print(f"\nSuccesso! Scaricati {len(df_gpdp)} provvedimenti completi.")
        return df_gpdp
        
    except Exception as e:
        print(f"Errore durante lo scraping: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    df_test = scrape_provvedimenti_garante()
    
    if not df_test.empty:
        cartella_script = os.path.dirname(os.path.abspath(__file__))
        cartella_raw = os.path.join(cartella_script, '..', 'data', 'raw')
        os.makedirs(cartella_raw, exist_ok=True)
        
        percorso_salvataggio = os.path.join(cartella_raw, 'gpdp_sample.csv')
        df_test.to_csv(percorso_salvataggio, index=False)
        
        print("\nLista delle colonne salvate:", df_test.columns.tolist())
        
        if 'testo_completo' in df_test.columns:
            print("\nEstratto del VERO testo scaricato (prime 400 lettere):")
            print(str(df_test['testo_completo'].iloc[0])[:400] + "...\n")
            
        print(f"Dati salvati in modo sicuro in: {percorso_salvataggio}")

