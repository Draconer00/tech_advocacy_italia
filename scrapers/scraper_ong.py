import feedparser
import pandas as pd
import os
import hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ✅ DIZIONARIO PROFILI ORGANIZZAZIONI
# Ogni ONG può autodefinirsi e aggiungere la propria descrizione
# Questo file è pubblico e trasparente, chiunque può proporre modifiche via PR
PROFILI_ONG = {
    "Privacy Network": {
        "tipo_organizzazione": "Associazione Advocacy",
        "area_geografica": "Italia",
        "descrizione": "Associazione italiana per la tutela della privacy e dei diritti digitali",
        "focus": ["dati personali", "sorveglianza", "intelligenza artificiale"],
        "url_sito": "https://privacynetwork.it"
    },
    "Noyb (Privacy UE)": {
        "tipo_organizzazione": "Organizzazione Legale",
        "area_geografica": "Unione Europea",
        "descrizione": "Organizzazione europea che porta avanti casi legali e strategie per applicare il GDPR",
        "focus": ["GDPR", "multate", "contenziosi strategici"],
        "url_sito": "https://noyb.eu"
    },
    "EDRi (Europa)": {
        "tipo_organizzazione": "Rete Europea",
        "area_geografica": "Europa",
        "descrizione": "Rete di oltre 40 organizzazioni che difendono i diritti digitali in UE",
        "focus": ["policy europea", "diritti civili", "regolamentazione"],
        "url_sito": "https://edri.org"
    },
    "AlgorithmWatch": {
        "tipo_organizzazione": "Organizzazione di Ricerca",
        "area_geografica": "Internazionale",
        "descrizione": "Monitora e valuta l'impatto sociale degli algoritmi e dell'intelligenza artificiale",
        "focus": ["auditing algoritmico", "trasparenza IA"],
        "url_sito": "https://algorithmwatch.org"
    },
    "Hermes Center": {
        "tipo_organizzazione": "Centro Ricerca",
        "area_geografica": "Italia",
        "descrizione": "Centro internazionale studi su sicurezza informatica e diritti digitali",
        "focus": ["crittografia", "anonimato", "censura"],
        "url_sito": "https://hermescenter.org"
    },
    "AI Forensics": {
        "tipo_organizzazione": "Organizzazione di Ricerca",
        "area_geografica": "Internazionale",
        "descrizione": "Organizzazione indipendente che investiga e audita sistemi di intelligenza artificiale",
        "focus": ["audit IA", "trasparenza algoritmica", "responsabilità AI"],
        "url_sito": "https://aiforensics.org"
    },
    "Slow Web": {
        "tipo_organizzazione": "Associazione Advocacy",
        "area_geografica": "Italia",
        "descrizione": "Movimento per un web più umano, sostenibile e rispettoso delle persone",
        "focus": ["decentralizzazione", "etica digitale", "sostenibilità"],
        "url_sito": "https://slow-web.it"
    },
    "NINA": {
        "tipo_organizzazione": "Progetto Culturale",
        "area_geografica": "Italia",
        "descrizione": "Not Intelligent Not Artificial - Critica e analisi sull'intelligenza artificiale",
        "focus": ["critica IA", "filosofia tecnologica"],
        "url_sito": "https://ninabot.org"
    },
    "The Good Lobby Italia": {
        "tipo_organizzazione": "Organizzazione Advocacy",
        "area_geografica": "Italia",
        "descrizione": "Formazione e attivismo per la partecipazione democratica e il lobbying civico",
        "focus": ["democrazia", "trasparenza istituzionale"],
        "url_sito": "https://thegoodlobby.it"
    },
    "Amnesty Italia": {
        "tipo_organizzazione": "Organizzazione Diritti Umani",
        "area_geografica": "Italia",
        "descrizione": "Sezione italiana di Amnesty International per la difesa dei diritti umani",
        "focus": ["diritti umani", "giustizia"],
        "url_sito": "https://amnesty.it"
    },
    "Antigone": {
        "tipo_organizzazione": "Associazione",
        "area_geografica": "Italia",
        "descrizione": "Associazione per i diritti e le garanzie nel sistema penitenziario",
        "focus": ["carceri", "giustizia penale"],
        "url_sito": "https://antigone.it"
    },
    "Italiani Senza Cittadinanza": {
        "tipo_organizzazione": "Rete Advocacy",
        "area_geografica": "Italia",
        "descrizione": "Rete per i diritti dei migranti e la cittadinanza universale",
        "focus": ["cittadinanza", "migrazioni"],
        "url_sito": "https://italianisenzacittadinanza.it"
    },
    "SOMO (Multinazionali)": {
        "tipo_organizzazione": "Centro Ricerca",
        "area_geografica": "Internazionale",
        "descrizione": "Organizzazione che monitora l'impatto delle multinazionali sui diritti umani",
        "focus": ["corporate accountability", "diritti economici"],
        "url_sito": "https://somo.nl"
    },
    "STRALI": {
        "tipo_organizzazione": "Centro Studi",
        "area_geografica": "Italia",
        "descrizione": "Studi e ricerche su lavoro, diritti e trasformazioni sociali",
        "focus": ["lavoro", "economia"],
        "url_sito": "https://strali.org"
    }
}


def _classifica_livello_allarme(titolo: str) -> int:
    """Assegna livello allarme 0-3 in base al contenuto"""
    titolo_low = titolo.lower()
    
    parole_allarme_alto = ["multa", "causa", "citazione", "campagna", "azione legale", "denuncia"]
    parole_allarme_medio = ["report", "analisi", "posizione", "comunicato", "studio"]
    
    if any(p in titolo_low for p in parole_allarme_alto):
        return 3
    elif any(p in titolo_low for p in parole_allarme_medio):
        return 2
    else:
        return 1


def scrape_comunicati_ong():
    """
    Estrae le ultime campagne dai feed RSS delle principali ONG 
    italiane ed europee (Tech Advocacy e Diritti Umani).
    ✅ Profilo ogni organizzazione pubblica e modificabile da tutti
    """
    # Il nostro Radar espanso
    fonti_ong = {
        # --- Core Tech Advocacy & Privacy ---
        "Privacy Network": "https://www.privacynetwork.it/feed/",
        "Hermes Center": "https://www.hermescenter.org/feed/",
        "EDRi (Europa)": "https://edri.org/feed/",
        "Noyb (Privacy UE)": "https://noyb.eu/en/rss.xml",
        "AlgorithmWatch": "https://algorithmwatch.org/en/feed/",
        "AI Forensics": "https://aiforensics.org/feed.xml",
        "Slow Web": "https://www.slow-web.it/feed/",
        "NINA": "https://ninabot.org/feed/", # Not Intelligent Not Artificial
        
        # --- Diritti Civili, Sociali & Trasparenza ---
        "The Good Lobby Italia": "https://www.thegoodlobby.it/feed/",
        "Amnesty Italia": "https://www.amnesty.it/feed/",
        "Antigone": "https://www.antigone.it/news?format=feed&type=rss",
        "Italiani Senza Cittadinanza": "https://italianisenzacittadinanza.it/feed/",
        "SOMO (Multinazionali)": "https://www.somo.nl/feed/",
        "STRALI": "https://www.strali.org/blog-feed.xml" 
    }
    
    tutte_le_notizie = []

    print(f"✅ Avvio scraping parallelo {len(fonti_ong)} fonti ONG...")

    # ✅ PARALLELIZZAZIONE FEED RSS
    def processa_fonte(nome_ong, url_feed):
        try:
            feed = feedparser.parse(url_feed)
            risultati = []

            for entry in feed.entries:
                testo_completo = f"{entry.title} {getattr(entry, 'summary', '')}"
                hash_contenuto = hashlib.sha256(testo_completo.encode('utf-8')).hexdigest()
                
                profilo = PROFILI_ONG.get(nome_ong, {
                    "tipo_organizzazione": "Generico",
                    "area_geografica": "Non specificato"
                })

                risultati.append({
                    'id_univoco': hash_contenuto,
                    'fonte': 'ong',
                    'nome_organizzazione': nome_ong,
                    'tipo_organizzazione': profilo.get('tipo_organizzazione'),
                    'area_geografica': profilo.get('area_geografica'),
                    'descrizione_organizzazione': profilo.get('descrizione', ''),
                    'data_pubblicazione': getattr(entry, 'published', datetime.now().date().isoformat()),
                    'data_scraping': datetime.now().isoformat(),
                    'titolo': entry.title,
                    'url': entry.link,
                    'tipo_contenuto': 'comunicato',
                    'livello_allarme': _classifica_livello_allarme(entry.title),
                    'lingua': 'it',
                    'testo_completo': testo_completo,
                    'hash_contenuto': hash_contenuto
                })
            
            print(f"✅ {nome_ong}: {len(risultati)} comunicati scaricati")
            return risultati

        except Exception as e:
            print(f"❌ Errore {nome_ong}: {str(e)}")
            return []


    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [
            executor.submit(processa_fonte, nome, url)
            for nome, url in fonti_ong.items()
        ]

        for future in as_completed(futures):
            tutte_le_notizie.extend(future.result())

    df_ong = pd.DataFrame(tutte_le_notizie)
    print(f"\n✅ Completato! Raccolti {len(df_ong)} comunicati totali dalla società civile.")
    return df_ong

# Esecuzione di test
if __name__ == "__main__":
    df_test = scrape_comunicati_ong()
    
    if not df_test.empty:
        # --- SOLUZIONE DEL PERCORSO ANONIMO E UNIVERSALE ---
        # 1. Trova la cartella esatta dove si trova questo file (scraper_ong.py)
        cartella_script = os.path.dirname(os.path.abspath(__file__))
        
        # 2. Torna indietro di un livello e vai in data/raw
        cartella_raw = os.path.join(cartella_script, '..', 'data', 'raw')
        
        # 3. Assicurati che esista
        os.makedirs(cartella_raw, exist_ok=True)
        
        # 4. Unisci il nome del file
        percorso_salvataggio = os.path.join(cartella_raw, 'ong_sample.csv')
        
        # Salviamo il CSV
        df_test.to_csv(percorso_salvataggio, index=False)
        
        print("\nPrime 3 righe estratte:")
        print(df_test.head(3))
        print(f"\nDati salvati in modo sicuro in: {percorso_salvataggio}")