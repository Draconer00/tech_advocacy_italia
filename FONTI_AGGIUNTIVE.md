# 📚 Fonti e Repository Aggiuntivi Attendibili

Questo documento contiene l'elenco di fonti pubbliche, dataset e repository open source che puoi integrare nel progetto per aumentare la quantità e qualità dei dati.

---

## ✅ Repository Github Utili

| Repository | Descrizione | Tipo Dati | Licenza |
|------------|-------------|-----------|---------|
| https://github.com/topics/italia-open-data | Collezione di tutti i progetti open data italiani | Dataset vari | Miste |
| https://github.com/italia/opendata | Repository ufficiale dati.gov.it | Dati pubblici PA | CC-BY |
| https://github.com/EDRi/edri-digital-rights-monitor | Monitoraggio diritti digitali EDRi | Report, policy | MIT |
| https://github.com/noyb/gdpr-enforcement-database | Database mondiale sanzioni GDPR | Multate GPDP internazionali | CC0 |
| https://github.com/AlgorithmWatch/gdpr-enforcement | Dataset storico sanzioni Garante Privacy | Dataset strutturato | CC-BY |
| https://github.com/privacyinternational/datasets | Privacy International ricerche e dati | Report internazionali | Open |
| https://github.com/accessnow/holidays | Monitoraggio shutdown internet globali | Eventi | MIT |
| https://github.com/civictechitalia/awesome-civictech-italy | Elenco completo organizzazioni civic tech italiane | Directory ONG | CC0 |

---

## 📰 Fonti Ufficiali e Feed Aggiuntivi

### Istituzioni Italiane
- [ ] Garante Privacy feed RSS ufficiale: `https://www.garanteprivacy.it/web/guest/home/docweb?p_p_id=101&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view&p_p_col_id=column-1&p_p_col_count=1&_101_struts_action=%2Fasset_publisher%2Fview_rss&_101_assetEntryId=0&_101_type=entries&_101_version=2.0`
- [ ] AGCOM comunicati e provvedimenti: `https://www.agcom.it/rss`
- [ ] Autorità Garante Concorrenza e Mercato: `https://www.agcm.it/rss`
- [ ] Parlamento Italiano - Monitoraggio leggi: `https://www.parlamento.it/rss`

### Europee
- [ ] Commissione Europea DG Connect: `https://digital-strategy.ec.europa.eu/en/rss.xml`
- [ ] EDPS (Garante Privacy UE): `https://edps.europa.eu/news/rss_en.xml`
- [ ] Consiglio d'Europa Diritti Umani: `https://www.coe.int/en/web/hrcouncil/rss`

### Organizzazioni Internazionali
- [ ] Access Now News: `https://www.accessnow.org/feed/`
- [ ] Electronic Frontier Foundation: `https://www.eff.org/rss/updates.xml`
- [ ] Privacy International: `https://privacyinternational.org/rss.xml`
- [ ] Open Rights Group UK: `https://www.openrightsgroup.org/feed/`

---

## 📊 Dataset Pubblici

1. **GDPR Fines Dataset** - oltre 2000 sanzioni GDPR raccolte a livello mondiale
2. **Digital Rights Tracker** - stato dei diritti digitali per ogni paese europeo
3. **AI Act Monitor** - monitoraggio implementazione AI Act in UE
4. **Italian Law Database** - estrazione automatica nuove leggi e decreti

---

## 🚀 Come Integrare

Puoi aggiungere queste fonti semplicemente aggiungendo l'URL del feed RSS nel file `scrapers/scraper_ong.py` all'interno del dizionario `fonti_ong`. Lo scraper è già predisposto per gestire automaticamente qualsiasi feed RSS standard.

Per i dataset strutturati puoi creare nuovi scraper ad-hoc o importare direttamente i file CSV nella cartella `data/raw/`.