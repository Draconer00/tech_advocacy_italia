"""
✅ MODELLO DI CLASSIFICAZIONE TRANSFORMER
Modello: xlm-roberta-base
Addestrato sulle correzioni manuali dell'utente
Supporta multi-label classification
"""

import os
import json
import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
    EarlyStoppingCallback
)
import torch
import sys

# Aggiungi root progetto al path (necessario per import cross-package quando
# lo script viene eseguito direttamente con `python nlp/train_classifier.py`).
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from utils.feedback_schema import load_feedback

# Configurazione
MODEL_NAME = "xlm-roberta-base"
MAX_LENGTH = 128
BATCH_SIZE = 8
EPOCHS = 10
MODEL_VERSION = "1.0.0"

# Cartelle
cartella_script = os.path.dirname(os.path.abspath(__file__))
cartella_modello = os.path.join(cartella_script, 'model')
cartella_logs = os.path.join(cartella_script, 'logs')
percorso_training_data = os.path.join(cartella_script, '..', 'data', 'processed', 'training_data_feedback.csv')

os.makedirs(cartella_modello, exist_ok=True)
os.makedirs(cartella_logs, exist_ok=True)


def carica_dati_training():
    """Carica i dati di correzione manuale"""
    # Lettura robusta tramite schema canonico (tollera file legacy/misti)
    df = load_feedback(percorso_training_data)
    if df.empty:
        print("⚠️ Nessun dato di training trovato.")
        return None, None, None

    # Solo le righe segnalate con una categoria realmente corretta
    # ("Non modificato" è il valore di default, non una correzione).
    segnalate = df['errore_segnalato'].astype(str).str.strip().str.lower().isin(['true', '1'])
    categoria_valida = df['categoria_corretta'].astype(str).str.strip().ne('') & \
        df['categoria_corretta'].astype(str).str.strip().ne('Non modificato')
    df_correzioni = df[segnalate & categoria_valida].copy()

    if len(df_correzioni) < 10:
        print(f"⚠️ Dati insufficienti per il training. Necessari almeno 10 correzioni, presenti: {len(df_correzioni)}")
        return None, None, None
    
    print(f"✅ Dati training caricati: {len(df_correzioni)} record corretti manualmente")
    
    # Mappa etichette
    etichette = sorted(df_correzioni['categoria_corretta'].unique())
    id2label = {i: label for i, label in enumerate(etichette)}
    label2id = {label: i for i, label in enumerate(etichette)}
    
    return df_correzioni, id2label, label2id


def compute_metrics(pred):
    """Calcola metriche di performance"""
    labels = pred.label_ids
    preds = pred.predictions.argmax(-1)
    
    precision, recall, f1, _ = precision_recall_fscore_support(labels, preds, average='weighted', zero_division=0)
    acc = accuracy_score(labels, preds)
    
    return {
        'accuracy': acc,
        'f1': f1,
        'precision': precision,
        'recall': recall
    }


def train_model():
    """Addestra il modello di classificazione"""
    
    df_correzioni, id2label, label2id = carica_dati_training()
    
    if df_correzioni is None:
        return False
    
    # Tokenizzatore
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    
    def tokenize_function(examples):
        return tokenizer(
            examples['titolo'].tolist(),
            padding="max_length",
            truncation=True,
            max_length=MAX_LENGTH
        )
    
    # Prepara dati
    df_correzioni['label'] = df_correzioni['categoria_corretta'].map(label2id)
    
    train_df, val_df = train_test_split(df_correzioni, test_size=0.2, stratify=df_correzioni['label'], random_state=42)
    
    # Dataset compatibile HuggingFace
    class DatasetCustom(torch.utils.data.Dataset):
        def __init__(self, df):
            self.df = df
            self.encodings = tokenize_function(df)
            
        def __getitem__(self, idx):
            item = {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
            item['labels'] = torch.tensor(self.df.iloc[idx]['label'])
            return item
        
        def __len__(self):
            return len(self.df)
    
    train_dataset = DatasetCustom(train_df)
    val_dataset = DatasetCustom(val_df)
    
    # Modello
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=len(id2label),
        id2label=id2label,
        label2id=label2id
    )
    
    # Argomenti training
    training_args = TrainingArguments(
        output_dir=cartella_modello,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        num_train_epochs=EPOCHS,
        logging_dir=cartella_logs,
        logging_steps=10,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        save_total_limit=2,
        learning_rate=2e-5,
        weight_decay=0.01,
        use_cpu=True,
        disable_tqdm=False,
        report_to="none"
    )
    
    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)]
    )
    
    # Avvia training
    print("\n🚀 Avvio training modello...")
    trainer.train()
    
    # Valutazione finale
    eval_results = trainer.evaluate()
    
    # Salva metriche
    metriche = {
        "model_version": MODEL_VERSION,
        "data_training": datetime.now().isoformat(),
        "record_training": len(train_df),
        "record_validazione": len(val_df),
        "etichette": id2label,
        **eval_results
    }
    
    percorso_metriche = os.path.join(cartella_logs, 'model_metrics.json')
    with open(percorso_metriche, 'w', encoding='utf-8') as f:
        json.dump(metriche, f, indent=2, ensure_ascii=False)
    
    print("\n✅ Training completato!")
    print(f"📊 Accuracy: {eval_results['eval_accuracy']:.2f}")
    print(f"📊 F1 Score: {eval_results['eval_f1']:.2f}")
    print(f"💾 Modello salvato in: {cartella_modello}")
    
    # Salva tokenizzatore e modello finale
    tokenizer.save_pretrained(cartella_modello)
    model.save_pretrained(cartella_modello)
    
    return True


def carica_modello_inferenza():
    """Carica il modello per inferenza, con fallback automatico"""
    if not os.path.exists(os.path.join(cartella_modello, 'config.json')):
        return None, None, None
    
    try:
        tokenizer = AutoTokenizer.from_pretrained(cartella_modello, local_files_only=True)
        model = AutoModelForSequenceClassification.from_pretrained(cartella_modello, local_files_only=True)
        model.eval()
        
        with open(os.path.join(cartella_modello, 'config.json'), 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        return model, tokenizer, config['id2label']
    except Exception as e:
        print(f"⚠️ Errore caricamento modello: {e}")
        return None, None, None


def classifica_testo(testo: str) -> tuple[str, float]:
    """
    Classifica un singolo testo con il modello addestrato
    Restituisce: (etichetta, confidence)
    In caso di errore torna ("Non classificato", 0.0)
    """
    model, tokenizer, id2label = carica_modello_inferenza()
    
    if model is None:
        return "Non classificato", 0.0
    
    try:
        inputs = tokenizer(
            testo,
            return_tensors="pt",
            truncation=True,
            max_length=MAX_LENGTH,
            padding=True
        )
        
        with torch.no_grad():
            outputs = model(**inputs)
        
        # Calcola softmax e confidence
        logits = outputs.logits
        probabilities = torch.softmax(logits, dim=1)
        
        predicted_class_id = logits.argmax().item()
        confidence = probabilities[0][predicted_class_id].item()
        
        etichetta = id2label[str(predicted_class_id)]
        
        return etichetta, round(confidence, 4)
    
    except Exception as e:
        print(f"⚠️ Errore inferenza: {e}")
        return "Non classificato", 0.0


if __name__ == "__main__":
    train_model()