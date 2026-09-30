# NLP Roadmap — Tech Advocacy Radar

Technical roadmap for improving the NLP pipeline in `nlp/text_analysis.py`. Items are ordered by implementation priority.

---

## Current Limitations

| Component | Known Issue |
|-----------|-------------|
| NER | General-purpose Italian model (`it_core_news_md`) underperforms on legal and regulatory terminology; regulatory body names and jurisdiction-specific acronyms are frequently misclassified |
| Geographic classification | Rule-based matching; does not handle implicit geographic references or multilingual abbreviations |
| Sentiment | Rule-based; insufficient for formal legal language where polarity signals are weak or hedged |
| Translation | Translate-then-process approach for non-Italian sources introduces information loss |
| Topic structure | TF-IDF keywords reflect term frequency but do not capture stable thematic clusters across the corpus. Mitigated on two fronts: (a) documents are tagged against a curated theme lexicon (`data/utils/temi.csv`) with a **hybrid** matcher — exact lexical + semantic embedding (`nlp/theme_matching.py`) — persisted as `temi_rilevati`/`temi_dettaglio`; (b) an unsupervised **BERTopic discovery layer** (`nlp/topic_discovery.py`) surfaces emergent clusters *not* in the lexicon; (c) the lexicon is a **two-level registry** (8 stable macro-themes + dynamic sub-themes) so a discovered topic can be promoted to a tracked sub-theme after human review. TF-IDF itself now excludes HTML/web junk tokens. Remaining limits: new sub-themes are uncalibrated until the gold set covers them, and BERTopic topic IDs are not stable across runs (a promoted sub-theme records its source topic's keywords, not just the ID) |

---

## Planned Improvements

### Domain-Adapted NER

Fine-tune `it_core_news_md` on a manually annotated corpus of privacy and AI governance documents using spaCy's training pipeline. Annotation target: 200–300 documents covering GDPR enforcement decisions, DPA rulings, and civil society position papers.

As a complementary approach, evaluate legal-domain language models as backbone encoders:
- **Legal-BERT** (Chalkidis et al., 2020) — pre-trained on EU legislation and court decisions
- **EUR-Lex-BERT** — trained on the EUR-Lex corpus of European legislative text
- **MultiLegalPile models** — multilingual legal pre-training covering multiple EU jurisdictions

### Multilingual NER Without Translation

Replace the current translate-then-process approach for English, French, and Spanish sources with a multilingual NER model (`xlm-roberta-base` fine-tuned on CoNLL/WikiAnn NER). This eliminates translation-induced entity loss and handles cross-lingual entity variants natively.

### Relation Extraction

Extend the pipeline to extract subject-verb-object triples from document text, representing not only which entities appear in a document but how they interact — for instance, which authority sanctioned which company under which article. Candidate approaches: spaCy dependency parsing for lightweight extraction; fine-tuned transformer models (e.g. REBEL) for higher recall.

### Topic Modelling and Dynamic Themes

*Implemented (2026-09-20 → 2026-09-30).* BERTopic (shared MiniLM embeddings → UMAP → HDBSCAN → c-TF-IDF) runs offline as a **discovery** layer; it does not replace the curated lexicon. Clusters are statistical and shift between runs, so they are never tracked directly. Instead:

- **Two-level registry** (`data/utils/temi.csv`): 8 macro-themes stay fixed, so long-term trends remain comparable and the gold-set codebook stays stable; sub-themes (`padre` = a macro-theme) are added over time, each with `stato` (attivo/candidato/dismesso), `dal` (introduction date) and `origine` (manuale / `bertopic#N: keywords`).
- **Topic ↔ registry comparison**: for each discovered topic, `confronta_con_temi()` measures the share of its documents already tagged with each theme (from the persisted `temi_rilevati`). The result is easy to explain and needs no new similarity threshold: *covered* (a sub-theme ≥ 50%), *sub-theme candidate* (a macro-theme ≥ 50%, no sub-theme), *outside lexicon*.
- **Human approval**: promotion happens from the dashboard (Topic Emergenti tab), with validation and backup; nothing is added automatically.
- **Parent propagation**: a sub-theme match also tags its parent (`metodo: da_sottotema`), so macro-theme counts remain complete.
- **Retroactive application**: processed data is regenerated from raw on each run, so a new sub-theme covers the whole archive; its `dal` date is shown in the trends so the reader knows that the earlier part of the series was reconstructed after the fact.

Open follow-ups: calibrate sub-theme thresholds with targeted gold labels (a small per-sub-theme worksheet); optionally match topics across BERTopic runs (centroid similarity) to follow a candidate over time before promoting it.

### Sentiment Refinement

Replace the current rule-based sentiment classifier with a transformer model fine-tuned on legal and regulatory text, improving stance detection in documents where polarity is expressed through formal, hedged language.

### NGO Testimony Integration

Incorporate structured first-person input from monitored organisations (position statements, declared priorities) as an additional training signal for the entity linker and urgency classifier. This grounds model predictions in explicitly annotated domain knowledge provided by the organisations themselves.

---

## Implementation Status

| Feature | Status |
|---------|--------|
| Text cleaning + blacklist | Implemented |
| HTML/entity stripping + WordPress feed-footer removal (`pulisci_html`, processed layer only — raw text and its `hash_contenuto` id stay untouched) | Implemented (2026-09-30) — ONG 290/307, rss_eu 8/70, tech_news 283/330 texts cleaned |
| NER (spaCy `it_core_news_md`) | Implemented |
| TF-IDF keyword extraction (bilingual IT/EN stop words, HTML/web junk excluded) | Implemented |
| Curated theme lexicon for temporal trends (`data/utils/temi.csv`) | Implemented (2026-09-20) |
| Hybrid theme tagging (exact lexical + semantic embedding, `nlp/theme_matching.py`) | Implemented (2026-09-20) — per-theme semantic thresholds in `temi.csv` (`soglia` column), calibrated via `nlp/valuta_temi.py` |
| Two-level theme registry (8 stable macro-themes + dynamic sub-themes; `padre`/`stato`/`dal`/`origine` columns in `temi.csv`) | Implemented (2026-09-30) — see "Topic Modelling and Dynamic Themes" above |
| Sub-theme threshold calibration | Planned — per-sub-theme gold labels; until then, the conservative option is `soglia = 1.0` (exact terms only) |
| Theme gold set for objective P/R/F1 tuning | Scaffold ready (`nlp/prepara_gold.py` → `data/utils/temi_gold_worksheet.csv`, 129 docs); awaiting human labeling, then `valuta_temi.py --gold` |
| Fuzzy deduplication (SequenceMatcher) | Implemented |
| Semantic deduplication (sentence-transformers) | Implemented |
| Geographic classification | Implemented |
| Sentiment analysis (rule-based) | Implemented |
| Urgency index (active learning) | Implemented |
| Gazzetta Ufficiale / CJEU NLP integration | Implemented (2026-08-31) |
| GDPR fines structured layer | Planned (scraper not yet implemented — see FONTI_AGGIUNTIVE.md) |
| Domain-adapted NER | Planned |
| Multilingual NER without translation | Planned |
| Relation extraction | Planned |
| BERTopic topic modelling (discovery layer, `nlp/topic_discovery.py` → dashboard "Topic Emergenti") | Implemented (2026-09-20) — offline/periodic, exploratory; reuses shared MiniLM embeddings, UMAP `random_state` fixed, HDBSCAN `leaf` |
| Legal language model integration | Planned |
| NGO testimony as training signal | Planned |
