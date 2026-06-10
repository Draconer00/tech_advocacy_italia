"""
Entity linking: associa un documento alla ONG monitorata più pertinente.

Metodo descritto nel paper (Sez. 2.6, step 5 "Entity Linking"): per ogni
documento si conta quante focus-keyword del profilo di ciascuna ONG compaiono
nel testo; vince la ONG con l'overlap più alto. Una menzione esplicita del nome
(o del suo acronimo) vale come segnale forte aggiuntivo. È un approccio leggero,
interpretabile e correggibile a mano tramite la dashboard.

Questo è l'UNICO punto in cui il linking è definito: sia la pipeline NLP
(text_analysis) sia la dashboard (tab Network) lo richiamano, così l'algoritmo
resta identico ovunque.
"""
import re


def _nome_base(nome_ong: str) -> str:
    """Nome ONG senza parte tra parentesi: 'Noyb (Privacy UE)' -> 'noyb'."""
    return re.sub(r"\(.*?\)", "", nome_ong).strip().lower()


def punteggio_ong(testo_lower: str, nome_ong: str, dati_ong: dict) -> int:
    """Punteggio di pertinenza di una singola ONG per un testo (già in minuscolo)."""
    score = sum(
        1
        for kw in dati_ong.get("focus", [])
        if kw and kw.lower() in testo_lower
    )
    # Menzione esplicita del nome o dell'acronimo = segnale forte (+2).
    # Match su confine di parola: evita falsi positivi come l'acronimo "isc"
    # (Italiani Senza Cittadinanza) che altrimenti combacerebbe dentro "discute".
    nome_base = _nome_base(nome_ong)
    if nome_base and re.search(rf"\b{re.escape(nome_base)}\b", testo_lower):
        score += 2
    else:
        parole = [p for p in nome_base.split() if p]
        if len(parole) >= 2:
            acronimo = "".join(p[0] for p in parole)
            if len(acronimo) >= 2 and re.search(rf"\b{re.escape(acronimo)}\b", testo_lower):
                score += 2
    return score


def link_ong(testo: str, profili: dict | None = None, return_score: bool = False):
    """
    Restituisce il nome della ONG più pertinente al testo (o "" se nessuna).

    Se return_score=True restituisce la tupla (nome_ong, punteggio): un punteggio
    basso (es. <2) indica un linking a bassa confidenza, da trattare come stima.
    """
    if profili is None:
        from scrapers.scraper_ong import PROFILI_ONG
        profili = PROFILI_ONG

    testo_lower = str(testo).lower()
    migliore = ""
    punteggio_massimo = 0
    for nome_ong, dati_ong in profili.items():
        score = punteggio_ong(testo_lower, nome_ong, dati_ong)
        if score > punteggio_massimo:
            punteggio_massimo = score
            migliore = nome_ong

    return (migliore, punteggio_massimo) if return_score else migliore
