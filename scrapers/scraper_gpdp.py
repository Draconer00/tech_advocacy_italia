import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import os

def estrai_testo_completo(url):
    """
    Visita il link del singolo provvedimento ed estrae il testo completo.
    """
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) (Progetto Ricerca Civica)'}
    try:
        # Pausa etica e strategica: aspettiamo 1 secondo per non sovraccaricare il server
        time.sleep(1) 
        
        risposta = requests.get(url, headers=headers, timeout=10)
        if risposta.status_code != 200:
            return "Errore di connessione"
            
        zuppa = BeautifulSoup(risposta.content, 'html.parser')
        
        # Estraiamo tutti i paragrafi di testo
        paragrafi = zuppa.find_all('p')
        testo_completo = " ".join([p.text.strip() for p in paragrafi if len(p.text.strip()) > 20])
        
        return testo_completo
    except Exception as e:
        print(f"Errore nell'estrazione del testo da {url}: {e}")
        return "Errore estrazione"

def scrape_provvedimenti_garante():
    """
    Estrae i link dalla homepage e poi scarica il testo completo di ciascuno (Livello 2).
    """
    url_base = "https://www.garanteprivacy.it/"
    print(f"Ricerca nuovi provvedimenti su: {url_base}")
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) (Progetto Ricerca Civica)'}
    
    try:
        risposta = requests.get(url_base, headers=headers, timeout=10)
        risposta.raise_for_status() 
        zuppa = BeautifulSoup(risposta.content, 'html.parser')
        
        provvedimenti = []
        tutti_i_link = zuppa.find_all('a', href=True)
        
        # Filtro Anti-Rumore
        parole_escluse = ["agenda", "eventi", "newsletter", "convegno", "seminario", "podcast"]
        
        link_trovati = 0
        for tag_a in tutti_i_link:
            link = tag_a['href']
            titolo = tag_a.text.strip()
            titolo_lower = titolo.lower()
            
            if "docweb" in link and len(titolo) > 10:
                if not any(parola in titolo_lower for parola in parole_escluse):
                    if link.startswith("/"):
                        link = "https://www.garanteprivacy.it" + link
                    
                    # Controlliamo se abbiamo già aggiunto questo link per evitare doppioni
                    if not any(p['Link'] == link for p in provvedimenti):
                        print(f"Trovato: {titolo[:50]}... -> Estrazione testo in corso...")
                        # --- QUI AVVIENE LA MAGIA DEL LIVELLO 2 ---
                        testo = estrai_testo_completo(link)
                        
                        provvedimenti.append({
                            'Titolo': titolo,
                            'Link': link,
                            'Testo_Completo': testo # Salviamo la "polpa"
                        })
                        link_trovati += 1
                        
                        # Limite temporaneo per test (scarichiamo solo i primi 10 per non aspettare ore)
                        if link_trovati >= 10: 
                            break
                            
        df_gpdp = pd.DataFrame(provvedimenti)
        print(f"\nSuccesso! Scaricati {len(df_gpdp)} provvedimenti completi.")
        return df_gpdp
        
    except Exception as e:
        print(f"Errore durante lo scraping base: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    df_test = scrape_provvedimenti_garante()
    if not df_test.empty:
        cartella_script = os.path.dirname(os.path.abspath(__file__))
        cartella_raw = os.path.join(cartella_script, '..', 'data', 'raw')
        os.makedirs(cartella_raw, exist_ok=True)
        
        percorso_salvataggio = os.path.join(cartella_raw, 'gpdp_sample.csv')
        df_test.to_csv(percorso_salvataggio, index=False)
        
        print("\nEstratto del primo testo scaricato:")
        print(df_test['Testo_Completo'].iloc[0][:300] + "...\n")
        print(f"Dati salvati in: {percorso_salvataggio}")