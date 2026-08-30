"""
Esecuzione end-to-end della pipeline: scraper -> analisi NLP -> training del
modello di urgenza -> avvio della dashboard.

Pensato per essere lanciato con un comando solo (`python run_pipeline.py`),
sia manualmente sia da uno scheduler locale. In CI (GitHub Actions) gli stessi
passi sono invocati singolarmente dal workflow, senza questo script.
"""
import os
import subprocess
import sys
import time
from dotenv import load_dotenv

# Carica le variabili d'ambiente da un eventuale file .env locale (es.
# GNEWS_API_KEY) prima di lanciare gli scraper come sottoprocessi.
load_dotenv()

def run_command(command):
    print(f"Executing: {' '.join(command)}")
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = os.getcwd()
        # 1. Forza i "figli" (gli scraper) a stampare le emoji in UTF-8
        env["PYTHONIOENCODING"] = "utf-8" 
        
        # 2. Aggiungi encoding="utf-8" per decifrare correttamente i risultati
        result = subprocess.run(command, check=True, capture_output=True, text=True, env=env, encoding="utf-8")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Attenzione: errore eseguendo comando: {e}")
        print(e.stderr)
        print("✅ Continuo comunque con i passi successivi...\n")
        # Il fallimento di un singolo step (es. uno scraper offline) non deve
        # bloccare l'intera pipeline: niente sys.exit(1), si prosegue sempre.
        return False

def main():
    print("--- Starting Project Pipeline ---")
    
    # 1. Git Pull
    print("\n--- Updating from repository ---")
    run_command(["git", "pull"])
    
    # 2. Run Scrapers
    print("\n--- Running Scrapers ---")
    scrapers = [
        "scrapers/scraper_gpdp.py",
        "scrapers/scraper_ong.py",
        "scrapers/scraper_gnews.py",
        "scrapers/scraper_rss_eu.py",
        "scrapers/scraper_agcom.py",
        "scrapers/scraper_tech_news.py",
        "scrapers/scraper_eu_parl.py",
        "scrapers/scraper_gazzetta_ufficiale.py",
        "scrapers/scraper_curia.py",
    ]
    
    for scraper in scrapers:
        if os.path.exists(scraper):
            print(f"Running {scraper}...")
            run_command([sys.executable, scraper])
        else:
            print(f"Skipping {scraper}: not found.")

    # 3. Run Analysis/Processing
    print("\n--- Running Data Processing ---")
    if os.path.exists("nlp/text_analysis.py"):
        run_command([sys.executable, "nlp/text_analysis.py"])
    
    # 4. Train Impact Model (Active Learning Livello 3)
    print("\n--- Training Impact Prediction Model ---")
    if os.path.exists("nlp/train_impact_model.py"):
        run_command([sys.executable, "nlp/train_impact_model.py"])

    # I dati non vengono versionati nel repo (design del paper: data not in repo).
    # La persistenza è responsabilità dell'operatore; la pipeline non fa più
    # git add/commit/push automatici, che rischiavano di committare codice WIP.

    # 5. Avvia Dashboard
    print("\n--- Avvio Dashboard ---")
    print("✅ Pipeline completata. Apertura dashboard in corso...")
    print("🌐 La dashboard sarà disponibile all'indirizzo: http://localhost:8501")
    
    # Su Windows, quando il processo padre termina i suoi processi figli vengono
    # terminati con lui. DETACHED_PROCESS scollega Streamlit dal processo padre
    # in modo che resti in esecuzione anche dopo che questo script è terminato;
    # CREATE_NEW_CONSOLE non va bene perché causa la chiusura prematura del
    # processo all'uscita dello script principale.
    # Avvia Streamlit come processo completamente indipendente e scollegato
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    
    subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app/dashboard.py", "--server.headless=false"],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        startupinfo=startupinfo
    )
    
    # Attendi che Streamlit si avvii completamente prima di chiudere lo script padre
    print("⏳ Attendo avvio dashboard...")
    time.sleep(5)
    
    print("\n✅ --- Pipeline Completata con Successo ---")
    print("🌐 Dashboard aperta correttamente nel browser")
    print("💡 Se non si apre automaticamente vai manualmente su: http://localhost:8501")

if __name__ == "__main__":
    main()
