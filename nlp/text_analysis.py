import pandas as pd
import spacy
import os
from collections import Counter

print("Caricamento del modello linguistico (spaCy)...")
try:
    nlp = spacy.load("it_core_news_md")
except OSError:
    print("Modello non trovato! Esegui nel terminale: python -m spacy download it_core_news_md")
    exit()

def estrai_entita(testo):
    """
    Legge un intero provvedimento ed estrae le Organizzazioni (ORG) e i Luoghi (LOC),
    filtrando il gergo burocratico.
    """
    # Se il testo è vuoto o troppo corto, restituiamo una lista vuota
    if not isinstance(testo, str) or len(testo) < 10:
        return []
        
    # Permettiamo a spaCy di leggere documenti molto lunghi senza andare in crash
    nlp.max_length = 2000000 
    
    doc = nlp(testo)
    entita_trovate = []
    
    # LA NOSTRA BLACKLIST LEGALE (Aggiungi qui le parole se l'IA fa altri errori in futuro)
    parole_escluse = [
        "Garante", "Garante Privacy", "Roma", "Italia", 
        "Autorità", "Autorita", "Autorità Garante", "Garante Per La Protezione Dei Dati",
        "Provvedimento", "Provvedimenti", "Comunicato", "Comunicato Stampa", 
        "Stampa", "Legge", "Decreto", "Regolamento", "Gdpr", 
        "Privacy", "Codice", "Articolo", "Stato", "Repubblica",
        "Gazzetta Ufficiale", "Parlamento", "Governo", "Direttiva", "Misure",
        "Piazza Venezia", "Linee", "Linee Guida", "Dati Personali", "Protezione Dei Dati"
    ]
    
    for ent in doc.ents:
        if ent.label_ in ['ORG', 'LOC']:
            nome_pulito = ent.text.strip().title()
            
            # Filtro: lunghezza minima e assenza nella blacklist
            if len(nome_pulito) > 3 and nome_pulito not in parole_escluse:
                entita_trovate.append(nome_pulito)
                
    # Usiamo 'set' per contare un'azienda 1 sola volta per documento, anche se citata 100 volte
    return list(set(entita_trovate))

def processa_dati_garante():
    """Legge i testi completi dal CSV grezzo, applica l'IA e salva i risultati."""
    cartella_script = os.path.dirname(os.path.abspath(__file__))
    percorso_raw = os.path.join(cartella_script, '..', 'data', 'raw', 'gpdp_sample.csv')
    percorso_processed = os.path.join(cartella_script, '..', 'data', 'processed', 'gpdp_analyzed.csv')
    
    # Creiamo la cartella 'processed' se non esiste
    os.makedirs(os.path.dirname(percorso_processed), exist_ok=True)
    
    if not os.path.exists(percorso_raw):
        print(f"File raw non trovato in: {percorso_raw}")
        return
        
    print("Lettura del database dei testi completi...")
    df = pd.read_csv(percorso_raw)
    
    if 'Testo_Completo' not in df.columns:
        print("Errore: Manca la colonna 'Testo_Completo'. Hai lanciato il nuovo scraper?")
        return
        
    print(f"Inizio analisi NLP su {len(df)} documenti legali. L'IA sta leggendo...")
    
    # Questo è il momento in cui l'IA lavora su tutto il database
    df['Entita_Coinvolte'] = df['Testo_Completo'].apply(estrai_entita)
    
    # Salviamo il CSV processato
    df.to_csv(percorso_processed, index=False)
    print(f"\nAnalisi completata! Dati puliti salvati in: {percorso_processed}")
    
    # --- LA CLASSIFICA FINALE CORAZZATA ---
    # Usiamo isinstance(lista, list) per evitare il famoso crash "NoneType is not iterable"
    tutte_entita = [ent for lista in df['Entita_Coinvolte'] if isinstance(lista, list) for ent in lista]
    classifica = Counter(tutte_entita)
    
    print("\n--- TOP 5 BERSAGLI/ATTORI REALI SOTTO LA LENTE DEL GARANTE ---")
    for ente, conteggio in classifica.most_common(5):
        print(f"- {ente} (Citato in {conteggio} provvedimenti)")

if __name__ == "__main__":
    processa_dati_garante()