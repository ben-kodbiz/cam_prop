# Open Evidence

An open-source, evidence-first platform for documenting contested claims,
international-law records and corporate relationships.

> **Evidence first. Attribution always. Uncertainty explicitly stated.**

The objective is a transparent evidence machine that makes propaganda harder
to sustain — regardless of who produces it. The project does not assume that
any government, political movement, company, media organization or activist
group is always truthful or always dishonest.

## Status

Phase 1 (foundation): repository, SQLite schema, source ingestion, claim and
evidence models, review gate, static website, tests. No LLM required.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

python -m app init-db      # create data/evidence.db
python -m app seed         # load fixture data (all marked SEED)
python -m app export       # write data/generated/*.json and web/data/*.json
python -m app queue        # show pending review queue
python -m app stats        # database statistics

# Ingestion
python -m app feeds                        # list enabled RSS feeds
python -m app ingest-rss                    # fetch feeds, register new sources
pip install -e ".[pdf]"                     # once, for PDF book support
python -m app ingest-book FILE.pdf --title "…" --author "…" --year 2020
python -m app books                         # list imported books
python -m app book-search SRC-… "query"     # search inside a book

# International law / publishing / corrections / AI
python -m app legal [--body ICJ]            # list legal documents
python -m app publish CLM-…                 # publish approved claim + card
python -m app report --kind weekly|corporate|cards
python -m app retract --subject-type claim --subject-id CLM-… --reason "…"
python -m app correct CLM-… --kind clarification --reason "…" --reviewer NAME
python -m app stats --days 30               # §43 quality metrics
python -m app extract-claims SRC-…          # LLM proposes *pending* claims
python -m app draft CLM-… --kind explanation|translation
python -m app apply-draft DFT-… --reviewer NAME   # human applies a draft
```
Serve the static site (any static file server works):

```bash
python -m http.server --directory web 8000
# http://localhost:8000
```

## Workflow

The pipeline is deliberate and human-gated:

```text
source ingestion -> claim extraction -> evidence linking
  -> provisional assessment (deterministic) -> HUMAN REVIEW -> publication -> export
```

- A claim **cannot** become `supported` without at least one linked evidence
  record; it cannot become `contradicted` without contradicting evidence.
  These invariants are enforced in code (`app/claims.py:set_status`) and tested.
- High-impact topics (deaths, alleged war crimes, accusations against
  individuals or companies, legal conclusions) require a completed review
  checklist before approval.
- Every change is recorded in an append-only audit log. History is never
  silently rewritten.

## Development

```bash
pytest            # tests
ruff check .      # lint
ruff format .     # format
mypy              # typecheck
```

See `AGENTS.md` for repository conventions.

## Project layout

```text
app/         core package: db, sources, claims, evidence, review, search, export, CLI
ingestion/   RSS / HTML / PDF / sitemap / scheduler
agents/      deterministic evidence agent (Phase 1: no LLM)
modules/     international law, corporate accountability, alternatives
publishing/  content generators (approved claims only)
web/         static PWA frontend (HTML/CSS/vanilla JS)
data/        schema.sql, seed/, generated JSON
archive/     local source archive (YYYY/MM/source-id/…)
tests/       pytest suite
```

## License

- Code: AGPL-3.0 (see `LICENSE`)
- Project-created data: CC BY 4.0 where legally appropriate
- Third-party material: referenced by short excerpt, URL and metadata only —
  never mirrored
