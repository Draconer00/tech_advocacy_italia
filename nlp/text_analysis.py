import pandas as pd
import spacy
import os
from collections import Counter

# 1. Carichiamo il modello linguistico italiano
print("Caricamento del modello di Intelligenza Artificiale (spaCy)...")
try:
    nlp = spacy.load("it_core_news_md")
except OSError:
    print("Modello non trovato! Esegui nel terminale: python -m spacy download it_core_news_md")
    exit()

def estrai_entita(testo):
    """
    Legge un intero provvedimento ed estrae le Organizzazioni (ORG) e i Luoghi (LOC).
    """
    if not isinstance(testo, str) or len(testo) < 10:
        return []
        
    # Aumentiamo il limite di lunghezza massima del testo analizzabile da spaCy
    nlp.max_length = 2000000 
    
    doc = nlp(testo)
    entita_trovate = []
    
# Filtriamo le entità
    for ent in doc.ents:
        if ent.label_ in ['ORG', 'LOC']:
            # Pulizia base: rimuoviamo spazi extra e convertiamo in minuscolo per raggruppare meglio
            nome_pulito = ent.text.strip().title()
            
            # --- LA NOSTRA NUOVA BLACKLIST LEGALE ---
            parole_escluse = [
                "Garante", "Garante Privacy", "Roma", "Italia", 
                "Autorità", "Autorita", "Autorità Garante",
                "Provvedimento", "Provvedimenti", "Comunicato", "Comunicato Stampa", 
                "Stampa", "Legge", "Decreto", "Regolamento", "Gdpr", 
                "Privacy", "Codice", "Articolo", "Stato", "Repubblica",
                "Gazzetta Ufficiale", "Parlamento", "Governo"
            ]
            
            # Controlliamo che la parola non sia nella blacklist e non sia troppo corta
            if len(nome_pulito) > 3 and nome_pulito not in parole_escluse:
                entita_trovate.append(nome_pulito)

def processa_dati_garante():
    """Legge i dati raw, applica l'NLP e salva in processed."""
    cartella_script = os.path.dirname(os.path.abspath(__file__))
    percorso_raw = os.path.join(cartella_script, '..', 'data', 'raw', 'gpdp_sample.csv')
    percorso_processed = os.path.join(cartella_script, '..', 'data', 'processed', 'gpdp_analyzed.csv')
    
    # Assicuriamoci che la cartella processed esista
    os.makedirs(os.path.dirname(percorso_processed), exist_ok=True)
    
    if not os.path.exists(percorso_raw):
        print(f"File raw non trovato: {percorso_raw}")
        return
        
    print("Lettura del database grezzo del Garante...")
    df = pd.read_csv(percorso_raw)
    
    if 'Testo_Completo' not in df.columns:
        print("Errore: La colonna 'Testo_Completo' non esiste. Assicurati di aver lanciato il nuovo scraper.")
        return
        
    print(f"Inizio analisi NLP su {len(df)} documenti legali completi. Questa operazione richiederà qualche secondo...")
    
    # Applichiamo la funzione NLP a tutta la colonna dei testi completi
    df['Entita_Coinvolte'] = df['Testo_Completo'].apply(estrai_entita)
    
    # Salviamo il risultato
    df.to_csv(percorso_processed, index=False)
    print(f"\nAnalisi completata! Dati salvati in: {percorso_processed}")
    
    # Mostriamo un'anteprima veloce di chi sono i bersagli principali
    tutte_entita = [ent for lista in df['Entita_Coinvolte'] if isinstance(lista, list) for ent in lista]
    classifica = Counter(tutte_entita)
    print("\n--- TOP 5 ENTI/AZIENDE SOTTO LA LENTE DEL GARANTE ---")
    for ente, conteggio in classifica.most_common(5):
        print(f"- {ente} (Citato in {conteggio} provvedimenti)")

if __name__ == "__main__":
    processa_dati_garante()