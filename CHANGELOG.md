# Changelog

All notable changes to this project are documented here.
The format is based on Keep a Changelog; the project adheres to
[SemVer](https://semver.org) once a public release exists.

## [Unreleased]

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
