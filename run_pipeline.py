import os
import subprocess
import sys
from dotenv import load_dotenv # Aggiungi questa riga

load_dotenv() # Aggiungi questa riga per caricare le chiavi dal file .env

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
        print(f"Error executing command: {e}")
        print(e.stderr)
        sys.exit(1)

def main():
    print("--- Starting Project Pipeline ---")
    
    # 1. Git Pull
    print("\n--- Updating from repository ---")
    run_command(["git", "pull"])
    
    # 2. Run Scrapers
    print("\n--- Running Scrapers ---")
    scrapers = [
        "scrapers/scraper_ong.py",
        "scrapers/scraper_gnews.py",
        "scrapers/scraper_gpdp.py",
        "scrapers/scraper_rss_eu.py"
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
    
    # 4. Git Push
    print("\n--- Committing and Pushing Updates ---")
    run_command(["git", "add", "."])
    # Ignore error if nothing to commit
    subprocess.run(["git", "commit", "-m", "chore: automated pipeline update"], capture_output=True)
    run_command(["git", "push"])
    
    # 5. Avvia Dashboard
    print("\n--- Avvio Dashboard ---")
    print("✅ Pipeline completata. Apertura dashboard in corso...")
    print("🌐 La dashboard sarà disponibile all'indirizzo: http://localhost:8501")
    print("⏳ Attendi 5 secondi...")
    
    # Lancia Streamlit in background SENZA catturare output (risolve il blocco su Windows)
    import subprocess
    import time
    
    time.sleep(3)
    
    # Avvia come processo separato indipendente
    subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app/dashboard.py", "--server.headless=false"],
        creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    print("\n--- Pipeline Completata con Successo ---")

if __name__ == "__main__":
    main()
