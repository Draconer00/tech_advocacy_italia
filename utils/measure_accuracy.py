import os
import sys

import pandas as pd

sys.path.append('.')

# La console Windows usa cp1252 e non sa codificare le emoji dell'output: forza
# UTF-8 sullo stdout così lo script gira identico su Windows, Linux e macOS.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from nlp.text_analysis import carica_modello_impatto, calcola_livello_allarme
from utils.feedback_schema import load_feedback


def calcola_metriche():
    """
    Misura l'errore del modello di urgenza confrontando le sue predizioni con il
    Gold Standard delle correzioni manuali (`livello_allarme_corretto`).

    Questa è l'unica colonna del file di feedback che contiene una *label* reale:
    il livello di allarme (1-5) assegnato a mano dall'operatore sulla dashboard.
    Si rifà predire al modello corrente lo stesso testo su cui è stato addestrato
    (`"titolo fonte"`, identico a nlp/train_impact_model.py) e si confronta la
    predizione con la label.

    NOTA DI METODO (onestà sull'incertezza): con poche correzioni il set di
    valutazione coincide quasi del tutto con quello di addestramento. Il numero
    qui sotto è quindi un *fit in-sample* (controllo di sanità), non una stima di
    generalizzazione su dati mai visti. Va letto come tale finché le correzioni
    non bastano per un hold-out separato.
    """

    percorso_feedback = os.path.join('data', 'processed', 'training_data_feedback.csv')

    df_gold = load_feedback(percorso_feedback)
    if df_gold.empty:
        print("❌ Nessuna correzione salvata ancora.")
        print("💡 Usa il sistema di correzione sulla scheda Home della dashboard per aggiungere almeno 10 correzioni.")
        return

    # Tieni solo le correzioni di urgenza valide, con gli stessi criteri del
    # trainer: riga segnalata + livello_allarme_corretto interpretabile come
    # intero 1-5 + titolo non vuoto. Così valutiamo esattamente ciò su cui il
    # modello è (o sarebbe) addestrato.
    segnalate = df_gold['errore_segnalato'].astype(str).str.strip().str.lower().isin(['true', '1'])
    urgenza = pd.to_numeric(df_gold['livello_allarme_corretto'], errors='coerce')
    titolo_valido = df_gold['titolo'].astype(str).str.strip().ne('')
    validi = df_gold[segnalate & urgenza.between(1, 5) & titolo_valido].copy()
    validi['gold'] = urgenza[validi.index].round().astype(int)

    if len(validi) < 10:
        print(f"⚠️ Hai solo {len(validi)} correzioni di urgenza valide.")
        print("   Per una misurazione significativa servono almeno 10 correzioni.")
        print("   Continua ad etichettare il livello di allarme nella dashboard :)")
        return

    clf, embedding_model = carica_modello_impatto()
    if clf is None or embedding_model is None:
        print("❌ Modello di urgenza non addestrato (models/impact_classifier.pkl assente).")
        print("   Senza modello le predizioni sarebbero un valore neutro costante: misura non significativa.")
        print("💡 Esegui prima:  python -m nlp.train_impact_model")
        return

    print(f"\n📊 ERRORE REALE MODELLO DI URGENZA (vs Gold Standard)")
    print(f"=====================================================")
    print(f"Esempi etichettati nel Gold Standard: {len(validi)}")
    print("⚠️ Fit in-sample: con così poche correzioni il set valutato coincide")
    print("   con quello di training. Leggilo come sanity check, non generalizzazione.")
    print(f"\n")

    errori = []
    corrette = 0
    for idx, row in validi.iterrows():
        # Stesso input del trainer: titolo + fonte.
        testo = f"{row['titolo']} {row['fonte']}".strip()
        pred = calcola_livello_allarme(testo, clf, embedding_model)
        gold = int(row['gold'])
        scarto = abs(pred - gold)
        if pred == gold:
            corrette += 1
        errori.append({
            'indice': idx,
            'titolo': str(row['titolo'])[:60] + "...",
            'predetto': pred,
            'reale': gold,
            'scarto': scarto,
        })

    df_errori = pd.DataFrame(errori)

    accuratezza = corrette / len(validi) * 100
    mae = df_errori['scarto'].mean()

    print(f"✅ ACCURATEZZA ESATTA (predizione == label): {accuratezza:.1f} %")
    print(f"📏 Errore assoluto medio (MAE) sulla scala 1-5: {mae:.3f}")
    print(f"\n")
    print(f"💡 MAE eccellente: < 0.30")
    print(f"💡 MAE buono:      < 0.60")
    print(f"💡 MAE da migliorare: > 1.00")
    print(f"\n")
    print(f"🔝 5 errori PEGGIORI:")
    print(f"----------------------")

    peggiori = df_errori.sort_values('scarto', ascending=False).head(5)
    for _, r in peggiori.iterrows():
        print(f"❌ scarto {r['scarto']} (predetto {r['predetto']} ≠ reale {r['reale']}) | {r['titolo']}")

    print(f"\n")
    print("💡 Queste sono le notizie su cui il modello di urgenza sbaglia di più.")
    print("   Correggile nella dashboard e ri-addestra: il modello migliorerà.")


if __name__ == "__main__":
    calcola_metriche()
