# Changelog

## Initial release scope — v1.0.0

This entry defines the first stable release scope. The annotated Git tag
identifies the final source commit; the release record identifies its published
image digest and deployment verification. Source approval, image publication and
AWS deployment are separate operations.

The recorded AWS baseline was functionally checked on 22 October 2026 using
application revision `bf89dad7e79b6976fc863114adfded3d153e2a31`. The later interface
changes listed below passed reported CI checks. Verification of the final `main`
image is required by the [release process](docs/release-process.md).

### Application and analytics

- Portfolio, asset, position and purchase/sale transaction management.
- Composition, historical performance, risk, attribution and diversification
  analytics under the implemented holdings-only calculation convention.
- Market quotes and daily history from Alpha Vantage, with Redis caching.
- English (United States) formatting for displayed amounts, percentages and chart
  labels, with explicit unavailable metrics.
- Optional sample portfolio preparation with separate import, preview and creation
  operations, preservation of existing records and duplicate prevention.

### Web interface

- Author attribution on the sign-in page for desktop and mobile layouts.
- Dashboard AI Analyst shortcut retaining the selected portfolio.
- Dashboard Refresh action that reloads the selected portfolio while respecting
  the existing market quote cache.
- Last selected portfolio retained across application pages within the current
  Django session, with ownership checks and fallback for unavailable selections.
- Period-end dates displayed beneath the best and worst return chart labels.

### AI services

- Structured portfolio reports generated asynchronously through Celery.
- Stored report contexts, evidence checks, required-content checks and evaluation
  of unavailable sections and language rules.
- Persistent conversations using allowlisted read-only portfolio tools.
- Retrieval of financial knowledge with OpenAI embeddings and PostgreSQL/pgvector.
- Classified provider/output failures with fixed public diagnostic messages.
- Boolean evidence comparison compatible with equivalent JSON/Python spellings,
  while retaining strict comparison for other values.

### Infrastructure and delivery

- Local Docker Compose development and production-like verification environments.
- Gunicorn application serving, WhiteNoise static assets and Caddy HTTPS ingress.
- AWS EC2 ARM64 infrastructure defined with Terraform and configured with Ansible.
- GitHub Actions checks and private GHCR image publication by immutable digest.
- Operator-initiated registry deployment with commit, platform and target checks.
- Database backups with checksum validation and isolated PostgreSQL restore tests.

### Validation and limitations

Targeted checks for number presentation, sample preparation and boolean evidence
passed in Docker/PostgreSQL. The deployed sample portfolio, analytical pages and
saved AI reports were checked. The recorded baseline backup restored with three
assets, three portfolios, ten transactions and 31 knowledge chunks.

The deployment is a single-host environment with manual startup and shutdown.
Publication does not automatically deploy or start EC2. Provider quotas and
availability remain external dependencies. Full brokerage cash accounting,
fees, dividends, high availability and automatic rollback are outside this
baseline. Passing the configured AI checks does not prove financial completeness.

The [functional validation record](docs/functional-validation-review.md) contains
the observed revisions, calculation assumptions and verification details.
