# Gold set temi — istruzioni di etichettatura

Il file `temi_gold_worksheet.csv` contiene 129 documenti scelti con un
campionamento stratificato (`nlp/prepara_gold.py`). Le etichette che inserisci
diventano la **verità di riferimento** con cui si misurano precision, recall e F1
del rilevamento temi (`nlp/valuta_temi.py`) e si scelgono le soglie per tema in
`temi.csv`. Il gold set **non addestra** alcun modello: serve solo a misurare.

## Cosa compilare

Solo la colonna **`temi`**. Non modificare le altre colonne, in particolare
`id_documento`, che è la chiave usata per l'allineamento.

| Valore in `temi` | Significato |
|---|---|
| `Privacy e Dati` | un tema |
| `Privacy e Dati\|Intelligenza Artificiale` | più temi, separati da `\|` |
| `NESSUNO` | letto: il documento non tratta nessuno degli 8 temi |
| *(vuoto)* | non ancora etichettato: il documento viene escluso dalla valutazione |

`NESSUNO` è importante: i documenti senza tema sono quelli che misurano i falsi
positivi. Non lasciarli vuoti.

## Regola di decisione

Assegna un tema se è un **argomento sostanziale** del documento, non una
menzione di passaggio. Prova pratica: *"Se dovessi archiviare questo documento
per tema, lo metterei in questa cartella?"* Di solito i temi sono da 0 a 2.

- Giudica leggendo `titolo` + `testo_estratto`. Se sono ambigui, apri la fonte
  (cerca il titolo) prima di decidere.
- **Ignora `temi_suggeriti`** quando decidi: è la previsione del modello, ed
  è proprio quella che stiamo misurando. Copiarla renderebbe la misura circolare.
- In caso di dubbio persistente, scegli l'interpretazione più stretta e annota
  il caso (vedi sotto).

## Codebook

Usa **esattamente** questi nomi (maiuscole e accenti compresi). La definizione
indica l'ambito; i termini tra parentesi vengono da `temi.csv`.

| Tema | Ambito |
|---|---|
| `Privacy e Dati` | protezione dei dati personali, GDPR, trattamenti, data breach, profilazione |
| `Intelligenza Artificiale` | sistemi di IA, AI Act, algoritmi decisionali, chatbot, deepfake, IA generativa |
| `Sorveglianza` | videosorveglianza, riconoscimento facciale, biometria, tracciamento, spyware/captatori |
| `Cybersicurezza` | attacchi informatici, ransomware, vulnerabilità, malware, sicurezza di sistemi e reti |
| `Piattaforme e Contenuti` | DSA/DMA, moderazione dei contenuti, disinformazione, regole per i social network |
| `Diritti Digitali` | libertà di espressione online, censura, net neutrality, accesso a internet, sorveglianza di massa come questione di diritti |
| `Minori` | tutela dei minori online, verifica dell'età |
| `Chat e Messaggistica` | app di messaggistica, crittografia end-to-end, Chat Control |

Il gold set si etichetta **solo con questi 8 macro-temi**, anche quando nel
registro esistono sotto-temi: la previsione di un sotto-tema viene contata come
previsione del suo macro-tema padre.

Sovrapposizioni frequenti:
- un provvedimento del Garante su un sistema di IA va sia in `Privacy e Dati` sia
  in `Intelligenza Artificiale`, se entrambi gli aspetti sono centrali;
- Chat Control va in `Chat e Messaggistica`, e anche in `Sorveglianza` o `Diritti
  Digitali` se il documento lo tratta come questione di sorveglianza o di diritti.

## Strumento consigliato

Non usare Excel con impostazioni italiane: salva i CSV con il `;` e può rovinare
gli accenti. Usa:
- **VS Code** con l'estensione *Edit CSV* o *Rainbow CSV*; oppure
- **LibreOffice Calc**: all'apertura scegli *UTF-8* e separatore *virgola*; al
  salvataggio usa *Mantieni formato CSV* con le stesse impostazioni.

## Dopo l'etichettatura

```bash
.venv\Scripts\python.exe nlp/valuta_temi.py --gold data/utils/temi_gold_worksheet.csv
```

L'output riporta precision/recall/F1 per ogni soglia e segnala eventuali nomi di
tema scritti male. Si può valutare anche un foglio etichettato solo in parte: le
righe vuote vengono escluse. Poi fai il commit del foglio compilato: è ground
truth curata e va versionata, come `training_data_feedback.csv`.

**Limite noto:** il campione è concentrato sui casi-limite. Serve a *scegliere
le soglie*, non a stimare la precisione sul corpus nel suo insieme.
