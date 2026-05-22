# Tech Advocacy Italy

## Project Mission

Tech Advocacy Italy is an open-source civic intelligence and advocacy platform.

The platform:
- collects public-interest digital rights data
- monitors privacy and AI governance developments
- aggregates institutional and NGO communications
- analyzes trends through NLP pipelines
- provides transparent and auditable outputs

The project must remain:
- transparent
- reproducible
- evidence-based
- non-partisan in data processing
- open-source friendly

---

# Core Rules

## Data Integrity

- Never invent data
- Never fabricate entities
- Preserve raw source material
- Every claim must trace back to a source
- Maintain historical archives permanently
- Do not overwrite datasets unless explicitly requested

## Scraping Rules

- Respect robots.txt when possible
- Use retries and timeout handling
- Save raw HTML snapshots when extraction fails
- Never silently discard malformed rows
- Log extraction failures

## NLP Rules

- Keep explainability over complexity
- Prefer deterministic pipelines when possible
- Preserve original text before cleaning
- Flag low-confidence entity extraction
- Separate facts from inferred classifications

## Advocacy Rules

- Advocacy outputs must be evidence-grounded
- Clearly separate analysis from opinion
- Avoid sensational language
- Include methodology notes when generating reports
- Mention uncertainty when confidence is low

## Code Quality

Prioritize maintainability over cleverness
