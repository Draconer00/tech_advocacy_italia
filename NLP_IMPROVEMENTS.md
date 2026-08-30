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
| Topic structure | TF-IDF keywords reflect term frequency but do not capture stable thematic clusters across the corpus |
| Source coverage | `scraper_gazzetta_ufficiale.py` and `scraper_curia.py` (added 2026-08-29) collect raw documents but are not yet in `text_analysis.py`'s source list — no NLP enrichment for these two sources yet, see [FONTI_AGGIUNTIVE.md](FONTI_AGGIUNTIVE.md) |

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

### Topic Modelling

Complement TF-IDF with BERTopic — combining sentence-transformer embeddings with HDBSCAN clustering — to produce stable, semantically coherent topic clusters that can be tracked over time independently of keyword frequency fluctuations.

### Sentiment Refinement

Replace the current rule-based sentiment classifier with a transformer model fine-tuned on legal and regulatory text, improving stance detection in documents where polarity is expressed through formal, hedged language.

### NGO Testimony Integration

Incorporate structured first-person input from monitored organisations (position statements, declared priorities) as an additional training signal for the entity linker and urgency classifier. This grounds model predictions in explicitly annotated domain knowledge provided by the organisations themselves.

---

## Implementation Status

| Feature | Status |
|---------|--------|
| Text cleaning + blacklist | Implemented |
| NER (spaCy `it_core_news_md`) | Implemented |
| TF-IDF keyword extraction (bilingual IT/EN stop words) | Implemented |
| Fuzzy deduplication (SequenceMatcher) | Implemented |
| Semantic deduplication (sentence-transformers) | Implemented |
| Geographic classification | Implemented |
| Sentiment analysis (rule-based) | Implemented |
| Urgency index (active learning) | Implemented |
| Gazzetta Ufficiale / CJEU NLP integration | Planned (scrapers implemented, not yet wired into `text_analysis.py`) |
| GDPR fines structured layer | Planned (scraper not yet implemented — see FONTI_AGGIUNTIVE.md) |
| Domain-adapted NER | Planned |
| Multilingual NER without translation | Planned |
| Relation extraction | Planned |
| BERTopic topic modelling | Planned |
| Legal language model integration | Planned |
| NGO testimony as training signal | Planned |
