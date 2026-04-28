"""
Modello di Active Learning per predizione automatica del livello di allarme
Questo modello impara direttamente dalle correzioni che fai nella sezione Golden Standard
"""
import pandas as pd
import numpy as np
import os
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

def train_impact_model():
    cartella_script = os.path.dirname(os.path.abspath(__file__))
    percorso_feedback = os.path.join(cartella_script, '..', 'data', 'processed', 'training_data_feedback.csv')
    percorso_modello = os.path.join(cartella_script, '..', 'models', 'impact_model.pkl')
    
    # Crea cartella modelli se non esiste
    os.makedirs(os.path.dirname(percorso_modello), exist_ok=True)
    
    if not os.path.exists(percorso_feedback):
        print("⚠️ Nessun dato di training presente. Inizia a correggere le notizie nella dashboard per addestrare il modello.")
        return False
    
    print("\n📚 Caricamento dati Golden Standard...")
    df = pd.read_csv(percorso_feedback)
    
    if len(df) < 10:
        print(f"⚠️ Servono almeno 10 correzioni per addestrare il modello. Attualmente ce ne sono {len(df)}.")
        return False
    
    # Prepara dati training
    X = df['titolo']
    y = df['livello_allarme_corretto'].astype(int)
    
    print(f"✅ Dati caricati: {len(df)} notizie corrette dall'utente")
    
    # Crea pipeline modello
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(max_features=5000, stop_words=['italiano', 'english'])),
        ('classifier', RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced'))
    ])
    
    # Addestramento
    print("\n🤖 Addestramento modello Active Learning...")
    pipeline.fit(X, y)
    
    # Salva modello
    joblib.dump(pipeline, percorso_modello)
    print(f"✅ Modello salvato in: {percorso_modello}")
    
    # Calcola accuratezza
    y_pred = pipeline.predict(X)
    accuratezza = np.mean(y_pred == y)
    print(f"\n📊 Accuratezza modello: {round(accuratezza * 100, 1)} %")
    
    print("\n✅ Modello pronto! Ora verrà usato automaticamente per assegnare il livello di allarme alle nuove notizie.")
    
    return True

def predici_livello_allarme(testo: str) -> int:
    """
    Predice il livello di allarme 1-5 usando il modello addestrato
    Se il modello non esiste usa il sistema di default
    """
    cartella_script = os.path.dirname(os.path.abspath(__file__))
    percorso_modello = os.path.join(cartella_script, '..', 'models', 'impact_model.pkl')
    
    if not os.path.exists(percorso_modello):
        # Fallback sul vecchio sistema a parole chiave
        testo_lower = testo.lower()
        parole_allarme_alto = ['multa', 'condanna', 'violazione', 'dati sensibili', 'hacking', 'fuga dati']
        if any(p in testo_lower for p in parole_allarme_alto):
            return 4
        return 2
    
    modello = joblib.load(percorso_modello)
    return int(modello.predict([testo])[0])

if __name__ == "__main__":
    train_impact_model()