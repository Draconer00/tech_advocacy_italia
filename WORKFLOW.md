# 🔄 WORKFLOW: Pipeline Tech Advocacy Italy

Guida completa e ufficiale della pipeline di estrazione, analisi semantica, network analysis e visualizzazione.

Questo documento è valido sia per utenti non tecnici che per sviluppatori.
Aggiornato al 02/05/2026

---

## 🎯 Che cosa fa questo progetto

Questo sistema crea una mappa in tempo reale dell'ecosistema dei diritti digitali in Italia e Europa. Non è un semplice aggregatore di notizie:

✅ **Monitora** oltre 25 fonti ufficiali tra ONG, istituzioni europee e garanti
✅ **Analizza semanticamente** ogni documento con NLP
✅ **Crea relazioni** tra temi, organizzazioni e notizie
✅ **Visualizza** un network dinamico dove si vede chi parla di cosa
✅ **Permette correzioni umane** che migliorano continuamente il modello
✅ **✅ NUOVO: Storico permanente per sempre**: tutti i dati vengono mantenuti per sempre

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

✅ **✅ NOVITÀ: NESSUNA SOVRASCRITTURA**
✅ Tutti gli scraper adesso **NON CANCELLANO PIÙ NULLA**. Tutti i dati vengono aggiunti in append, deduplicati e mantenuti permanentemente.

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

✅ **✅ COMPORTAMENTO NUOVO:** Tutti gli scraper adesso usano lo stesso sistema di salvataggio permanente:
✅ Aggiunge i nuovi dati a quelli esistenti
✅ Deduplicazione automatica
✅ Non cancella niente
✅ Lo storico cresce per sempre

Ogni scraper è indipendente e produce dati standardizzati. Puoi eseguirli in qualsiasi ordine.

---

#### 🔹 2.1 Garante Privacy GPDP
```bash
python scrapers/scraper_gpdp.py
```

✅ **Cosa fa**: Estrae solamente provvedimenti ufficiali. **NON scarica comunicati stampa, notizie o annunci**.
✅ Output: `data/raw/gpdp_sample.csv`
✅ Tempo: ~1 minuto
✅ ✅ Storico permanente

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
✅ ✅ Storico permanente

---

#### 🔹 2.3 Notizie Generali GNews
```bash
$env:GNEWS_API_KEY="la_tua_chiave"
python scrapers/scraper_gnews.py
```

✅ Cosa fa: Ricerca notizie su temi di diritti digitali su tutti i media italiani
✅ Output: `data/raw/gnews_sample.csv`
✅ ✅ Storico permanente
✅ ✅ Rimosso limite 3 minuti: salva TUTTE le notizie trovate

---

#### 🔹 2.4 Regolatori Europei
```bash
python scrapers/scraper_rss_eu.py
```

✅ Cosa fa: Monitora tutti i garanti privacy europei (EDPB, CNIL, ICO, AEPD)
✅ ✅ Automaticamente traduce tutti i testi in italiano
✅ Output: `data/raw/rss_eu_sample.csv`
✅ ✅ Storico permanente

---

### **Fase 3: Analisi Semantica NLP**
```bash
python nlp/text_analysis.py
```

✅ Questa è la parte intelligente del sistema:
1. 🧹 Pulisce il testo da rumore, link e duplicati
2. 🧠 Estrae automaticamente entità (aziende, persone, istituzioni)
3. 🗺️ Classifica l'ambito geografico di ogni provvedimento
4. 🔗 Entity Linking: riconosce automaticamente quale ONG viene citata
5. 🤖 **Active Learning Livello 3**: Predice il livello di allarme 1-5 usando il modello che ha imparato dalle tue correzioni manuali
6. 💾 Salva tutto in database SQLite per velocità

✅ Elabora TUTTE le fonti automaticamente: Garante Privacy, ONG, GNews, RSS EU

✅ Output:
- `data/processed/gpdp_analyzed.csv`
- `data/processed/ong_analyzed.csv`
- `data/processed/gnews_analyzed.csv`
- `data/processed/rss_eu_analyzed.csv`
- `data/tech_advocacy.db` (Database principale unificato)

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

✅ **✅ NOVITÀ MAGGIO 2026**:
✅ Disposizione STABILE e SEMPRE LA STESSA ad ogni refresh
✅ Rimosso il caos dei nodi che si muovevano
✅ Seed fisso 42
✅ Solver forceAtlas2Based
✅ Nessuna sovrapposizione nodi

✅ **Caratteristiche**:
- Stile brutalista minimalista, senza distrazioni
- Zoom bloccato per evitare di perdere il contesto
- Tutti i nodi sono draggabili
- Sistema di correzione manuale: puoi ricollegare una notizia ad un'altra ONG se l'AI ha sbagliato
- Le correzioni salvate vengono usate per migliorare le classificazioni future

---

## 📍 Mappa di Posizionamento Cartesiano

✅ ✅ NOVITÀ MAGGIO 2026:
✅ Posizioni ONG **PERMANENTI e salvate in modo permanente
✅ Non si perdono più, non tornano più al centro
✅ Vengono aggiornate solamente quando ci sono nuovi dati
✅ Ogni ONG mantiene per sempre la sua posizione calcolata storicamente

✅ Funzionalità:
- Tutte le ONG e le notizie sono posizionate su un piano cartesiano bidimensionale
- ✅ **Asse X (Orizzontale)**: Italia ↔ Mondo
- ✅ **Asse Y (Verticale)**: Legale ↔ Tecnico
- ✅ Centroidi ONG calcolati come media di tutte le loro notizie
- ✅ Dimensione del punto proporzionale al numero di articoli pubblicati

---

## 🗄️ Database Manager

✅ **✅ NUOVA SCHEDA MAGGIO 2026:
✅ Pannello completo di gestione dati

✅ Funzionalità disponibili:
1.  📋 Visualizza tutte le tabelle e lo schema del database
2.  📊 Anteprima dati con filtri
3.  ⚡ Esegui query SQL dirette
4.  🗑️ **Pulizia dati manuale: cancella dati più vecchi di 7/30/90/180/365 giorni
5.  Backup automatico prima di ogni cancellazione

---

##  Workflow Rapido End-to-End

Per eseguire TUTTO in sequenza con un solo comando:
```bash
python run_pipeline.py
```

✅ ✅ NOVITÀ: Adesso la pipeline non si blocca più al primo errore, continua sempre fino alla fine e apre comunque la dashboard.

---

## 🛠️ Sistema Human-In-The-Loop

Questo progetto non è completamente automatico per scelta:

✅ Puoi correggere qualsiasi classificazione sbagliata direttamente dalla dashboard
✅ Tutte le correzioni vengono salvate nel Golden Standard
✅ **Ad ogni esecuzione della pipeline viene automaticamente addestrato un nuovo modello più accurato
✅ Il modello migliora in modo continuo in base alle tue correzioni
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
| ✅ Storico permanente | Sempre attivo |

---

## ❌ Troubleshooting Comuni

| Errore | Soluzione |
|--------|-----------|
| `ModuleNotFoundError` | Esegui `pip install -r requirements.txt` |
| `No module named 'scrapers'` | Usa `python -m streamlit run app/dashboard.py` invece di `streamlit run` |
| Errore timeout GPDP | Il sito è lento, attendi e riprova |
| Porta 8501 occupata | `streamlit run app/dashboard.py --server.port 8502` |
| Modello spaCy mancante | `python -m spacy download it_core_news_md` |
| ParserError CSV | Risolto automaticamente adesso, salta le righe malformate |
| Dashboard non si apre su Windows | Risolto, adesso si apre correttamente |
| ONG al centro nella mappa | Risolto, posizioni permanenti |

---

## 📅 Scheduling Automatico

✅ **Adesso compatibile al 100% con Github Actions e schedulazione automatica**

Per aggiornare i dati automaticamente ogni giorno:
```bash
python run_pipeline.py
```

✅ Tutti i dati verranno aggiunti automaticamente allo storico, nessuna perdita di dati, nessun conflitto.

---

## ✅ Checklist Funzionamento Corretto

- [ ] Tutti gli scraper terminano senza errori
- [ ] `text_analysis.py` non mostra warning
- [ ] SQLite database è presente in `data/tech_advocacy.db`
- [ ] Dashboard si apre correttamente
- [ ] Tutte le 6 tab sono visibili
- [ ] Network Map si carica e mostra i nodi
- [ ] Mappa Posizionamento mostra punti e etichette ONG
- [ ] Le posizioni delle ONG non cambiano più ad ogni refresh
- [ ] Il file `ong_posizioni_permanenti.csv` è stato creato

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