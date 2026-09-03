# Changelog

All notable changes to this project are documented here.
The format is based on Keep a Changelog; the project adheres to
[SemVer](https://semver.org) once a public release exists.

## [Unreleased]

### Added — Phase 7: publishing automation + analytics
- Analytics (§43): `app/analytics.py` computes review coverage, average
  review age, correction rate, citation completeness, evidence depth —
  never engagement/virality. `python -m app stats [--days N --out PATH]`;
  exported to `web/data/stats.json`.
- Corrections & retractions (§21): `app/corrections.py` — tracked
  corrections (correction/clarification/evidence_update/status_change/
  source_removal) with mandatory reasons, revision bumps, audit entries;
  `python -m app retract` keeps retracted publications visible;
  republishing clears the retraction (never silent).
- Reports: weekly digest, corporate monthly report, fact-check card
  batch (`python -m app report --kind weekly|corporate|cards`).
- Publishing pipeline: `python -m app publish CLM-…` records the
  publication and writes a card artifact; unapproved claims are refused.

### Added — Phase 3: local AI (no cloud, human-gated)
- `agents/llm.py`: minimal OpenAI-compatible client (llama.cpp/Ollama/
  LM Studio) configured via `.env` (`OE_LLM_*`); tolerant JSON parsing;
  client injectable — tests run with zero network.
- `agents/claim_extraction.py`: LLM proposes claims from source text;
  the pipeline enforces compound splitting, dedup and source linkage;
  every proposal becomes a *pending* claim. The LLM never sets status.
- `agents/drafts.py`: explanation/translation drafts stored in
  `claim_drafts` (new table, DFT- IDs) and applied only by a human
  (`python -m app extract-claims|draft|drafts|apply-draft`).
  Translations set `translation_method='llm'`; the original claim text
  is never replaced (§42).
- Claims gained `explanation` (rendered as the "Why" block on claim
  pages); export includes explanation/translated fields.
- 34 new tests (166 total) including fake-LLM invariant tests.

### Added — Phases 4-6: law module, corporate depth, alternatives
- Phase 4 — international-law database: `legal_documents` table (body,
  case, document_type from a fixed vocabulary, finding, mandatory
  `does_not_establish`, jurisdiction, source) + `claim_legal_documents`
  cross-links; `LGL-` IDs; approved legal documents export to
  `web/data/legal.json`; new legal page with type pills and search;
  claims can display their linked legal records.
- Phase 5 — corporate accountability depth: company directory (grouped
  approved relationships), per-company timelines (relationship
  milestones, statements, responses, approved claims),
  claims-for-relationship lookup; company detail page on the site.
- Phase 6 — alternatives with §45 scoring (10 dimensions, 0-5, never
  political affiliation), §16 migration guides (structured fields),
  §6 vendor-dependency mapping; scores and guides exported and
  rendered on the alternatives page.
- Review gate extended to `legal_document` subjects with a dedicated
  8-point checklist (record type correct, negation stated, primary
  source…).
- Lightweight migrations: `reviews`/`publications` rebuilt when their
  subject_type CHECK predates `legal_document`; `alternatives` gains
  `score_json`, `migration_notes`, `limitations`.
- CLI: `python -m app legal [--body ICJ] [--approved-only]`.
- Seed fixtures now include an approved legal document, corporate
  relationship + statement, and a scored alternative. 7 new integration
  tests (132 total).

### Added — Real ingestion: RSS feeds + PDF books
- Real RSS ingestion: `data/feeds.json` config, `python -m app feeds` /
  `ingest-rss`. Per-host rate limiting, tracking-param stripping, canonical
  URL dedup, RFC822→ISO date parsing; a failing feed never aborts the run.
  Network is injectable (`fetcher`) so tests run offline.
- Books as sources of truth: `python -m app ingest-book FILE.pdf` (PyMuPDF
  via the `[pdf]` extra). Books are tier 3, `doc_kind='book'`, deduped by
  content hash, archived under `archive/books/SRC-…/` with per-page text
  in `pages.json`. New CLI: `books`, `book-search`.
- Page-cited evidence: `page_number` is validated against the book's page
  range and rejected for URL sources (they must cite `section`/URL).
  Claim pages on the site show "p.N" citations; sources page shows book
  metadata (author, year, pages, ISBN).
- Schema: `sources` gained `local_path`, `doc_kind`, `book_author`,
  `book_isbn`, `book_publisher`, `book_year`, `book_pages`; existing DBs are
  lightweight-migrated by `init_db` (ALTER TABLE ADD COLUMN).
- 21 new tests (RSS pipeline, book pipeline, page citations): 112 total.

### Added — Phase 1: Foundation
- SQLite schema with 14 tables, FTS5 full-text index, foreign keys and
  check constraints enforcing the claim-status vocabulary.
- Core package `app/`: sources (with SHA-256 hashing and local archiving),
  claims (duplicate detection, compound-claim splitting), evidence
  (multi-dimensional scoring), review gate with high-impact checklist,
  hybrid search, citations, export to static JSON, and a CLI
  (`python -m app init-db|seed|export|queue|review|assess|search|stats|backup`).
- Ingestion package: RSS (rate-limited, tracking-param stripping), HTML
  text extraction, PDF via PyMuPDF (optional), sitemap, daily scheduler.
- Deterministic evidence agent producing provisional assessments
  (no LLM in Phase 1).
- Modules: international law (finding + does-not-establish), corporate
  accountability (relationship classification + company statements),
  open-source alternatives.
- Publishing generators (short posts, fact-check cards, carousels) gated
  on approved claims only.
- Static PWA frontend (HTML/CSS/vanilla JS) loading exported JSON.
- Test suite covering the critical invariants; CI workflow (ruff, mypy,
  pytest); backup script.
- Documentation: README, METHODOLOGY, CONTRIBUTING, SECURITY, AGENTS.
