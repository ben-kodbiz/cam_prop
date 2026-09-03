"""Central constants and controlled vocabularies."""

from __future__ import annotations

CLAIM_STATUSES: tuple[str, ...] = (
    "supported",
    "mostly_supported",
    "misleading",
    "unsupported",
    "contradicted",
    "disputed",
    "insufficient_evidence",
    "unknown",
)

# Statuses a claim may move to, and whether they require linked evidence.
# A claim can never become supported/contradicted without evidence records.
STATUS_EVIDENCE_REQUIREMENTS: dict[str, tuple[str, int]] = {
    # status: (required relationship, min count)
    "supported": ("supports", 1),
    "mostly_supported": ("supports", 1),
    "contradicted": ("contradicts", 1),
    "misleading": ("supports", 1),
    "unsupported": ("contradicts", 1),
    "disputed": ("supports", 1),
    # informational statuses require no minimum evidence
    "insufficient_evidence": ("", 0),
    "unknown": ("", 0),
}

REVIEW_STATUSES: tuple[str, ...] = ("pending", "in_review", "approved", "rejected")

# High-impact topics always require human review before publication (agentodo §10).
HIGH_IMPACT_TOPICS: tuple[str, ...] = (
    "deaths",
    "war_crimes",
    "genocide",
    "terrorism",
    "individual_accusations",
    "corporate_allegations",
    "illegal_conduct",
    "financial_relationships",
    "military_activity",
    "international_law",
)

# Legal record types that must never be conflated (agentodo §11).
LEGAL_RECORD_TYPES: tuple[str, ...] = (
    "allegation",
    "provisional_measure",
    "advisory_opinion",
    "judgment",
    "arrest_warrant",
    "conviction",
    "investigative_finding",
    "political_resolution",
)

SOURCE_TIERS: dict[str, int] = {
    "icj": 1,
    "icc": 1,
    "un": 1,
    "un_agency": 1,
    "court_record": 1,
    "government_document": 1,
    "parliamentary_record": 1,
    "corporate_filing": 1,
    "company_contract": 1,
    "company_statement": 1,
    "dataset": 1,
    "satellite_imagery": 1,
    "news": 2,
    "academic": 3,
    "ngo_report": 3,
    "investigative_journalism": 3,
    "book": 3,
    "social_media": 4,
}

SPEAKER_TYPES: tuple[str, ...] = (
    "government",
    "military",
    "company",
    "media",
    "activist",
    "individual",
    "un_body",
    "other",
)

EVIDENCE_DIMENSIONS: tuple[str, ...] = (
    "source_quality",
    "primary_source",
    "independence",
    "directness",
    "corroboration",
    "contradiction",
    "recency",
)

ID_PREFIXES: dict[str, str] = {
    "source": "SRC",
    "claim": "CLM",
    "evidence": "EVD",
    "organization": "ORG",
    "person": "PER",
    "event": "EVT",
    "relationship": "CORP",
    "statement": "CST",
    "alternative": "ALT",
    "review": "REV",
    "publication": "PUB",
}
