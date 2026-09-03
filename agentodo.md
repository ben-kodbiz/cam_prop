# AGENT TODO — Open Evidence & Corporate Accountability Pipeline

## Project codename

`open-evidence`

## Mission

Build an open-source, evidence-first platform for documenting:

1. Claims about Israel/Palestine and related conflicts.
2. Claims made by governments, military organizations, companies, media outlets and activists.
3. Whether claims are supported, contradicted, misleading, disputed or currently unverifiable.
4. International-law documents and findings relevant to the conflict.
5. Corporate relationships, contracts, technology services and public statements relevant to ethical consumer decisions.
6. Practical open-source alternatives for users who want to reduce dependence on particular technology companies.

### Core principle

> **Evidence first. Attribution always. Uncertainty explicitly stated.**

This project MUST NOT become an automated propaganda generator.

It must be capable of concluding:

* Supported
* Mostly supported
* Misleading
* Unsupported
* Contradicted
* Disputed
* Insufficient evidence
* Unknown

regardless of which side made the claim.

---

# 1. NON-NEGOTIABLE RULES

## 1.1 No predetermined conclusion

Never implement:

```text
Israel = false
USA = false
Palestine = true
West = propaganda
```

or any equivalent hard-coded assumption.

The system evaluates individual claims.

---

## 1.2 No LLM-generated facts without evidence

The LLM may:

* summarize
* classify
* extract claims
* compare evidence
* identify contradictions
* generate draft explanations

The LLM MUST NOT:

* invent evidence
* invent statistics
* invent quotations
* invent sources
* upgrade "unknown" to "true"
* downgrade "disputed" to "false"
* manufacture citations

Hard rule:

```text
NO SOURCE -> NO FACTUAL ASSERTION
```

---

## 1.3 Primary sources have priority

Source hierarchy:

### Tier 1 — Primary

* ICJ
* ICC
* UN
* UN agencies
* official court records
* official government documents
* parliamentary records
* corporate filings
* company contracts
* official company statements
* independently verifiable datasets
* satellite/remote-sensing evidence where appropriate

### Tier 2 — Professional journalism

Examples:

* Reuters
* AP
* BBC
* Financial Times
* Guardian
* other established outlets

### Tier 3 — Specialist investigations

* academic research
* investigative journalism
* reputable NGOs
* research institutes

### Tier 4 — Social media

Use primarily for:

* discovering claims
* discovering events
* locating original material

Never automatically treat social-media posts as proof.

---

# 2. PROJECT ARCHITECTURE

Use a simple local-first architecture.

```text
                 ┌─────────────────────┐
                 │ SOURCE DISCOVERY    │
                 │ RSS / APIs / URLs   │
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │ SOURCE INGESTION    │
                 │ HTML / PDF / JSON   │
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │ SOURCE ARCHIVE      │
                 │ hash + metadata     │
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │ CLAIM EXTRACTION    │
                 │ LLM-assisted        │
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │ EVIDENCE ENGINE     │
                 │ primary + secondary │
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │ HUMAN REVIEW        │
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │ PUBLISHED DATA      │
                 │ JSON + SQLite       │
                 └──────────┬──────────┘
                            ↓
              ┌─────────────┼─────────────┐
              ↓             ↓             ↓
           Website        Reports        Social
```

---

# 3. FREE / OPEN-SOURCE STACK

Prefer the following.

## Language

Primary:

```text
Python 3.x
```

Frontend:

```text
HTML
CSS
Vanilla JavaScript
```

Do NOT introduce React/Tailwind unless there is a compelling reason.

The project should remain easy to maintain.

---

# 4. DATABASE

Use:

```text
SQLite
```

SQLite is ideal for the first version because the database is a single portable file and requires no database server.

Suggested:

```text
data/evidence.db
```

Never put secrets inside the database.

---

# 5. FULL DATABASE MODEL

Create:

```text
sources
claims
evidence
claim_evidence
entities
organizations
people
events
corporate_relationships
company_statements
alternatives
reviews
publications
audit_log
```

## sources

```sql
id
url
canonical_url
title
publisher
author
published_at
retrieved_at
source_type
source_tier
language
content_hash
archive_path
reliability_notes
```

## claims

```sql
id
claim_text
normalized_claim
speaker
speaker_type
organization_id
published_at
discovered_at
status
confidence
importance
topic
review_status
reviewer
created_at
updated_at
```

Allowed status:

```text
supported
mostly_supported
misleading
unsupported
contradicted
disputed
insufficient_evidence
unknown
```

## evidence

```sql
id
source_id
evidence_type
excerpt
page_number
section
context
supports_claim
strength
created_at
```

Never store huge copyrighted passages.

Store:

* short excerpts where legally appropriate
* page/section references
* URL
* source metadata
* local archive/hash

---

# 6. EVIDENCE SCORING

Do NOT create a simplistic:

```text
TRUE = 100
FALSE = 0
```

Instead calculate separate dimensions.

Example:

```yaml
source_quality: 0-5
primary_source: true/false
independence: 0-5
directness: 0-5
corroboration: 0-5
contradiction: 0-5
recency: 0-5
```

Then let the reviewer determine the final classification.

The score is evidence assistance, NOT truth itself.

---

# 7. CLAIM PROCESSING PIPELINE

For every discovered statement:

```text
1. Capture original statement
2. Identify speaker
3. Identify date
4. Identify organization
5. Normalize claim
6. Split compound claims
7. Identify factual assertions
8. Search primary sources
9. Search independent corroboration
10. Search contradictory evidence
11. Assign provisional status
12. Human review
13. Publish
```

---

# 8. COMPOUND CLAIM SPLITTING

Example:

```text
"X happened because Y and therefore Z is justified."
```

must become:

```text
CLAIM A:
X happened.

CLAIM B:
Y caused X.

CLAIM C:
Z follows from X/Y.
```

Never fact-check a complicated political argument as though it were one factual statement.

---

# 9. EVIDENCE AGENT

Create:

```text
agents/evidence_agent.py
```

Responsibilities:

* retrieve evidence
* compare source statements
* identify contradictions
* identify missing evidence
* generate provisional assessment

Output:

```json
{
  "claim_id": "...",
  "assessment": "disputed",
  "confidence": 0.82,
  "supporting_evidence": [],
  "contradicting_evidence": [],
  "missing_evidence": [],
  "reasoning_summary": ""
}
```

The final database status must not be changed automatically for high-impact claims.

---

# 10. HUMAN REVIEW GATE

Anything involving:

* deaths
* alleged war crimes
* genocide
* terrorism
* accusations against individuals
* allegations against companies
* allegations of illegal conduct
* financial relationships
* military activity
* international-law conclusions

requires human approval before publication.

Pipeline:

```text
AI discovery
      ↓
AI analysis
      ↓
human verification
      ↓
publication
```

NOT:

```text
AI → Internet
```

---

# 11. INTERNATIONAL-LAW MODULE

Create:

```text
modules/international_law/
```

Track:

```text
ICJ
ICC
UN Security Council
UN General Assembly
UN Human Rights Council
UN commissions
international treaties
national courts
```

Every legal record must contain:

```text
court/organization
case/document
date
jurisdiction
document type
actual finding
what the finding DOES NOT establish
source
```

The last field is extremely important.

Example:

```text
Finding:
Court issued provisional measure X.

DO NOT automatically transform this into:
"Court finally ruled that X occurred."
```

Distinguish:

```text
allegation
provisional measure
advisory opinion
judgment
arrest warrant
conviction
investigative finding
political resolution
```

---

# 12. CORPORATE ACCOUNTABILITY MODULE

Create:

```text
modules/corporate/
```

Track companies such as:

```text
Amazon
Google
Microsoft
other companies as evidence warrants
```

Do not begin with a predetermined accusation.

For every company create:

```text
company
service
customer
contract
date
contract value
public documentation
reported use
company response
independent investigation
current status
confidence
```

Example:

```yaml
company: ExampleCorp
relationship:
  service: cloud infrastructure
  customer: government entity
  contract: documented
  value: documented/unknown
  period: YYYY-YYYY

evidence:
  primary:
  secondary:

company_response:
  statement:
  date:

assessment:
  status: documented_relationship
  confidence: high
```

Possible relationship classifications:

```text
documented_contract
documented_service
reported_relationship
company_denial
company_confirmation
disputed
unknown
ended
ongoing
```

Do NOT automatically classify a documented commercial relationship as criminal conduct.

---

# 13. COMPANY RESPONSE TRACKING

Every significant corporate allegation must include:

```text
What is alleged?
Who alleges it?
What evidence supports it?
What does the company say?
What independent evidence exists?
What remains unknown?
```

This prevents the project from becoming one-sided.

---

# 14. BOYCOTT / ALTERNATIVES MODULE

The purpose is:

> Help users make informed voluntary consumer choices.

NOT:

> Harass employees or individuals.

Database:

```text
product
company
category
dependency
alternative
alternative_license
alternative_hosting
migration_difficulty
privacy_notes
self_hosting_available
```

Example:

```yaml
category: cloud_storage

commercial_service:
  company: ExampleCorp
  product: ExampleDrive

alternatives:
  - Nextcloud
  - local NAS
  - WebDAV-compatible server
```

Only recommend alternatives that actually exist and are maintained.

---

# 15. OPEN-SOURCE ALTERNATIVE CATEGORIES

Research and maintain alternatives for:

```text
cloud storage
office suites
email
search
cloud computing
Kubernetes hosting
CI/CD
Git hosting
video conferencing
analytics
DNS
monitoring
object storage
databases
AI inference
AI development
password management
```

Prefer:

```text
open-source
self-hostable
Linux-compatible
documented
actively maintained
```

---

# 16. USER MIGRATION GUIDES

For each alternative:

```text
What it replaces
Why someone may choose it
Installation difficulty
Self-hosting requirements
Data migration
Limitations
Security considerations
License
Project health
```

Never claim:

```text
"100% ethical"
```

Instead say:

```text
"Provides greater user control because..."
```

---

# 17. FRONTEND

Build a lightweight PWA.

No heavy frontend framework initially.

Structure:

```text
/
├── index.html
├── claims.html
├── claim.html
├── companies.html
├── company.html
├── sources.html
├── methodology.html
├── alternatives.html
├── about.html
├── css/
├── js/
├── data/
└── assets/
```

---

# 18. MAIN PAGE

Show:

```text
OPEN EVIDENCE

Evidence-based documentation of contested claims,
international records and corporate relationships.

[ Search ]

Latest reviewed claims

[ Supported ]
[ Misleading ]
[ Contradicted ]
[ Disputed ]
[ Unknown ]

Corporate accountability

Open-source alternatives
```

Avoid inflammatory slogans.

---

# 19. CLAIM PAGE

Every claim page should show:

```text
CLAIM

Who said it
When
Original source

ASSESSMENT

Status
Confidence

WHY

Short explanation

SUPPORTING EVIDENCE

...

CONTRADICTING EVIDENCE

...

WHAT WE DON'T KNOW

...

PRIMARY SOURCES

...

COMPANY/GOVERNMENT RESPONSE

...

LAST REVIEWED
```

---

# 20. METHODOLOGY PAGE

This is mandatory.

Explain:

```text
How claims are selected
How sources are ranked
How evidence is evaluated
How conflicts are handled
How corrections work
How AI is used
How humans review material
```

Include:

> "The project does not assume that any government, political movement, company, media organization or activist group is always truthful or always dishonest."

---

# 21. CORRECTION SYSTEM

Every published record needs:

```text
created_at
updated_at
last_reviewed
reviewer
revision
```

Allow:

```text
Correction
Clarification
Evidence update
Status change
Source removal
```

Maintain an audit trail.

Never silently rewrite history.

---

# 22. SOURCE ARCHIVING

For every important source:

```text
URL
retrieval timestamp
SHA256 hash
publisher
title
publication date
document type
archive location
```

Recommended structure:

```text
archive/
  YYYY/
    MM/
      source-id/
        metadata.json
        source.pdf
        source.html
        sha256.txt
```

Respect copyright.

Do not mirror entire copyrighted news websites.

For PDFs/documents where redistribution is permitted, retain the original.

Otherwise retain:

```text
metadata
hash
URL
short quotation
notes
```

---

# 23. CONTENT HASHING

Calculate:

```text
SHA256
```

for archived documents.

This allows later verification that:

```text
the evidence examined today
=
the evidence originally captured
```

---

# 24. RSS / INGESTION

Create:

```text
ingestion/
├── rss.py
├── html.py
├── pdf.py
├── sitemap.py
└── scheduler.py
```

Start with RSS wherever available.

Avoid aggressive crawling.

Respect:

```text
robots.txt
rate limits
terms of service
copyright
```

---

# 25. AI / LLM

Architecture must support local models.

Preferred interface:

```text
OpenAI-compatible HTTP API
```

Then local inference can use:

```text
llama.cpp
Ollama
LM Studio
```

without tying the project to a proprietary API.

Configuration:

```yaml
llm:
  provider: local
  endpoint: http://localhost:1234/v1
  model: configurable
```

Do not hard-code API keys.

---

# 26. RAG

Do NOT immediately build a giant vector database.

Phase 1:

```text
SQLite
FTS5
metadata
keyword search
```

SQLite's built-in capabilities are sufficient for the first version.

Phase 2:

```text
embedding generation
vector index
hybrid retrieval
```

Only introduce vector search when actual data volume demonstrates the need.

---

# 27. SEARCH STRATEGY

Use hybrid retrieval:

```text
exact phrase
AND
keyword search
AND
metadata filtering
AND
semantic search
```

Never allow semantic similarity alone to establish factual correctness.

---

# 28. AUTOMATED SOCIAL CONTENT

Create:

```text
publishing/
├── short_generator.py
├── carousel_generator.py
├── post_generator.py
└── citation_generator.py
```

Every generated item must include:

```text
claim
assessment
source
publication date
review date
```

Example:

```text
CLAIM CHECK

Claim:
"..."

Assessment:
MISLEADING

Why:
...

Primary evidence:
ICJ document, YYYY-MM-DD

Sources:
...
```

---

# 29. SOCIAL CONTENT SAFETY

Never generate:

```text
harassment
threats
dehumanization
racial/religious attacks
calls for violence
personal targeting
doxxing
```

Criticize:

```text
policies
claims
institutions
documented actions
corporate decisions
```

Do not target ordinary employees or private individuals.

---

# 30. CONTENT GENERATION RULE

The LLM should generate from structured evidence:

```text
DATABASE
   ↓
CLAIM
   ↓
EVIDENCE
   ↓
ASSESSMENT
   ↓
HUMAN APPROVAL
   ↓
CONTENT
```

Never:

```text
LLM
 ↓
political opinion
 ↓
published as fact
```

---

# 31. SEO

Use:

```text
semantic HTML
OpenGraph
JSON-LD
sitemap.xml
robots.txt
canonical URLs
descriptive titles
descriptive meta descriptions
```

Each claim should have a stable URL:

```text
/claim/CLM-2026-0001/
```

Each source:

```text
/source/SRC-2026-0001/
```

Each company:

```text
/company/examplecorp/
```

---

# 32. STATIC DEPLOYMENT

Primary:

```text
GitHub Pages
```

GitHub Pages can publish a static site directly from a repository.

Optional mirror:

```text
Cloudflare Pages
```

Cloudflare Pages supports static HTML deployment and has a free plan.

Do NOT require a backend server for the public site.

Generate:

```text
data/claims.json
data/companies.json
data/sources.json
data/alternatives.json
```

Frontend loads these files.

---

# 33. LOCAL BACKEND

Development/research environment:

```text
Python
SQLite
FastAPI
```

FastAPI is optional.

The public production website should remain static wherever possible.

---

# 34. FREE / OPEN-SOURCE DEPENDENCY POLICY

Prefer:

```text
Python
SQLite
FastAPI
BeautifulSoup
feedparser
PyMuPDF
httpx
pytest
ruff
mypy
Git
GitHub Actions
```

For frontend:

```text
HTML
CSS
JavaScript
Web APIs
```

Avoid unnecessary dependencies.

---

# 35. NO CLOUD AI REQUIREMENT

The entire research pipeline must work using:

```text
local LLM
local embeddings
local SQLite
local filesystem
```

Internet is needed only for:

```text
source acquisition
public deployment
optional external verification
```

This keeps operating costs close to zero.

---

# 36. BACKUP

Implement:

```text
scripts/backup.sh
```

Backup:

```text
SQLite DB
source metadata
claim JSON
configuration
hash manifests
```

Never depend exclusively on GitHub.

Maintain local copies.

---

# 37. GIT STRUCTURE

Recommended:

```text
open-evidence/
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── SECURITY.md
├── METHODOLOGY.md
├── CHANGELOG.md
├── agentodo.md
│
├── app/
├── agents/
├── ingestion/
├── evidence/
├── corporate/
├── international_law/
├── publishing/
├── scripts/
├── tests/
│
├── data/
│   ├── schema.sql
│   ├── seed/
│   └── generated/
│
├── archive/
│
└── web/
    ├── index.html
    ├── claims.html
    ├── companies.html
    ├── alternatives.html
    ├── methodology.html
    ├── css/
    └── js/
```

---

# 38. TESTING

Create automated tests for:

```text
claim extraction
claim splitting
source ranking
duplicate detection
URL canonicalization
hash generation
SQLite schema
status transitions
citation generation
JSON generation
static site generation
```

Critical invariant:

```text
A claim cannot become "supported"
without at least one evidence record.
```

Critical invariant:

```text
A claim cannot become "contradicted"
without evidence supporting the contradiction.
```

Critical invariant:

```text
Unknown remains unknown when evidence is insufficient.
```

---

# 39. DUPLICATE DETECTION

The same claim may appear in:

```text
Reuters
Guardian
BBC
social media
government statement
company statement
```

Do not create five separate claims automatically.

Normalize:

```text
speaker
statement
event
date
subject
predicate
object
```

and detect duplicates.

---

# 40. EVENT MODEL

Separate:

```text
CLAIM
```

from:

```text
EVENT
```

Example:

```text
EVENT:
Airstrike occurred.

CLAIM:
"Only military targets were struck."

CLAIM:
"Civilians were deliberately targeted."

CLAIM:
"The strike violated international humanitarian law."
```

These require different evidence.

---

# 41. LANGUAGE SUPPORT

Initial:

```text
English
Malay
```

Later:

```text
Arabic
Indonesian
```

Store original language.

Never replace the original claim with a translation.

Database:

```text
original_text
original_language
translated_text
translation_method
```

---

# 42. TRANSLATION RULE

For legal or politically sensitive documents:

```text
original source
+
translation
```

Never present an AI translation as the authoritative legal wording.

---

# 43. ANALYTICS

Track:

```text
claims reviewed
claims by status
claims by source
claims by organization
claims by topic
evidence per claim
correction rate
average review age
```

Do NOT optimize for:

```text
viral outrage
engagement
rage
partisan sharing
```

Optimize for:

```text
source quality
citation completeness
correction speed
review coverage
```

---

# 44. CORPORATE BOYCOTT SCORE

Do NOT create a simplistic:

```text
Company = 90% evil
```

Instead create transparent dimensions:

```text
documented relationship
contract evidence
service type
customer
duration
company acknowledgement
company denial
independent corroboration
current status
```

Users decide what action to take.

The site provides the evidence.

---

# 45. ALTERNATIVE SCORE

Score practical alternatives based on:

```text
open-source
self-hostable
active development
security
documentation
migration difficulty
cost
vendor lock-in
privacy
community
```

Not political affiliation.

---

# 46. AUTONOMOUS DAILY PIPELINE

Run:

```text
06:00
Source discovery

07:00
Download new documents

08:00
Extract claims

09:00
Find evidence

10:00
Generate review queue

Human review

Later:
Generate approved content
```

Do not automatically publish politically sensitive claims.

---

# 47. REVIEW QUEUE

Dashboard:

```text
┌─────────────────────────────────────┐
│ REVIEW QUEUE                        │
├─────────────────────────────────────┤
│ HIGH PRIORITY                       │
│                                     │
│ Claim #104                          │
│ 7 supporting sources                │
│ 3 contradictory sources             │
│ Primary source available             │
│                                     │
│ [Review] [Reject] [Need Evidence]   │
└─────────────────────────────────────┘
```

---

# 48. HUMAN REVIEW CHECKLIST

Before publishing:

```text
[ ] Is the original claim correctly represented?
[ ] Is the speaker correctly identified?
[ ] Is the date correct?
[ ] Is there a primary source?
[ ] Did we search contradictory evidence?
[ ] Did we separate fact from interpretation?
[ ] Did we distinguish allegation from finding?
[ ] Did we accurately represent legal terminology?
[ ] Did we include the other party's response where relevant?
[ ] Are citations correct?
[ ] Is uncertainty clearly stated?
[ ] Could this wording falsely imply certainty?
```

---

# 49. EDITORIAL STYLE

Use:

```text
calm
precise
direct
evidence-based
non-inflammatory
```

Prefer:

> "The available evidence does not support this claim."

instead of:

> "They are lying."

Prefer:

> "The statement is misleading because it omits..."

instead of:

> "They deliberately manipulated everyone."

Unless deliberate intent is itself established by evidence.

---

# 50. PHASE ROADMAP

## Phase 1 — Foundation

Build:

```text
repository
SQLite schema
source ingestion
claim database
basic frontend
methodology
tests
```

No AI required yet.

---

## Phase 2 — Evidence engine

Add:

```text
source ranking
claim extraction
evidence linking
contradiction detection
citation generation
review queue
```

---

## Phase 3 — Local AI

Add:

```text
llama.cpp / compatible API
claim extraction
summarization
evidence comparison
translation
draft generation
```

Human approval remains mandatory.

---

## Phase 4 — International-law database

Add:

```text
ICJ
ICC
UN
treaties
resolutions
court records
```

Create cross-links:

```text
claim
 ↓
event
 ↓
legal document
 ↓
primary evidence
```

---

## Phase 5 — Corporate accountability

Add:

```text
companies
contracts
services
government customers
company statements
investigations
timeline
```

---

## Phase 6 — Alternatives

Add:

```text
open-source replacement database
migration guides
self-hosting guides
privacy comparison
vendor-dependency mapping
```

---

## Phase 7 — Publishing

Generate:

```text
website
fact-check cards
short-form scripts
social graphics
weekly reports
monthly corporate reports
```

Only approved evidence may enter the publishing pipeline.

---

# 51. FUTURE: KNOWLEDGE GRAPH

Eventually build:

```text
PERSON
   │
   ├── said → CLAIM
   │             │
   │             ├── supported_by → SOURCE
   │             ├── contradicted_by → SOURCE
   │             └── concerns → EVENT
   │
ORGANIZATION
   │
   ├── owns → COMPANY
   ├── contracted_with → COMPANY
   └── issued → STATEMENT
```

This becomes significantly more powerful than a conventional blog.

---

# 52. FUTURE: PROPAGANDA PATTERN DETECTION

Do NOT automatically label something propaganda.

Instead detect patterns such as:

```text
unsupported certainty
selective omission
false equivalence
quote without context
outdated information
citation mismatch
misleading statistics
cherry-picked denominator
compound claim
appeal to authority
anonymous-source dependence
```

Output:

```text
Potential issue:
Selective omission

Evidence:
...

Human review required.
```

---

# 53. REPRODUCIBILITY

Every published assessment should be reproducible.

Someone should be able to obtain:

```text
claim ID
source IDs
source URLs
retrieval dates
evidence excerpts
assessment
methodology version
review date
```

and independently reach the same conclusion.

---

# 54. OPEN LICENSE

Code:

```text
AGPL-3.0
```

Data:

Prefer:

```text
CC BY 4.0
```

where legally appropriate.

Clearly distinguish:

```text
project-created data
third-party copyrighted material
government/public-domain material
```

---

# 55. SECURITY

Never commit:

```text
API keys
tokens
credentials
private documents
personal information
```

Use:

```text
.env
```

and provide:

```text
.env.example
```

Run:

```text
gitleaks
```

or another open-source secret scanner locally/CI.

---

# 56. SUCCESS CRITERIA

The first usable release is successful when:

```text
✓ User can search claims
✓ Every claim has provenance
✓ Sources are visible
✓ Evidence is linked
✓ Contradictory evidence is visible
✓ Unknown is a legitimate outcome
✓ Human approval exists
✓ Corrections are tracked
✓ Corporate relationships have evidence
✓ Alternatives are documented
✓ Site works without a backend
✓ Local LLM is optional
✓ No proprietary cloud service is required
✓ Repository can be cloned and reproduced
```

---

# 57. FINAL AGENT INSTRUCTION

Build incrementally.

DO NOT attempt the entire system in one pass.

Order:

```text
1. Repository
2. SQLite schema
3. Source ingestion
4. Claim model
5. Evidence model
6. Review workflow
7. Static website
8. Tests
9. Local LLM
10. International-law module
11. Corporate module
12. Alternatives
13. Publishing automation
14. Analytics
```

After every phase:

```text
run tests
inspect output
document decisions
commit changes
```

If a design choice is uncertain:

```text
choose the simplest reversible option
```

If evidence is insufficient:

```text
mark UNKNOWN
```

If sources disagree:

```text
mark DISPUTED
```

If an assertion cannot be independently verified:

```text
do not publish it as fact
```

The objective is not to create another propaganda machine.

The objective is to create a **transparent evidence machine that makes propaganda harder to sustain — regardless of who produces it.**
