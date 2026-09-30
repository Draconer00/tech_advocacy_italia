"""
Genera il WORKSHEET di annotazione per il gold set dei temi.

Perché uno strumento e non un file scritto a mano: il gold set è ground truth
umana (regole CLAUDE.md "Never invent data", "separate facts from inferred
classifications"). Questo script NON etichetta: prepara solo un foglio campionato
che poi UN UMANO compila. Le etichette suggerite (`temi_suggeriti`) sono lì solo
come riferimento per velocizzare — la colonna `temi`, che diventa il gold, parte
VUOTA e va compilata verificando il testo, non fidandosi del suggerimento.

Campionamento STRATIFICATO (non casuale puro): per calibrare le soglie servono i
casi-limite. Includiamo quindi, con seed fisso: per ogni tema un mix di match
esatti e semantici (questi ultimi sono i borderline informativi), più un blocco
di NEGATIVI (nessun tema rilevato) e un po' di casuali per rappresentatività.
Nota: la P/R misurata su questo campione è pensata per SCEGLIERE le soglie
(concentra i confini di decisione), non per stimare la precisione sulla
distribuzione naturale del corpus — per quella servirebbe un campione casuale.

Uso:
    python nlp/prepara_gold.py                 # scrive data/utils/temi_gold_worksheet.csv
    python nlp/prepara_gold.py --n 150         # dimensione target
    python nlp/prepara_gold.py --force         # sovrascrive un worksheet esistente

Dopo la compilazione della colonna `temi`:
    python nlp/valuta_temi.py --gold data/utils/temi_gold_worksheet.csv
"""
import os
import sys
import random
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
from nlp.valuta_temi import _carica_documenti          # stessa risoluzione id del valutatore
from nlp.theme_matching import carica_temi, rileva_temi_batch
from nlp.deduplication import get_embedding_model

logger = setup_logger(__name__)

OUTPUT = os.path.join(_ROOT, 'data', 'utils', 'temi_gold_worksheet.csv')
SEED = 42
PER_TEMA = 12          # candidati per tema (metà esatti, metà semantici)
N_NEGATIVI = 15        # documenti senza alcun tema rilevato
N_TARGET = 130         # dimensione massima del worksheet


def _suggerimento(match_list) -> str:
    parti = []
    for m in match_list:
        if m['metodo'] == 'semantico':
            parti.append(f"{m['tema']}(sem:{m['score']})")
        else:
            parti.append(f"{m['tema']}(esatto)")
    return '|'.join(parti)


def _seleziona(matches, rng, n_target: int) -> set[int]:
    """Indici stratificati: mix esatto/semantico per tema + negativi + casuali."""
    temi_presenti = {m['tema'] for ml in matches for m in ml}
    scelti: set[int] = set()

    for tema in sorted(temi_presenti):
        sem = [i for i, ml in enumerate(matches)
               if any(m['tema'] == tema and m['metodo'] == 'semantico' for m in ml)]
        exa = [i for i, ml in enumerate(matches)
               if any(m['tema'] == tema and m['metodo'] == 'esatto' for m in ml)]
        rng.shuffle(sem)
        rng.shuffle(exa)
        scelti.update(sem[:PER_TEMA // 2])              # borderline: i più informativi
        scelti.update(exa[:PER_TEMA - PER_TEMA // 2])   # esatti: per misurare la precisione

    negativi = [i for i, ml in enumerate(matches) if not ml]
    rng.shuffle(negativi)
    scelti.update(negativi[:N_NEGATIVI])

    resto = list(range(len(matches)))
    rng.shuffle(resto)
    for i in resto:
        if len(scelti) >= n_target:
            break
        scelti.add(i)
    return scelti


def main():
    ap = argparse.ArgumentParser(description="Genera il worksheet del gold set temi")
    ap.add_argument('--n', type=int, default=N_TARGET, help="dimensione target del worksheet")
    ap.add_argument('--force', action='store_true', help="sovrascrivi un worksheet esistente")
    args = ap.parse_args()

    if os.path.exists(OUTPUT) and not args.force:
        logger.error("Esiste già %s — non lo sovrascrivo per non perdere le etichette. "
                     "Usa --force se vuoi rigenerarlo da zero.", OUTPUT)
        return

    docs_df = _carica_documenti(None)
    if docs_df.empty:
        logger.error("Nessun documento processato. Esegui prima nlp/text_analysis.py.")
        return

    temi = carica_temi()
    logger.info("Rilevamento temi su %d documenti per stratificare il campione...", len(docs_df))
    matches = rileva_temi_batch(docs_df['testo'].tolist(), temi, get_embedding_model())

    rng = random.Random(SEED)
    idx = sorted(_seleziona(matches, rng, args.n))

    righe = []
    for i in idx:
        r = docs_df.iloc[i]
        testo_pulito = ' '.join(str(r['testo']).split())[:220]
        righe.append({
            'id_documento': r['id'],
            'fonte': r['fonte'],
            'titolo': r['titolo'],
            'testo_estratto': testo_pulito,
            'temi_suggeriti': _suggerimento(matches[i]),  # riferimento, DA VERIFICARE
            'temi': '',                                     # <-- GOLD: compilare a mano
        })
    # Solo id validi e unici: scarta i doc senza chiave (id_univoco e hash entrambi
    # assenti → inutilizzabili come gold) e l'eventuale stesso contenuto in due fonti
    # (hash identico), che collasserebbe nel dict di valutazione falsando la P/R.
    df_out = pd.DataFrame(righe)
    df_out = df_out[df_out['id_documento'].astype(str).str.strip().ne('')]
    df_out = (df_out.drop_duplicates(subset='id_documento')
              .sort_values(['fonte', 'titolo'])
              .reset_index(drop=True))
    df_out.to_csv(OUTPUT, index=False, encoding='utf-8')

    logger.info("Worksheet scritto: %s (%d documenti da etichettare)", OUTPUT, len(df_out))
    # Codebook: le definizioni dei temi che l'annotatore deve applicare
    print("\n=== CODEBOOK — temi ammessi e termini di riferimento ===")
    for tema, termini in temi.items():
        print(f"  • {tema}: {', '.join(termini[:6])}...")
    print("\nIstruzioni: nella colonna 'temi' scrivi i temi che il documento tratta")
    print("davvero (non solo di sfuggita), separati da '|'. Scrivi NESSUNO se non ne")
    print("tratta alcuno (vuoto = non ancora etichettato). Guida: data/utils/GOLD_ISTRUZIONI.md")
    print("Usa ESATTAMENTE i nomi del codebook. Verifica il testo, non fidarti di 'temi_suggeriti'.")


if __name__ == "__main__":
    main()
