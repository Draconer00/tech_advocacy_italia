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
import shutil
from datetime import datetime

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


# ---------------------------------------------------------------------------
# REGISTRO DEI TEMI (data/utils/temi.csv)
# Due livelli: i MACRO-TEMI (padre vuoto) sono stabili e garantiscono serie
# storiche confrontabili; i SOTTO-TEMI (padre = un macro-tema) si aggiungono nel
# tempo, tipicamente promossi da un topic scoperto con BERTopic. Ogni riga porta
# la sua storia: stato, data di introduzione (dal) e origine (manuale/bertopic#N).
# ---------------------------------------------------------------------------
COLONNE_REGISTRO = ['tema', 'termini', 'soglia', 'padre', 'stato', 'dal', 'origine']
STATI = ('attivo', 'candidato', 'dismesso')   # solo 'attivo' viene rilevato
SOGLIA_SOTTOTEMA = 0.55   # default per i nuovi sotto-temi: semi più specifici e meno collaudati
_LUNGHEZZA_MIN_TERMINE = 3  # match per sottostringa: "ai" catturerebbe "mai", "dai"...


def carica_registro_temi(percorso: str = _PERCORSO_TEMI) -> pd.DataFrame:
    """Registro completo (tutti gli stati), con colonne normalizzate.
    Un temi.csv di vecchio formato (solo tema/termini/soglia) viene letto come
    8 macro-temi attivi."""
    if not os.path.exists(percorso):
        righe = [{'tema': t, 'termini': '|'.join(v)} for t, v in _TEMI_FALLBACK.items()]
        df = pd.DataFrame(righe)
    else:
        df = pd.read_csv(percorso, dtype=str, keep_default_na=False)
    for col, default in (('soglia', str(SOGLIA_SEMANTICA)), ('padre', ''), ('stato', 'attivo'),
                         ('dal', ''), ('origine', 'manuale')):
        if col not in df.columns:
            df[col] = default
    df = df[COLONNE_REGISTRO].copy()
    for col in COLONNE_REGISTRO:
        df[col] = df[col].fillna('').astype(str).str.strip()
    df['stato'] = df['stato'].replace('', 'attivo')
    df['soglia'] = pd.to_numeric(df['soglia'], errors='coerce').fillna(SOGLIA_SEMANTICA)
    return df[df['tema'] != ''].reset_index(drop=True)


def _termini(cella: str) -> list[str]:
    return [t.strip().lower() for t in str(cella).split('|') if t.strip()]


def carica_temi(percorso: str = _PERCORSO_TEMI) -> dict[str, list[str]]:
    """Temi ATTIVI (macro e sotto-temi) -> termini-seme minuscoli.
    È il lessico che la pipeline rileva; candidati e dismessi sono esclusi."""
    reg = carica_registro_temi(percorso)
    temi = {r['tema']: _termini(r['termini'])
            for _, r in reg[reg['stato'] == 'attivo'].iterrows() if _termini(r['termini'])}
    return temi or dict(_TEMI_FALLBACK)


def carica_soglie(percorso: str = _PERCORSO_TEMI,
                  default: float = SOGLIA_SEMANTICA) -> dict[str, float]:
    """Soglia semantica PER-TEMA dalla colonna 'soglia' di temi.csv.
    I temi astratti (semi larghi) meritano soglie più alte per non sovra-aggregare.
    Una soglia di 1.0 disattiva di fatto il match semantico (solo match esatto)."""
    if not os.path.exists(percorso):
        return {}
    reg = carica_registro_temi(percorso)
    return {r['tema']: float(r['soglia']) if pd.notna(r['soglia']) else default
            for _, r in reg.iterrows()}


def carica_gerarchia(percorso: str = _PERCORSO_TEMI) -> dict[str, str]:
    """{sotto-tema attivo: macro-tema padre}."""
    reg = carica_registro_temi(percorso)
    attivi = reg[(reg['stato'] == 'attivo') & (reg['padre'] != '')]
    return dict(zip(attivi['tema'], attivi['padre']))


def macro_temi(percorso: str = _PERCORSO_TEMI) -> list[str]:
    """Nomi dei macro-temi attivi (padre vuoto), nell'ordine del registro."""
    reg = carica_registro_temi(percorso)
    return reg[(reg['stato'] == 'attivo') & (reg['padre'] == '')]['tema'].tolist()


def valida_registro(df: pd.DataFrame) -> list[str]:
    """Errori bloccanti del registro (lista vuota = valido). Usata prima di ogni
    salvataggio, anche da dashboard: un registro malformato romperebbe il tagging."""
    errori: list[str] = []
    nomi = df['tema'].astype(str).str.strip()
    if (nomi == '').any():
        errori.append("C'è un tema senza nome.")
    dup = nomi[nomi.str.lower().duplicated()]
    if not dup.empty:
        errori.append(f"Nomi duplicati: {sorted(set(dup))}.")
    macro = set(df[(df['padre'] == '') & (df['stato'] == 'attivo')]['tema'])
    for _, r in df.iterrows():
        nome = str(r['tema']).strip()
        if '|' in nome:
            errori.append(f"'{nome}': il nome non può contenere '|'.")
        if r['stato'] not in STATI:
            errori.append(f"'{nome}': stato '{r['stato']}' non valido (ammessi: {', '.join(STATI)}).")
        termini = _termini(r['termini'])
        if not termini:
            errori.append(f"'{nome}': serve almeno un termine.")
        corti = [t for t in termini if len(t) < _LUNGHEZZA_MIN_TERMINE]
        if corti:
            errori.append(f"'{nome}': termini troppo corti per il match per sottostringa: {corti}.")
        try:
            s = float(r['soglia'])
            if not 0.30 <= s <= 1.0:
                raise ValueError
        except (TypeError, ValueError):
            errori.append(f"'{nome}': la soglia deve essere un numero tra 0.30 e 1.0.")
        padre = str(r['padre']).strip()
        if padre and r['stato'] == 'attivo' and padre not in macro:
            errori.append(f"'{nome}': il padre '{padre}' non è un macro-tema attivo "
                          "(ammessi solo due livelli).")
    return errori


def salva_registro_temi(df: pd.DataFrame, percorso: str = _PERCORSO_TEMI) -> str | None:
    """Valida e salva il registro, con backup timestampato del file precedente
    (stesso schema di utils/ong_profile.py). È configurazione curata, non un
    dataset: sovrascriverla è ammesso, perderne la storia no.
    Ritorna il percorso del backup; solleva ValueError se il registro non è valido."""
    df = df[COLONNE_REGISTRO].copy()
    for col in ('tema', 'padre', 'stato', 'dal', 'origine'):
        df[col] = df[col].fillna('').astype(str).str.strip()
    df['termini'] = df['termini'].apply(lambda c: '|'.join(_termini(c)))
    errori = valida_registro(df)
    if errori:
        raise ValueError('\n'.join(errori))
    df['soglia'] = df['soglia'].astype(float).map(lambda s: f"{s:.2f}")

    backup = None
    if os.path.exists(percorso):
        cartella_bk = os.path.join(os.path.dirname(percorso), 'backup_temi')
        os.makedirs(cartella_bk, exist_ok=True)
        backup = os.path.join(cartella_bk, f"temi_{datetime.now():%Y%m%d_%H%M%S}.csv")
        shutil.copy2(percorso, backup)
        logger.info("Backup registro temi: %s", backup)
    df.to_csv(percorso, index=False, encoding='utf-8')
    _cache_semi.clear()
    logger.info("Registro temi salvato: %d temi (%d attivi)",
                len(df), int((df['stato'] == 'attivo').sum()))
    return backup


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
                      soglie=None, gerarchia=None) -> list[list[dict]]:
    """Per ogni testo, la lista dei temi rilevati come dict
    {tema, metodo, score, seme}. 'esatto' ha priorità sul 'semantico'.

    soglie: None -> soglia per-tema da temi.csv (colonna 'soglia'); un float ->
    soglia globale unica; un dict tema->float -> override esplicito.
    gerarchia: None -> da temi.csv; {} -> nessuna. Un sotto-tema rilevato implica
    il suo macro-tema padre (metodo 'da_sottotema', seme = nome del sotto-tema),
    così i trend dei macro-temi restano completi e confrontabili nel tempo."""
    if not testi:
        return []
    etichette, sim = matrice_similarita(testi, temi, model)
    soglia_di = _soglie_per_tema(soglie, temi)
    padre_di = carica_gerarchia() if gerarchia is None else gerarchia

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
        # 3) propagazione sotto-tema -> macro-tema (solo se il padre non è già rilevato)
        for sotto, m in list(per_tema.items()):
            padre = padre_di.get(sotto)
            if padre and padre in temi and padre not in per_tema:
                per_tema[padre] = {'tema': padre, 'metodo': 'da_sottotema',
                                   'score': m['score'], 'seme': sotto}
        risultati.append(list(per_tema.values()))
    return risultati


def serializza(match_list: list[dict]) -> tuple[str, str]:
    """Da una lista di match a (temi_rilevati pipe-joined, temi_dettaglio JSON)."""
    nomi = '|'.join(m['tema'] for m in match_list)
    dettaglio = json.dumps(match_list, ensure_ascii=False)
    return nomi, dettaglio
