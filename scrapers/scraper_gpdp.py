import requests
from bs4 import BeautifulSoup
import pandas as pd

def scrape_provvedimenti_garante():
    """
    Estrae i provvedimenti leggendo l'HTML diretto del sito del Garante.
    """
    # Puntiamo alla pagina web normale, non all'RSS
    url = "https://www.garanteprivacy.it/"
    
    print(f"Tentativo di connessione a: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) (Progetto Ricerca Civica)'
    }
    
    try:
        risposta = requests.get(url, headers=headers, timeout=10)
        risposta.raise_for_status() 
        
        # Usiamo il parser HTML, non più XML!
        zuppa = BeautifulSoup(risposta.content, 'html.parser')
        
        provvedimenti = []
        
        # Sul sito del Garante, i documenti importanti sono link (<a>) che contengono "docweb"
        # Cerchiamo tutti i link nella pagina
        tutti_i_link = zuppa.find_all('a', href=True)
        
        for tag_a in tutti_i_link:
            link = tag_a['href']
            titolo = tag_a.text.strip()
            titolo_lower = titolo.lower() # Convertiamo in minuscolo per facilitare la ricerca
            
            # 1. Definiamo le parole che NON vogliamo (il rumore)
            parole_escluse = ["agenda", "eventi", "newsletter", "convegno", "seminario", "podcast"]
            
            # 2. Controlliamo se è un documento lungo abbastanza
            if "docweb" in link and len(titolo) > 10:
                
                # 3. FILTRO: Se NON contiene nessuna delle parole escluse, lo salviamo
                if not any(parola in titolo_lower for parola in parole_escluse):
                    
                    if link.startswith("/"):
                        link = "https://www.garanteprivacy.it" + link
                        
                    provvedimenti.append({
                        'Titolo': titolo,
                        'Link': link
                    })
        
        # Rimuoviamo eventuali duplicati
        df_gpdp = pd.DataFrame(provvedimenti).drop_duplicates(subset=['Link'])
        
        print(f"Successo! Trovati {len(df_gpdp)} link a provvedimenti/comunicati.")
        return df_gpdp
        
    except Exception as e:
        print(f"Errore durante lo scraping: {e}")
        return pd.DataFrame()

# Esecuzione di test
if __name__ == "__main__":
    df_test = scrape_provvedimenti_garante()
    if not df_test.empty:
        import os
        os.makedirs('../data/raw', exist_ok=True)
        # Salviamo il CSV
        percorso_salvataggio = '../data/raw/gpdp_sample.csv'
        df_test.to_csv(percorso_salvataggio, index=False)
        print("\nPrime 3 righe estratte:")
        print(df_test.head(3))
        print(f"\nDati salvati con successo in: {percorso_salvataggio}")