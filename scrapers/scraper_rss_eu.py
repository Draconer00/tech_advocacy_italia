import feedparser
import pandas as pd
import os
from deep_translator import GoogleTranslator
from bs4 import BeautifulSoup
import time

def pulisci_html(testo_sporco):
    """Rimuove eventuali tag HTML (<p>, <a>, ecc.) che a volte inquinano gli RSS."""
    if not testo_sporco:
        return ""
    zuppa = BeautifulSoup(testo_sporco, "html.parser")
    return zuppa.text.strip()

def traduci_in_italiano(testo, lingua_origine='auto'):
    """Usa Google Translate per convertire tutto in italiano."""
    if not testo or len(testo) < 3:
        return testo
    
    try:
        # Il traduttore ha un limite di 5000 caratteri alla volta, tagliamo se necessario
        testo_tagliato = testo[:4999] 
        traduttore = GoogleTranslator(source=lingua_origine, target='it')
        return traduttore.translate(testo_tagliato)
    except Exception as e:
        print(f"    [!] Errore di traduzione: {e}")
        return testo # Se fallisce, restituisce il testo originale per non perdere il dato

def caccia_rss_istituzionali():
    print("🌍 Avvio Cacciatore RSS Europeo...")
    
    # La nostra rubrica istituzionale (Aggiungi qui altri link in futuro!)
    fonti_rss = {
        "EDPB (Unione Europea)": "https://edpb.europa.eu/news/news/feed_en",
        "CNIL (Francia)": "https://www.cnil.fr/fr/rss.xml",
        "AEPD (Spagna)": "https://www.aepd.es/es/rss.xml",
        "ICO (Regno Unito)": "https://ico.org.uk/rss/news/"
    }
    
    notizie_estratte = []
    
    for ente, url in fonti_rss.items():
        print(f"\n📡 Connessione a: {ente}")
        try:
            feed = feedparser.parse(url)
            
            # Controlliamo se il feed è valido
            if feed.bozo != 0 and not hasattr(feed, 'entries'):
                print(f"  [!] Impossibile leggere il feed di {ente}")
                continue
                
            # Prendiamo solo le ultime 5 notizie per ogni ente per non sovraccaricare il traduttore
            for notizia in feed.entries[:5]:
                titolo_orig = pulisci_html(notizia.get('title', ''))
                
                # A volte il riassunto si chiama 'summary', a volte 'description'
                sommario_orig = pulisci_html(notizia.get('summary', notizia.get('description', '')))
                link = notizia.get('link', '')
                data = notizia.get('published', notizia.get('updated', 'Data Sconosciuta'))
                
                print(f"  - Trovata: {titolo_orig[:40]}...")
                
                # LA MAGIA: Traduzione al volo!
                time.sleep(1) # Piccola pausa per non farci bloccare da Google
                titolo_ita = traduci_in_italiano(titolo_orig)
                sommario_ita = traduci_in_italiano(sommario_orig)
                
                notizie_estratte.append({
                    'Ente_Origine': ente,
                    'Data': data,
                    'Titolo_Originale': titolo_orig,
                    'Titolo_Italiano': titolo_ita,
                    'Sommario_Italiano': sommario_ita,
                    'Link': link
                })
                
        except Exception as e:
            print(f"  [!] Errore critico su {ente}: {e}")
            
    # Salvataggio
    df_rss = pd.DataFrame(notizie_estratte)
    print(f"\n✅ Successo! {len(df_rss)} notizie istituzionali europee scaricate e tradotte.")
    return df_rss

if __name__ == "__main__":
    df_europa = caccia_rss_istituzionali()
    
    if not df_europa.empty:
        cartella_script = os.path.dirname(os.path.abspath(__file__))
        cartella_raw = os.path.join(cartella_script, '..', 'data', 'raw')
        os.makedirs(cartella_raw, exist_ok=True)
        
        percorso_salvataggio = os.path.join(cartella_raw, 'rss_eu_sample.csv')
        
        # ✅ SISTEMA DI SALVATAGGIO STORICO: NON SOVRASCRIVE, AGGIUNGE
        if os.path.exists(percorso_salvataggio):
            df_esistente = pd.read_csv(percorso_salvataggio)
            # Unisci vecchi e nuovi dati
            df_unito = pd.concat([df_esistente, df_europa], ignore_index=True)
            # Rimuovi duplicati basati su Link, mantieni il più nuovo
            df_finale = df_unito.drop_duplicates(subset=['Link'], keep='last')
        else:
            df_finale = df_europa
        
        df_finale.to_csv(percorso_salvataggio, index=False)
        
        print("\n--- ESTRATTO (Già tradotto in Italiano!) ---")
        # Stampiamo i primi 3 risultati per vedere come ha lavorato il traduttore
        for index, row in df_europa.head(3).iterrows():
            print(f"[{row['Ente_Origine']}] {row['Titolo_Italiano']}")