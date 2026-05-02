import pandas as pd
import spacy
import os
import re
import sqlite3
import csv
import time
import psutil
from collections import Counter
from difflib import SequenceMatcher
from functools import wraps

# Carica lista ONG per Entity Linking
PROFILI_ONG = [
    "ALDE", "Amnesty International Italia", "Centro Galileo", "Codice Consumatori",
    "Diritto Digitale", "Electronic Frontier Foundation", "Epicenter.works",
    "European Digital Rights", "Federtutela", "Freedom House", "Internet Society",
    "La Cosa Nostra Digitale", "Luca Cominassi", "Open Rights Group", "Partito Pirata",
    "Privacy International", "Reporters Without Borders", "Slow Food", "Tactical Tech"
]

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
        print(f"Blacklist caricata: {len(blacklist)} parole escluse")
    except FileNotFoundError:
        print(f"Blacklist non trovata in {filepath}. Uso blacklist di default.")
        blacklist = {
            "Garante", "Roma", "Italia", "Autorità", "Provvedimento", 
            "Comunicato", "Stampa", "Gdpr", "Privacy", "Codice"
        }
    return blacklist

cartella_script = os.path.dirname(os.path.abspath(__file__))
BLACKLIST_PATH = os.path.join(cartella_script, '..', 'data', 'utils', 'nlp_blacklist.csv')
BLACKLIST = carica_blacklist(BLACKLIST_PATH)

# ==============================================
# 📊 METRICHE DI PERFORMANCE NLP
# ==============================================
class PerformanceMetrics:
    """Colleziona metriche di efficienza e qualità per monitoraggio"""
    def __init__(self):
        self.start_time = time.time()
        self.documents_processed = 0
        self.total_entities = 0
        self.time_per_doc = []
        self.memory_usage = []
    
    def timer(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            metrics.time_per_doc.append(elapsed)
            metrics.documents_processed +=1
            return result
        return wrapper
    
    def get_summary(self):
        avg_time = sum(self.time_per_doc) / len(self.time_per_doc) if self.time_per_doc else 0
        avg_entities = self.total_entities / self.documents_processed if self.documents_processed else 0
        memory_rss = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        
        return {
            'documenti_totali': self.documents_processed,
            'tempo_medio_doc_ms': round(avg_time * 1000, 2),
            'entita_medie_doc': round(avg_entities, 1),
            'memoria_utilizzata_mb': round(memory_rss, 1),
            'tempo_totale_elaborazione_s': round(time.time() - self.start_time, 1)
        }
    
    def get_quality_metrics(self, all_entities):
        """Calcola metriche di qualità specifiche per NLP"""
        entities_count = Counter(all_entities)
        
        # Rumore: entità che compaiono solo 1 volta
        singletons = sum(1 for e, cnt in entities_count.items() if cnt == 1)
        noise_ratio = singletons / len(entities_count) if entities_count else 0
        
        # Coverage: distribuzione delle entità
        top_10_entities = sum(cnt for e, cnt in entities_count.most_common(10))
        coverage_top_10 = top_10_entities / len(all_entities) if all_entities else 0
        
        # Entropia (diversità delle entità)
        import math
        total = len(all_entities)
        entropia = -sum( (cnt/total) * math.log2(cnt/total) for cnt in entities_count.values() )
        
        return {
            'rumore_percentuale': round(noise_ratio * 100, 1),
            'coverage_top10_percentuale': round(coverage_top_10 * 100, 1),
            'entropia_distribuzione': round(entropia, 2),
            'entita_totali_trovate': len(all_entities),
            'entita_uniche': len(entities_count)
        }
    
    def print_report(self, all_entities=None):
        s = self.get_summary()
        print("\n" + "="*60)
        print("📊 REPORT COMPLETO PERFORMANCE E QUALITÀ NLP")
        print("="*60)
        
        print("\n⚡ PERFORMANCE RUNTIME:")
        print(f"  ✅ Documenti processati:    {s['documenti_totali']}")
        print(f"  ⏱  Tempo medio per doc:    {s['tempo_medio_doc_ms']} ms")
        print(f"  💾 Memoria utilizzata:     {s['memoria_utilizzata_mb']} MB")
        print(f"  ⌛ Tempo totale:        {s['tempo_totale_elaborazione_s']} secondi")
        
        if all_entities:
            q = self.get_quality_metrics(all_entities)
            print("\n🎯 QUALITÀ ANALISI NLP:")
            print(f"  🔍 Entità totali trovate:   {q['entita_totali_trovate']}")
            print(f"  📌 Entità uniche:          {q['entita_uniche']}")
            print(f"  📉 Rapporto Rumore:        {q['rumore_percentuale']} %")
            print(f"  🎯 Coverage Top 10:        {q['coverage_top10_percentuale']} %")
            print(f"  🧩 Entropia Distribuzione: {q['entropia_distribuzione']}")
        
        print("\n" + "="*60)
        print("📘 Interpretazione metriche:")
        print("  • Rumore < 25% = Ottimo | < 40% = Buono")
        print("  • Entropia > 3 = Buona diversità tematica")
        print("  • Coverage > 30% = Concentrazione attori principali")
        print("="*60)

metrics = PerformanceMetrics()

# ===== PRIORITY 2.1: Sentiment Analysis su Provvedimenti =====
from transformers import pipeline

# ✅ NUOVI MODULI
from nlp.train_classifier import classifica_testo
from nlp.deduplication import deduplica_dataframe

# Carica modello sentiment analysis multilingua
sentiment_pipe = pipeline("sentiment-analysis", 
                          model="nlptown/bert-base-multilingual-uncased-sentiment")

def classifica_sentiment_provvedimento(testo):
    """Classifica tono: positivo (diritti protetti), negativo (libertà compromessa)."""
    # Focus su prime frasi (headline effect)
    testo_core = str(testo)[:500]  
    try:
        result = sentiment_pipe(testo_core, truncation=True)
        label = result[0]['label']  # 5 stars = positive, 1 star = negative
        
        if label in ['5 stars', '4 stars']:
            return 'POSITIVO (Diritti tutelati)'
        elif label in ['1 stars', '2 stars']:
            return 'NEGATIVO (Libertà ristretta)'
        else:
            return 'NEUTRALE'
    except:
        return 'NEUTRALE'

# ===== PRIORITY 2.2: Riconoscimento Acronimi Legali e Tech =====
ACRONIMI_LEGALI = {
    'GDPR': 'Leggi e Regolamentazioni || EU',
    'EDPB': 'Istituzioni || EU',
    'CCPA': 'Leggi e Regolamentazioni || USA',
    'LGPD': 'Leggi e Regolamentazioni || Brasile',
    'RGPD': 'Leggi e Regolamentazioni || Francia',
    'AMI': 'Tecnologie || IA',
    'SARI': 'Tecnologie || Polizia'
}

def estrai_acronimi(testo):
    """Estrae acronimi noti e aggiunge come entità."""
    trovati = []
    for sigla, categoria in ACRONIMI_LEGALI.items():
        if sigla.upper() in str(testo).upper():
            trovati.append(f"{sigla} || {categoria}")
    return trovati

# ===== PRIORITY 2.3: Keyword Extraction per Tematica =====
from sklearn.feature_extraction.text import TfidfVectorizer

def estrai_topic_keywords(testo, num_keywords=5):
    """Estrae parole-chiave principali per identificare tematica."""
    try:
        vectorizer = TfidfVectorizer(max_features=num_keywords, 
                                      stop_words=['italiano', 'english'])
        tfidf = vectorizer.fit_transform([str(testo)])
        keywords = vectorizer.get_feature_names_out()
        return list(keywords)
    except:
        return []

# ===== PRIORITY 3.1: Topic Modeling BERTopic =====
def topic_modeling(testi_lista):
    """
    Implementa Topic Modeling non supervisionato.
    Teoria: BERTopic usa embedding semantici + clustering HDBSCAN + c-TF-IDF
    per generare topic interpretabili senza etichette predefinite.
    A differenza di LDA funziona bene anche con pochi documenti e mantiene contesto semantico.
    """
    try:
        from bertopic import BERTopic
        
        topic_model = BERTopic(
            language="italian",
            min_topic_size=3,
            verbose=False,
            calculate_probabilities=True
        )
        
        topics, probabilita = topic_model.fit_transform(testi_lista)
        etichette = topic_model.generate_topic_labels(nr_words=3)
        
        return topics, etichette
    except ImportError:
        print("⚠️  BERTopic non installato. Skip topic modeling.")
        print("   Per attivare: pip install bertopic")
        # Fallback: tutti topic 0
        return [0]*len(testi_lista), ["Generico"]
    except Exception as e:
        print(f"⚠️  Errore Topic Modeling: {str(e)}")
        return [0]*len(testi_lista), ["Generico"]

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

@PerformanceMetrics.timer
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

def calcola_score_posizionamento(testo: str) -> tuple[float, float]:
    """
    Calcola i due score per la mappa di posizionamento.
    
    Valori restituiti:
    score_geografia: -1.0 = Italia 🇮🇹  ...  +1.0 = Mondo 🌍
    score_tech_legale: -1.0 = Legale ⚖️  ...  +1.0 = Tecnico ⚙️
    
    Entrambi sono valori continui float tra -1.0 e +1.0
    """
    testo_lower = str(testo).lower()
    
    # ========================================
    # Asse X: GEOGRAFIA
    # ========================================
    punti_geo = 0.0
    
    # Punti negativi = Italia
    parole_italia = ["italia", "italiano", "roma", "governo italiano", "garante privacy", "agcom"]
    for p in parole_italia:
        if p in testo_lower: punti_geo -= 0.25
    
    # Punti neutri = Europa
    parole_europa = ["unione europea", "ue", "bruxelles", "commissione europea", "edpb", "gdpr"]
    for p in parole_europa:
        if p in testo_lower: punti_geo += 0.0
    
    # Punti positivi = Internazionale
    parole_mondo = ["stati uniti", "usa", "mondo", "internazionale", "globale", "cina", "silicon valley"]
    for p in parole_mondo:
        if p in testo_lower: punti_geo += 0.25
    
    # Normalizza tra -1.0 e +1.0
    score_geografia = max(-1.0, min(1.0, punti_geo))

    # ========================================
    # Asse Y: TECNICO vs LEGALE
    # ========================================
    punti_tl = 0.0
    
    # Punti negativi = Legale
    parole_legale = ["legge", "normativa", "provvedimento", "multa", "sentenza", "regolamento", "tribunale", "avvocato"]
    for p in parole_legale:
        if p in testo_lower: punti_tl -= 0.25
    
    # Punti positivi = Tecnico
    parole_tecnico = ["algoritmo", "codice", "crittografia", "software", "hardware", "ai", "intelligenza artificiale", "sicurezza informatica"]
    for p in parole_tecnico:
        if p in testo_lower: punti_tl += 0.25
    
    # Normalizza tra -1.0 e +1.0
    score_tech_legale = max(-1.0, min(1.0, punti_tl))
    
    # Aggiungi piccolo rumore per evitare sovrapposizioni perfette
    import random
    score_geografia += random.uniform(-0.05, 0.05)
    score_tech_legale += random.uniform(-0.05, 0.05)
    
    return (score_tech_legale, score_geografia)


def associa_ong(testo: str) -> str:
    """
    Entity Linking: Associa una notizia ad una ONG se viene menzionata nel testo
    Restituisce il nome della ONG o stringa vuota se nessuna è trovata
    """
    testo_lower = str(testo).lower()
    
    for ong_nome in PROFILI_ONG:
        ong_nome_lower = ong_nome.lower()
        # Controllo match esatto e varianti comuni
        if ong_nome_lower in testo_lower:
            return ong_nome
        
        # Controllo anche acronimi e versioni abbreviate
        parole = ong_nome_lower.split()
        if len(parole) >= 2:
            acronimo = "".join([p[0] for p in parole if p])
            if len(acronimo) >=2 and acronimo in testo_lower:
                return ong_nome
    
    return ""

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

def carica_modello_impatto():
    """
    Carica il modello addestrato di predizione impatto se disponibile
    Livello 3: Active Learning
    """
    import joblib
    
    cartella_script = os.path.dirname(os.path.abspath(__file__))
    percorso_modello = os.path.join(cartella_script, '..', 'models', 'impact_classifier.pkl')
    percorso_embedding = os.path.join(cartella_script, '..', 'models', 'sentence_transformer.pkl')
    
    if os.path.exists(percorso_modello) and os.path.exists(percorso_embedding):
        try:
            clf = joblib.load(percorso_modello)
            embedding_model = joblib.load(percorso_embedding)
            return clf, embedding_model
        except Exception as e:
            print(f"⚠️ Errore caricamento modello impatto: {e}")
            return None, None
    return None, None


def calcola_livello_allarme(testo: str, clf, embedding_model) -> int:
    """
    Predice il livello di allarme (1-5) usando il modello addestrato
    Fallback a valore 2 se il modello non è disponibile
    """
    if clf is None or embedding_model is None:
        return 2
    
    try:
        embedding = embedding_model.encode([testo])
        predizione = clf.predict(embedding)[0]
        return int(max(1, min(5, predizione)))
    except Exception as e:
        print(f"⚠️ Errore predizione impatto: {e}")
        return 2


def salva_in_sqlite(df, db_path):
    """Salva dati analizzati in SQLite, convertendo liste in stringhe (Priority 0)."""
    df_copy = df.copy()
    for col in df_copy.columns:
        if df_copy[col].apply(lambda x: isinstance(x, list)).any():
            df_copy[col] = df_copy[col].apply(lambda x: ', '.join(x) if isinstance(x, list) else x)
            
    try:
        conn = sqlite3.connect(db_path)
        df_copy.to_sql('provvedimenti_analyzed', conn, if_exists='replace', index=False)
        conn.close()
        print(f"Dati salvati in SQLite: {db_path}")
    except Exception as e:
        print(f"Errore salvataggio SQLite: {e}")

def processa_dataframe(df: pd.DataFrame, fonte_nome: str) -> pd.DataFrame:
    """
    Funzione generica di analisi NLP applicabile a QUALSIASI fonte
    Applica TUTTI i passaggi di analisi su qualsiasi dataframe in ingresso
    
    Args:
        df: DataFrame raw da processare
        fonte_nome: Nome identificativo della fonte per logging
    
    Returns:
        DataFrame con tutti i campi calcolati
    """
    print(f"\n🚀 Inizio analisi NLP per {fonte_nome}: {len(df)} documenti")
    
    # Carica modello di predizione impatto
    clf, embedding_model = carica_modello_impatto()
    
    # 1. Entity Linking ONG
    df['ong_collegata'] = df['testo_completo'].apply(associa_ong)
    
    # 2. Classificazione Geografica
    df['Ambito_Geografico'] = df['testo_completo'].apply(classifica_geografia)
    
    # 3. Active Learning: Predizione Livello Allarme
    df['livello_allarme'] = df['testo_completo'].apply(
        lambda testo: calcola_livello_allarme(testo, clf, embedding_model)
    )
    
    # 4. Classificazione Sentiment
    df['Sentiment_Direzione'] = df['testo_completo'].apply(classifica_sentiment_provvedimento)
    
    # 5. Estrazione Keywords
    df['Parole_Chiave'] = df['testo_completo'].apply(estrai_topic_keywords)
    
    # 6. ✅ NUOVO: Classificazione Transformer con Confidence
    def classifica_riga(riga):
        etichetta, confidenza = classifica_testo(riga['titolo'] + " " + riga['testo_completo'][:300])
        return pd.Series([etichetta, confidenza])
    
    df[['topic_label', 'confidence']] = df.apply(classifica_riga, axis=1)
    
    # 7. ✅ NUOVO: Deduplicazione Semantica DBSCAN
    df = deduplica_dataframe(df)
    
    print(f"✅ Completata analisi {fonte_nome}")
    
    return df


def main():
    """
    Pipeline NLP principale - processa TUTTE le fonti disponibili
    GPDP, GNews, RSS EU
    """
    cartella_script = os.path.dirname(os.path.abspath(__file__))
    cartella_raw = os.path.join(cartella_script, '..', 'data', 'raw')
    cartella_processed = os.path.join(cartella_script, '..', 'data', 'processed')
    
    os.makedirs(cartella_processed, exist_ok=True)
    
    # Elenco di tutte le fonti da processare
    fonti = [
        {
            'nome': 'Garante Privacy GPDP',
            'file_raw': 'gpdp_sample.csv',
            'file_processed': 'gpdp_analyzed.csv'
        },
        {
            'nome': 'GNews',
            'file_raw': 'gnews_sample.csv',
            'file_processed': 'gnews_analyzed.csv'
        },
        {
            'nome': 'RSS Unione Europea',
            'file_raw': 'rss_eu_sample.csv',
            'file_processed': 'rss_eu_analyzed.csv'
        }
    ]
    
    # Processa ogni fonte se il file esiste
    for fonte in fonti:
        percorso_raw = os.path.join(cartella_raw, fonte['file_raw'])
        percorso_processed = os.path.join(cartella_processed, fonte['file_processed'])
        
        if os.path.exists(percorso_raw):
            df = pd.read_csv(percorso_raw)
            
            if 'testo_completo' in df.columns:
                df_processato = processa_dataframe(df, fonte['nome'])
                
                # ✅ SISTEMA DI MERGE STORICO: NON CANCELLA PIU' NULLA
                # Carica dati esistenti se il file è già presente
                if os.path.exists(percorso_processed):
                    df_esistente = pd.read_csv(percorso_processed)
                    # Unisci nuovi e vecchi dati
                    df_unito = pd.concat([df_esistente, df_processato], ignore_index=True)
                    # Rimuovi duplicati basati su titolo, mantieni quello più nuovo
                    df_finale = df_unito.drop_duplicates(subset=['titolo'], keep='last')
                else:
                    # File non esistente, usa direttamente quello nuovo
                    df_finale = df_processato
                
                df_finale.to_csv(percorso_processed, index=False)
                print(f"💾 Salvato: {percorso_processed} | Totale: {len(df_finale)} record")
            else:
                print(f"⚠️ Salto {fonte['nome']}: manca colonna testo_completo")
        else:
            print(f"ℹ️ File {fonte['file_raw']} non trovato, salto questa fonte")
    
    # Aggiorna anche il database SQLite
    print("\n🗄️ Aggiornamento database SQLite...")
    percorso_db = os.path.join(cartella_script, '..', 'data', 'tech_advocacy.db')
    
    # Carica tutti i dati processati per unire nel DB
    tutti_dati = []
    for fonte in fonti:
        p = os.path.join(cartella_processed, fonte['file_processed'])
        if os.path.exists(p):
            df = pd.read_csv(p)
            df['fonte_origine'] = fonte['nome']
            tutti_dati.append(df)
    
    if tutti_dati:
        df_unificato = pd.concat(tutti_dati, ignore_index=True)
        salva_in_sqlite(df_unificato, percorso_db)
        print(f"✅ Database SQLite aggiornato con {len(df_unificato)} documenti totali")


if __name__ == "__main__":
    main()
