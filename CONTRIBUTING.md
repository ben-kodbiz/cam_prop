# Contributing to Open Evidence

## Core principle

Evidence first. Attribution always. Uncertainty explicitly stated.
This project must remain capable of concluding that a claim is supported,
misleading, contradicted, disputed or unknown — **regardless of who made
the claim.** PRs that hard-code conclusions about any side of any conflict
will be rejected.

## Ground rules

1. **No invented facts.** Every factual assertion in the database must trace
   to a source. No source → no factual assertion.
2. **Primary sources first.** ICJ/ICC/UN, court records, government documents,
   filings, contracts, official statements, verifiable datasets.
3. **Social media is not proof.** Use it to locate claims and original material.
4. **Never conflate** allegation with finding, or provisional measure with
   judgment. Legal records must state what they do *not* establish.
5. **No harassment.** We criticize policies, claims, institutions and
   documented actions — never employees or private individuals.
6. **Uncertainty is a valid outcome.** `unknown` and `insufficient_evidence`
   are legitimate, publishable statuses.

## Code contributions

```bash
pip install -e ".[dev]"
pytest && ruff check . && ruff format --check . && mypy
```

- Python 3.11+; stdlib-first; avoid unnecessary dependencies.
- Frontend: HTML, CSS, vanilla JS only. No frameworks.
- Every new claim/evidence/review code path needs tests, especially the
  invariants in `tests/test_claims.py` and `tests/test_review.py`.
- Keep excerpts short (≤ 500 chars); store pointers, not copies.

## Data contributions

- Sources must be archived via the ingestion tooling (hash + metadata).
- Claims enter as `unknown` and only move after evidence + review.
- Corrections are new revisions, never silent rewrites.

## Reporting errors in published content

Open an issue with the claim ID (`CLM-YYYY-NNNN`). Corrections follow the
audit-trail process described in `METHODOLOGY.md`.
