import os
import sys
import re
import csv
import math
import random
import sqlite3
import time
import joblib
import psutil
from collections import Counter
from difflib import SequenceMatcher
from functools import wraps

import pandas as pd
import spacy
from spacy.lang.it.stop_words import STOP_WORDS as STOPWORD_IT
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS

# Il corpus è multilingua: alcune ONG monitorate (EFF, noyb, ecc.) pubblicano in
# inglese, quindi le keyword vanno filtrate su entrambe le lingue.
STOPWORD_IT_EN = set(STOPWORD_IT) | set(ENGLISH_STOP_WORDS)

# Aggiungi root progetto al path (necessario per import cross-package)
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from utils.logger_config import setup_logger
from scrapers.scraper_ong import PROFILI_ONG  # dict {nome_ong: {tipo, area, ...}}
from nlp.deduplication import deduplica_dataframe
from nlp.entity_linking import link_ong

logger = setup_logger(__name__)

# ==============================================
# LAZY LOADING MODELLI PESANTI
# I modelli vengono caricati solo alla prima chiamata,
# non all'import del modulo — evita rallentamenti nel dashboard.
# ==============================================
_nlp = None
_sentiment_pipe = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        logger.info("Caricamento modello spaCy it_core_news_md...")
        try:
            _nlp = spacy.load("it_core_news_md")
        except OSError:
            raise RuntimeError(
                "Modello spaCy non trovato. Esegui: python -m spacy download it_core_news_md"
            )
    return _nlp


def _get_sentiment_pipe():
    global _sentiment_pipe
    if _sentiment_pipe is None:
        from transformers import pipeline
        logger.info("Caricamento modello sentiment analysis BERT...")
        _sentiment_pipe = pipeline(
            "sentiment-analysis",
            model="nlptown/bert-base-multilingual-uncased-sentiment",
        )
    return _sentiment_pipe


# ===== PRIORITY 1.3: Blacklist dinamica da CSV =====
def carica_blacklist(filepath: str) -> set:
    blacklist: set = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                blacklist.add(row['parola_esclusa'].strip())
        logger.info("Blacklist caricata: %d parole escluse", len(blacklist))
    except FileNotFoundError:
        logger.warning("Blacklist non trovata in %s. Uso blacklist di default.", filepath)
        blacklist = {
            "Garante", "Roma", "Italia", "Autorità", "Provvedimento",
            "Comunicato", "Stampa", "Gdpr", "Privacy", "Codice",
        }
    return blacklist


_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BLACKLIST_PATH = os.path.join(_SCRIPT_DIR, '..', 'data', 'utils', 'nlp_blacklist.csv')
BLACKLIST = carica_blacklist(BLACKLIST_PATH)


# ==============================================
# METRICHE DI PERFORMANCE NLP
# ==============================================
class PerformanceMetrics:
    """Raccoglie metriche di efficienza e qualità per monitoraggio NLP."""

    def __init__(self):
        self.start_time = time.time()
        self.documents_processed = 0
        self.total_entities = 0
        self.time_per_doc: list[float] = []
        self.memory_usage: list[float] = []

    def timer(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            metrics.time_per_doc.append(time.perf_counter() - start)
            metrics.documents_processed += 1
            return result
        return wrapper

    def get_summary(self) -> dict:
        avg_time = sum(self.time_per_doc) / len(self.time_per_doc) if self.time_per_doc else 0
        avg_ent = self.total_entities / self.documents_processed if self.documents_processed else 0
        memory_mb = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        return {
            'documenti_totali': self.documents_processed,
            'tempo_medio_doc_ms': round(avg_time * 1000, 2),
            'entita_medie_doc': round(avg_ent, 1),
            'memoria_utilizzata_mb': round(memory_mb, 1),
            'tempo_totale_elaborazione_s': round(time.time() - self.start_time, 1),
        }

    def get_quality_metrics(self, all_entities: list) -> dict:
        entities_count = Counter(all_entities)
        singletons = sum(1 for _, cnt in entities_count.items() if cnt == 1)
        noise_ratio = singletons / len(entities_count) if entities_count else 0
        top_10 = sum(cnt for _, cnt in entities_count.most_common(10))
        coverage_top_10 = top_10 / len(all_entities) if all_entities else 0
        total = len(all_entities)
        entropia = -sum((c / total) * math.log2(c / total) for c in entities_count.values())
        return {
            'rumore_percentuale': round(noise_ratio * 100, 1),
            'coverage_top10_percentuale': round(coverage_top_10 * 100, 1),
            'entropia_distribuzione': round(entropia, 2),
            'entita_totali_trovate': len(all_entities),
            'entita_uniche': len(entities_count),
        }

    def print_report(self, all_entities: list | None = None) -> None:
        sep = "=" * 60
        s = self.get_summary()
        logger.info("%s\nREPORT PERFORMANCE E QUALITA' NLP\n%s", sep, sep)
        logger.info("Documenti processati: %d", s['documenti_totali'])
        logger.info("Tempo medio/doc:      %s ms", s['tempo_medio_doc_ms'])
        logger.info("Memoria utilizzata:   %s MB", s['memoria_utilizzata_mb'])
        logger.info("Tempo totale:         %s s", s['tempo_totale_elaborazione_s'])
        if all_entities:
            q = self.get_quality_metrics(all_entities)
            logger.info("Entita' totali: %d | uniche: %d", q['entita_totali_trovate'], q['entita_uniche'])
            logger.info("Rumore: %s%% | Coverage top10: %s%% | Entropia: %s",
                        q['rumore_percentuale'], q['coverage_top10_percentuale'], q['entropia_distribuzione'])
        logger.info("Interpretazione: Rumore<25%%=Ottimo | Entropia>3=Diversita' alta")


metrics = PerformanceMetrics()


# ===== PRIORITY 2.1: Sentiment Analysis =====
def classifica_sentiment_provvedimento(testo: str) -> str:
    """Classifica tono: POSITIVO (diritti tutelati) / NEGATIVO / NEUTRALE."""
    testo_core = str(testo)[:500]
    try:
        result = _get_sentiment_pipe()(testo_core, truncation=True)
        label = result[0]['label']
        if label in ('5 stars', '4 stars'):
            return 'POSITIVO (Diritti tutelati)'
        if label in ('1 stars', '2 stars'):
            return "NEGATIVO (Liberta' ristretta)"
        return 'NEUTRALE'
    except Exception as e:
        logger.debug("Sentiment fallback NEUTRALE per eccezione: %s", e)
        return 'NEUTRALE'


# ===== PRIORITY 2.2: Riconoscimento Acronimi =====
# Espanso con le normative EU post-2022 (DSA, DMA, NIS2, AI Act, DORA, eIDAS)
# e le principali DPA europee (ICO, CNIL, AEPD, AGCOM).
ACRONIMI_LEGALI: dict[str, str] = {
    'GDPR':   'Leggi e Regolamentazioni || EU',
    'EDPB':   'Istituzioni || EU',
    'CCPA':   'Leggi e Regolamentazioni || USA',
    'LGPD':   'Leggi e Regolamentazioni || Brasile',
    'RGPD':   'Leggi e Regolamentazioni || Francia',
    'AMI':    'Tecnologie || IA',
    'SARI':   'Tecnologie || Polizia',
    'DSA':    'Leggi e Regolamentazioni || EU',
    'DMA':    'Leggi e Regolamentazioni || EU',
    'NIS2':   'Leggi e Regolamentazioni || EU',
    'AI ACT': 'Leggi e Regolamentazioni || EU',
    'DORA':   'Leggi e Regolamentazioni || EU',
    'EIDAS':  'Leggi e Regolamentazioni || EU',
    'AGCOM':  'Istituzioni || Italia',
    'GPDP':   'Istituzioni || Italia',
    'ICO':    'Istituzioni || Regno Unito',
    'CNIL':   'Istituzioni || Francia',
    'AEPD':   'Istituzioni || Spagna',
}


def estrai_acronimi(testo: str) -> list[str]:
    testo_upper = str(testo).upper()
    return [
        f"{sigla} || {categoria}"
        for sigla, categoria in ACRONIMI_LEGALI.items()
        if sigla.upper() in testo_upper
    ]


# ===== PRIORITY 2.3: Keyword Extraction corpus-level =====
def estrai_keywords_corpus(testi: list[str], num_keywords: int = 5) -> list[list[str]]:
    """
    Estrae keyword via TF-IDF fittato sull'intero corpus.
    Fittare su un singolo documento renderebbe IDF=0 per tutti i termini,
    vanificando il peso TF-IDF. Qui il fit avviene sul batch completo.

    Stopword italiane e bigrammi (ngram_range) sono necessari per far emergere
    termini di dominio come "intelligenza artificiale" o "riconoscimento facciale"
    invece di articoli/preposizioni isolati.
    """
    if not testi:
        return []
    try:
        testi_puliti = [str(t) if t and str(t).strip() != 'nan' else '' for t in testi]
        vectorizer = TfidfVectorizer(
            max_features=200,
            min_df=1,
            ngram_range=(1, 2),
            stop_words=list(STOPWORD_IT_EN),
        )
        tfidf_matrix = vectorizer.fit_transform(testi_puliti)
        feature_names = vectorizer.get_feature_names_out()
        risultati = []
        for i in range(len(testi)):
            row = tfidf_matrix[i].toarray()[0]
            top_idx = row.argsort()[::-1][:num_keywords]
            risultati.append([feature_names[j] for j in top_idx if row[j] > 0])
        return risultati
    except Exception as e:
        logger.warning("TF-IDF corpus fallito: %s", e)
        return [[] for _ in testi]


# ===== PRIORITY 3.1: Topic Modeling BERTopic =====
def topic_modeling(testi_lista: list[str]) -> tuple[list[int], list[str]]:
    """
    Topic modeling non supervisionato via BERTopic + HDBSCAN.

    NOTA (roadmap, Fase 2): funzione NON ancora agganciata alla pipeline. È lo
    stub del topic modeling indicato tra le Future Directions del paper, da
    integrare come step corpus-level per produrre cluster tematici stabili nel
    tempo (in sostituzione del classificatore topic ad-hoc, rimosso perché non
    descritto nel paper e ridondante con la classificazione geografica).
    """
    try:
        from bertopic import BERTopic
        topic_model = BERTopic(
            language="italian",
            min_topic_size=3,
            verbose=False,
            calculate_probabilities=True,
        )
        topics, _ = topic_model.fit_transform(testi_lista)
        etichette = topic_model.generate_topic_labels(nr_words=3)
        return topics, etichette
    except ImportError:
        logger.warning("BERTopic non installato. Per attivare: pip install bertopic")
        return [0] * len(testi_lista), ["Generico"]
    except Exception as e:
        logger.warning("Errore Topic Modeling: %s", e)
        return [0] * len(testi_lista), ["Generico"]


# ===== PRIORITY 1.1: Pulizia testo =====
def pulisci_testo_gpdp(testo: str) -> str:
    if not isinstance(testo, str):
        return ""
    testo = re.sub(r'\s+', ' ', testo).strip()
    testo = re.sub(r'http[s]?://\S+', '', testo)
    testo = re.sub(r'\[\d+\]', '', testo)
    return testo[:5000]


# ===== PRIORITY 1.2: Deduplicazione fuzzy entità =====
def deduplica_entita(lista_entita: list[str], soglia: float = 0.85) -> list[str]:
    """Unisce entità simili per fuzzy matching (SequenceMatcher)."""
    if not lista_entita:
        return []
    unica: list[str] = []
    for ent in lista_entita:
        ent_nome = ent.split(' || ')[0]
        if not any(
            SequenceMatcher(None, ent_nome.lower(), u.split(' || ')[0].lower()).ratio() > soglia
            for u in unica
        ):
            unica.append(ent)
    return unica


def categorizza_entita(nome: str, etichetta_spacy: str) -> str:
    nome_low = nome.lower()
    if any(k in nome_low for k in ("comune di", "città metropolitana", "provincia di")):
        return "Comuni e Province"
    istituzioni_kw = (
        "ministero", "università", "polizia", "istituto", "agenzia",
        "regione", "asl", "ospedale", "inps", "inl",
        "commissione", "comitato", "consiglio", "tribunale", "corte",
        "autorità", "garante", "direzione", "prefettura", "edpb",
    )
    if any(k in nome_low for k in istituzioni_kw):
        return "Istituzioni"
    leggi_kw = ("legge", "regolamento", "direttiva", "gdpr", "decreto", "d.lgs", "costituzione")
    if any(k in nome_low for k in leggi_kw):
        return "Leggi e Regolamentazioni"
    if etichetta_spacy == "PER":
        return "Personaggi Pubblici"
    if etichetta_spacy == "LOC":
        return "Stati e Luoghi"
    return "Aziende e Org Private"


@PerformanceMetrics.timer
def estrai_entita(testo: str) -> list[str]:
    if not isinstance(testo, str) or len(testo) < 10:
        return []
    testo = pulisci_testo_gpdp(testo)
    nlp = _get_nlp()
    nlp.max_length = 2_000_000
    doc = nlp(testo)
    entita_trovate = []
    for ent in doc.ents:
        if ent.label_ not in ('ORG', 'LOC', 'PER'):
            continue
        nome_pulito = ent.text.strip().title()
        nome_lower = nome_pulito.lower()
        if re.search(r"http|www\.|[a-z0-9]+\.[a-z]{2,3}", nome_lower):
            continue
        if len(nome_pulito) <= 3 or nome_pulito in BLACKLIST:
            continue
        entita_trovate.append(f"{nome_pulito} || {categorizza_entita(nome_pulito, ent.label_)}")
    return deduplica_entita(list(set(entita_trovate)) + estrai_acronimi(testo))


def calcola_score_posizionamento(testo: str) -> tuple[float, float]:
    """
    Restituisce (score_tech_legale, score_geografia).
    score_geografia:   -1.0 = Italia   ...  +1.0 = Mondo
    score_tech_legale: -1.0 = Tecnico  ...  +1.0 = Legale
    Convenzione allineata al paper e alla Mappa di Posizionamento della dashboard.
    """
    testo_lower = str(testo).lower()

    punti_geo = 0.0
    for p in ("italia", "italiano", "roma", "governo italiano", "garante privacy", "agcom"):
        if p in testo_lower:
            punti_geo -= 0.25
    for p in ("stati uniti", "usa", "mondo", "internazionale", "globale", "cina", "silicon valley"):
        if p in testo_lower:
            punti_geo += 0.25
    score_geografia = max(-1.0, min(1.0, punti_geo))

    punti_tl = 0.0
    for p in ("legge", "normativa", "provvedimento", "multa", "sentenza", "regolamento", "tribunale", "avvocato"):
        if p in testo_lower:
            punti_tl += 0.25  # termini legali -> +1 (Legale)
    for p in ("algoritmo", "codice", "crittografia", "software", "hardware", "ai", "intelligenza artificiale", "sicurezza informatica"):
        if p in testo_lower:
            punti_tl -= 0.25  # termini tecnici -> -1 (Tecnico)
    score_tech_legale = max(-1.0, min(1.0, punti_tl))

    return (score_tech_legale, score_geografia)


def associa_ong(testo: str) -> str:
    """
    Entity linking: associa il testo alla ONG più pertinente via keyword-overlap.
    Delega a nlp.entity_linking.link_ong, unico punto di definizione dell'algoritmo
    (lo stesso usato dalla dashboard), così pipeline e UI restano allineate al paper.
    """
    return link_ong(testo, PROFILI_ONG)


def classifica_geografia(testo: str) -> str:
    testo_lower = str(testo).lower()
    parole_usa = ("stati uniti", "usa", "america", "california", "washington",
                  "new york", "silicon valley", "oltreoceano")
    parole_europa = ("unione europea", "comitato europeo", "edpb", "bruxelles",
                     "parlamento europeo", "commissione europea", "irlanda",
                     "lussemburgo", "corte di giustizia", "europeo", "europea")
    parole_asia = ("cina", "giappone", "india", "corea", "sud-est asiatico", "asia")
    if any(p in testo_lower for p in parole_usa):
        return "USA / Internazionale"
    if any(p in testo_lower for p in parole_europa):
        return "Europa"
    if any(p in testo_lower for p in parole_asia):
        return "Asia"
    return "Italia"


def carica_modello_impatto() -> tuple:
    """
    Carica il classificatore d'urgenza addestrato (Random Forest sulle correzioni).
    Il modello di embedding NON viene deserializzato da un .pkl da ~480MB: è
    pubblico e immutabile, quindi si riusa l'istanza condivisa della deduplica
    (stesso paraphrase-multilingual-MiniLM-L12-v2, una sola copia in memoria).
    """
    cartella = os.path.dirname(os.path.abspath(__file__))
    percorso_modello = os.path.join(cartella, '..', 'models', 'impact_classifier.pkl')
    if os.path.exists(percorso_modello):
        try:
            from nlp.deduplication import get_embedding_model
            return joblib.load(percorso_modello), get_embedding_model()
        except Exception as e:
            logger.warning("Errore caricamento modello impatto: %s", e)
    return None, None


def calcola_livello_allarme(testo: str, clf, embedding_model) -> int:
    if clf is None or embedding_model is None:
        return 2
    testo = str(testo) if pd.notna(testo) else ''
    try:
        predizione = clf.predict(embedding_model.encode([testo]))[0]
        return int(max(1, min(5, predizione)))
    except Exception as e:
        logger.warning("Errore predizione impatto: %s", e)
        return 2


def _tipo_sqlite(dtype) -> str:
    """Mappa un dtype pandas al tipo SQLite più vicino, per ALTER TABLE ADD COLUMN."""
    if pd.api.types.is_integer_dtype(dtype) or pd.api.types.is_bool_dtype(dtype):
        return "INTEGER"
    if pd.api.types.is_float_dtype(dtype):
        return "REAL"
    return "TEXT"


def _migra_schema_sqlite(conn: sqlite3.Connection, tabella: str, df: pd.DataFrame) -> None:
    """
    Allinea le colonne della tabella a quelle del DataFrame prima di un append,
    aggiungendo (mai rimuovendo) le colonne mancanti. Senza questo, un to_sql
    con colonne nuove (es. Entita_Coinvolte introdotta dopo la creazione della
    tabella) fallisce silenziosamente e la tabella smette di aggiornarsi.
    """
    colonne_esistenti = {
        riga[1] for riga in conn.execute(f"PRAGMA table_info({tabella})").fetchall()
    }
    if not colonne_esistenti:
        return  # la tabella non esiste ancora: to_sql la crea da zero con lo schema corretto
    for colonna in df.columns:
        if colonna not in colonne_esistenti:
            tipo = _tipo_sqlite(df[colonna].dtype)
            conn.execute(f'ALTER TABLE {tabella} ADD COLUMN "{colonna}" {tipo}')
            logger.info("Migrazione schema SQLite: aggiunta colonna '%s' (%s) a %s", colonna, tipo, tabella)


def salva_in_sqlite(df: pd.DataFrame, db_path: str) -> None:
    """
    Salva in SQLite con strategia upsert:
    append + deduplicazione in-place per hash_contenuto.
    Non sovrascrive mai la tabella intera (evita perdita dati su crash).
    """
    df_copy = df.copy()

    # SQLite tratta i nomi colonna come case-insensitive: alcune fonti (es. RSS EU)
    # producono sia 'Ente_Origine' che 'ente_origine' come colonne pandas distinte,
    # che altrimenti farebbero fallire ALTER TABLE/to_sql con "duplicate column name".
    colonne_normalizzate: dict[str, str] = {}
    colonne_da_tenere: list[str] = []
    for col in df_copy.columns:
        chiave = col.lower()
        if chiave in colonne_normalizzate:
            logger.warning(
                "Colonna duplicata (case-insensitive) ignorata per SQLite: '%s' (già presente come '%s')",
                col, colonne_normalizzate[chiave],
            )
            continue
        colonne_normalizzate[chiave] = col
        colonne_da_tenere.append(col)
    df_copy = df_copy[colonne_da_tenere]

    for col in df_copy.columns:
        if df_copy[col].apply(lambda x: isinstance(x, list)).any():
            df_copy[col] = df_copy[col].apply(
                lambda x: ', '.join(x) if isinstance(x, list) else x
            )
    try:
        conn = sqlite3.connect(db_path)
        _migra_schema_sqlite(conn, 'provvedimenti_analyzed', df_copy)
        df_copy.to_sql('provvedimenti_analyzed', conn, if_exists='append', index=False)
        conn.execute("""
            DELETE FROM provvedimenti_analyzed
            WHERE rowid NOT IN (
                SELECT MAX(rowid) FROM provvedimenti_analyzed
                GROUP BY hash_contenuto
            )
        """)
        conn.commit()
        conn.close()
        logger.info("Dati salvati in SQLite: %s", db_path)
    except Exception as e:
        logger.error("Errore salvataggio SQLite: %s", e)


def processa_dataframe(df: pd.DataFrame, fonte_nome: str) -> pd.DataFrame:
    """Applica l'intera pipeline NLP a qualsiasi DataFrame in ingresso."""
    logger.info("Inizio analisi NLP per %s: %d documenti", fonte_nome, len(df))
    clf, embedding_model = carica_modello_impatto()

    # Entity linking keyword-overlap + punteggio di confidenza (score basso = stima incerta)
    _link = df['testo_completo'].apply(lambda t: link_ong(t, PROFILI_ONG, return_score=True))
    df['ong_collegata'] = _link.apply(lambda r: r[0])
    df['ong_link_score'] = _link.apply(lambda r: r[1])
    df['Ambito_Geografico'] = df['testo_completo'].apply(classifica_geografia)
    df['livello_allarme'] = df['testo_completo'].apply(
        lambda t: calcola_livello_allarme(t, clf, embedding_model)
    )
    df['Entita_Coinvolte'] = df['testo_completo'].apply(estrai_entita)
    df['Sentiment_Direzione'] = df['testo_completo'].apply(classifica_sentiment_provvedimento)

    # Sanitizza NaN nelle colonne testo prima di qualsiasi operazione stringa
    df['titolo'] = df['titolo'].fillna('') if 'titolo' in df.columns else df.get('titolo', '')
    df['testo_completo'] = df['testo_completo'].fillna('')

    # TF-IDF fittato sull'intero batch, non documento per documento
    df['Parole_Chiave'] = estrai_keywords_corpus(df['testo_completo'].tolist())

    # Deduplica semantica APPLICATA (non solo annotata): tiene un solo
    # rappresentante per cluster (is_primary), così i near-duplicate non entrano
    # nel processed layer. Il layer raw resta append-only e intatto.
    df = deduplica_dataframe(df)
    n_prima = len(df)
    df = (
        df[df['is_primary']]
        .drop(columns=['is_primary', 'cluster_id'])
        .reset_index(drop=True)
    )
    rimossi = n_prima - len(df)
    if rimossi:
        logger.info("Deduplica semantica %s: rimossi %d near-duplicate", fonte_nome, rimossi)
    logger.info("Completata analisi %s", fonte_nome)
    return df


def main() -> None:
    """Pipeline NLP principale — processa GPDP, GNews, RSS EU."""
    cartella_raw = os.path.join(_SCRIPT_DIR, '..', 'data', 'raw')
    cartella_processed = os.path.join(_SCRIPT_DIR, '..', 'data', 'processed')
    os.makedirs(cartella_processed, exist_ok=True)

    fonti = [
        {'nome': 'Garante Privacy GPDP', 'file_raw': 'gpdp_sample.csv',       'file_processed': 'gpdp_analyzed.csv'},
        {'nome': 'ONG RSS',              'file_raw': 'ong_sample.csv',         'file_processed': 'ong_analyzed.csv'},
        {'nome': 'GNews',                'file_raw': 'gnews_sample.csv',       'file_processed': 'gnews_analyzed.csv'},
        {'nome': 'RSS Unione Europea',   'file_raw': 'rss_eu_sample.csv',      'file_processed': 'rss_eu_analyzed.csv'},
        {'nome': 'AGCOM',                'file_raw': 'agcom_sample.csv',       'file_processed': 'agcom_analyzed.csv'},
        {'nome': 'Tech News Italia',     'file_raw': 'tech_news_sample.csv',   'file_processed': 'tech_news_analyzed.csv'},
        {'nome': 'Parlamento Europeo',   'file_raw': 'eu_parl_sample.csv',     'file_processed': 'eu_parl_analyzed.csv'},
    ]

    all_entities: list[str] = []  # raccolta per il report di qualità NLP finale

    for fonte in fonti:
        percorso_raw = os.path.join(cartella_raw, fonte['file_raw'])
        percorso_processed = os.path.join(cartella_processed, fonte['file_processed'])

        if not os.path.exists(percorso_raw):
            logger.info("File %s non trovato, salto questa fonte", fonte['file_raw'])
            continue

        df = pd.read_csv(percorso_raw)
        if 'testo_completo' not in df.columns:
            logger.warning("Salto %s: manca colonna testo_completo", fonte['nome'])
            continue

        df_processato = processa_dataframe(df, fonte['nome'])

        for ents in df_processato['Entita_Coinvolte']:
            if isinstance(ents, list):
                all_entities.extend(ents)

        # Rigenerazione completa dal raw, non merge incrementale col CSV esistente:
        # la deduplicazione semantica sceglie il rappresentante "primario" di ogni
        # cluster in base all'INTERO corpus raw corrente, e quella scelta può
        # cambiare da un run all'altro (nuovi articoli si aggiungono ai cluster).
        # Un merge per 'titolo' con keep='last' non rimuove mai il vecchio primario
        # quando ne subentra uno nuovo: i due finivano per convivere nel CSV
        # processato, vanificando la deduplica, e i campi NLP delle righe non più
        # primarie restavano congelati ai valori di quando lo erano state l'ultima
        # volta. Il layer raw è append-only e mai troncato, quindi rigenerare da
        # zero non perde nulla: è solo la cache derivata a essere ricalcolata.
        df_finale = df_processato

        df_finale.to_csv(percorso_processed, index=False)
        logger.info("Salvato: %s | Totale: %d record", percorso_processed, len(df_finale))

    logger.info("Aggiornamento database SQLite...")
    percorso_db = os.path.join(_SCRIPT_DIR, '..', 'data', 'tech_advocacy.db')
    tutti_dati = []
    for fonte in fonti:
        p = os.path.join(cartella_processed, fonte['file_processed'])
        if os.path.exists(p):
            d = pd.read_csv(p)
            d['fonte_origine'] = fonte['nome']
            tutti_dati.append(d)

    if tutti_dati:
        df_unificato = pd.concat(tutti_dati, ignore_index=True)
        salva_in_sqlite(df_unificato, percorso_db)
        logger.info("Database SQLite aggiornato con %d documenti totali", len(df_unificato))

    # Report finale di performance e qualità NLP (le metriche del paper:
    # rumore, entropia, coverage, tempo/doc). Prima venivano raccolte ma mai emesse.
    metrics.print_report(all_entities)


if __name__ == "__main__":
    main()
