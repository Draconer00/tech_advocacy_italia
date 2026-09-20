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
   da '|') calcola precision/recall/F1 per soglia, per scegliere in modo oggettivo.
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

from nlp.theme_matching import carica_temi, carica_soglie, temi_lessicali, matrice_similarita
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
            testo = f"{r.get('titolo', '')} {r.get('testo_completo', '')}".strip()
            if not testo:
                continue
            righe.append({
                'id': str(r.get('id_univoco', r.get('hash_contenuto', ''))),
                'titolo': str(r.get('titolo', ''))[:110],
                'fonte': nome.replace('_analyzed.csv', ''),
                'testo': testo,
            })
    return pd.DataFrame(righe)


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


def valuta_gold(docs_df, temi, etichette, sim, percorso_gold, soglie):
    """Precision/Recall/F1 per soglia rispetto a etichette manuali."""
    gold = pd.read_csv(percorso_gold)
    atteso = {str(r['id_documento']): set(str(r['temi']).split('|'))
              for _, r in gold.iterrows() if str(r.get('temi', '')).strip()}
    idx_gold = [i for i, rid in enumerate(docs_df['id']) if rid in atteso]
    if not idx_gold:
        print(f"\n[gold] Nessun id in comune tra {percorso_gold} e i documenti processati.")
        return
    testi = docs_df['testo'].tolist()
    lex = [set(temi_lessicali(testi[i], temi)) for i in range(len(testi))]
    print(f"\n=== GOLD — precision/recall/F1 su {len(idx_gold)} documenti etichettati ===\n")
    print("soglia   precision   recall     F1")
    for s in soglie:
        tp = fp = fn = 0
        for i in idx_gold:
            pred = lex[i] | _temi_semantici(sim[i], etichette, s)
            veri = atteso[docs_df['id'].iloc[i]]
            tp += len(pred & veri)
            fp += len(pred - veri)
            fn += len(veri - pred)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        print(f"{s:.2f}     {prec:8.3f}   {rec:7.3f}   {f1:6.3f}")


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
        valuta_gold(docs_df, temi, etichette, sim, args.gold, _SOGLIE_DEFAULT)


if __name__ == "__main__":
    main()
