# Security policy

## Never commit

- API keys, tokens, credentials
- private documents
- personal information of private individuals

Use `.env` (gitignored) and `.env.example` as the template. A secret scanner
(gitleaks) should be run locally and in CI.

## Reporting a vulnerability

Open a private security advisory or contact the maintainers directly.
Do not open public issues for vulnerabilities.

## Data safety

- The database and archives contain references to public documents only.
- Archived third-party content is limited to short excerpts, hashes and
  metadata; we do not mirror copyrighted news sites.
