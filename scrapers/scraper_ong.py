import feedparser
import pandas as pd
import os

def scrape_comunicati_ong():
    """
    Estrae le ultime campagne dai feed RSS delle principali ONG 
    italiane ed europee (Tech Advocacy e Diritti Umani).
    """
    # Il nostro Radar espanso
    fonti_ong = {
        # --- Core Tech Advocacy & Privacy ---
        "Privacy Network": "https://www.privacynetwork.it/feed/",
        "Hermes Center": "https://www.hermescenter.org/feed/",
        "EDRi (Europa)": "https://edri.org/feed/",
        "Noyb (Privacy UE)": "https://noyb.eu/en/rss.xml",
        "AlgorithmWatch": "https://algorithmwatch.org/en/feed/",
        "AI Forensics": "https://aiforensics.org/feed.xml",
        "Slow Web": "https://www.slow-web.it/feed/",
        "NINA": "https://ninabot.org/feed/", # Not Intelligent Not Artificial
        
        # --- Diritti Civili, Sociali & Trasparenza ---
        "The Good Lobby Italia": "https://www.thegoodlobby.it/feed/",
        "Amnesty Italia": "https://www.amnesty.it/feed/",
        "Antigone": "https://www.antigone.it/news?format=feed&type=rss",
        "Italiani Senza Cittadinanza": "https://italianisenzacittadinanza.it/feed/",
        "SOMO (Multinazionali)": "https://www.somo.nl/feed/",
        "STRALI": "https://www.strali.org/blog-feed.xml" 
    }
    
    tutte_le_notizie = []
    
    for nome_ong, url_feed in fonti_ong.items():
        print(f"Raccolta dati da: {nome_ong}...")
        
        try:
            feed = feedparser.parse(url_feed)
            
            for entry in feed.entries:
                tutte_le_notizie.append({
                    'ONG': nome_ong,
                    'Titolo': entry.title,
                    'Link': entry.link,
                    'Data': getattr(entry, 'published', 'Data non disponibile')
                })
        except Exception as e:
            print(f"Errore durante la lettura di {nome_ong}: {e}")
            
    df_ong = pd.DataFrame(tutte_le_notizie)
    print(f"\nSuccesso! Raccolti {len(df_ong)} comunicati totali dalla società civile.")
    return df_ong

# Esecuzione di test
if __name__ == "__main__":
    df_test = scrape_comunicati_ong()
    
    if not df_test.empty:
        # --- SOLUZIONE DEL PERCORSO ANONIMO E UNIVERSALE ---
        # 1. Trova la cartella esatta dove si trova questo file (scraper_ong.py)
        cartella_script = os.path.dirname(os.path.abspath(__file__))
        
        # 2. Torna indietro di un livello e vai in data/raw
        cartella_raw = os.path.join(cartella_script, '..', 'data', 'raw')
        
        # 3. Assicurati che esista
        os.makedirs(cartella_raw, exist_ok=True)
        
        # 4. Unisci il nome del file
        percorso_salvataggio = os.path.join(cartella_raw, 'ong_sample.csv')
        
        # Salviamo il CSV
        df_test.to_csv(percorso_salvataggio, index=False)
        
        print("\nPrime 3 righe estratte:")
        print(df_test.head(3))
        print(f"\nDati salvati in modo sicuro in: {percorso_salvataggio}")