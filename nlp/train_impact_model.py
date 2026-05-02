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
    percorso_embedding_model = os.path.join(cartella_script, '..', 'models', 'sentence_transformer.pkl')
    
    # Crea cartella models se non esiste
    os.makedirs(os.path.dirname(percorso_modello), exist_ok=True)
    
    # 1. Controllo se esistono abbastanza dati di training
    if not os.path.exists(percorso_feedback):
        logger.info("⚠️ Nessun dato di feedback trovato. Training non eseguibile.")
        return False
    
    # Gestione CSV corrotto / righe malformate: salta le righe sbagliate invece di crashare
    try:
        df_feedback = pd.read_csv(percorso_feedback, on_bad_lines='skip', engine='python')
    except Exception as e:
        logger.warning(f"⚠️ Errore nella lettura del file feedback: {str(e)}")
        logger.info("Provo a leggere il file con modalità permissiva...")
        try:
            # Modalità emergenza: leggi ogni riga e ignora errori
            df_feedback = pd.read_csv(percorso_feedback, 
                                     sep=None, 
                                     engine='python',
                                     on_bad_lines='skip',
                                     quoting=3)
        except Exception as e2:
            logger.error(f"❌ Impossibile leggere il file feedback: {str(e2)}")
            return False
    
    MINIMO_RIGHE_TRAINING = 10
    if len(df_feedback) < MINIMO_RIGHE_TRAINING:
        logger.info(f"⚠️ Dati insufficienti per il training. Necessari almeno {MINIMO_RIGHE_TRAINING} correzioni, presenti: {len(df_feedback)}")
        return False
    
    logger.info(f"🚀 Avvio training modello impatto su {len(df_feedback)} record annotati manualmente")
    
    # 2. Carica modello per embeddings multilingua
    logger.info("📥 Caricamento modello Sentence Transformers...")
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    
    # 3. Prepara dati
    # Combina titolo e fonte come testo di input
    testi = df_feedback.apply(lambda row: f"{row['titolo']} {row['fonte']}", axis=1).tolist()
    labels = df_feedback['livello_allarme_corretto'].astype(int).values
    
    # 4. Genera embeddings
    logger.info("🔢 Generazione vettori embedding...")
    embeddings = model.encode(testi, show_progress_bar=True, batch_size=32)
    
    # 5. Split train / test
    X_train, X_test, y_train, y_test = train_test_split(embeddings, labels, test_size=0.2, random_state=42, stratify=labels)
    
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
    
    # 8. Salva modello
    joblib.dump(clf, percorso_modello)
    joblib.dump(model, percorso_embedding_model)
    
    logger.info(f"💾 Modello salvato correttamente in: {percorso_modello}")
    logger.info("✅ Training completato con successo!")
    
    return True


if __name__ == "__main__":
    train_impact_classifier()