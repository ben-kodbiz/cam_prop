# Methodology

This document is the authoritative description of how Open Evidence works.
The public methodology page (`web/methodology.html`) is generated from the
same rules.

The project does not assume that any government, political movement, company,
media organization or activist group is always truthful or always dishonest.

## 1. Claim selection

Claims are discovered from public sources: official documents, court records,
established news organizations, and social media. Social-media posts are used
to *locate* claims and original material, never automatically treated as proof.

## 2. Source ranking

| Tier | Sources |
|------|---------|
| 1 — Primary | ICJ, ICC, UN bodies, official court records, government documents, parliamentary records, corporate filings, contracts, official company statements, verifiable datasets, satellite imagery |
| 2 — Professional journalism | Reuters, AP, BBC, FT, Guardian, other established outlets |
| 3 — Specialist investigations | academic research, investigative journalism, reputable NGOs, research institutes |
| 4 — Social media | claim discovery and locating original material only |

The tier mapping is code: `app/constants.py:SOURCE_TIERS`.

## 3. Evidence evaluation

Evidence is scored on separate dimensions — never a simplistic true/false:

```
source_quality   0-5      primary_source  true/false
independence     0-5      directness      0-5
corroboration    0-5      contradiction   0-5
recency          0-5
```

The computed strength is *evidence assistance, not truth*. A human reviewer
determines the final classification. See `app/evidence.py:evidence_strength`.

## 4. Possible outcomes

supported · mostly_supported · misleading · unsupported · contradicted ·
disputed · insufficient_evidence · unknown

`unknown` is a legitimate outcome. If evidence is insufficient, that is what we
publish.

## 5. Compound claims

Compound statements are split into atomic factual assertions before
evaluation ("X happened because Y, therefore Z" → three claims, three bodies
of evidence). See `app/claims.py:split_compound_claim`.

## 6. Conflicts between sources

When sources disagree, the claim is marked **disputed** and both supporting
and contradicting evidence are shown side by side. Semantic similarity never
establishes factual correctness.

## 7. Use of AI

The LLM may summarize, classify, extract claims, compare evidence and draft
explanations. It must not invent evidence, statistics, quotations or sources,
and must never upgrade `unknown` to `true` or downgrade `disputed` to `false`.

Phase 1 uses no LLM at all: the evidence agent (`agents/evidence_agent.py`)
is fully deterministic. When LLM support is added, it will run against a
local, OpenAI-compatible endpoint only.

## 8. Human review

Every claim requires human approval before publication. High-impact topics —
deaths, alleged war crimes, genocide, terrorism, accusations against
individuals or companies, financial relationships, military activity,
international-law conclusions — require a completed 12-point checklist
(enforced in `app/review.py`).

## 9. Corrections

Every published record carries `created_at`, `updated_at`, `last_reviewed`,
`reviewer` and `revision`. All changes are appended to an audit log; history
is never silently rewritten. Corrections, clarifications, evidence updates,
status changes and source removals are all first-class, logged operations.

## 10. Reproducibility

Every published assessment is reproducible: claim ID, source IDs, URLs,
retrieval dates, evidence excerpts, assessment, methodology version and review
date are exported with each claim (`app/citations.py:reproducibility_bundle`).

## 11. Source archiving

For every important source we retain URL, retrieval timestamp, SHA-256 hash,
publisher, title, publication date, document type and a local archive path
(`archive/YYYY/MM/source-id/…`). Hashes allow anyone to verify that the
evidence examined today is the evidence originally captured.
