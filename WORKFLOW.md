# 🔄 WORKFLOW: Pipeline Tech Advocacy Italy

Guida completa e ufficiale della pipeline di estrazione, analisi semantica, network analysis e visualizzazione.

Questo documento è valido sia per utenti non tecnici che per sviluppatori.

---

## 🎯 Che cosa fa questo progetto

Questo sistema crea una mappa in tempo reale dell'ecosistema dei diritti digitali in Italia e Europa. Non è un semplice aggregatore di notizie:

✅ **Monitora** oltre 25 fonti ufficiali tra ONG, istituzioni europee e garanti
✅ **Analizza semanticamente** ogni documento con NLP
✅ **Crea relazioni** tra temi, organizzazioni e notizie
✅ **Visualizza** un network dinamico dove si vede chi parla di cosa
✅ **Permette correzioni umane** che migliorano continuamente il modello

---

## 📍 Architettura Generale

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   SCRAPERS  │────▶│  DATI RAW   │────▶│  NLP ENGINE │────▶│  DASHBOARD  │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
  25 Fonti             CSV Files        Classificazione      Network Map
  RSS + Web            SQLite DB        Estrazione Entità     Time Series
```

Tutti i passaggi sono completamente trasparenti, auditabili e modificabili.

---

## 🚀 Sequenza di Esecuzione Completa

---

### **Fase 1: Setup Iniziale** (Una sola volta)

```bash
# 1. Entra nella cartella del progetto
cd tech_advocacy_italia

# 2. Installa tutte le dipendenze
pip install -r requirements.txt

# 3. Scarica modello linguistico italiano
python -m spacy download it_core_news_md
```

✅ Fatto. Non c'è nient'altro da installare.

---

### **Fase 2: Scraping Dati**

Ogni scraper è indipendente e produce dati standardizzati. Puoi eseguirli in qualsiasi ordine.

---

#### 🔹 2.1 Garante Privacy GPDP
```bash
python scrapers/scraper_gpdp.py
```

✅ **Cosa fa**: Estrae solamente provvedimenti ufficiali. **NON scarica comunicati stampa, notizie o annunci**.
✅ Output: `data/raw/gpdp_sample.csv`
✅ Tempo: ~1 minuto

---

#### 🔹 2.2 Organizzazioni Civiche e Istituzioni Europee
```bash
python scrapers/scraper_ong.py
```

✅ **23 Fonti Monitorate**:
- 🇮🇹 13 Organizzazioni italiane
- 🇪🇺 5 Istituzioni ufficiali europee
- 🌍 5 Organizzazioni internazionali
- ✅ **AI Act Monitor** incluso in modo nativo

✅ Output: `data/raw/ong_sample.csv`
✅ Tempo: ~30 secondi
✅ Tutte le fonti sono elencate in modo pubblico e trasparente nel file stesso.

---

#### 🔹 2.3 Notizie Generali GNews
```bash
$env:GNEWS_API_KEY="la_tua_chiave"
python scrapers/scraper_gnews.py
```

✅ Cosa fa: Ricerca notizie su temi di diritti digitali su tutti i media italiani
✅ Output: `data/raw/gnews_sample.csv`

---

#### 🔹 2.4 Regolatori Europei
```bash
python scrapers/scraper_rss_eu.py
```

✅ Cosa fa: Monitora tutti i garanti privacy europei (EDPB, CNIL, ICO, AEPD)
✅ ✅ Automaticamente traduce tutti i testi in italiano
✅ Output: `data/raw/rss_eu_sample.csv`

---

### **Fase 3: Analisi Semantica NLP**
```bash
python nlp/text_analysis.py
```

✅ Questa è la parte intelligente del sistema:
1. 🧹 Pulisce il testo da rumore, link e duplicati
2. 🧠 Estrae automaticamente entità (aziende, persone, istituzioni)
3. 🗺️ Classifica l'ambito geografico di ogni provvedimento
4. 🏷️ Assegna categoria e livello di allarme
5. 💾 Salva tutto in database SQLite per velocità

✅ Output:
- `data/processed/gpdp_analyzed.csv`
- `data/tech_advocacy.db` (Database principale)

---

### **Fase 4: Dashboard e Visualizzazione**
```bash
python -m streamlit run app/dashboard.py
```

✅ La dashboard si aprirà automaticamente nel browser all'indirizzo `http://localhost:8501`

---

## 🕸️ Funzionalità Network Map

Questa è la caratteristica principale del progetto:

✅ **Come funziona**:
- Ogni ONG è un nodo rosso
- Ogni tema di cui si occupa è un nodo blu
- Ogni notizia è un nodo verde
- La **distanza tra i nodi** rappresenta la correlazione semantica
- Più due nodi sono vicini, più sono correlati semanticamente

✅ **Caratteristiche**:
- Stile brutalista minimalista, senza distrazioni
- Zoom bloccato per evitare di perdere il contesto
- Tutti i nodi sono draggabili
- Sistema di correzione manuale: puoi ricollegare una notizia ad un'altra ONG se l'AI ha sbagliato
- Le correzioni salvate vengono usate per migliorare le classificazioni future

✅ **Statistiche Network**:
- Numero organizzazioni monitorate
- Numero temi tracciati
- Numero notizie collegate
- Numero totale connessioni nel grafo

---

## 📍 Mappa di Posizionamento Cartesiano

✅ Nuova funzionalità aggiunta Aprile 2026:
- Tutte le ONG e le notizie sono posizionate su un piano cartesiano bidimensionale
- ✅ **Asse X (Orizzontale)**: Italia ↔ Mondo
- ✅ **Asse Y (Verticale)**: Legale ↔ Tecnico
- ✅ Normalizzazione automatica MIN-MAX per coprire tutta la scala
- ✅ Jitter leggero per separare punti sovrapposti
- ✅ Etichette permanenti gialle con freccia per OGNI ONG
- ✅ Stile uniforme Y2K brutalista con griglia viola e linee magenta
- ✅ Centroidi ONG calcolati come media di tutte le loro notizie
- ✅ Dimensione del punto proporzionale al numero di articoli pubblicati

---

##  Workflow Rapido End-to-End

Per eseguire TUTTO in sequenza con un solo comando:
```bash
python scrapers/scraper_ong.py && python scrapers/scraper_gpdp.py && python nlp/text_analysis.py && python -m streamlit run app/dashboard.py
```

---

## 🛠️ Sistema Human-In-The-Loop

Questo progetto non è completamente automatico per scelta:

✅ Puoi correggere qualsiasi classificazione sbagliata direttamente dalla dashboard
✅ Tutte le correzioni vengono salvate nel dataset di training
✅ Ad ogni ciclo il modello migliora automaticamente
✅ Non c'è black box: puoi vedere e modificare ogni decisione

---

## 📊 Metriche e Performance

| Metrica | Valore Attuale |
|---------|----------------|
| Fonti monitorate | 25 |
| Organizzazioni civiche | 18 |
| Istituzioni | 7 |
| Tempo ciclo completo | ~2 minuti |
| Deduplicazione NLP | -40% duplicati |
| Velocità dashboard | < 100ms |

---

## ❌ Troubleshooting Comuni

| Errore | Soluzione |
|--------|-----------|
| `ModuleNotFoundError` | Esegui `pip install -r requirements.txt` |
| `No module named 'scrapers'` | Usa `python -m streamlit run app/dashboard.py` invece di `streamlit run` |
| Errore timeout GPDP | Il sito è lento, attendi e riprova |
| Porta 8501 occupata | `streamlit run app/dashboard.py --server.port 8502` |
| Modello spaCy mancante | `python -m spacy download it_core_news_md` |

---

## 📅 Scheduling Automatico

Per aggiornare i dati automaticamente ogni giorno alle 8:00 di mattina:

1. Crea un file `daily_run.bat`:
```batch
@echo off
cd C:\percorso\alla\cartella\tech_advocacy_italia
python scrapers/scraper_ong.py
python scrapers/scraper_gpdp.py
python nlp/text_analysis.py
```

2. Aggiungilo a **Utilità di pianificazione** di Windows

---

## ✅ Checklist Funzionamento Corretto

- [ ] Tutti gli scraper terminano senza errori
- [ ] `text_analysis.py` non mostra warning
- [ ] SQLite database è presente in `data/tech_advocacy.db`
- [ ] Dashboard si apre correttamente
- [ ] Tutte e 5 le tab sono visibili
- [ ] Network Map si carica e mostra i nodi
- [ ] Mappa Posizionamento mostra punti e etichette ONG
- [ ] Le statistiche nella scheda Network mostrano numeri > 0

---

## 📚 Note Architetturali per Sviluppatori

- Nessuna dipendenza da servizi cloud
- Tutti i dati sono salvati localmente in open standard
- Tutti i modelli sono open source
- Nessuna telemetria
- Tutto il codice è auditabile riga per riga
- Le dipendenze sono fissate e versionate
- Nessun magic code: ogni passaggio è esplicito e loggato

---

> Questo progetto è progettato per essere trasparente, modificabile e affidabile. Non è ottimizzato per la velocità a tutti i costi, ma per essere comprensibile da chiunque.