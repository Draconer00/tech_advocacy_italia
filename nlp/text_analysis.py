import pandas as pd
import spacy
import os
import re
import sqlite3
import csv
from collections import Counter
from difflib import SequenceMatcher

print("Caricamento del modello linguistico (spaCy)...")
try:
    nlp = spacy.load("it_core_news_md")
except OSError:
    print("Modello non trovato! Esegui nel terminale: python -m spacy download it_core_news_md")
    exit()

# ===== PRIORITY 1.3: Carica blacklist dinamica da CSV =====
def carica_blacklist(filepath):
    """Legge la blacklist da CSV invece di hardcodare."""
    blacklist = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                blacklist.add(row['parola_esclusa'].strip())
        print(f"✅ Blacklist caricata: {len(blacklist)} parole escluse")
    except FileNotFoundError:
        print(f"⚠️ Blacklist non trovata in {filepath}. Uso blacklist di default.")
        blacklist = {
            "Garante", "Roma", "Italia", "Autorità", "Provvedimento", 
            "Comunicato", "Stampa", "Gdpr", "Privacy", "Codice"
        }
    return blacklist

cartella_script = os.path.dirname(os.path.abspath(__file__))
BLACKLIST_PATH = os.path.join(cartella_script, '..', 'data', 'utils', 'nlp_blacklist.csv')
BLACKLIST = carica_blacklist(BLACKLIST_PATH)

# ===== PRIORITY 1.1: Funzione per pulire testo da GPDP =====
def pulisci_testo_gpdp(testo):
    """Pulisce il testo estratto dal sito GPDP (rimuove rumore HTML/whitespace)."""
    if not isinstance(testo, str):
        return ""
    
    # Rimuovi whitespace eccessivo
    testo = re.sub(r'\s+', ' ', testo).strip()
    
    # Rimuovi URLs
    testo = re.sub(r'http[s]?://\S+', '', testo)
    
    # Rimuovi numeri di docweb (es. "[10235001]")
    testo = re.sub(r'\[\d+\]', '', testo)
    
    # Limita a lunghezza ragionevole (mantieni essenza)
    max_len = 5000
    if len(testo) > max_len:
        testo = testo[:max_len]
    
    return testo

# ===== PRIORITY 1.2: Funzione per deduplicazione con fuzzy matching =====
def deduplica_entita(lista_entita, soglia=0.85):
    """Unisce entità simili usando fuzzy matching per ridurre duplicati."""
    if not lista_entita:
        return []
    
    unica = []
    for ent in lista_entita:
        trovato_simile = False
        ent_nome = ent.split(' || ')[0]  # Estrai nome senza categoria
        
        for ent_unica in unica:
            ent_unica_nome = ent_unica.split(' || ')[0]
            ratio = SequenceMatcher(None, ent_nome.lower(), ent_unica_nome.lower()).ratio()
            
            if ratio > soglia:
                trovato_simile = True
                break
        
        if not trovato_simile:
            unica.append(ent)
    
    return unica


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
    
    # PRIORITY 1.1: Pulisci testo prima dell'elaborazione
    testo = pulisci_testo_gpdp(testo)
        
    nlp.max_length = 2000000 
    doc = nlp(testo)
    entita_trovate = []
    
    # BLACKLIST DINAMICA (caricata da CSV)
    spazzatura_dinamica = [
        "ufficio", "maggiori", "chiese", "clicca", "leggi", "informativa", 
        "pagina", "sezione", "articolo", "legge", "decreto", "regolamento"
    ]
    
    for ent in doc.ents:
        if ent.label_ in ['ORG', 'LOC', 'PER']:
            nome_pulito = ent.text.strip().title()
            nome_lower = nome_pulito.lower()
            
            # 1. SCUDO ANTI-LINK
            if re.search(r"http|www\.|[a-z0-9]+\.[a-z]{2,3}", nome_lower):
                continue
                
            # 2. SCUDO DINAMICO
            if any(parola in nome_lower for parola in spazzatura_dinamica):
                continue
                
            # 3. SCUDO ESATTO CON BLACKLIST DA CSV
            if len(nome_pulito) > 3 and nome_pulito not in BLACKLIST:
                
                # Applichiamo la classificazione
                categoria = categorizza_entita(nome_pulito, ent.label_)
                
                # Salviamo usando un separatore speciale " || "
                entita_trovate.append(f"{nome_pulito} || {categoria}")
    
    # PRIORITY 1.2: Deduplica entità simili prima di ritornare
    entita_deduplicate = deduplica_entita(list(set(entita_trovate)))
    return entita_deduplicate

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
        return "Italia"

def salva_in_sqlite(df, db_path):
    """Salva dati analizzati in SQLite per query veloci (Priority 0)."""
    try:
        conn = sqlite3.connect(db_path)
        df.to_sql('provvedimenti_analyzed', conn, if_exists='replace', index=False)
        conn.close()
        print(f"✅ Dati salvati in SQLite: {db_path}")
    except Exception as e:
        print(f"⚠️ Errore salvataggio SQLite: {e}")

def processa_dati_garante():
    """Legge i testi completi dal CSV grezzo, applica l'IA e salva i risultati (con Priority 1 improvements)."""
    cartella_script = os.path.dirname(os.path.abspath(__file__))
    percorso_raw = os.path.join(cartella_script, '..', 'data', 'raw', 'gpdp_sample.csv')
    percorso_processed = os.path.join(cartella_script, '..', 'data', 'processed', 'gpdp_analyzed.csv')
    percorso_db = os.path.join(cartella_script, '..', 'data', 'tech_advocacy.db')
    
    # Creiamo le cartelle se non esistono
    os.makedirs(os.path.dirname(percorso_processed), exist_ok=True)
    os.makedirs(os.path.dirname(percorso_db), exist_ok=True)
    
    if not os.path.exists(percorso_raw):
        print(f"File raw non trovato in: {percorso_raw}")
        return
        
    print("📖 Lettura del database dei testi completi...")
    df = pd.read_csv(percorso_raw)
    
    if 'Testo_Completo' not in df.columns:
        print("Errore: Manca la colonna 'Testo_Completo'. Hai lanciato il nuovo scraper?")
        return
    
    print(f"🧠 Inizio analisi NLP su {len(df)} documenti legali (Priority 1 improvements attivate)...")
    
    # Priority 1.1 + 1.2 + 1.3: Estrazione entità con pulizia, dedup e blacklist dinamica
    df['Entita_Coinvolte'] = df['Testo_Completo'].apply(estrai_entita)

    # --- CLASSIFICAZIONE GEOGRAFICA ---
    df['Ambito_Geografico'] = df['Testo_Completo'].apply(classifica_geografia)
    
    # Salviamo il CSV processato
    df.to_csv(percorso_processed, index=False)
    print(f"✅ CSV processato salvato in: {percorso_processed}")
    
    # Priority 0: Salva anche in SQLite per query veloci
    salva_in_sqlite(df, percorso_db)
    
    # --- STATISTICHE FINALI ---
    tutte_entita = [ent for lista in df['Entita_Coinvolte'] if isinstance(lista, list) for ent in lista]
    classifica = Counter(tutte_entita)
    
    print("\n🏆 --- TOP 5 ATTORI SOTTO LA LENTE DEL GARANTE ---")
    for ente, conteggio in classifica.most_common(5):
        print(f"   {ente}: {conteggio} provvedimenti")
    
    print(f"\n📊 Statistiche:")
    print(f"   - Documenti processati: {len(df)}")
    print(f"   - Entità uniche estratte: {len(classifica)}")
    enti_list = [e for lista in df['Entita_Coinvolte'] if isinstance(lista, list) for e in lista]
    duplicati_rimosse = len(enti_list) - len(classifica) if len(enti_list) > 0 else 0
    print(f"   - Entità duplicate rimosse: ~{duplicati_rimosse}")

if __name__ == "__main__":
    processa_dati_garante()