"""
Rilevamento dei temi tech/diritti digitali su ogni documento: approccio IBRIDO.

Due segnali, tracciati separatamente per restare spiegabili (regole CLAUDE.md
"explainability over complexity" e "separate facts from inferred classifications"):

  - ESATTO    : match lessicale di sottostringa contro il lessico curato
                data/utils/temi.csv. Alta precisione, deterministico. È il
                segnale di cui ci si fida.
  - SEMANTICO : similarità coseno fra l'embedding del documento e quello dei
                termini-seme del tema (stesso modello multilingue della
                deduplica). Recupera sinonimi, parafrasi e altre lingue che il
                match letterale non vede — al prezzo di una soglia da calibrare,
                quindi è un segnale AGGIUNTIVO, non sostitutivo.

Il lessico curato resta la fonte di verità: i termini-seme definiscono i temi;
l'embedding estende soltanto il raggio d'azione attorno a quei semi. Un tema che
matcha in entrambi i modi viene riportato una sola volta come 'esatto'.
"""
import os
import sys
import json

import numpy as np
import pandas as pd

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from utils.logger_config import setup_logger

logger = setup_logger(__name__)

_PERCORSO_TEMI = os.path.join(_ROOT, 'data', 'utils', 'temi.csv')

# Soglia di similarità coseno per il match semantico. Va CALIBRATO sui dati reali
# (vedi nlp/valuta_temi.py). Troppo bassa -> falsi positivi (tutto matcha tutto);
# troppo alta -> tornano i sinonimi persi.
# Calibrazione 2026-09-20 su 819 doc processati: sotto 0.45 le aggiunte esplodono
# (rumore); a 0.50 la maggior parte dei temi si assesta. I temi con semi astratti
# ("Diritti Digitali", "Cybersicurezza") restano sovra-aggreganti anche a 0.50 →
# candidati a semi più specifici o a una soglia per-tema (follow-up).
SOGLIA_SEMANTICA = 0.50

# Usato solo se temi.csv manca del tutto (non dovrebbe: il file è tracciato).
_TEMI_FALLBACK = {
    'Privacy e Dati': ['privacy', 'gdpr', 'dati personali'],
    'Intelligenza Artificiale': ['intelligenza artificiale', 'ai act', 'algoritm'],
    'Sorveglianza': ['sorveglian', 'telecamer', 'biometr'],
}

# Cache degli embedding dei termini-seme, per non ricalcolarli a ogni fonte.
# Chiave = contenuto del lessico, così un temi.csv modificato invalida la cache.
_cache_semi: dict = {}


def carica_temi(percorso: str = _PERCORSO_TEMI) -> dict[str, list[str]]:
    """Lessico curato dei temi (colonne: tema, termini separati da '|'), minuscolo."""
    temi: dict[str, list[str]] = {}
    if os.path.exists(percorso):
        df = pd.read_csv(percorso)
        for _, r in df.iterrows():
            nome = str(r.get('tema', '')).strip()
            termini = [t.strip().lower() for t in str(r.get('termini', '')).split('|') if t.strip()]
            if nome and termini:
                temi[nome] = termini
    return temi or dict(_TEMI_FALLBACK)


def carica_soglie(percorso: str = _PERCORSO_TEMI,
                  default: float = SOGLIA_SEMANTICA) -> dict[str, float]:
    """Soglia semantica PER-TEMA dalla colonna opzionale 'soglia' di temi.csv.
    Temi senza valore (o file senza la colonna) usano il default globale.
    I temi astratti (semi larghi) meritano soglie più alte per non sovra-aggregare."""
    soglie: dict[str, float] = {}
    if os.path.exists(percorso):
        df = pd.read_csv(percorso)
        ha_colonna = 'soglia' in df.columns
        for _, r in df.iterrows():
            nome = str(r.get('tema', '')).strip()
            if not nome:
                continue
            try:
                soglie[nome] = float(r['soglia']) if ha_colonna else default
            except (TypeError, ValueError):
                soglie[nome] = default
    return soglie


def _soglie_per_tema(soglie, temi: dict[str, list[str]]) -> dict[str, float]:
    """Normalizza l'argomento soglie in un dict tema->float che copre ogni tema.
    Accetta: None (legge temi.csv), un float (globale), o un dict parziale."""
    if isinstance(soglie, (int, float)):
        return {t: float(soglie) for t in temi}
    fonte = soglie if isinstance(soglie, dict) else carica_soglie()
    return {t: float(fonte.get(t, SOGLIA_SEMANTICA)) for t in temi}


def temi_lessicali(testo: str, temi: dict[str, list[str]]) -> dict[str, str]:
    """Temi il cui testo contiene almeno un termine-seme. Ritorna {tema: termine_trovato}."""
    t = str(testo or '').lower()
    trovati: dict[str, str] = {}
    for tema, termini in temi.items():
        for term in termini:
            if term in t:
                trovati[tema] = term
                break
    return trovati


def _prepara_semi(temi: dict[str, list[str]], model):
    """Embedding (normalizzati) di ogni termine-seme. Cache per lessico."""
    chiave = tuple(sorted((tema, tuple(termini)) for tema, termini in temi.items()))
    if chiave in _cache_semi:
        return _cache_semi[chiave]
    etichette: list[tuple[str, str]] = []  # (tema, termine)
    frasi: list[str] = []
    for tema, termini in temi.items():
        for term in termini:
            etichette.append((tema, term))
            frasi.append(term)
    emb = model.encode(frasi, show_progress_bar=False, batch_size=64,
                       normalize_embeddings=True)
    emb = np.asarray(emb, dtype=np.float32)
    _cache_semi[chiave] = (etichette, emb)
    logger.info("Termini-seme temi preparati: %d termini su %d temi", len(frasi), len(temi))
    return etichette, emb


def matrice_similarita(testi: list[str], temi: dict[str, list[str]], model) -> tuple:
    """Ritorna (etichette_semi, matrice_sim doc×seme) — coseno in [-1, 1].
    Esposto a parte così lo script di calibrazione riusa il calcolo pesante una
    volta sola per tutte le soglie."""
    etichette, semi_emb = _prepara_semi(temi, model)
    doc_emb = model.encode([str(t or '') for t in testi], show_progress_bar=False,
                           batch_size=32, normalize_embeddings=True)
    doc_emb = np.asarray(doc_emb, dtype=np.float32)
    return etichette, doc_emb @ semi_emb.T


def rileva_temi_batch(testi: list[str], temi: dict[str, list[str]], model,
                      soglie=None) -> list[list[dict]]:
    """Per ogni testo, la lista dei temi rilevati come dict
    {tema, metodo, score, seme}. 'esatto' ha priorità sul 'semantico'.

    soglie: None -> soglia per-tema da temi.csv (colonna 'soglia'); un float ->
    soglia globale unica; un dict tema->float -> override esplicito."""
    if not testi:
        return []
    etichette, sim = matrice_similarita(testi, temi, model)
    soglia_di = _soglie_per_tema(soglie, temi)

    risultati: list[list[dict]] = []
    for i, testo in enumerate(testi):
        per_tema: dict[str, dict] = {}
        # 1) lessicale (priorità: alta precisione, score pieno)
        for tema, seme in temi_lessicali(testo, temi).items():
            per_tema[tema] = {'tema': tema, 'metodo': 'esatto', 'score': 1.0, 'seme': seme}
        # 2) semantico (solo dove non c'è già un esatto; tiene il seme più vicino)
        riga = sim[i]
        for j, punteggio in enumerate(riga):
            tema, seme = etichette[j]
            if punteggio < soglia_di[tema]:  # soglia specifica del tema
                continue
            prec = per_tema.get(tema)
            if prec is not None and prec['metodo'] == 'esatto':
                continue
            if prec is None or punteggio > prec['score']:
                per_tema[tema] = {'tema': tema, 'metodo': 'semantico',
                                  'score': round(float(punteggio), 3), 'seme': seme}
        risultati.append(list(per_tema.values()))
    return risultati


def serializza(match_list: list[dict]) -> tuple[str, str]:
    """Da una lista di match a (temi_rilevati pipe-joined, temi_dettaglio JSON)."""
    nomi = '|'.join(m['tema'] for m in match_list)
    dettaglio = json.dumps(match_list, ensure_ascii=False)
    return nomi, dettaglio
