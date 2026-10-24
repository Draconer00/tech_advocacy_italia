"""
Calibrazione e valutazione del rilevamento temi ibrido (nlp/theme_matching.py).

A cosa serve
------------
Il match semantico ha una sola manopola: la soglia di similarità coseno. Questo
script la calibra e misura quanto la componente semantica aggiunge rispetto al
solo lessicale, su dati REALI (i CSV già processati). Non tocca nulla: legge e
riporta soltanto.

Uso
---
    python nlp/valuta_temi.py                       # sweep soglie, tutte le fonti
    python nlp/valuta_temi.py --fonte tech_news     # una sola fonte processata
    python nlp/valuta_temi.py --soglia 0.45 --esempi 6   # esempi solo-semantici
    python nlp/valuta_temi.py --gold data/utils/temi_gold.csv  # precision/recall

Cosa guardare
-------------
1) SWEEP: per varie soglie, quanti documenti in più (rispetto al solo lessicale)
   vengono agganciati a ciascun tema dal segnale semantico. Se calando la soglia
   i "nuovi" esplodono di colpo, sei sceso sotto il rumore = falsi positivi.
2) ESEMPI: i titoli dei match SOLO-semantici a una soglia. Leggendoli giudichi
   a occhio la PRECISIONE (sono davvero pertinenti?) e il guadagno di RECALL
   (il lessicale li perdeva davvero?). È la verifica più onesta senza gold set.
3) GOLD (opzionale): con un file etichettato a mano (id_documento, temi separati
   da '|', 'NESSUNO' se non tratta alcun tema, vuoto = non ancora etichettato) calcola precision/recall/F1 per soglia, per scegliere in modo oggettivo.
"""
import os
import sys
import argparse
from collections import defaultdict

import pandas as pd

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# stdout UTF-8 su Windows (evita UnicodeEncodeError sui titoli accentati)
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from nlp.theme_matching import (carica_temi, carica_soglie, carica_gerarchia, macro_temi,
                                temi_lessicali, matrice_similarita,
                                SOGLIA_SEMANTICA as SOGLIA_DEFAULT)
from nlp.deduplication import get_embedding_model

_DIR_PROCESSED = os.path.join(_ROOT, 'data', 'processed')
_SOGLIE_DEFAULT = [0.35, 0.40, 0.45, 0.50, 0.55, 0.60]


def _carica_documenti(fonte: str | None) -> pd.DataFrame:
    """Raccoglie (id, titolo, testo) dai *_analyzed.csv processati."""
    righe = []
    for nome in sorted(os.listdir(_DIR_PROCESSED)):
        if not nome.endswith('_analyzed.csv'):
            continue
        if fonte and fonte not in nome:
            continue
        df = pd.read_csv(os.path.join(_DIR_PROCESSED, nome))
        if 'testo_completo' not in df.columns:
            continue
        for _, r in df.iterrows():
            # STESSO input della pipeline (processa_dataframe rileva i temi su
            # testo_completo, già ripulito): si valuta il sistema reale, non una
            # variante con il titolo aggiunto.
            testo = str(r.get('testo_completo', '')) if pd.notna(r.get('testo_completo')) else ''
            if not testo.strip():
                continue
            righe.append({
                'id': _id_documento(r),
                'titolo': str(r.get('titolo', ''))[:110],
                'fonte': nome.replace('_analyzed.csv', ''),
                'testo': testo,
            })
    return pd.DataFrame(righe)


def _id_documento(row) -> str:
    """Id stabile del documento: id_univoco, con fallback a hash_contenuto quando
    è mancante/NaN (alcune righe rss_eu lo hanno vuoto). Evita che più documenti
    collassino sulla stessa chiave 'nan' — critico per allineare il gold set."""
    for col in ('id_univoco', 'hash_contenuto'):
        val = row.get(col)
        if pd.notna(val) and str(val).strip() not in ('', 'nan'):
            return str(val).strip()
    return ''


def _temi_semantici(sim_riga, etichette, soglia) -> set[str]:
    """Temi con almeno un termine-seme sopra soglia per questo documento."""
    return {etichette[j][0] for j, s in enumerate(sim_riga) if s >= soglia}


def sweep(docs, temi, etichette, sim, soglie):
    """Per ogni soglia: nuovi match SOLO-semantici per tema (non già lessicali)."""
    lex = [set(temi_lessicali(d, temi)) for d in docs]
    print("\n=== SWEEP SOGLIE — nuovi documenti solo-semantici per tema ===")
    print("(quanti doc ogni soglia AGGIUNGE oltre al match lessicale esatto)\n")
    intestazione = "tema".ljust(28) + "esatto".rjust(8) + "".join(f"τ={s:.2f}".rjust(9) for s in soglie)
    print(intestazione)
    print("-" * len(intestazione))
    for tema in temi:
        n_esatti = sum(1 for L in lex if tema in L)
        celle = [tema.ljust(28), str(n_esatti).rjust(8)]
        for s in soglie:
            nuovi = 0
            for i in range(len(docs)):
                if tema in lex[i]:
                    continue
                if tema in _temi_semantici(sim[i], etichette, s):
                    nuovi += 1
            celle.append(f"+{nuovi}".rjust(9))
        print("".join(celle))
    print("\nLettura: la colonna 'esatto' è la baseline. I '+N' sono il RECALL "
          "aggiunto dal semantico. Scegli la soglia più bassa a cui gli esempi "
          "(--esempi) restano pertinenti.")


def config_attuale(docs, temi, etichette, sim, soglie_map):
    """Soglia configurata per ogni tema (temi.csv) e recall semantico che produce."""
    lex = [set(temi_lessicali(d, temi)) for d in docs]
    print("\n=== CONFIG ATTUALE — soglia per-tema (colonna 'soglia' di temi.csv) ===\n")
    print("tema".ljust(28) + "soglia".rjust(8) + "esatto".rjust(9) + "+semantico".rjust(12))
    print("-" * 57)
    for tema in temi:
        s = soglie_map.get(tema, 0.50)
        n_es = sum(1 for L in lex if tema in L)
        nuovi = sum(1 for i in range(len(docs)) if tema not in lex[i]
                    and any(sim[i][j] >= s for j in range(len(etichette)) if etichette[j][0] == tema))
        print(tema.ljust(28) + f"{s:.2f}".rjust(8) + str(n_es).rjust(9) + f"+{nuovi}".rjust(12))


def esempi(docs, titoli, fonti, temi, etichette, sim, soglie_map, n):
    """Titoli dei match solo-semantici, ognuno alla soglia del proprio tema:
    giudizio di precisione a occhio."""
    lex = [set(temi_lessicali(d, temi)) for d in docs]
    print(f"\n=== ESEMPI SOLO-SEMANTICI (soglia per-tema, max {n} per tema) ===\n")
    for tema in temi:
        soglia = soglie_map.get(tema, 0.50)
        trovati = []
        for i in range(len(docs)):
            if tema in lex[i]:
                continue
            semantici = {etichette[j]: sim[i][j] for j in range(len(etichette))
                         if etichette[j][0] == tema and sim[i][j] >= soglia}
            if semantici:
                (_, seme), punteggio = max(semantici.items(), key=lambda kv: kv[1])
                trovati.append((punteggio, seme, titoli[i], fonti[i]))
        if not trovati:
            continue
        trovati.sort(reverse=True)
        print(f"▸ {tema}  (τ={soglia:.2f})")
        for punteggio, seme, titolo, fonte in trovati[:n]:
            print(f"   {punteggio:.2f}  [~{seme}]  ({fonte})  {titolo}")
        print()


NESSUN_TEMA = 'NESSUNO'   # etichetta esplicita: "letto, non tratta alcun tema"


def carica_gold(percorso_gold, temi) -> dict[str, set[str]]:
    """Legge le etichette manuali: {id_documento: set(temi)}.

    Cella vuota = NON ancora etichettato (escluso dalla valutazione);
    'NESSUNO' = etichettato senza temi (negativo, serve a misurare i falsi
    positivi). Una riga con un nome di tema sconosciuto (refuso) viene ESCLUSA e
    segnalata: interpretarla falserebbe la misura.
    """
    gold = pd.read_csv(percorso_gold, dtype=str, keep_default_na=False)
    atteso, scartate = {}, []
    for _, r in gold.iterrows():
        cella = r.get('temi', '').strip()
        if not cella:
            continue
        valori = {t.strip() for t in cella.split('|') if t.strip()}
        if valori == {NESSUN_TEMA}:
            valori = set()
        ignoti = valori - set(temi)
        if ignoti:
            scartate.append((r['id_documento'][:12], sorted(ignoti)))
            continue
        atteso[r['id_documento'].strip()] = valori
    if scartate:
        print(f"\n[gold] ATTENZIONE: {len(scartate)} righe escluse per nomi di tema "
              f"non presenti in temi.csv (correggile nel foglio):")
        for rid, nomi in scartate:
            print(f"   id {rid}…  {nomi}")
    return atteso


_SOLO_ESATTO = 2.0   # soglia irraggiungibile (coseno <= 1): disattiva il semantico


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    """Precision, recall, F1 da conteggi. 0 quando il denominatore è nullo."""
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f1


def _conteggi(pred_per_doc, veri_per_doc, universo) -> dict[str, list[int]]:
    """TP/FP/FN per tema, sulle coppie (documento, tema): multi-etichetta, ogni
    tema è una decisione sì/no indipendente per ogni documento."""
    c = {t: [0, 0, 0] for t in universo}
    for pred, veri in zip(pred_per_doc, veri_per_doc):
        for t in pred & veri:
            c[t][0] += 1
        for t in pred - veri:
            c[t][1] += 1
        for t in veri - pred:
            c[t][2] += 1
    return c


def _riassunto(pred_per_doc, veri_per_doc, universo) -> dict[str, float]:
    """Micro, macro ed exact match di una configurazione."""
    c = _conteggi(pred_per_doc, veri_per_doc, universo)
    micro = _prf(*[sum(v[k] for v in c.values()) for k in range(3)])
    # Macro: media sui temi valutabili (almeno un positivo nel gold o una previsione)
    per_tema = [_prf(*v) for v in c.values() if v[0] + v[1] + v[2] > 0]
    macro = tuple(sum(x[k] for x in per_tema) / len(per_tema) for k in range(3)) if per_tema else (0, 0, 0)
    esatti = sum(1 for p, v in zip(pred_per_doc, veri_per_doc) if p == v) / len(veri_per_doc)
    return {'micro': micro, 'macro': macro, 'exact': esatti}


def valuta_gold(docs_df, temi, etichette, sim, percorso_gold, soglie, soglie_map):
    """Valuta il rilevamento temi contro le etichette manuali del gold set.

    Stampa: (1) configurazione in produzione (soglie per-tema di temi.csv) vs
    baseline solo-lessicale, in micro/macro/exact match; (2) dettaglio per tema;
    (3) sweep con soglia globale; (4) soglia migliore per singolo tema.
    """
    atteso = carica_gold(percorso_gold, temi)
    assenti = set(atteso) - set(docs_df['id'])
    if assenti:
        # Tipicamente: la deduplica semantica ora sceglie un altro rappresentante
        # del cluster, quindi il documento non è più nel layer processato.
        print(f"\n[gold] {len(assenti)} documenti etichettati non sono più nei dati "
              f"processati (es. rimossi dalla deduplica): esclusi dalla valutazione.")
    # Un id per documento: lo stesso contenuto in due fonti ha lo stesso hash e
    # verrebbe contato due volte.
    visti, idx_gold = set(), []
    for i, rid in enumerate(docs_df['id']):
        if rid in atteso and rid not in visti:
            visti.add(rid)
            idx_gold.append(i)
    if not idx_gold:
        print(f"\n[gold] Nessun id in comune tra {percorso_gold} e i documenti processati.")
        return

    testi = docs_df['testo'].tolist()
    lex = {i: set(temi_lessicali(testi[i], temi)) for i in idx_gold}
    # Stessa regola della pipeline: un sotto-tema implica il padre. Si valutano
    # solo i temi che il gold può giudicare (macro-temi + quelli usati nelle
    # etichette): un sotto-tema mai etichettato non è un falso positivo.
    padre_di = carica_gerarchia()
    universo = set(macro_temi()) | {t for v in atteso.values() for t in v}
    veri = [atteso[docs_df['id'].iloc[i]] for i in idx_gold]

    def predici(soglia_di: dict[str, float]) -> list[set[str]]:
        out = []
        for i in idx_gold:
            pred = lex[i] | {etichette[j][0] for j, s in enumerate(sim[i])
                             if s >= soglia_di.get(etichette[j][0], SOGLIA_DEFAULT)}
            out.append((pred | {padre_di[t] for t in pred if t in padre_di}) & universo)
        return out

    n_neg = sum(1 for v in veri if not v)
    print(f"\n=== GOLD — {len(idx_gold)} documenti etichettati "
          f"({n_neg} senza temi, {sum(len(v) for v in veri)} coppie documento-tema positive) ===")

    # (1) produzione vs baseline
    configurazioni = {
        'Solo lessicale (baseline)': {t: _SOLO_ESATTO for t in temi},
        'Ibrido, soglie per-tema (produzione)': {t: soglie_map.get(t, SOGLIA_DEFAULT) for t in temi},
    }
    print("\n(1) Configurazioni a confronto\n")
    print("configurazione".ljust(38) + "micro P   micro R  micro F1 | macro P   macro R  macro F1 | exact")
    pred_prod = None
    for nome, soglia_di in configurazioni.items():
        pred = predici(soglia_di)
        if 'produzione' in nome:
            pred_prod = pred
        r = _riassunto(pred, veri, universo)
        print(nome.ljust(38) + "  ".join(f"{x:7.3f}" for x in r['micro']) + " | " +
              "  ".join(f"{x:7.3f}" for x in r['macro']) + f" | {r['exact']:5.3f}")

    # (2) dettaglio per tema, configurazione in produzione
    print("\n(2) Per tema — configurazione in produzione\n")
    print("tema".ljust(28) + "soglia  gold  prev    TP   FP   FN   precision  recall    F1")
    c = _conteggi(pred_prod, veri, universo)
    for t in sorted(c, key=lambda t: -(c[t][0] + c[t][2])):
        tp, fp, fn = c[t]
        p, r, f1 = _prf(tp, fp, fn)
        print(t.ljust(28) + f"{soglie_map.get(t, SOGLIA_DEFAULT):5.2f}" +
              f"{tp + fn:6}{tp + fp:6}{tp:6}{fp:5}{fn:5}   {p:8.3f}  {r:7.3f}  {f1:6.3f}")

    # (3) sweep con soglia globale unica (micro)
    print("\n(3) Soglia globale unica (stessa per tutti i temi) — micro\n")
    print("soglia   precision   recall     F1")
    for s in soglie:
        p, r, f1 = _riassunto(predici({t: s for t in temi}), veri, universo)['micro']
        print(f"{s:.2f}     {p:8.3f}   {r:7.3f}   {f1:6.3f}")

    # (4) soglia migliore per singolo tema: le metriche di un tema dipendono solo
    # dalla sua soglia, quindi si ottimizzano indipendentemente.
    print("\n(4) Soglia con F1 migliore per tema (indicativa: pochi esempi per tema)\n")
    candidati = [_SOLO_ESATTO] + list(soglie)
    per_soglia = {s: _conteggi(predici({t: s for t in temi}), veri, universo) for s in candidati}
    print("tema".ljust(28) + "attuale  F1 att. | migliore  F1 migl.  (gold)")
    for t in sorted(universo & set(temi)):
        att = soglie_map.get(t, SOGLIA_DEFAULT)
        conteggi_t = {s: per_soglia[s][t] for s in candidati}
        conteggi_t[att] = c[t]            # la soglia attuale è sempre tra i candidati
        f1_di = {s: _prf(*v)[2] for s, v in conteggi_t.items()}
        # a parità di F1 si preferisce la soglia più alta (più precisa, più prudente)
        migliore = max(f1_di, key=lambda s: (round(f1_di[s], 3), s))
        etich = 'esatto' if migliore == _SOLO_ESATTO else f"{migliore:.2f}"
        print(t.ljust(28) + f"{att:6.2f}  {f1_di[att]:7.3f} | {etich:>8}  {f1_di[migliore]:7.3f}  "
              f"({c[t][0] + c[t][2]})")


def main():
    ap = argparse.ArgumentParser(description="Calibrazione rilevamento temi ibrido")
    ap.add_argument('--fonte', help="filtra i CSV processati per sottostringa (es. tech_news)")
    ap.add_argument('--soglia', type=float, default=None,
                    help="override globale della soglia per --esempi (default: per-tema da temi.csv)")
    ap.add_argument('--esempi', type=int, default=0, help="quanti esempi solo-semantici per tema")
    ap.add_argument('--gold', help="CSV etichettato (id_documento, temi) per precision/recall")
    args = ap.parse_args()

    docs_df = _carica_documenti(args.fonte)
    if docs_df.empty:
        print("Nessun documento processato trovato. Esegui prima nlp/text_analysis.py.")
        return
    temi = carica_temi()
    print(f"Documenti: {len(docs_df)} | Temi: {len(temi)} | calcolo embedding...")

    etichette, sim = matrice_similarita(docs_df['testo'].tolist(), temi, get_embedding_model())

    # Soglia per-tema configurata in temi.csv; --soglia la sovrascrive (esplorazione).
    soglie_map = carica_soglie()
    if args.soglia is not None:
        soglie_map = {t: args.soglia for t in temi}

    sweep(docs_df['testo'].tolist(), temi, etichette, sim, _SOGLIE_DEFAULT)
    config_attuale(docs_df['testo'].tolist(), temi, etichette, sim, soglie_map)
    if args.esempi:
        esempi(docs_df['testo'].tolist(), docs_df['titolo'].tolist(),
               docs_df['fonte'].tolist(), temi, etichette, sim, soglie_map, args.esempi)
    if args.gold and os.path.exists(args.gold):
        valuta_gold(docs_df, temi, etichette, sim, args.gold, _SOGLIE_DEFAULT, soglie_map)


if __name__ == "__main__":
    main()
