"""
Layer di SCOPERTA dei temi (BERTopic) — complementare al matcher a lessico.

theme_matching.py TRACCIA i temi che conosci (temi.csv). Questo modulo SCOPRE
cluster tematici emergenti che NON sono nel lessico, così puoi accorgerti di
argomenti nuovi e, se rilevanti, promuoverli in temi.csv.

Natura ESPLORATIVA (regola CLAUDE.md "separate facts from inferred
classifications"): i cluster BERTopic sono statistici e possono cambiare tra run
(UMAP/HDBSCAN). Per questo:
  - gira OFFLINE/periodicamente, NON a ogni run della pipeline;
  - produce artefatti CSV (data/processed/topic_emergenti*.csv) che la dashboard
    mostra in una vista dedicata, etichettata come scoperta, distinta dai trend
    affidabili del lessico curato;
  - UMAP con random_state fisso per ridurre (non azzerare) la deriva tra run;
  - riusa lo stesso sentence-transformer multilingue della pipeline (nessun
    modello/dipendenza extra a runtime) e le stopword IT/EN già curate.

Uso:
    python nlp/topic_discovery.py                 # tutte le fonti processate
    python nlp/topic_discovery.py --min-topic 8   # cluster minimo più piccolo
"""
import os
import sys
import argparse

import pandas as pd

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from utils.logger_config import setup_logger
from nlp.deduplication import get_embedding_model

logger = setup_logger(__name__)

_DIR_PROCESSED = os.path.join(_ROOT, 'data', 'processed')
REPORT_TOPIC = os.path.join(_DIR_PROCESSED, 'topic_emergenti.csv')
REPORT_TREND = os.path.join(_DIR_PROCESSED, 'topic_emergenti_trend.csv')

MIN_TOPIC_SIZE = 8    # documenti minimi per formare un cluster (HDBSCAN)
SEED = 42             # riproducibilità UMAP
_N_PAROLE = 8
_N_ESEMPI = 3

# Residui HTML/RSS che sporcano SOLO le etichette dei topic (non sono contenuto):
# 'ecl'/'icon'/'cnt' = classi CSS Europa Component Library (EDRi), 'noreferrer'/
# 'noopener'/'rel' = attributi dei link, 'proviene'/'articolo' = footer RSS
# ("l'articolo X proviene da Y"). Esclusi qui, non nel TF-IDF globale.
_JUNK_TOPIC = {'ecl', 'icon', 'cnt', 'rel', 'noreferrer', 'noopener', 'lang',
               'proviene', 'articolo', 'https', 'http', 'www'}


def _carica_documenti() -> pd.DataFrame:
    """Raccoglie (testo, titolo, fonte, data) da tutti i *_analyzed.csv."""
    righe = []
    for nome in sorted(os.listdir(_DIR_PROCESSED)):
        if not nome.endswith('_analyzed.csv'):
            continue
        df = pd.read_csv(os.path.join(_DIR_PROCESSED, nome))
        if 'testo_completo' not in df.columns:
            continue
        fonte = nome.replace('_analyzed.csv', '')
        for _, r in df.iterrows():
            testo = f"{r.get('titolo', '')} {r.get('testo_completo', '')}".strip()
            if len(testo) < 20:
                continue
            righe.append({
                'testo': testo,
                'titolo': str(r.get('titolo', ''))[:120],
                'fonte': fonte,
                'data': r.get('data_pubblicazione', r.get('Data', r.get('data', ''))),
            })
    return pd.DataFrame(righe)


def _costruisci_modello(min_topic_size: int, seed: int):
    """BERTopic configurato: nostro embedder condiviso, stopword curate, UMAP riproducibile."""
    from bertopic import BERTopic
    from umap import UMAP
    from hdbscan import HDBSCAN
    from sklearn.feature_extraction.text import CountVectorizer
    from nlp.text_analysis import STOPWORD_IT_EN  # import lazy: evita import circolare

    # n_neighbors basso = struttura più locale; 'leaf' = cluster più fini. Con i
    # default di BERTopic (n_neighbors=15, 'eom') un corpus omogeneo come questo
    # ("diritti digitali") collassa in un unico mega-topic: leaf lo scompone nei
    # suoi sotto-temi (AI, sorveglianza, cyber, minori...).
    umap_model = UMAP(n_neighbors=10, n_components=5, min_dist=0.0,
                      metric='cosine', random_state=seed)
    hdbscan_model = HDBSCAN(min_cluster_size=min_topic_size, metric='euclidean',
                            cluster_selection_method='leaf', prediction_data=True)
    # Le etichette dei topic vengono dalle parole distintive (c-TF-IDF): puliamole
    # con le stesse stopword/junk del TF-IDF principale, altrimenti emergono "span"/"org".
    vectorizer = CountVectorizer(stop_words=list(STOPWORD_IT_EN | _JUNK_TOPIC), min_df=2,
                                 ngram_range=(1, 2), token_pattern=r"(?u)\b[a-zà-ÿ]{3,}\b")
    return BERTopic(
        embedding_model=get_embedding_model(),
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer,
        calculate_probabilities=False,
        verbose=False,
    )


def scopri_topic(docs: list[str], min_topic_size: int = MIN_TOPIC_SIZE, seed: int = SEED):
    """Fitta BERTopic sui documenti. Ritorna (model, topics_per_doc)."""
    model = _costruisci_modello(min_topic_size, seed)
    topics, _ = model.fit_transform(docs)
    n_topic = len({t for t in topics if t != -1})
    n_outlier = sum(1 for t in topics if t == -1)
    logger.info("BERTopic: %d topic scoperti, %d documenti outlier su %d",
                n_topic, n_outlier, len(docs))
    return model, topics


def costruisci_report(model, topics, titoli, fonti) -> pd.DataFrame:
    """Un topic per riga: dimensione, parole distintive, titoli d'esempio, fonti."""
    righe = []
    for tid in sorted({t for t in topics if t != -1}):
        parole = [w for w, _ in (model.get_topic(tid) or [])][:_N_PAROLE]
        idx = [i for i, t in enumerate(topics) if t == tid]
        esempi = [titoli[i] for i in idx[:_N_ESEMPI]]
        fonti_topic = sorted({fonti[i] for i in idx})
        righe.append({
            'topic_id': tid,
            'dimensione': len(idx),
            'parole_chiave': ', '.join(parole),
            'titoli_esempio': ' | '.join(esempi),
            'fonti': ', '.join(fonti_topic),
        })
    return pd.DataFrame(righe).sort_values('dimensione', ascending=False)


def costruisci_trend(topics, date) -> pd.DataFrame:
    """Conteggio mensile per topic (per il grafico temporale della vista)."""
    df = pd.DataFrame({'topic_id': topics, 'ts': date})
    df['ts'] = pd.to_datetime(df['ts'], errors='coerce', utc=True, format='mixed')
    df = df[(df['topic_id'] != -1) & df['ts'].notna()].copy()
    if df.empty:
        return pd.DataFrame(columns=['topic_id', 'mese', 'conteggio'])
    df['mese'] = df['ts'].dt.to_period('M').astype(str)
    return (df.groupby(['topic_id', 'mese']).size()
              .reset_index(name='conteggio').sort_values('mese'))


def main():
    ap = argparse.ArgumentParser(description="Scoperta topic emergenti (BERTopic)")
    ap.add_argument('--min-topic', type=int, default=MIN_TOPIC_SIZE,
                    help="documenti minimi per formare un cluster")
    args = ap.parse_args()

    docs_df = _carica_documenti()
    if len(docs_df) < args.min_topic * 2:
        logger.warning("Solo %d documenti: troppo pochi per una scoperta affidabile "
                       "(BERTopic ha bisogno di volume). Esco.", len(docs_df))
        return

    logger.info("Scoperta topic su %d documenti (min_topic_size=%d)...",
                len(docs_df), args.min_topic)
    model, topics = scopri_topic(docs_df['testo'].tolist(), args.min_topic)

    report = costruisci_report(model, topics, docs_df['titolo'].tolist(),
                               docs_df['fonte'].tolist())
    trend = costruisci_trend(topics, docs_df['data'].tolist())

    report.to_csv(REPORT_TOPIC, index=False)
    trend.to_csv(REPORT_TREND, index=False)
    logger.info("Report salvati: %s (%d topic) | %s",
                REPORT_TOPIC, len(report), REPORT_TREND)
    print(f"\nTopic emergenti scoperti: {len(report)}")
    for _, r in report.head(12).iterrows():
        print(f"  #{r['topic_id']:>2} ({r['dimensione']:>3} doc)  {r['parole_chiave']}")


if __name__ == "__main__":
    main()
