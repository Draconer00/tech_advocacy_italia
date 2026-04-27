import pandas as pd
import os
import sys
sys.path.append('.')
from nlp.text_analysis import calcola_score_posizionamento


def calcola_metriche():
    """
    Calcola le metriche di errore reale del modello di classificazione
    usando il Gold Standard delle correzioni fatte manualmente sulla dashboard.
    
    Questa è l'unica metrica onesta che ti dice quanto sbaglia veramente il modello.
    """
    
    percorso_feedback = os.path.join('data', 'processed', 'training_data_feedback.csv')
    
    if not os.path.exists(percorso_feedback):
        print("❌ Nessuna correzione salvata ancora.")
        print("💡 Usa il sistema di correzione sulla scheda Home della dashboard per aggiungere almeno 10 correzioni.")
        return

    df_gold = pd.read_csv(percorso_feedback)
    
    if len(df_gold) < 10:
        print(f"⚠️ Hai solo {len(df_gold)} correzioni.")
        print("   Per una misurazione significativa servono almeno 10 correzioni.")
        print("   Continua ad etichettare :)")
        return

    errori = []
    classificazione_corretta = 0

    print(f"\n📊 CALCOLO ERRORE REALE MODELLO")
    print(f"=================================")
    print(f"Numero esempi nel Gold Standard: {len(df_gold)}")
    print(f"\n")

    for idx, row in df_gold.iterrows():
        # Fai predire al modello lo stesso testo
        pred_tech, pred_geo = calcola_score_posizionamento(row['titolo'])
        
        errore_geo = abs(pred_geo - float(row.get('score_geografia', 0)))
        errore_tech = abs(pred_tech - float(row.get('score_tech_legale', 0)))
        
        # Contiamo come corretto se errore < 0.2
        if errore_geo < 0.2 and errore_tech < 0.2:
            classificazione_corretta += 1
        
        errori.append({
            'indice': idx,
            'titolo': row['titolo'][:60] + "...",
            'errore_geografia': errore_geo,
            'errore_tecnico': errore_tech
        })

    df_errori = pd.DataFrame(errori)

    print(f"✅ ACCURATEZZA GENERALE: {classificazione_corretta / len(df_gold) * 100:.1f} %")
    print(f"\n")
    print(f"📏 Errore medio Asse Geografia (Italia ↔ Mondo):  {df_errori['errore_geografia'].mean():.3f}")
    print(f"📏 Errore medio Asse Tipologico (Legale ↔ Tecnico): {df_errori['errore_tecnico'].mean():.3f}")
    print(f"\n")
    print(f"💡 Valori eccellenti: < 0.10")
    print(f"💡 Valori buoni:      < 0.15")
    print(f"💡 Valori da migliorare: > 0.25")
    print(f"\n")
    print(f"🔝 5 errori PEGGIORI:")
    print(f"----------------------")
    
    peggiori = df_errori.sort_values('errore_geografia', ascending=False).head(5)
    
    for _, r in peggiori.iterrows():
        print(f"❌ {r['errore_geografia']:.2f} | {r['titolo']}")
    
    print(f"\n")
    print("💡 Queste sono le notizie su cui il modello sbaglia di più.")
    print("   Correggile nella dashboard e il modello migliorerà automaticamente.")


if __name__ == "__main__":
    calcola_metriche()