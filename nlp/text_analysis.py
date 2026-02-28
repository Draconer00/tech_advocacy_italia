import pandas as pd
import spacy
import os
import re
from collections import Counter

print("Caricamento del modello linguistico (spaCy)...")
try:
    nlp = spacy.load("it_core_news_md")
except OSError:
    print("Modello non trovato! Esegui nel terminale: python -m spacy download it_core_news_md")
    exit()


def categorizza_entita(nome, etichetta_spacy):
    """
    Assegna una categoria specifica all'entità estratta.
    """
    nome_low = nome.lower()
    
    # 1. Comuni
    if "comune di" in nome_low or "città metropolitana" in nome_low or "provincia di" in nome_low:
        return "Comuni e Province"
    
    # 2. Istituzioni, PA e Organi Europei (AGGIORNATA)
    istituzioni_keywords = [
        "ministero", "università", "polizia", "istituto", "agenzia", 
        "regione", "asl", "ospedale", "inps", "inl",
        "commissione", "comitato", "consiglio", "tribunale", "corte", 
        "autorità", "garante", "direzione", "prefettura", "edpb"
    ]
    if any(k in nome_low for k in istituzioni_keywords):
        return "Istituzioni"
        
    # 3. Leggi e Regolamentazioni
    leggi_keywords = ["legge", "regolamento", "direttiva", "gdpr", "decreto", "d.lgs", "costituzione"]
    if any(k in nome_low for k in leggi_keywords):
        return "Leggi e Regolamentazioni"
        
    # 4. Personaggi Pubblici
    if etichetta_spacy == "PER":
        return "Personaggi Pubblici"
        
    # 5. Stati e Luoghi
    if etichetta_spacy == "LOC":
        return "Stati e Luoghi"
        
    # 6. Default
    return "Aziende e Org Private"

def estrai_entita(testo):
    if not isinstance(testo, str) or len(testo) < 10:
        return []
        
    nlp.max_length = 2000000 
    doc = nlp(testo)
    entita_trovate = []
    
    # BLACKLIST ESATTA
    parole_escluse = [
        "Garante", "Garante Privacy", "Roma", "Italia", 
        "Autorità", "Autorita", "Autorità Garante", "Garante Per La Protezione Dei Dati",
        "Provvedimento", "Provvedimenti", "Comunicato", "Comunicato Stampa", 
        "Stampa", "Gdpr", "Privacy", "Codice", "Gazzetta Ufficiale", "Parlamento", "Governo",
        "Piazza Venezia", "Linee Guida", "Dati Personali"
    ]
    
    # BLACKLIST DINAMICA
    spazzatura_dinamica = [
        "ufficio", "maggiori", "chiese", "clicca", "leggi", "informativa", 
        "pagina", "sezione", "articolo", "legge", "decreto", "regolamento"
    ]
    
    for ent in doc.ents:
        if ent.label_ in ['ORG', 'LOC', 'PER']: # Aggiunto PER (Persone)
            nome_pulito = ent.text.strip().title()
            nome_lower = nome_pulito.lower() # <--- ECCO LA RIGA CHE MANCAVA!
            
            # 1. SCUDO ANTI-LINK
            if re.search(r"http|www\.|[a-z0-9]+\.[a-z]{2,3}", nome_lower):
                continue
                
            # 2. SCUDO DINAMICO
            if any(parola in nome_lower for parola in spazzatura_dinamica):
                continue
                
            # 3. SCUDO ESATTO E LUNGHEZZA
            if len(nome_pulito) > 3 and nome_pulito not in parole_escluse:
                
                # Applichiamo la classificazione
                categoria = categorizza_entita(nome_pulito, ent.label_)
                
                # Salviamo usando un separatore speciale " || " (ci sarà utilissimo dopo per i grafici!)
                entita_trovate.append(f"{nome_pulito} || {categoria}")
                
    return list(set(entita_trovate))

def classifica_geografia(testo):
    """
    Analizza il testo per capire se il provvedimento ha respiro internazionale, 
    europeo o puramente nazionale.
    """
    testo_lower = str(testo).lower()
    
    # Lista di parole chiave per gli USA / Big Tech
    parole_usa = ["stati uniti", "usa", "america", "california", "washington", "new york", "silicon valley", "oltreoceano"]
    
    # Lista di parole chiave per l'Europa
    parole_europa = ["unione europea", "comitato europeo", "edpb", "bruxelles", "parlamento europeo", "commissione europea", "irlanda", "lussemburgo", "corte di giustizia", "europeo", "europea"]
    
    parole_Asia = ["cina", "giappone", "india", "corea", "sud-est asiatico", "asia"]
    if any(parola in testo_lower for parola in parole_usa):
        return "USA / Internazionale"
    elif any(parola in testo_lower for parola in parole_europa):
        return "Europa"
    elif any(parola in testo_lower for parola in parole_Asia):
        return "Asia"
    else:
        # Se non parla di Europa o USA, assumiamo sia una questione locale/nazionale
        return "Italia"

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

    # --- CLASSIFICAZIONE GEOGRAFICA ---
    df['Ambito_Geografico'] = df['Testo_Completo'].apply(classifica_geografia)
    
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