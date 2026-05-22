"""
scraper_gdpr_fines.py
=====================
Importa il dataset mondiale di sanzioni GDPR da due fonti pubbliche:

  1. enforcementtracker.com  (CMS Law) — dati JSON embedded nella pagina
  2. GDPRhub MediaWiki API  (noyb)     — API pubblica strutturata

Strategia:
- Tenta la fonte 1; se fallisce salva uno snapshot HTML e passa alla fonte 2.
- Normalizza entrambe le fonti nello schema unificato del progetto.
- Appende a data/raw/gdpr_fines_sample.csv con deduplicazione per hash_contenuto.
- Non sovrascrive mai i dati storici.
- Tutti i fallimenti vengono loggati; nessuna riga viene scartata silenziosamente.

Licenza dataset:
  - enforcementtracker.com: dati pubblici, nessuna licenza esplicita restrittiva
  - GDPRhub: CC BY-SA 4.0
  - noyb/gdpr-enforcement-database (GitHub): CC0

Riferimento progetto: FONTI_AGGIUNTIVE.md riga 14.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Path setup — consente import da root progetto
# ---------------------------------------------------------------------------
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from utils.logger_config import setup_logger

logger = setup_logger(__name__)

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------
FONTE_LABEL = "GDPR Fines - enforcementtracker/gdprhub"

OUTPUT_RAW      = os.path.join(_ROOT, "data", "raw", "gdpr_fines_sample.csv")
SNAPSHOT_DIR    = os.path.join(_ROOT, "data", "raw", "snapshots")

# enforcementtracker.com — la pagina principale carica i dati via DataTables
ET_URL          = "https://www.enforcementtracker.com/"
ET_JSON_URL     = "https://www.enforcementtracker.com/?export"  # fallback spesso ritorna JSON

# GDPRhub MediaWiki API — endpoint pubblico senza autenticazione
GDPRHUB_API      = "https://gdprhub.eu/api.php"
GDPRHUB_TEMPLATE = "Template:DPAdecisionBOX"  # template usato da tutte le decisioni DPA

REQUEST_TIMEOUT = 15
MAX_RETRIES     = 3
RETRY_DELAY     = 4   # secondi tra i tentativi

HEADERS = {
    "User-Agent": (
        "TechAdvocacyItaliaBot/1.0 "
        "(open-source civic intelligence; "
        "https://github.com/tech-advocacy-italia; "
        "non-commercial research)"
    ),
    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _crea_sessione() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def _richiesta_con_retry(
    session: requests.Session,
    url: str,
    metodo: str = "GET",
    params: dict | None = None,
    n_retry: int = MAX_RETRIES,
) -> requests.Response | None:
    """Esegue la richiesta con retry esponenziale; restituisce None su fallimento definitivo."""
    for tentativo in range(1, n_retry + 1):
        try:
            logger.debug("Richiesta %s %s (tentativo %d/%d)", metodo, url, tentativo, n_retry)
            risposta = session.request(metodo, url, params=params, timeout=REQUEST_TIMEOUT)
            risposta.raise_for_status()
            return risposta
        except requests.exceptions.Timeout:
            logger.warning("Timeout su %s (tentativo %d/%d)", url, tentativo, n_retry)
        except requests.exceptions.HTTPError as e:
            logger.warning("HTTP %s su %s (tentativo %d/%d): %s", e.response.status_code, url, tentativo, n_retry, e)
            if e.response.status_code in (403, 404, 410):
                # Errori permanenti: inutile riprovare
                break
        except requests.exceptions.ConnectionError as e:
            logger.warning("Connessione fallita %s (tentativo %d/%d): %s", url, tentativo, n_retry, e)
        if tentativo < n_retry:
            attesa = RETRY_DELAY * tentativo
            logger.info("Attendo %d s prima del prossimo tentativo...", attesa)
            time.sleep(attesa)
    logger.error("Fallimento definitivo per %s dopo %d tentativi", url, n_retry)
    return None


def _salva_snapshot(contenuto: bytes | str, nome: str) -> str:
    """Salva snapshot HTML/JSON in data/raw/snapshots/ per debugging."""
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    percorso = os.path.join(SNAPSHOT_DIR, f"{nome}_{timestamp}.html")
    if isinstance(contenuto, bytes):
        with open(percorso, "wb") as f:
            f.write(contenuto)
    else:
        with open(percorso, "w", encoding="utf-8") as f:
            f.write(contenuto)
    logger.info("Snapshot salvato: %s", percorso)
    return percorso


def _genera_id(titolo: str, data: str, fonte: str) -> str:
    """SHA-256 di titolo+data+fonte come ID univoco."""
    chiave = f"{titolo}|{data}|{fonte}"
    return hashlib.sha256(chiave.encode("utf-8")).hexdigest()


def _genera_hash_contenuto(testo: str) -> str:
    """SHA-256 del testo completo."""
    return hashlib.sha256(str(testo).encode("utf-8")).hexdigest()


def _normalizza_importo(valore_raw: Any) -> float | None:
    """
    Converte importi GDPR in float EUR.
    Gestisce formati europei (1.200.000 / 30.000) e americani (1,200,000 / 30,000).
    Logica: se ci sono punti seguiti da 3 cifre → punti = separatori migliaia.
            se ci sono virgole seguite da 3 cifre → virgole = separatori migliaia.
            altrimenti virgola = decimale.
    """
    if valore_raw is None:
        return None
    testo = str(valore_raw).replace("\xa0", " ").strip()
    testo = re.sub(r"[€$£\s]", "", testo)
    if not testo:
        return None
    try:
        if re.search(r'\.\d{3}', testo):
            # Formato europeo: 1.200.000 o 30.000 → rimuovi punti, virgola=decimale
            testo = testo.replace(".", "").replace(",", ".")
        elif re.search(r',\d{3}', testo):
            # Formato americano: 1,200,000 o 30,000 → rimuovi virgole
            testo = testo.replace(",", "")
        else:
            # Solo decimale: 30,5 → 30.5
            testo = testo.replace(",", ".")
        return float(testo)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Fonte 1: enforcementtracker.com
# ---------------------------------------------------------------------------

def _parse_et_json(dati_json: list[dict]) -> list[dict]:
    """
    Normalizza i record JSON di enforcementtracker.com allo schema unificato.

    Colonne attese (DataTables):
      ET-Id, Country, Authority, Date, QuotedArticles, Type, Fine,
      Controller/Processor, Summary, Source, Sector, Notes
    """
    record_normalizzati = []
    for riga in dati_json:
        # Gestisci sia chiavi con trattino che con underscore/spazio
        azienda = (
            riga.get("Controller/Processor")
            or riga.get("controller_processor")
            or riga.get("controller")
            or ""
        )
        paese = riga.get("Country", "")
        autorita = riga.get("Authority", "")
        data_raw = riga.get("Date", "")
        importo_raw = riga.get("Fine", riga.get("fine", ""))
        sommario = riga.get("Summary", riga.get("summary", ""))
        link = riga.get("Source", riga.get("source", ""))
        articoli = riga.get("QuotedArticles", riga.get("quoted_articles", ""))
        tipo = riga.get("Type", riga.get("type", ""))
        et_id = riga.get("ET-Id", riga.get("et_id", ""))

        titolo = f"[{paese}] {azienda} – {autorita}"
        if not azienda and not autorita:
            titolo = f"Sanzione GDPR {et_id} – {paese}"

        testo_completo = (
            f"{titolo}. "
            f"Articoli violati: {articoli}. "
            f"Tipo: {tipo}. "
            f"Sommario: {sommario}"
        ).strip()

        importo_eur = _normalizza_importo(importo_raw)

        hash_contenuto = _genera_hash_contenuto(testo_completo)
        id_univoco = _genera_id(titolo, str(data_raw), "enforcementtracker")

        record_normalizzati.append({
            # --- Schema unificato obbligatorio ---
            "id_univoco":          id_univoco,
            "hash_contenuto":      hash_contenuto,
            "titolo":              titolo,
            "testo_completo":      testo_completo,
            "data_pubblicazione":  data_raw,
            "fonte":               FONTE_LABEL,
            "link":                link,
            "ente_origine":        autorita,
            # --- Campi extra GDPR fines ---
            "paese":               paese,
            "importo_eur":         importo_eur,
            "azienda_sanzionata":  azienda,
            "tipo_violazione":     tipo,
            # --- Metadati di scraping ---
            "data_scraping":       datetime.now().isoformat(),
            "fonte_tecnica":       "enforcementtracker.com",
        })
    return record_normalizzati


def fetch_enforcementtracker(session: requests.Session) -> list[dict]:
    """
    Scarica i dati da enforcementtracker.com.

    Il sito carica i record GDPR tramite DataTables; il JSON è spesso
    incorporato inline nella pagina HTML o disponibile via richiesta XHR.
    Tentiamo:
      1. GET con Accept: application/json (alcuni server rispondono con JSON)
      2. Parsing dell'HTML per trovare l'array inline
    """
    logger.info("Tentativo fetch enforcementtracker.com...")

    # Tentativo 1: header JSON esplicito
    session_json = _crea_sessione()
    session_json.headers.update({"Accept": "application/json"})
    risposta = _richiesta_con_retry(session_json, ET_URL)

    if risposta is not None:
        ct = risposta.headers.get("Content-Type", "")
        if "application/json" in ct or risposta.text.lstrip().startswith("["):
            try:
                dati = risposta.json()
                if isinstance(dati, list) and len(dati) > 0:
                    logger.info("JSON diretto da enforcementtracker: %d record", len(dati))
                    return _parse_et_json(dati)
            except json.JSONDecodeError:
                pass

        # Tentativo 2: parsing HTML per array JSON inline
        try:
            soup = BeautifulSoup(risposta.content, "html.parser")
            for script in soup.find_all("script"):
                testo_script = script.string or ""
                # DataTables di solito inietta i dati come: var data = [...]
                # oppure come: "data": [...]
                match = re.search(r'"data"\s*:\s*(\[.*?\])\s*[,}]', testo_script, re.DOTALL)
                if not match:
                    match = re.search(r'var\s+\w*[Dd]ata\s*=\s*(\[.*?\]);', testo_script, re.DOTALL)
                if match:
                    try:
                        dati = json.loads(match.group(1))
                        if isinstance(dati, list) and len(dati) > 0:
                            logger.info(
                                "JSON estratto da HTML enforcementtracker: %d record", len(dati)
                            )
                            return _parse_et_json(dati)
                    except json.JSONDecodeError as e:
                        logger.warning("JSON non parsabile da script tag: %s", e)
        except Exception as e:
            logger.warning("Errore parsing HTML enforcementtracker: %s", e)

        # Fallimento: salva snapshot per diagnosi
        logger.warning("Dati non trovati in enforcementtracker.com — salvo snapshot")
        _salva_snapshot(risposta.content, "enforcementtracker_fallback")

    logger.warning("Fonte enforcementtracker.com non disponibile — passo a GDPRhub")
    return []


# ---------------------------------------------------------------------------
# Fonte 2: GDPRhub MediaWiki API (noyb)
# ---------------------------------------------------------------------------

def _parse_gdprhub_page(titolo_pagina: str, session: requests.Session) -> dict | None:
    """
    Recupera i dati strutturati di una singola pagina GDPRhub tramite
    l'API MediaWiki (action=parse) e le proprietà Semantic MediaWiki.
    """
    params = {
        "action": "parse",
        "page": titolo_pagina,
        "prop": "wikitext",
        "format": "json",
    }
    risposta = _richiesta_con_retry(session, GDPRHUB_API, params=params, n_retry=2)
    if risposta is None:
        logger.warning("Impossibile leggere pagina GDPRhub: %s", titolo_pagina)
        return None

    try:
        dati = risposta.json()
        wikitext = dati.get("parse", {}).get("wikitext", {}).get("*", "")
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Errore parse JSON GDPRhub per %s: %s", titolo_pagina, e)
        return None

    # Estrai campi dal template MediaWiki
    # Formato tipico: | Fine = 5000 | Country = Germany | ...
    def _estrai_campo(testo: str, campo: str) -> str:
        match = re.search(
            rf"\|\s*{re.escape(campo)}\s*=\s*([^\|\}}\n]+)", testo, re.IGNORECASE
        )
        return match.group(1).strip() if match else ""

    # Nomi campo reali del template DPAdecisionBOX (verificati su wikitext)
    paese         = _estrai_campo(wikitext, "Jurisdiction")
    autorita      = _estrai_campo(wikitext, "DPA_With_Country") or _estrai_campo(wikitext, "DPA_Abbrevation")
    azienda       = _estrai_campo(wikitext, "Party_Name_1")
    importo_raw   = _estrai_campo(wikitext, "Fine")
    valuta        = _estrai_campo(wikitext, "Currency") or "EUR"
    data_raw      = _estrai_campo(wikitext, "Date_Published") or _estrai_campo(wikitext, "Date_Decided") or _estrai_campo(wikitext, "Year")
    tipo          = _estrai_campo(wikitext, "Type")
    articoli      = _estrai_campo(wikitext, "GDPR_Article_1")
    link_source   = _estrai_campo(wikitext, "Original_Source_Link_1")
    link_pagina   = f"https://gdprhub.eu/index.php?title={titolo_pagina.replace(' ', '_')}"

    # Estrai il testo narrativo (fuori dal template, dopo "}}")
    pos_fine_template = wikitext.find("}}")
    sommario = wikitext[pos_fine_template + 2:pos_fine_template + 500].strip() if pos_fine_template != -1 else ""
    sommario = re.sub(r"\s+", " ", sommario)

    titolo = f"[{paese}] {azienda} – {autorita}".strip(" –")
    if not azienda and not autorita:
        titolo = titolo_pagina

    testo_completo = (
        f"{titolo}. "
        f"Articoli: {articoli}. "
        f"Tipo: {tipo}. "
        f"Sommario: {sommario}"
    ).strip()

    importo_eur = _normalizza_importo(importo_raw)
    hash_contenuto = _genera_hash_contenuto(testo_completo)
    id_univoco = _genera_id(titolo, str(data_raw), "gdprhub")

    return {
        "id_univoco":          id_univoco,
        "hash_contenuto":      hash_contenuto,
        "titolo":              titolo,
        "testo_completo":      testo_completo,
        "data_pubblicazione":  data_raw,
        "fonte":               FONTE_LABEL,
        "link":                link_source or link_pagina,
        "ente_origine":        autorita,
        "paese":               paese,
        "importo_eur":         importo_eur,
        "azienda_sanzionata":  azienda,
        "tipo_violazione":     tipo,
        "data_scraping":       datetime.now().isoformat(),
        "fonte_tecnica":       "gdprhub.eu",
    }


def fetch_gdprhub(session: requests.Session, max_pagine: int = 100) -> list[dict]:
    """
    Scarica le decisioni DPA da GDPRhub via API MediaWiki.
    Usa embeddedin sul Template:DPAdecisionBOX per elencare tutte le pagine
    che usano quel template, poi legge ogni pagina individualmente.
    """
    logger.info("Tentativo fetch GDPRhub API (max %d pagine)...", max_pagine)
    record_grezzi = []

    # 1. Elenca le pagine che incorporano il template DPAdecisionBOX
    params_lista: dict[str, Any] = {
        "action": "query",
        "list": "embeddedin",
        "eititle": GDPRHUB_TEMPLATE,
        "eilimit": "50",
        "einamespace": "0",
        "format": "json",
    }

    pagine_trovate: list[dict] = []
    continua = True
    while continua and len(pagine_trovate) < max_pagine:
        risposta = _richiesta_con_retry(session, GDPRHUB_API, params=params_lista)
        if risposta is None:
            logger.error("Impossibile elencare pagine GDPRhub con template %s", GDPRHUB_TEMPLATE)
            _salva_snapshot(b"", "gdprhub_embeddedin_fail")
            break
        try:
            dati = risposta.json()
        except json.JSONDecodeError as e:
            logger.error("Errore JSON GDPRhub embeddedin: %s", e)
            _salva_snapshot(risposta.content, "gdprhub_embeddedin_error")
            break

        membri = dati.get("query", {}).get("embeddedin", [])
        pagine_trovate.extend(membri)
        logger.debug("GDPRhub: %d pagine trovate finora", len(pagine_trovate))

        continua_token = dati.get("continue", {})
        if continua_token and len(pagine_trovate) < max_pagine:
            params_lista.update(continua_token)
        else:
            continua = False

    logger.info("GDPRhub: %d pagine con template %s", len(pagine_trovate), GDPRHUB_TEMPLATE)

    # 2. Per ogni pagina, estrai i dati strutturati
    for i, pagina in enumerate(pagine_trovate[:max_pagine]):
        titolo_pagina = pagina.get("title", "")
        if not titolo_pagina:
            continue
        logger.debug("GDPRhub parsing (%d/%d): %s", i + 1, min(max_pagine, len(pagine_trovate)), titolo_pagina)
        record = _parse_gdprhub_page(titolo_pagina, session)
        if record:
            record_grezzi.append(record)
        else:
            logger.warning("Riga scartata (None) per pagina: %s", titolo_pagina)
        # Pausa cortesia per non sovraccaricare il server
        time.sleep(0.5)

    logger.info("GDPRhub: %d record estratti", len(record_grezzi))
    return record_grezzi


# ---------------------------------------------------------------------------
# Aggregazione e salvataggio
# ---------------------------------------------------------------------------

def fetch_gdpr_fines() -> pd.DataFrame:
    """
    Funzione principale: tenta le due fonti nell'ordine di priorità,
    combina i risultati e restituisce un DataFrame normalizzato.
    """
    session = _crea_sessione()
    tutti_record: list[dict] = []

    # --- Fonte 1: enforcementtracker.com ---
    try:
        record_et = fetch_enforcementtracker(session)
        if record_et:
            logger.info("Fonte enforcementtracker: %d record", len(record_et))
            tutti_record.extend(record_et)
        else:
            logger.info("enforcementtracker.com non ha restituito dati — proseguo con GDPRhub")
    except Exception as e:
        logger.error("Errore inatteso su enforcementtracker: %s", e, exc_info=True)

    # --- Fonte 2: GDPRhub (sempre aggiunta, anche se ET ha avuto successo) ---
    try:
        record_gdprhub = fetch_gdprhub(session, max_pagine=100)
        if record_gdprhub:
            logger.info("Fonte GDPRhub: %d record", len(record_gdprhub))
            tutti_record.extend(record_gdprhub)
        else:
            logger.warning("GDPRhub non ha restituito record")
    except Exception as e:
        logger.error("Errore inatteso su GDPRhub: %s", e, exc_info=True)

    if not tutti_record:
        logger.error("Nessun record estratto da nessuna fonte GDPR fines")
        return pd.DataFrame()

    df = pd.DataFrame(tutti_record)
    logger.info("Totale grezzo prima di deduplicazione: %d record", len(df))

    # Deduplicazione per hash_contenuto (preferisci l'ultimo visto)
    df = df.drop_duplicates(subset=["hash_contenuto"], keep="last")
    logger.info("Totale dopo deduplicazione: %d record", len(df))
    return df


def salva_gdpr_fines(df: pd.DataFrame) -> str:
    """
    Appende i nuovi record a gdpr_fines_sample.csv con deduplicazione.
    Non sovrascrive mai i dati esistenti.
    """
    os.makedirs(os.path.dirname(OUTPUT_RAW), exist_ok=True)

    if os.path.exists(OUTPUT_RAW):
        try:
            df_esistente = pd.read_csv(OUTPUT_RAW)
            n_pre = len(df_esistente)
            df_unito = pd.concat([df_esistente, df], ignore_index=True)
            df_finale = df_unito.drop_duplicates(subset=["hash_contenuto"], keep="last")
            n_nuovi = len(df_finale) - n_pre
            logger.info(
                "Append: %d record esistenti + %d nuovi = %d totali",
                n_pre, n_nuovi, len(df_finale)
            )
        except Exception as e:
            logger.error("Errore lettura CSV esistente %s: %s — salvo snapshot", OUTPUT_RAW, e)
            _salva_snapshot(open(OUTPUT_RAW, "rb").read(), "gdpr_fines_backup")
            df_finale = df
    else:
        df_finale = df
        logger.info("Nuovo file CSV: %d record", len(df_finale))

    df_finale.to_csv(OUTPUT_RAW, index=False, encoding="utf-8")
    logger.info("Salvato: %s (%d record totali)", OUTPUT_RAW, len(df_finale))
    return OUTPUT_RAW


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("=== Avvio importer GDPR Fines ===")
    df_fines = fetch_gdpr_fines()

    if not df_fines.empty:
        percorso = salva_gdpr_fines(df_fines)
        logger.info("=== Completato. Output: %s ===", percorso)
    else:
        logger.error("=== FALLIMENTO: nessun dato estratto. Verificare connessione e snapshot. ===")
        sys.exit(1)
