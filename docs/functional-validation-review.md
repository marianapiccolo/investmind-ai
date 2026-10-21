# AWS functional validation review

This record describes validation of the deployed demo, the calculation convention
behind its test results, and the bounded corrections made during review. It is a
record of observed behavior rather than a load test or a complete financial audit.

## Verified deployment and application flows

The AWS demo was exercised through HTTPS on the EC2 host. Verified flows include
login, portfolio creation, asset selection, buy/sell transactions, market quote
caching, background history synchronization, financial knowledge retrieval,
conversational tool use and asynchronous report generation.

The AWS database is independent of the development database. An initially empty
asset catalog explained the empty transaction asset selector. Registering the
Asset model in Django administration made catalog maintenance available; adding
an asset supplied the record needed by the form. Model registration alone did
not create or import asset records.

## Market data and knowledge validation

- A successful quote request was stored in Redis and read back through the cache
  helper with the same value.
- A historical synchronization task reached the Celery worker. An initial request
  was rejected by the provider's rate limit; a later separately submitted task
  succeeded and stored 100 AAPL price records.
- The recorded history ranged from 28 May to 19 October 2026. A closing price dated
  16 October was available before the first transaction on 17 October.
- Knowledge ingestion produced five documents and 31 embedded chunks. A semantic
  diversification query returned three relevant passages with source references.
- The conversational analyst used portfolio tools and financial knowledge search
  in the deployed environment.

The history retry was submitted during validation. It is not evidence of an
automatic application retry or global provider rate-limit queue. A fresh quote
and stored historical prices are separate data sources.

## Reconstruction of the demo return

The verified snapshot contained seven transactions across two portfolios and
31 knowledge chunks. The following calculation uses portfolio 2, Reserva, only.

Transactions on 17 October 2026:

| Type | Quantity | Unit price in USD | Signed flow in USD |
| --- | ---: | ---: | ---: |
| BUY | 5 | 10 | +50 |
| BUY | 3 | 11 | +33 |
| BUY | 1 | 8 | +8 |
| SELL | 2 | 7 | -14 |

The resulting position was seven shares with a signed flow of 77. Using the
available close of 343.46, the end-of-day holding value was 2404.22.

On 18 October, a sale of one share at the entered test price of 4 left six shares.
Using the same available close, the holding value became 2060.76. Under the
implemented holdings-only convention, purchases are contributions and sales are
withdrawals; a separate cash account is not modeled. The end-of-period
flow-adjusted return is:

```text
(2060.76 - (-4)) / 2404.22 - 1 = approximately -14.12%
```

The later close of 342.94 produces an ending value of 2057.64 and a linked return
of approximately -14.25%. Net signed flows are 73. The large loss reflects the
entered transaction prices, not evidence of a Sunday stock-price movement.

These records are test executions. Full brokerage accounting with cash, fees,
dividends and intraday cash-flow timing requires additional modeling. The
correction retained the existing end-of-period convention.

The dashboard's unrealized return and the historical period return are different
metrics. A formatting change to a large dashboard percentage does not change
either calculation or establish that its demo inputs represent real executions.

## Annualization availability correction

Valuation dates combine transaction dates and stored market-price dates.
Previously, all resulting return intervals were used with the daily
252-observation annualization convention. This included transaction-only dates
without fresh prices. An additional neutral weekend contribution could therefore
change annualized volatility by adding a zero-return observation.

Each valuation point now records whether a market-price update exists on that
date. If a computed return ends on a transaction-only date, the series is marked
unsupported for the existing annualization convention. Annualized volatility and
downside deviation are returned as null with an explicit reason. Annualized
Sharpe/Sortino calculations raise a descriptive domain validation error.
Annualized risk metrics also require at least two return observations.

Period returns, linked return, cash flows, holdings, drawdown and event dates are
preserved. Weekend transactions are neither deleted nor moved. Normal
Friday-to-Monday price observations remain supported. A fresh price means a dated
record, even if its numeric close is unchanged.

This is a conservative availability guard. It is not an exchange calendar,
missing-price detector, market-session resampling implementation or a complete
mixed-market/crypto annualization model. A long series containing an unsupported
transaction-only return interval also remains unavailable for annualization.
Short supported samples still provide limited evidence about risk.

The API exposes optional `annualization_available` and
`annualization_unavailable_reason` fields. Report instructions require explanation
of null metrics rather than estimation from available period returns.

## AI failure classification and runtime adjustment

`AIProviderError` carries a validated diagnostic code and a fixed public message.
The report task persists that safe message and logs the report ID and code.
Output-limit, other incomplete, empty, invalid-JSON and missing-configuration
failures are distinguished from a generic provider failure. Raw exception text
is not copied into a public report error.

The backend correction added no automatic task retries or extra provider calls.
A later runtime change increased the output ceiling from 1200 to 4096 after
report 6 failed with the output-limit-specific message. The model and timeout
remained unchanged. Report 7 completed and passed evaluation, preserving the
-14.25% return/drawdown and explaining the unavailable annualized metrics.

The cause of the older report 4 failure remains undetermined without its original
worker log. A subsequent successful request does not establish that cause.
See [report output and presentation](demo-report-output-limit.md) for the verified
runtime adjustment and container recreation procedure.

## Automated and browser verification

Fourteen regression tests were added for the recorded transactions, unsupported
event sampling, normal market observations, a single-return sample, API
serialization, response error classification and safe error persistence. The
complete project Django suite then passed 288 tests in its Docker/PostgreSQL
environment.

The later risk-template correction passed nine targeted tests, including five
new template tests. CI and image publication completed successfully. The deployed
image from commit `975ba1a705e278e120992e0ef04e132ad373b8c7` passed Ansible deployment
checks, and browser inspection on 21 October 2026 confirmed:

- Unavailable annualized metrics displayed with an explanatory banner.
- A negative best-period value of -0.15% displayed in red without a leading plus.
- Period return and maximum drawdown preserved at -14.25%.

The template tests do not execute chart JavaScript; browser inspection provides
separate presentation evidence. The existing chart script was not modified.

Relevant tests can be rerun from the repository root **on the Mac**:

```bash
docker compose up -d --wait db redis
docker compose run --rm web python manage.py test \
  portfolios.tests.test_functional_validation_regressions \
  portfolios.tests.test_portfolio_performance \
  portfolios.tests.test_portfolio_risk \
  portfolios.tests.test_risk_adjusted_performance \
  portfolios.tests.test_performance_attribution \
  portfolios.tests.test_ai_openai_client \
  portfolios.tests.test_ai_report_task \
  portfolios.tests.test_risk_template \
  portfolios.tests.test_web_risk
```

Automated provider calls are mocked where appropriate. Passing those tests does
not establish live provider availability, HTTPS validity or every deployment
configuration. The recorded functional checks address those paths separately.

## Backup and shutdown

The 21 October snapshot passed checksum verification and an isolated local
PostgreSQL restoration test. Reported restored counts included one user, one
asset, two portfolios, two positions, seven transactions and 31 knowledge chunks.
The temporary restoration database and its anonymous volumes were removed.

After the final presentation deployment was checked, EC2 was stopped and the CLI
returned `stopped`. The [backup guide](aws-demo-backup.md) and
[operations guide](aws-demo-operations.md) describe repeatable procedures; this
record is not a substitute for verifying future backups and releases.

## Remaining scope

- Use coherent demo execution prices and explain the historical window.
- Standardize grouping and decimal separators for displayed returns.
- Retain explicit unavailable-data and short-sample explanations.
- Treat provider quotas, report evaluation and model output as bounded controls,
  not availability or financial-accuracy guarantees.
- Keep manual backup, state protection and deployment downtime limitations visible.
- Complete the documentation and presentation review before identifying the first
  stable project release.
