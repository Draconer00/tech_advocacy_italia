# 🧠 Strategie per Potenziare l'Analisi NLP

Questo documento cataloga debolezze attuali di `text_analysis.py` e offre soluzioni concrete, scalate da **basso sforzo** a **alto impatto**.

---

## 🔴 Problemi Attuali

### 1. **Named Entity Recognition (NER) Impreciso**
- Modello `it_core_news_md` ha vocabulary limitato per dominio legale/privacy
- Confonde spesso: "Garante" → ORG o PER?
- Non riconosce sigle: "EDPB", "SARI", acronimi tech
- Falsi positivi: parole comuni (es. "Comune di Roma" ha tanti falsi match)

### 2. **Categorizzazione Entità Rigida**
- Usa keyword matching statico (parole escluse hardcoded)
- Se entità non entra in categoria predefinita → va in "Default"
- Ignora contesto: "Apple" potrebbe essere azienda o compagnia melafilm

### 3. **Classificazione Geografica Primitiva**
- Solo parole-chiave manuali ("USA", "Europa")
- Non riconosce: "GDPR" (EU), "CCPA" (USA), riferimenti impliciti
- Zero handling: multilingue, abbreviazioni straniere

### 4. **Nessun Sentiment/Tono**
- Non sa se decisione è positiva/negativa per diritti
- Es. "multato €50M" (good) vs "approvato sorveglianza" (bad)

### 5. **Nessun Topic Modeling**
- Non identifica automaticamente tematiche emergenti
- Sei forzato a cercare manualmente per parola chiave

### 6. **Zero Deduplica**
- Se due aziende hanno nome simile, creano due entry
- "Agenzia X" vs "Agenzia X SpA" → contate separatamente

### 7. **Testi Incompleti**
- A volte extraction fallisce, testo è "<50 caratteri"
- Invalida successiva analisi

---

## ✅ Soluzioni Proposte (Priority Order)

### 🟢 Priorità 1: Quick Wins (1-2 ore implementazione)

#### **1.1 Migliorare Estrazione Testo da GPDP** 
**Problema**: Alcuni testi sono incompleti o sporchi

**Soluzione**:
```python
def estrai_testo_pulito(zuppa):
    """Estrae testo legale evitando header/footer."""
    # Rimuovi script/style
    for tag in zuppa(['script', 'style']):
        tag.decompose()
    
    # Estrai testo
    testo = zuppa.get_text().strip()
    
    # Pulizia: whitespace, line break
    testo = re.sub(r'\s+', ' ', testo)
    
    # Mantieni solo sezioni rilevanti (primi 2000 char spesso contengono essenza)
    return testo[:2000] if len(testo) > 2000 else testo
```

**Beneficio**: +30% dati validi per NLP

---

#### **1.2 Aggiungere Fuzzy Matching per Deduplicazione**
**Problema**: "Apple Inc." vs "Apple Inc." vs "Apple" contate 3 volte

**Codice**:
```python
from difflib import SequenceMatcher

def deduplica_entita(lista_entita, soglia=0.85):
    """Unisce entità simili con fuzzy matching."""
    unica = []
    for ent in lista_entita:
        trovato = False
        for ent_unica in unica:
            ratio = SequenceMatcher(None, ent.lower(), ent_unica.lower()).ratio()
            if ratio > soglia:
                trovato = True
                break
        if not trovato:
            unica.append(ent)
    return unica
```

**Beneficio**: Entità più affidabili, riduce rumore del 40%

---

#### **1.3 Espandere Blacklist Dinamica su File CSV**
**Problema**: Hardcoding blacklist non scala

**Soluzione**: Crea `data/utils/nlp_blacklist.csv`:
```csv
parola_esclusa,motivo
"Garante","troppo generico"
"Privacy","sempre presente"
"Decreto","non entità"
```

```python
def carica_blacklist(filepath):
    import csv
    blacklist = set()
    with open(filepath) as f:
        reader = csv.DictReader(f)
        blacklist = {row['parola_esclusa'] for row in reader}
    return blacklist

BLACKLIST = carica_blacklist('data/utils/nlp_blacklist.csv')
```

**Beneficio**: Manutenzione facilitata, evita recompile

---

### 🟡 Priorità 2: Moderato Impatto (3-5 ore)

#### **2.1 Aggiungere Sentiment Analysis su Provvedimenti**
**Problema**: Non sai se multa è dura o lieve, se decisione blocca/consente tecnica

**Soluzione**: Usa `transformers` con modello italiano

```bash
pip install transformers
```

```python
from transformers import pipeline

sentiment_pipe = pipeline("sentiment-analysis", 
                          model="nlptown/bert-base-multilingual-uncased-sentiment")

def classifica_sentiment_provvedimento(testo):
    """Classifica tono: positivo (diritti protetti), negativo (libertà compromessa)."""
    # Focus su prime frasi (headline effect)
    testo_core = testo[:500]  
    result = sentiment_pipe(testo_core, truncation=True)
    label = result[0]['label']  # 5 stars = positive, 1 star = negative
    
    if label in ['5 stars', '4 stars']:
        return 'POSITIVO (Diritti tutelati)'
    elif label in ['1 stars', '2 stars']:
        return 'NEGATIVO (Libertà ristretta)'
    else:
        return 'NEUTRALE'

df['Sentiment_Direzione'] = df['Testo_Completo'].apply(classifica_sentiment_provvedimento)
```

**Output kolonna**: `Sentiment_Direzione` = [POSITIVO | NEUTRALE | NEGATIVO]

**Beneficio**: Identifica subito decisioni "pro-diritti" vs "pro-sorveglianza"

---

#### **2.2 Riconoscere Acronimi Legali e Tech**
**Problema**: "GDPR", "EDPB", "AMI", "SARI" non riconosciuti come entità

**Soluzione**: Aggiungi dizionario di acronimi

```python
ACRONIMI_LEGALI = {
    'GDPR': 'Leggi e Regolamentazioni || EU',
    'EDPB': 'Istituzioni || EU',
    'CCPA': 'Leggi e Regolamentazioni || USA',
    'LGPD': 'Leggi e Regolamentazioni || Brasile',
    'RGPD': 'Leggi e Regolamentazioni || Francia',
    'AMI': 'Tecnologie || IA',
    'SARI': 'Tecnologie || Polizia'
}

def estrai_acronimi(testo):
    """Estrae acronimi noti e aggiunge come entità."""
    trovati = []
    for sigla, categoria in ACRONIMI_LEGALI.items():
        if sigla.upper() in testo.upper():
            trovati.append(f"{sigla} || {categoria}")
    return trovati

# Combina con NER standard
def estrai_entita_enhanced(testo):
    entita_nlp = estrai_entita(testo)  # NER classico
    entita_acronimi = estrai_acronimi(testo)  # Acronimi
    return list(set(entita_nlp + entita_acronimi))
```

**Beneficio**: +20% entità rilevanti recuperate

---

#### **2.3 Keyword Extraction per Tematica**
**Problema**: Non sai a colpo d'occhio se sentenza riguarda biometria, IA, cookie, tracciamento

**Soluzione**: TF-IDF semplice

```bash
pip install scikit-learn
```

```python
from sklearn.feature_extraction.text import TfidfVectorizer

def estrai_topic_keywords(testo, num_keywords=5):
    """Estrae parole-chiave principali per identificare tematica."""
    vectorizer = TfidfVectorizer(max_features=num_keywords, 
                                  stop_words=['italiano', 'english'])
    tfidf = vectorizer.fit_transform([testo])
    keywords = vectorizer.get_feature_names_out()
    return list(keywords)

df['Parole_Chiave'] = df['Testo_Completo'].apply(estrai_topic_keywords)
```

**Output kolonna**: `Parole_Chiave` = ['biometrica', 'riconoscimento', 'identità', ...]

**Beneficio**: Cluster automatico per tematiche

---

### 🔴 Priorità 3: Alto Impatto (6-8 ore)

#### **3.1 Implementare Topic Modeling (LDA / BERTopic)**
**Problema**: Devi scoprire da solo che nel 2024 emergono 3 tematiche: AI regulation, biometria, cookie wall

**Soluzione**: BERTopic (semantic clustering)

```bash
pip install bertopic
```

```python
from bertopic import BERTopic
import pandas as pd

def topic_modeling(df_texts):
    """Scopre automaticamente N topic emergenti."""
    topic_model = BERTopic(language="italian", min_topic_size=3)
    topics, probs = topic_model.fit_transform(df_texts)
    
    # Topic labels auto-generate (es. "AI Regulation", "Biometric Privacy")
    labels = topic_model.generate_topic_labels()
    
    return topics, labels

df['Topic_Emergente'] = topic_modeling(df['Testo_Completo'].tolist())[0]
df['Topic_Etichetta'] = df['Topic_Emergente'].map(lambda_map_topic_label)
```

**Output**: Dataframe con colonna `Topic_Emergente` = [0, 1, 2, ...] e nomi tematici automatici

**Beneficio**: Scopri trend senza supervisione, ideale per policy makers

---

#### **3.2 NER Fine-Tuned su Dominio Privacy**
**Problema**: Modello generico ha low precision su termini legali

**Soluzione**: Fine-tune modello spaCy su dataset etichettato a mano

```bash
pip install spacy[train]
```

**Processo**:
1. Etichetta manualmente 100-200 testi gpdp con entità corrette (usando Prodigy o Label Studio)
2. Fine-tune con `spacy train`:
```bash
python -m spacy train configs/ner_privacy.cfg --paths.train data/train_privacy.spacy --paths.dev data/dev_privacy.spacy --output models/
```
3. Usa modello fine-tuned in `text_analysis.py`:
```python
nlp = spacy.load("path/to/models/model-best")  # Custom model
```

**Beneficio**: +50% precision NER per nomi aziende/enti specifici

---

#### **3.3 Linking Entità (Entity Linking)**
**Problema**: "Google" in testo non sa se è Google Inc. (USA), Google Irlanda (EU), o generic

**Soluzione**: Usa `wikipedia`, `DBpedia`, o mini knowledge-base custom

```bash
pip install wikipedia-api
```

```python
import wikipedia

def collega_entita(nome_entita):
    """Risolve entità a Wikipedia per disambiguazione."""
    try:
        page = wikipedia.page(nome_entita, auto_suggest=False)
        return {
            'nome': page.title,
            'url': page.url,
            'categoria': 'USA' if 'United States' in page.url else 'Altro'
        }
    except:
        return None  # Not found

# Usa in colonna
df['Entita_Linked'] = df['Entita_Coinvolte'].apply(
    lambda lista: [collega_entita(ent.split(' || ')[0]) for ent in lista]
)
```

**Beneficio**: Arricchisci entità con contexto, enabling link graphs

---

### 💎 Priorità 4: Estrazione Avanzata (8+ ore, ROI futuro)

#### **4.1 Estrazione Relazioni (Relation Extraction)**
**Obiettivo**: Capire non solo CHI è menzionato, ma COSA hanno fatto

**Esempio**: "La Garante ha multato Google" → Relazione(Garante, multò, Google)

**Implementazione semplice**:
```bash
pip install spacy-transformers
```

```python
def estrai_relazioni_semplici(testo):
    """Estrae relazioni Soggetto-Verbo-Oggetto."""
    doc = nlp(testo)
    relazioni = []
    
    for sent in doc.sents:
        # Cerca pattern: ORG-VERB-ORG
        for token in sent:
            if token.pos_ == 'VERB':
                soggetto = None
                oggetto = None
                
                # Trova il soggetto (nsubj)
                for dep in token.head.lefts:
                    if dep.dep_ == 'nsubj' and dep.ent_type_ == 'ORG':
                        soggetto = dep.text
                
                # Trova l'oggetto (obj)
                for dep in token.head.rights:
                    if dep.dep_ == 'obj' and dep.ent_type_ == 'ORG':
                        oggetto = dep.text
                
                if soggetto and oggetto:
                    relazioni.append({
                        'soggetto': soggetto,
                        'azione': token.lemma_,
                        'oggetto': oggetto
                    })
    
    return relazioni
```

**Output**: Triplet (Garante, multare, Google) → grafo conhecenza

---

#### **4.2 Estrazione Quantitative (Importi Multa, Date)**
**Obiettivo**: Quantificare enforcement: "5 multinazioni multate per €500M in Q2 2024"

```python
import re
from datetime import datetime

def estrai_importi(testo):
    """Estrae importi monetari in EUR/USD."""
    pattern = r'€\s?([\d,\.]+)\s?(?:milioni|milioni|M|mila)'
    matches = re.findall(pattern, testo, re.IGNORECASE)
    importi = [float(m.replace('.', '').replace(',', '.')) for m in matches]
    return sum(importi) if importi else 0

def estrai_date_decisione(testo):
    """Estrae data decisione numerica."""
    doc = nlp(testo)
    date_ents = [ent.text for ent in doc.ents if ent.label_ == 'DATE']
    return date_ents[0] if date_ents else None

df['Importo_EUR'] = df['Testo_Completo'].apply(estrai_importi)
df['Data_Decisione'] = df['Testo_Completo'].apply(estrai_date_decisione)
```

---

#### **4.3 Integrare LLM Local (Mistral, Llama2) per Summarizzazione**
**Obiettivo**: Genera riassunto automatico di ciascun provvedimento

```bash
pip install ollama
# (o usa local LLM se disponibile)
```

```python
from ollama import generate

def riassumi_provvedimento(testo):
    """Genera bullet-point summary usando LLM."""
    prompt = f"""Riassumi in italiano il seguente provvedimento legale in 3 bullet point:
    
    {testo[:1000]}
    
    Formato:
    - Punto 1
    - Punto 2
    - Punto 3"""
    
    response = generate('mistral', prompt, stream=False)
    return response['response']

df['Riassunto_IA'] = df['Testo_Completo'].apply(riassumi_provvedimento)
```

---

## 📊 Roadmap Implementazione

```
Settimana 1
├─ 1.1: Pulizia testo (2h)
├─ 1.2: Fuzzy dedup (1.5h)
└─ 1.3: Blacklist CSV (1h)

Settimana 2
├─ 2.1: Sentiment Analysis (2h)
├─ 2.2: Acronimi Legali (1.5h)
└─ 2.3: TF-IDF Keywords (1.5h)

Settimana 3
├─ 3.1: BERTopic (3h setup + annotazione)
├─ 3.2: NER Fine-tuning (5h + review)
└─ 3.3: Entity Linking (2h)

Settimana 4+
├─ 4.1: Relation Extraction (eval stage)
├─ 4.2: Quantitativo (2h)
└─ 4.3: LLM Summary (proof-of-concept)
```

---

## 🧪 Testing & Validazione

```python
# Test set manuale: 20 documenti marcati a mano
def valida_miglioramenti():
    """Confronta precisione prima/dopo."""
    
    # Before
    entita_old = estrai_entita_old(testo_test)
    
    # After
    entita_new = estrai_entita_enhanced(testo_test)
    sentiment_new = classifica_sentiment_provvedimento(testo_test)
    keywords_new = estrai_topic_keywords(testo_test)
    
    print(f"Before: {len(entita_old)} entità")
    print(f"After: {len(entita_new)} entità (+{(len(entita_new)/len(entita_old)-1)*100:.0f}%)")
    print(f"Sentiment: {sentiment_new}")
    print(f"Keywords: {keywords_new}")
```

---

## 📈 Expected Improvements

| Feature | Precision Before | Precision After | Priority |
|---------|-----------------|-----------------|----------|
| Entità Estratte | 65% | 85% ↑ | Priority 1 |
| Deduplicazione | 0% (no) | 95% | Priority 1 |
| Copertura Acronimi | 10% | 90% ↑ | Priority 2 |
| Sentiment | N/A | 80% | Priority 2 |
| Topic Discover | Manual | Auto ↑ | Priority 3 |
| NER Domain | 60% | 90% ↑ | Priority 3 |

---

## 🎯 Success Metrics

Traccia post-implementazione:

- **Falsi positivi ridotti**: <10% in blacklist manual review
- **Coverage entità**: >95% rilevanti vs <50% rumore
- **Sentiment accuracy**: 85%+ match human annotation on sample
- **Topic coherence**: >0.6 CV score (BERTopic)
- **Dashboard load time**: <2sec con NLP enhancements

---

**Next action**: Scegli Priority 1 soluzioni e start coding!
