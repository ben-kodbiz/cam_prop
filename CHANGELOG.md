# Changelog

All notable changes to this project are documented here.
The format is based on Keep a Changelog; the project adheres to
[SemVer](https://semver.org) once a public release exists.

## [Unreleased]

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
