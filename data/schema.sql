-- Open Evidence schema. SQLite with WAL and foreign keys.
-- Canonical claim statuses:
--   supported, mostly_supported, misleading, unsupported, contradicted,
--   disputed, insufficient_evidence, unknown

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,                    -- SRC-YYYY-NNNN
    url TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    title TEXT NOT NULL,
    publisher TEXT,
    author TEXT,
    published_at TEXT,                      -- ISO 8601 date
    retrieved_at TEXT NOT NULL,
    source_type TEXT,                       -- icj, icc, un, government, corporate_filing,
                                            -- company_statement, news, ngo_report,
                                            -- social_media, academic, court_record
    source_tier INTEGER NOT NULL CHECK (source_tier BETWEEN 1 AND 4),
    language TEXT NOT NULL DEFAULT 'en',
    content_hash TEXT NOT NULL,             -- SHA-256 of archived content
    archive_path TEXT,                      -- relative path in archive/
    local_path TEXT,                        -- absolute path for local files (books)
    doc_kind TEXT CHECK (doc_kind IN ('url', 'book')),
                                            -- 'book' sources are local PDF files
    book_author TEXT,
    book_isbn TEXT,
    book_publisher TEXT,
    book_year TEXT,
    book_pages INTEGER,                     -- total page count
    reliability_notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS organizations (
    id TEXT PRIMARY KEY,                    -- ORG-YYYY-NNNN
    name TEXT NOT NULL,
    org_type TEXT,                          -- government, military, company, media,
                                            -- ngo, un_body, court, activist, other
    country TEXT,
    website TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (name, org_type)
);

CREATE TABLE IF NOT EXISTS people (
    id TEXT PRIMARY KEY,                    -- PER-YYYY-NNNN
    name TEXT NOT NULL,
    role TEXT,
    organization_id TEXT REFERENCES organizations (id),
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,                    -- EVT-YYYY-NNNN
    title TEXT NOT NULL,
    description TEXT,
    location TEXT,
    occurred_on TEXT,                       -- date or date range
    event_type TEXT,                        -- military, legal, political, economic,
                                            -- humanitarian, corporate, other
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,                    -- CLM-YYYY-NNNN
    claim_text TEXT NOT NULL,               -- original wording, never replaced
    normalized_claim TEXT NOT NULL,         -- for duplicate detection
    speaker TEXT NOT NULL,
    speaker_type TEXT,                      -- government, military, company, media,
                                            -- activist, individual, un_body, other
    organization_id TEXT REFERENCES organizations (id),
    event_id TEXT REFERENCES events (id),
    source_id TEXT REFERENCES sources (id), -- where the claim was made
    published_at TEXT,
    discovered_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unknown'
        CHECK (status IN ('supported', 'mostly_supported', 'misleading',
                          'unsupported', 'contradicted', 'disputed',
                          'insufficient_evidence', 'unknown')),
    confidence REAL NOT NULL DEFAULT 0.0 CHECK (confidence BETWEEN 0.0 AND 1.0),
    importance TEXT CHECK (importance IN ('low', 'medium', 'high', 'critical')),
    topic TEXT,
    original_language TEXT NOT NULL DEFAULT 'en',
    translated_text TEXT,                   -- translation, never authoritative
    translation_method TEXT,                -- human, llm, none
    review_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (review_status IN ('pending', 'in_review', 'approved', 'rejected')),
    reviewer TEXT,
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_reviewed TEXT
);

-- Store only short excerpts + pointers. Never mirror copyrighted content.
CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,                    -- EVD-YYYY-NNNN
    source_id TEXT NOT NULL REFERENCES sources (id),
    evidence_type TEXT,                     -- document, statistic, quotation, ruling,
                                            -- satellite_image, dataset, report, other
    excerpt TEXT,                          -- short quotation where legally appropriate
    page_number TEXT,
    section TEXT,
    context TEXT,                           -- what the excerpt says, in our words
    supports_claim INTEGER CHECK (supports_claim IN (0, 1)),
    strength REAL CHECK (strength BETWEEN 0.0 AND 1.0),
    dimensions_json TEXT NOT NULL DEFAULT '{}',  -- source_quality, primary_source,
                                                 -- independence, directness,
                                                 -- corroboration, contradiction, recency
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claim_evidence (
    claim_id TEXT NOT NULL REFERENCES claims (id) ON DELETE CASCADE,
    evidence_id TEXT NOT NULL REFERENCES evidence (id) ON DELETE CASCADE,
    relationship TEXT NOT NULL DEFAULT 'unspecified'
        CHECK (relationship IN ('supports', 'contradicts', 'context', 'unspecified')),
    created_at TEXT NOT NULL,
    PRIMARY KEY (claim_id, evidence_id)
);

CREATE TABLE IF NOT EXISTS corporate_relationships (
    id TEXT PRIMARY KEY,                    -- CORP-YYYY-NNNN
    company_org_id TEXT NOT NULL REFERENCES organizations (id),
    counterpart_org_id TEXT REFERENCES organizations (id),
    service TEXT,
    customer TEXT,
    contract_ref TEXT,
    contract_value TEXT,                    -- documented amount or 'unknown'
    start_date TEXT,
    end_date TEXT,
    classification TEXT NOT NULL DEFAULT 'unknown'
        CHECK (classification IN ('documented_contract', 'documented_service',
                                  'reported_relationship', 'company_denial',
                                  'company_confirmation', 'disputed',
                                  'unknown', 'ended', 'ongoing')),
    evidence_ids_json TEXT NOT NULL DEFAULT '[]',
    company_response TEXT,
    status_notes TEXT,
    confidence REAL CHECK (confidence BETWEEN 0.0 AND 1.0),
    review_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (review_status IN ('pending', 'in_review', 'approved', 'rejected')),
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_reviewed TEXT
);

CREATE TABLE IF NOT EXISTS company_statements (
    id TEXT PRIMARY KEY,                    -- CST-YYYY-NNNN
    organization_id TEXT NOT NULL REFERENCES organizations (id),
    source_id TEXT REFERENCES sources (id),
    statement_text TEXT NOT NULL,           -- short excerpt or faithful summary
    statement_type TEXT,                    -- denial, confirmation, clarification,
                                            -- policy, other
    statement_date TEXT,
    relates_to_claim_id TEXT REFERENCES claims (id),
    relates_to_relationship_id TEXT REFERENCES corporate_relationships (id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alternatives (
    id TEXT PRIMARY KEY,                    -- ALT-YYYY-NNNN
    product TEXT NOT NULL,                 -- commercial product being replaced
    company TEXT,
    category TEXT NOT NULL,                 -- cloud_storage, office_suites, email, ...
    alternative TEXT NOT NULL,
    alternative_license TEXT,
    alternative_hosting TEXT,               -- self-hosted, cloud, hybrid
    self_hosting_available INTEGER CHECK (self_hosting_available IN (0, 1)),
    migration_difficulty TEXT CHECK (migration_difficulty IN ('easy', 'moderate', 'hard')),
    privacy_notes TEXT,
    replaces_url TEXT,
    alternative_url TEXT,
    source_ids_json TEXT NOT NULL DEFAULT '[]',
    notes TEXT,
    review_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (review_status IN ('pending', 'in_review', 'approved', 'rejected')),
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,                    -- REV-YYYY-NNNN
    subject_type TEXT NOT NULL CHECK (subject_type IN ('claim', 'relationship', 'statement', 'alternative')),
    subject_id TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('approve', 'reject', 'request_evidence')),
    checklist_json TEXT NOT NULL DEFAULT '{}',
    notes TEXT,
    reviewed_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS publications (
    id TEXT PRIMARY KEY,                    -- PUB-YYYY-NNNN
    subject_type TEXT NOT NULL CHECK (subject_type IN ('claim', 'relationship', 'alternative')),
    subject_id TEXT NOT NULL,
    format TEXT,                            -- web_page, fact_check_card, short_script,
                                            -- carousel, report
    published_at TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    retracted_at TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (subject_type, subject_id, format)
);

-- Append-only. Never silently rewrite history.
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL,                    -- username or 'system' / 'agent'
    action TEXT NOT NULL,                   -- create, update, approve, reject,
                                            -- status_change, correction, publish, retract
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_claims_status ON claims (status);
CREATE INDEX IF NOT EXISTS idx_claims_review ON claims (review_status);
CREATE INDEX IF NOT EXISTS idx_claims_norm ON claims (normalized_claim);
CREATE INDEX IF NOT EXISTS idx_claims_speaker ON claims (speaker);
CREATE INDEX IF NOT EXISTS idx_claims_topic ON claims (topic);
CREATE INDEX IF NOT EXISTS idx_sources_canonical ON sources (canonical_url);
CREATE INDEX IF NOT EXISTS idx_sources_tier ON sources (source_tier);
CREATE INDEX IF NOT EXISTS idx_evidence_source ON evidence (source_id);
CREATE INDEX IF NOT EXISTS idx_claim_evidence_ev ON claim_evidence (evidence_id);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_reviews_subject ON reviews (subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_pub_subject ON publications (subject_type, subject_id);

-- Full-text search over claim text and original/translated text (Phase 1 RAG).
CREATE VIRTUAL TABLE IF NOT EXISTS claims_fts USING fts5(
    claim_id UNINDEXED,
    claim_text,
    normalized_claim,
    translated_text,
    tokenize = 'unicode61 remove_diacritics 2'
);
