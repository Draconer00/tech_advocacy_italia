"""
Caricamento e preparazione dei dati per la dashboard e per l'export HTML.

Funzioni pure (nessuna dipendenza da Streamlit): la dashboard le avvolge in
st.cache_data, app/export_html.py le chiama direttamente. Così le due viste
leggono esattamente gli stessi dati con la stessa logica.

Sola lettura sui dataset: l'unica scrittura è ong_posizioni_permanenti.csv,
e solo se il chiamante passa salva=True (la dashboard sì, l'export no).
"""
from __future__ import annotations

import ast
import logging
import os
import sqlite3
import sys
from datetime import datetime

import numpy as np
import pandas as pd

CARTELLA_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if CARTELLA_ROOT not in sys.path:
    sys.path.insert(0, CARTELLA_ROOT)

from scrapers.scraper_ong import PROFILI_ONG  # noqa: E402
from utils.feedback_schema import load_feedback  # noqa: E402
from utils.ong_manual_entries import carica_documenti_manuali  # noqa: E402
from nlp.theme_matching import carica_temi as carica_temi_registro, carica_registro_temi  # noqa: E402

log = logging.getLogger(__name__)

CARTELLA_PROCESSED = os.path.join(CARTELLA_ROOT, 'data', 'processed')
CARTELLA_RAW = os.path.join(CARTELLA_ROOT, 'data', 'raw')
PERCORSO_DB = os.path.join(CARTELLA_ROOT, 'data', 'tech_advocacy.db')
PERCORSO_FEEDBACK = os.path.join(CARTELLA_PROCESSED, 'training_data_feedback.csv')
PERCORSO_POSIZIONI_ONG = os.path.join(CARTELLA_PROCESSED, 'ong_posizioni_permanenti.csv')


def _leggi_processed(nome_file: str) -> pd.DataFrame:
    percorso = os.path.join(CARTELLA_PROCESSED, f'{nome_file}.csv')
    return pd.read_csv(percorso) if os.path.exists(percorso) else pd.DataFrame()


# --- LOADER PER FONTE --------------------------------------------------------
def carica_dati_ong() -> pd.DataFrame:
    """ONG analizzate dal NLP (fallback: grezze) + documenti inseriti a mano."""
    for percorso in [os.path.join(CARTELLA_PROCESSED, 'ong_analyzed.csv'),
                     os.path.join(CARTELLA_RAW, 'ong_sample.csv')]:
        if os.path.exists(percorso):
            df = pd.read_csv(percorso)
            df_manuali = carica_documenti_manuali()
            if not df_manuali.empty:
                df = pd.concat([df, df_manuali], ignore_index=True)
            return df
    return pd.DataFrame()


def _lista_da_stringa(x):
    if isinstance(x, list):
        return x
    if isinstance(x, str):
        try:
            v = ast.literal_eval(x)
            return v if isinstance(v, list) else []
        except (ValueError, SyntaxError):
            return []
    return []


def carica_dati_garante() -> pd.DataFrame:
    """Provvedimenti del Garante da SQLite (più veloce), fallback su CSV."""
    if os.path.exists(PERCORSO_DB):
        try:
            conn = sqlite3.connect(PERCORSO_DB)
            # provvedimenti_analyzed contiene l'unione di TUTTE le fonti: filtrare
            # per fonte_origine è indispensabile, altrimenti articoli di altre
            # fonti verrebbero mostrati come provvedimenti del Garante.
            df = pd.read_sql(
                "SELECT * FROM provvedimenti_analyzed WHERE fonte_origine = 'Garante Privacy GPDP'", conn)
            conn.close()
            if not df.empty:
                if 'Entita_Coinvolte' in df.columns:
                    df['Entita_Coinvolte'] = df['Entita_Coinvolte'].apply(_lista_da_stringa)
                return df
        except Exception as e:  # noqa: BLE001 — fallback esplicito su CSV, loggato
            log.warning("Errore lettura SQLite (%s): fallback su CSV", e)
    df = _leggi_processed('gpdp_analyzed')
    if not df.empty and 'Entita_Coinvolte' in df.columns:
        df['Entita_Coinvolte'] = df['Entita_Coinvolte'].apply(_lista_da_stringa)
    return df


def carica_dati_gnews() -> pd.DataFrame:
    df = _leggi_processed('gnews_analyzed')
    if not df.empty:
        df['ong_collegata'] = df.get('ong_collegata', "")
        df['fonte'] = 'GNews'
    return df


def carica_dati_rss_eu() -> pd.DataFrame:
    return _leggi_processed('rss_eu_analyzed')


def carica_dati_tech_news() -> pd.DataFrame:
    return _leggi_processed('tech_news_analyzed')


def carica_dati_eu_parl() -> pd.DataFrame:
    return _leggi_processed('eu_parl_analyzed')


def carica_dati_agcom() -> pd.DataFrame:
    return _leggi_processed('agcom_analyzed')


def carica_dati_gazzetta_ufficiale() -> pd.DataFrame:
    return _leggi_processed('gazzetta_ufficiale_analyzed')


def carica_dati_cjeu() -> pd.DataFrame:
    return _leggi_processed('cjeu_analyzed')


def carica_dati_feeds() -> pd.DataFrame:
    return _leggi_processed('feeds_analyzed')


def carica_temi() -> dict:
    """Temi attivi del registro -> termini-seme (fallback lessicale per CSV pre-feature)."""
    return carica_temi_registro()


def carica_registro() -> pd.DataFrame:
    """Registro completo dei temi (macro + sotto-temi, tutti gli stati)."""
    return carica_registro_temi()


def carica_topic_emergenti() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Report BERTopic prodotto OFFLINE da nlp/topic_discovery.py: (topic, trend)."""
    df_topic = _leggi_processed('topic_emergenti')
    df_trend = _leggi_processed('topic_emergenti_trend')
    return df_topic, df_trend


# --- VISTA UNIFICATA (Panoramica, Geografia) ---------------------------------
# (file_*_analyzed, etichetta_fonte, tipo_documento, categoria_fonte, canale, colonna_sottofonte)
# REGOLA: ogni scraper registrato deve comparire qui, o i suoi documenti restano
# invisibili nella Panoramica.
FONTI_UNIFICATE: list[tuple[str, str, str, str, str, str | None]] = [
    ('gpdp_analyzed',               'Garante Privacy',    'Provvedimento',  'Ufficiale', 'Garante Privacy',       None),
    ('gnews_analyzed',              'GNews',              'Articolo',       'Stampa',    'Google News',           'fonte_articolo'),
    ('rss_eu_analyzed',             'Regolatori UE',      'Comunicato',     'Ufficiale', 'Istituzioni UE',        'ente_origine'),
    ('agcom_analyzed',              'AGCOM',              'Documento',      'Ufficiale', 'AGCOM',                 None),
    ('tech_news_analyzed',          'Tech News',          'Articolo',       'Stampa',    'Testate tech',          'nome_testata'),
    ('eu_parl_analyzed',            'Parlamento UE',      'Atto',           'Ufficiale', 'Parlamento UE',         'sotto_fonte'),
    ('gazzetta_ufficiale_analyzed', 'Gazzetta Ufficiale', 'Atto normativo', 'Ufficiale', 'Gazzetta Ufficiale',    'serie'),
    ('cjeu_analyzed',               'CJEU',               'Sentenza',       'Ufficiale', 'Corte di Giustizia UE', None),
]
# I feed hanno fonti di natura diversa nello stesso file: etichetta e categoria
# si derivano per riga da tipo_fonte/trust_tier. Le ONG usano come fonte il nome
# dell'organizzazione (ground truth del publisher).

COLONNE_UNIFICATE = ['data', 'titolo', 'fonte', 'tipo', 'categoria', 'canale', 'sottofonte', 'url',
                     'sentiment', 'ambito_geografico', 'livello_allarme', 'temi', 'entita',
                     'ong_collegata', 'ong_link_score', 'testo', 'manuale']

_TIPO_FONTE_A_CATEGORIA = {
    'istituzionale': 'Ufficiale', 'media': 'Stampa',
    'ngo': 'Società civile', 'blog_newsletter': 'Blog/Opinione',
}


def _categoria_feed(row) -> str:
    tf = str(row.get('tipo_fonte', '')).strip().lower()
    if tf in _TIPO_FONTE_A_CATEGORIA:
        return _TIPO_FONTE_A_CATEGORIA[tf]
    try:
        tier = int(float(row.get('trust_tier', 2)))
    except (ValueError, TypeError):
        tier = 2
    return {1: 'Ufficiale', 2: 'Stampa', 3: 'Blog/Opinione'}.get(tier, 'Blog/Opinione')


def _entita(valore) -> list[tuple[str, str]]:
    """'Nome || Categoria || ...' -> [(nome, categoria)] (stringhe-lista del NLP)."""
    out = []
    for e in _lista_da_stringa(valore):
        parti = [p.strip() for p in str(e).split('||')]
        if parti and parti[0]:
            out.append((parti[0], parti[1] if len(parti) > 1 else ''))
    return out


def _pulito(v) -> str:
    s = '' if v is None or (isinstance(v, float) and np.isnan(v)) else str(v).strip()
    return '' if s.lower() == 'nan' else s


def _riga_unificata(row, fonte: str, tipo: str, categoria: str, canale: str, sottofonte: str = '') -> dict:
    return {
        'data': row.get('data_pubblicazione', row.get('Data', datetime.now().date().isoformat())),
        'titolo': row.get('titolo', row.get('Titolo', '')),
        'fonte': fonte, 'tipo': tipo, 'categoria': categoria,
        'canale': canale, 'sottofonte': _pulito(sottofonte),
        'url': row.get('url', row.get('Link', '')),
        'sentiment': row.get('Sentiment_Direzione', 'NEUTRALE'),
        'ambito_geografico': row.get('Ambito_Geografico', row.get('area_geografica', 'Italia')),
        'livello_allarme': row.get('livello_allarme', 2),
        'temi': _pulito(row.get('temi_rilevati', '')),
        'entita': _entita(row.get('Entita_Coinvolte')),
        'ong_collegata': _pulito(row.get('ong_collegata', '')),
        'ong_link_score': row.get('ong_link_score'),
        'testo': _pulito(row.get('testo_completo', '')),
        'manuale': _pulito(row.get('fonte', '')) == 'manuale',
    }


def carica_dati_unificati() -> pd.DataFrame:
    """Tutte le fonti processate in un dataframe standardizzato, con la
    categoria-macro (Ufficiale / Stampa / Blog-Opinione / Società civile) che
    separa i fatti dall'opinione e il canale (scraper) per i raggruppamenti."""
    righe = []
    for nome_file, fonte, tipo, categoria, canale, col_sotto in FONTI_UNIFICATE:
        for _, row in _leggi_processed(nome_file).iterrows():
            sotto = row.get(col_sotto, '') if col_sotto else ''
            righe.append(_riga_unificata(row, fonte, tipo, categoria, canale, sotto))

    for _, row in _leggi_processed('feeds_analyzed').iterrows():
        testata = str(row.get('nome_testata', 'Feed'))
        righe.append(_riga_unificata(row, testata, 'Approfondimento', _categoria_feed(row), 'Feed RSS', testata))

    for _, row in _leggi_processed('ong_analyzed').iterrows():
        nome_ong = str(row.get('nome_organizzazione', 'Organizzazione'))
        righe.append(_riga_unificata(row, nome_ong, 'Comunicato ONG', 'Società civile', 'ONG', nome_ong))

    if not righe:
        return pd.DataFrame(columns=COLONNE_UNIFICATE)
    df = pd.DataFrame(righe)
    df['data'] = pd.to_datetime(df['data'], errors='coerce', format='mixed', utc=True).dt.date
    df['livello_allarme'] = pd.to_numeric(df['livello_allarme'], errors='coerce')
    return df.sort_values('data', ascending=False).reset_index(drop=True)


def prepara_master(df_unificato: pd.DataFrame) -> pd.DataFrame:
    """Vista master: deduplicata per (titolo, fonte), più recente prima."""
    df = df_unificato.drop_duplicates(subset=['titolo', 'fonte'], keep='first').copy()
    df['data'] = pd.to_datetime(df['data'], errors='coerce', format='mixed', utc=True).dt.date
    return df.sort_values('data', ascending=False, na_position='last').reset_index(drop=True)


# Intervalli della Panoramica. L'export usa INTERVALLO_EXPORT (dati statici).
INTERVALLI_HOME = [("Ultimi 7 giorni", 7), ("Ultimi 14 giorni", 14), ("Ultimi 30 giorni", 30),
                   ("Ultimi 90 giorni", 90), ("Ultimi 180 giorni", 180), ("Tutto lo storico", 9999)]
INTERVALLO_HOME_DEFAULT = 1  # 14 giorni
INTERVALLO_EXPORT = 4        # 180 giorni


def filtra_master(df_master: pd.DataFrame, giorni: int, categorie=None, fonti=None, aree=None,
                  allarme_min: int = 1) -> pd.DataFrame:
    df = df_master
    if giorni != 9999:
        soglia = datetime.now().date() - pd.Timedelta(days=giorni)
        df = df[df['data'] >= soglia]
    mask = df['livello_allarme'].fillna(1) >= allarme_min
    if categorie is not None:
        mask &= df['categoria'].isin(categorie)
    if fonti is not None:
        mask &= df['fonte'].isin(fonti)
    if aree is not None:
        mask &= df['ambito_geografico'].isin(aree)
    return df[mask]


# --- DATI GREZZI PER FONTE -----------------------------------------------------
FONTI_RAW_CSV: dict[str, str] = {
    "Garante Privacy (GPDP)": "gpdp", "AGCOM": "agcom", "ONG e Società Civile": "ong",
    "GNews": "gnews", "RSS Regolatori Europei": "rss_eu", "Tech News Italiane": "tech_news",
    "Parlamento Europeo": "eu_parl", "Gazzetta Ufficiale": "gazzetta_ufficiale",
    "CJEU (Corte di Giustizia UE)": "cjeu", "Blog e Newsletter": "feeds",
}


def carica_dati_raw_per_fonte() -> dict:
    """Titolo + data di raccolta dal CSV grezzo di ogni scraper (data/raw/*_sample.csv).
    Non richiede che la pipeline NLP sia già stata eseguita."""
    fonti_raw = {}
    for etichetta, nome_file in FONTI_RAW_CSV.items():
        percorso = os.path.join(CARTELLA_RAW, f'{nome_file}_sample.csv')
        if not os.path.exists(percorso):
            continue
        df = pd.read_csv(percorso)
        if df.empty or 'titolo' not in df.columns or 'data_scraping' not in df.columns:
            continue
        df = df[['titolo', 'data_scraping']].copy()
        df['data_scraping'] = pd.to_datetime(df['data_scraping'], errors='coerce', format='mixed', utc=True)
        df = df.dropna(subset=['data_scraping']).sort_values('data_scraping', ascending=False)
        if not df.empty:
            fonti_raw[etichetta] = df.reset_index(drop=True)
    return fonti_raw


# --- ANALISI TEMPORALE --------------------------------------------------------
def _estrai_data_pubblicazione(df: pd.DataFrame) -> pd.Series:
    for col in ['data_pubblicazione', 'Data', 'publishedAt']:
        if col in df.columns:
            return pd.to_datetime(df[col], errors='coerce', format='mixed', utc=True)
    return pd.Series(pd.NaT, index=df.index)


def carica_dati_per_analisi_temporale() -> pd.DataFrame:
    """Unifica tutti i dataset in un formato standard per l'analisi temporale."""
    fonti_config = [
        (carica_dati_garante(), 'GPDP'), (carica_dati_ong(), 'ONG'), (carica_dati_gnews(), 'GNews'),
        (carica_dati_rss_eu(), 'EU RSS'), (carica_dati_tech_news(), 'Tech News'),
        (carica_dati_eu_parl(), 'Parlamento EU'), (carica_dati_agcom(), 'AGCOM'),
        (carica_dati_gazzetta_ufficiale(), 'Gazzetta Ufficiale'), (carica_dati_cjeu(), 'CJEU'),
        (carica_dati_feeds(), 'Blog/Newsletter'),
    ]
    blocchi = []
    for df_src, etichetta in fonti_config:
        if df_src.empty:
            continue
        blocco = pd.DataFrame()
        blocco['data'] = _estrai_data_pubblicazione(df_src)
        blocco['fonte'] = etichetta
        t_tit = df_src['titolo'].fillna('').astype(str) if 'titolo' in df_src.columns else pd.Series([''] * len(df_src))
        t_txt = df_src['testo_completo'].fillna('').astype(str) if 'testo_completo' in df_src.columns else pd.Series([''] * len(df_src))
        blocco['testo_ricerca'] = [f"{a} {b}".lower() for a, b in zip(t_tit.values, t_txt.values)]
        # Temi già rilevati dal NLP (persistiti); fallback lessicale solo per CSV pre-feature.
        if 'temi_rilevati' in df_src.columns:
            blocco['temi_rilevati'] = df_src['temi_rilevati'].fillna('').astype(str).values
        else:
            temi_fb = carica_temi()
            blocco['temi_rilevati'] = ['|'.join(t for t, termini in temi_fb.items() if any(x in ts for x in termini))
                                       for ts in blocco['testo_ricerca']]
        blocco['importo_eur'] = (pd.to_numeric(df_src['importo_eur'], errors='coerce')
                                 if 'importo_eur' in df_src.columns else float('nan'))
        blocchi.append(blocco)

    if not blocchi:
        return pd.DataFrame(columns=['data', 'fonte', 'temi_rilevati', 'importo_eur'])
    df = pd.concat(blocchi, ignore_index=True)
    df['data'] = pd.to_datetime(df['data'], errors='coerce', format='mixed', utc=True)
    return df.dropna(subset=['data'])


INTERVALLI_TEMPO = [("Ultimi 6 mesi", 180), ("Ultimo anno", 365), ("Tutto lo storico", 0)]
LIVELLI_TEMI = ["Macro-temi", "Sotto-temi", "Tutti"]


def filtra_periodo(df_temporale: pd.DataFrame, giorni: int) -> pd.DataFrame:
    if giorni <= 0:
        return df_temporale.copy()
    soglia = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=giorni)
    return df_temporale[df_temporale['data'] >= soglia].copy()


def _mese(serie_dt: pd.Series) -> pd.Series:
    return serie_dt.dt.tz_convert(None).dt.to_period('M').astype(str)


def conteggio_mensile_per_fonte(df: pd.DataFrame) -> pd.DataFrame:
    return (df.groupby([_mese(df['data']).rename('mese'), 'fonte']).size()
            .reset_index(name='conteggio').sort_values('mese'))


def sanzioni_mensili(df: pd.DataFrame) -> pd.DataFrame:
    if 'importo_eur' not in df.columns:
        return pd.DataFrame()
    s = df[pd.to_numeric(df['importo_eur'], errors='coerce') > 0]
    if s.empty:
        return pd.DataFrame()
    return (s.groupby(_mese(s['data']).rename('mese'))['importo_eur'].sum()
            .reset_index().sort_values('mese'))


def temi_ammessi(livello: str, registro: pd.DataFrame):
    attivi = registro[registro['stato'] == 'attivo']
    if livello == "Macro-temi":
        return set(attivi[attivi['padre'] == '']['tema'])
    if livello == "Sotto-temi":
        return set(attivi[attivi['padre'] != '']['tema'])
    return None


def conteggio_temi_mensile(df: pd.DataFrame, ammessi) -> pd.DataFrame:
    """mese x tema dai temi persistiti dal NLP (nessun ricalcolo a runtime)."""
    if df.empty:
        return pd.DataFrame(columns=['mese', 'tema', 'conteggio'])
    mesi = _mese(df['data']).values
    righe = []
    for mese, temi in zip(mesi, df['temi_rilevati'].fillna('').astype(str).values):
        for tema in temi.split('|'):
            if tema and (ammessi is None or tema in ammessi):
                righe.append((mese, tema))
    if not righe:
        return pd.DataFrame(columns=['mese', 'tema', 'conteggio'])
    return (pd.DataFrame(righe, columns=['mese', 'tema']).groupby(['mese', 'tema']).size()
            .reset_index(name='conteggio').sort_values('mese'))


def confronto_temi(df_kw: pd.DataFrame):
    """Variazione % della frequenza media: ultimi 2 mesi vs 2 precedenti.
    Ritorna (confronto, mesi_precedenti, mesi_recenti) o None se < 4 mesi."""
    mesi = sorted(df_kw['mese'].unique())
    if len(mesi) < 4:
        return None
    recenti, precedenti = mesi[-2:], mesi[-4:-2]

    def media(sel):
        return df_kw[df_kw['mese'].isin(sel)].groupby('tema')['conteggio'].mean()

    c = pd.DataFrame({'freq_recente': media(recenti), 'freq_precedente': media(precedenti)}).fillna(0)
    c['variazione_pct'] = ((c['freq_recente'] - c['freq_precedente'])
                           / c['freq_precedente'].replace(0, float('nan')) * 100).round(1)
    c = c.dropna(subset=['variazione_pct']).sort_values('variazione_pct', ascending=False)
    return c, precedenti, recenti


# --- MAPPA DI POSIZIONAMENTO --------------------------------------------------
_AMBITO_SCORE = {'Italia': -0.65, 'Europa': 0.15, 'USA / Internazionale': 0.75, 'Asia': 0.55}
_AREA_ONG_SCORE = {'italia': -0.5, 'europa': 0.1, 'unione europea': 0.1,
                   'internazionale': 0.6, 'mondiale': 0.7}
_KW_LEGALE = (
    "legge", "normativa", "provvedimento", "multa", "sentenza", "regolamento",
    "tribunale", "avvocato", "giurisprudenza", "ricorso", "decreto", "sanzione",
    "violazione", "illecito", "procedimento", "delibera", "autorità", "gdpr",
    "direttiva", "codice privacy", "corte", "giudice", "contenziosi",
    "regulation", "enforcement", "fine", "court", "compliance",
    "lawsuit", "ruling", "judgment", "penalty", "legislation",
    "infringement", "supervisory authority", "legal action", "appeal",
    "complaint", "sanction", "legal challenge", "gdpr article",
    "data protection authority", "dpa decision",
)
_KW_TECNICO = (
    "algoritmo", "crittografia", "software", "hardware",
    "intelligenza artificiale", "machine learning", "dataset",
    "biometri", "cybersecurity", "exploit", "vulnerabilit", "hacker",
    "cifratura", "open source", "api", "rete neurale", "llm", "deepfake",
    "algorithm", "encryption", "neural network", "biometric",
    "vulnerability", "open source software", "artificial intelligence",
    "surveillance technology", "fingerprinting", "large language model",
    "deepfake", "adversarial", "model training", "training data",
    "technical standard", "interoperability",
)
# Baseline Y dal focus dichiarato nel profilo ONG (negativo = tecnico, positivo = legale).
_BASELINE_Y_ONG = {
    "Hermes Center": -0.50, "AI Forensics": -0.45, "AlgorithmWatch": -0.40,
    "Electronic Frontier Foundation": -0.25, "Slow Web": -0.20, "NINA": -0.20,
    "Privacy International": -0.15, "Access Now": -0.15, "Privacy Network": -0.05,
    "Open Rights Group": 0.00, "EDRi (Europa)": 0.15, "Consiglio d'Europa": 0.25,
    "The Good Lobby Italia": 0.20, "Amnesty Italia": 0.20, "Antigone": 0.25,
    "SOMO (Multinazionali)": 0.15, "Italiani Senza Cittadinanza": 0.15, "STRALI": 0.10,
    "EDPS Garante Privacy UE": 0.30, "Commissione Europea DG Connect": 0.35,
    "AI Act Monitor": 0.40, "Noyb (Privacy UE)": 0.50,
}


def _calcola_scores(row) -> pd.Series:
    # Asse X: geografia, sfumata con la baseline del profilo ONG
    score_geo = _AMBITO_SCORE.get(str(row.get('Ambito_Geografico', '')).strip(), 0.0)
    area_ong = str(row.get('area_geografica', '')).lower()
    for k, v in _AREA_ONG_SCORE.items():
        if k in area_ong:
            score_geo = round((score_geo + v) / 2, 3)
            break
    # Asse Y: 60% baseline da profilo ONG, 40% segnale testuale bilingue
    baseline_y = _BASELINE_Y_ONG.get(str(row.get('nome_organizzazione', '')), 0.0)
    testo = ' '.join(filter(None, [str(row.get('titolo', '')),
                                   str(row.get('testo_completo', ''))[:1500]])).lower()
    punti = sum(0.1 for p in _KW_LEGALE if p in testo) - sum(0.1 for p in _KW_TECNICO if p in testo)
    text_signal = max(-1.0, min(1.0, punti))
    score_tl = round(max(-1.0, min(1.0, 0.6 * baseline_y + 0.4 * text_signal)), 3)
    return pd.Series([score_tl, score_geo])


def prepara_posizionamento(df_ong: pd.DataFrame, salva: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(notizie, centroidi ONG) per la mappa. Le posizioni ONG sono persistite in
    ong_posizioni_permanenti.csv e aggiornate solo per le ONG con dati nuovi, così
    una ONG non torna al centro quando le sue notizie escono dalla finestra.
    Con salva=False (export) il file viene solo letto."""
    df_notizie = df_ong.copy()
    df_notizie[['score_tech_legale', 'score_geografia']] = df_notizie.apply(_calcola_scores, axis=1)

    nuovi = df_notizie.groupby('nome_organizzazione').agg(
        score_tech_legale=('score_tech_legale', 'mean'),
        score_geografia=('score_geografia', 'mean'),
        numero_articoli=('titolo', 'count')).reset_index().rename(columns={'nome_organizzazione': 'nome'})

    if os.path.exists(PERCORSO_POSIZIONI_ONG):
        salvati = pd.read_csv(PERCORSO_POSIZIONI_ONG)
        for _, r in nuovi.iterrows():
            if r['nome'] in salvati['nome'].values:
                i = salvati.index[salvati['nome'] == r['nome']][0]
                for c in ('score_tech_legale', 'score_geografia', 'numero_articoli'):
                    salvati.at[i, c] = r[c]
            else:
                salvati = pd.concat([salvati, pd.DataFrame([r])], ignore_index=True)
        centroidi = salvati
    else:
        centroidi = nuovi
    if salva:
        centroidi.to_csv(PERCORSO_POSIZIONI_ONG, index=False)

    # Le ONG del profilo mai viste restano al centro (nessun dato)
    mancanti = [n for n in PROFILI_ONG if n not in set(centroidi['nome'])]
    if mancanti:
        centroidi = pd.concat([centroidi, pd.DataFrame(
            [{'nome': n, 'score_tech_legale': 0, 'score_geografia': 0, 'numero_articoli': 0} for n in mancanti])],
            ignore_index=True)
    return df_notizie, centroidi


# --- NETWORK ONG <-> TEMI -----------------------------------------------------
STOPWORDS_MATCHING = {
    "del", "della", "dei", "delle", "dello", "degli", "per", "con", "che", "una", "uno",
    "gli", "nella", "nel", "nello", "sul", "sulla", "sui", "come", "loro", "questo",
    "questa", "sono", "essere", "anche", "alla", "alle", "agli", "and", "the", "of", "for",
}


def _parole_significative(testo) -> set:
    """Parole >3 caratteri, minuscole, senza stopword (matching keyword-overlap)."""
    if not testo:
        return set()
    parole = set()
    for token in str(testo).lower().replace(',', ' ').replace(';', ' ').split():
        token = token.strip('.,;:()[]"\'')
        if len(token) > 3 and token not in STOPWORDS_MATCHING:
            parole.add(token)
    return parole


def _termini_da_lista_serializzata(valore) -> set:
    termini = set()
    for frase in _lista_da_stringa(valore):
        termini |= _parole_significative(frase)
    return termini


_SINONIMI_TEMA = {
    'intelligenza artificiale': 'Intelligenza Artificiale', 'ia': 'Intelligenza Artificiale',
    'ai': 'Intelligenza Artificiale', 'artificial intelligence': 'Intelligenza Artificiale',
    'crittografia': 'Crittografia', 'criptografia': 'Crittografia',
}


def _normalizza_tema(tema: str) -> str:
    low = tema.strip().lower()
    for sin, standard in _SINONIMI_TEMA.items():
        if sin in low or low == sin:
            return standard
    return tema.strip().title()


def correzioni_ong_manuali() -> dict:
    """titolo -> ONG corretta (tipo_correzione 'ong_collegata'); l'ultima vince."""
    df = load_feedback(PERCORSO_FEEDBACK)
    out: dict = {}
    if df.empty:
        return out
    for _, r in df[df['tipo_correzione'] == 'ong_collegata'].iterrows():
        t, o = str(r.get('titolo', '')).strip(), str(r.get('ong_collegata_corretta', '')).strip()
        if t and o:
            out[t] = o
    return out


GRUPPI_GRAFO = {
    'ONG': ('#5a4a8a', 'ONG'),
    'Tema': ('#1d5a7a', 'Temi / argomenti'),
    'Notizia': ('#2f6f5b', 'Notizie pubblicate dalle ONG'),
    'NotiziaGenerale': ('#9aa3ab', 'Notizie da altre fonti (per overlap di parole chiave)'),
}


def costruisci_grafo(df_ong: pd.DataFrame, fonti_generaliste: dict[str, pd.DataFrame],
                     profilo_keywords: dict, correzioni: dict, giorni: int = 30):
    """Grafo ONG -> Temi -> Notizie. Notizie ONG agganciate al publisher (ground
    truth), con override delle correzioni manuali; notizie di altre fonti agganciate
    al tema con più overlap lessicale (nessun aggancio forzato sotto soglia)."""
    import networkx as nx
    from datetime import timedelta
    from nlp.entity_linking import link_ong

    G = nx.Graph()
    c_ong, c_tema, c_notizia, c_generale = (GRUPPI_GRAFO[k][0] for k in
                                             ('ONG', 'Tema', 'Notizia', 'NotiziaGenerale'))
    tema_keywords: dict = {}
    for nome_ong, dati_ong in PROFILI_ONG.items():
        G.add_node(nome_ong, color=c_ong, size=25, group='ONG',
                   title=f"{nome_ong}\n{dati_ong['descrizione'][:120]}...")
        for tema in dati_ong.get('focus', []):
            tn = _normalizza_tema(tema)
            if tn not in G:
                G.add_node(tn, color=c_tema, size=15, group='Tema')
            G.add_edge(nome_ong, tn, value=1, title="Focus principale")
            tema_keywords.setdefault(tn, set())
            tema_keywords[tn] |= _parole_significative(tema) | _parole_significative(tn)

    profili_arricchiti = {n: {**d, 'focus': list(d.get('focus', [])) + profilo_keywords.get(n, [])}
                          for n, d in PROFILI_ONG.items()}
    soglia = datetime.now().date() - timedelta(days=giorni)

    df = df_ong.copy()
    df['data_pubblicazione'] = pd.to_datetime(df['data_pubblicazione'], errors='coerce',
                                              format='mixed', utc=True).dt.date
    df['livello_allarme'] = pd.to_numeric(df['livello_allarme'], errors='coerce').fillna(1)
    for _, n in df[(df['data_pubblicazione'] >= soglia) | (df['livello_allarme'] >= 3)].iterrows():
        titolo = str(n['titolo'])[:50] + "..."
        ancora = correzioni.get(str(n['titolo']).strip())
        ancora = ancora if ancora in G else None
        if ancora is None:
            pub = str(n.get('nome_organizzazione', '')).strip()
            ancora = pub if pub in G else None
        if ancora is None:
            testo = (str(n['titolo']) + " " + str(n.get('testo_completo', ''))).lower()
            cand, _ = link_ong(testo, profili_arricchiti, return_score=True)
            ancora = cand if cand in G else None
        if ancora is not None:
            G.add_node(titolo, color=c_notizia, size=8, group='Notizia', shape='diamond')
            G.add_edge(ancora, titolo, value=0.5, title=f"Pubblicato da {ancora}")

    for etichetta, df_f in fonti_generaliste.items():
        if df_f.empty or 'titolo' not in df_f.columns:
            continue
        df_f = df_f.copy()
        df_f['data_pubblicazione'] = pd.to_datetime(df_f.get('data_pubblicazione'), errors='coerce',
                                                    format='mixed', utc=True).dt.date
        df_f['livello_allarme'] = pd.to_numeric(df_f.get('livello_allarme', 1), errors='coerce').fillna(1)
        for _, n in df_f[(df_f['data_pubblicazione'] >= soglia) | (df_f['livello_allarme'] >= 3)].iterrows():
            titolo_raw = str(n.get('titolo', '')).strip()
            if not titolo_raw:
                continue
            termini = (_parole_significative(n.get('titolo', ''))
                       | _termini_da_lista_serializzata(n.get('Parole_Chiave'))
                       | _termini_da_lista_serializzata(n.get('Entita_Coinvolte')))
            migliore, punteggio = None, 0
            for tn, parole in tema_keywords.items():
                s = len(termini & parole)
                if s > punteggio:
                    migliore, punteggio = tn, s
            if migliore is None or punteggio < 1:
                continue
            nodo = titolo_raw[:50] + "..."
            if nodo not in G:
                G.add_node(nodo, color=c_generale, size=8, group='NotiziaGenerale', shape='diamond',
                           title=f"{etichetta}\n{titolo_raw}")
            G.add_edge(migliore, nodo, value=0.5, color=c_generale,
                       title=f"{etichetta} · overlap={punteggio} parole")
    return G


def statistiche_grafo(G) -> dict:
    gruppi = [d.get('group') for _, d in G.nodes(data=True)]
    return {'ONG': gruppi.count('ONG'), 'Tema': gruppi.count('Tema'),
            'Notizia': gruppi.count('Notizia'), 'NotiziaGenerale': gruppi.count('NotiziaGenerale'),
            'archi': G.number_of_edges()}


def data_aggiornamento() -> datetime | None:
    """Ultima modifica dei CSV processati: la 'data dei dati' mostrata nel masthead."""
    import glob
    file = glob.glob(os.path.join(CARTELLA_PROCESSED, '*_analyzed.csv'))
    return datetime.fromtimestamp(max(os.path.getmtime(f) for f in file)) if file else None


def ong_come_unificato(df_ong: pd.DataFrame) -> pd.DataFrame:
    """Documenti ONG (compresi quelli inseriti a mano) nel formato della vista
    unificata, per le schede documento della scheda Campagne ONG."""
    if df_ong.empty:
        return pd.DataFrame(columns=COLONNE_UNIFICATE)
    righe = [_riga_unificata(r, str(r.get('nome_organizzazione', 'Organizzazione')), 'Comunicato ONG',
                             'Società civile', 'ONG', str(r.get('nome_organizzazione', '')))
             for _, r in df_ong.iterrows()]
    df = pd.DataFrame(righe)
    df['data'] = pd.to_datetime(df['data'], errors='coerce', format='mixed', utc=True).dt.date
    return df
