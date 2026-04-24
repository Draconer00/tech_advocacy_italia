"""
Script di Active Learning e Fine-Tuning per spaCy TextCategorizer

Questo script permette di ri-addestrare il modello spaCy usando i feedback
raccolti dalla dashboard tramite Human-in-the-loop.

Implementa prevenzione del Catastrophic Forgetting mantenendo le performance
originali del modello anche dopo il fine-tuning.
"""
import spacy
from spacy.training import Example
from spacy.tokens import DocBin
import pandas as pd
import os
import random
from datetime import datetime

# ==============================================
# CONFIGURAZIONE
# ==============================================
BASE_MODEL = "it_core_news_md"
OUTPUT_MODEL_PATH = "../models/custom_spacy_model"
FEEDBACK_FILE = "../data/processed/training_data_feedback.csv"

# Iperparametri di training
TRAIN_EPOCHS = 15
DROPOUT = 0.2
LEARNING_RATE = 2e-5
BATCH_SIZE = 8

def load_feedback_data():
    """Carica i dati di feedback raccolti dalla dashboard"""
    if not os.path.exists(FEEDBACK_FILE):
        print("⚠️ Nessun file di feedback trovato.")
        return []
    
    df = pd.read_csv(FEEDBACK_FILE)
    
    # Filtra solo le righe valide con correzione
    df_valid = df[
        (df['errore_segnalato'] == True) &
        (df['categoria_corretta'] != "Non modificato")
    ].copy()
    
    print(f"✅ Caricati {len(df_valid)} esempi di training validi")
    
    training_data = []
    for _, row in df_valid.iterrows():
        testo = f"{row['titolo']}"
        label = row['categoria_corretta']
        
        training_data.append( (testo, label) )
    
    return training_data


def prepare_training_examples(nlp, training_data):
    """Converti i dati nel formato richiesto da spaCy v3"""
    
    labels = list({label for testo, label in training_data})
    print(f"🔖 Categorie presenti nel training set: {labels}")
    
    examples = []
    
    for testo, label in training_data:
        doc = nlp.make_doc(testo)
        
        # Crea dizionario delle categorie
        cats = {lbl: 1.0 if lbl == label else 0.0 for lbl in labels}
        
        # Crea oggetto Example
        example = Example.from_dict(doc, {"cats": cats})
        examples.append(example)
    
    # Mischia i dati
    random.shuffle(examples)
    
    # Dividi 80% training / 20% valutazione
    split = int(0.8 * len(examples))
    train_examples = examples[:split]
    dev_examples = examples[split:]
    
    print(f"📊 Training set: {len(train_examples)} esempi")
    print(f"📊 Validation set: {len(dev_examples)} esempi")
    
    return train_examples, dev_examples, labels


def train_textcat_pipeline():
    """Loop completo di training con prevenzione Catastrophic Forgetting"""
    
    # 1. Carica modello base
    print(f"\n🚀 Caricamento modello base: {BASE_MODEL}")
    nlp = spacy.load(BASE_MODEL)
    
    # 2. Carica dati feedback
    training_data = load_feedback_data()
    if not training_data:
        print("❌ Nessun dato di training disponibile.")
        return
    
    # 3. Prepara esempi di training
    train_examples, dev_examples, labels = prepare_training_examples(nlp, training_data)
    
    # 4. Aggiungi componente TextCategorizer se non presente
    if "textcat" not in nlp.pipe_names:
        print("➕ Aggiungo componente TextCategorizer alla pipeline")
        textcat = nlp.add_pipe("textcat", last=True)
    else:
        textcat = nlp.get_pipe("textcat")
        print("✅ TextCategorizer già presente nella pipeline")
    
    # Aggiungi le etichette al classificatore
    for label in labels:
        textcat.add_label(label)
    
    # 5. 🛡️ PREVENZIONE CATASTROPHIC FORGETTING
    # Congela tutti i componenti tranne textcat per mantenere performance originali
    other_pipes = [pipe for pipe in nlp.pipe_names if pipe != "textcat"]
    print(f"🔒 Congelamento componenti: {other_pipes}")
    
    with nlp.disable_pipes(*other_pipes):
        
        # Configura ottimizzatore
        optimizer = nlp.create_optimizer()
        optimizer.learn_rate = LEARNING_RATE
        
        print(f"\n🏁 Inizio training per {TRAIN_EPOCHS} epoche...")
        print(f"   Dropout: {DROPOUT} | Batch Size: {BATCH_SIZE} | LR: {LEARNING_RATE}")
        
        # Loop di training
        for epoch in range(TRAIN_EPOCHS):
            
            # Mischia esempi ogni epoca
            random.shuffle(train_examples)
            
            losses = {}
            
            for batch in spacy.util.minibatch(train_examples, size=BATCH_SIZE):
                nlp.update(
                    batch,
                    drop=DROPOUT,
                    sgd=optimizer,
                    losses=losses
                )
            
            # Valuta su dev set ogni epoca
            scores = nlp.evaluate(dev_examples)
            
            print(f"⏱  Epoca {epoch+1}/{TRAIN_EPOCHS} | Loss: {losses.get('textcat', 0):.4f} | Precision: {scores.get('cats_p', 0):.2f} | Recall: {scores.get('cats_r', 0):.2f}")
    
    # 6. Salva il modello fine-tunato
    os.makedirs(OUTPUT_MODEL_PATH, exist_ok=True)
    nlp.to_disk(OUTPUT_MODEL_PATH)
    
    print(f"\n✅ Training completato!")
    print(f"💾 Modello salvato in: {OUTPUT_MODEL_PATH}")
    print("\n📘 Il prossimo run di text_analysis.py caricherà automaticamente questo modello custom invece di quello base.")
    
    return nlp


if __name__ == "__main__":
    print("="*60)
    print("ACTIVE LEARNING - FINE TUNING spaCy TEXT CATEGORIZER")
    print("="*60)
    
    train_textcat_pipeline()
    
    print("\n✅ Operazione completata.")