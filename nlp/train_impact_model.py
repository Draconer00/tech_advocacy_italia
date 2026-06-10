import os
import sys
import pandas as pd
import numpy as np
import joblib
from sentence_transformers import SentenceTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

# Aggiungi root progetto al path
cartella_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, cartella_root)

from utils.logger_config import setup_logger
from utils.feedback_schema import load_feedback

logger = setup_logger(__name__)

def train_impact_classifier():
    """
    Addestra un modello di classificazione per predire il livello di allarme
    basandosi sulle correzioni manuali effettuate nella dashboard (Golden Standard)
    
    Livello 3: Active Learning
    """
    
    cartella_script = os.path.dirname(os.path.abspath(__file__))
    percorso_feedback = os.path.join(cartella_script, '..', 'data', 'processed', 'training_data_feedback.csv')
    percorso_modello = os.path.join(cartella_script, '..', 'models', 'impact_classifier.pkl')

    # Crea cartella models se non esiste
    os.makedirs(os.path.dirname(percorso_modello), exist_ok=True)
    
    # 1. Carica il feedback in modo robusto e allineato allo schema canonico.
    #    load_feedback tollera file legacy/misti e restituisce sempre le colonne attese.
    df_feedback = load_feedback(percorso_feedback)
    if df_feedback.empty:
        logger.info("⚠️ Nessun dato di feedback trovato. Training non eseguibile.")
        return False

    # 2. Tieni solo le correzioni di urgenza valide: riga segnalata dall'operatore
    #    e livello_allarme_corretto interpretabile come intero nell'intervallo 1-5.
    segnalate = df_feedback['errore_segnalato'].astype(str).str.strip().str.lower().isin(['true', '1'])
    urgenza = pd.to_numeric(df_feedback['livello_allarme_corretto'], errors='coerce')
    titolo_valido = df_feedback['titolo'].astype(str).str.strip().ne('')
    validi = df_feedback[segnalate & urgenza.between(1, 5) & titolo_valido].copy()
    validi['livello_allarme_corretto'] = urgenza[validi.index].round().astype(int)

    MINIMO_RIGHE_TRAINING = 10
    if len(validi) < MINIMO_RIGHE_TRAINING:
        logger.info(
            "⚠️ Correzioni di urgenza valide insufficienti: %d/%d necessarie. "
            "Modello non addestrato: i documenti useranno il punteggio neutro di default.",
            len(validi), MINIMO_RIGHE_TRAINING,
        )
        return False

    logger.info("🚀 Avvio training modello impatto su %d correzioni di urgenza valide", len(validi))

    # 3. Carica modello per embeddings multilingua
    logger.info("📥 Caricamento modello Sentence Transformers...")
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

    # 4. Prepara dati: combina titolo e fonte come testo di input
    testi = validi.apply(lambda row: f"{row['titolo']} {row['fonte']}", axis=1).tolist()
    labels = validi['livello_allarme_corretto'].to_numpy()
    
    # 4. Genera embeddings
    logger.info("🔢 Generazione vettori embedding...")
    embeddings = model.encode(testi, show_progress_bar=True, batch_size=32)
    
    # 5. Split train / test — stratifica solo se ogni classe ha almeno 2 campioni
    from collections import Counter
    puo_stratificare = min(Counter(labels.tolist()).values()) >= 2
    X_train, X_test, y_train, y_test = train_test_split(
        embeddings, labels, test_size=0.2, random_state=42,
        stratify=labels if puo_stratificare else None,
    )
    
    # 6. Addestramento classificatore
    logger.info("🤖 Addestramento Random Forest Classifier...")
    clf = RandomForestClassifier(
        n_estimators=200,
        max_depth=10,
        min_samples_split=5,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    
    clf.fit(X_train, y_train)
    
    # 7. Valutazione modello
    y_pred = clf.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    logger.info("\n✅ REPORT TRAINING:")
    logger.info(f"    Accuracy modello: {accuracy:.2f}")
    logger.info("\n" + classification_report(y_test, y_pred, zero_division=0))
    
    # 8. Salva il classificatore. Il sentence-transformer NON viene serializzato:
    # è pubblico e immutabile, in inferenza si ri-istanzia per nome (vedi
    # text_analysis.carica_modello_impatto), evitando un .pkl da ~480MB.
    joblib.dump(clf, percorso_modello)

    logger.info(f"💾 Modello salvato correttamente in: {percorso_modello}")
    logger.info("✅ Training completato con successo!")
    
    return True


if __name__ == "__main__":
    train_impact_classifier()