# AWS functional validation: calculation and AI error review

## Evidence from the demo

The AWS demo was stopped after a successful backup and isolated local restore.
The verified backup contains 7 transactions across 2 portfolios and 31 knowledge
chunks. The following reconstruction uses portfolio 2 (Reserva) only.

On 2026-10-17 its transactions were:

| Type | Quantity | Unit price | Signed flow |
| --- | ---: | ---: | ---: |
| BUY | 5 | 10 | +50 |
| BUY | 3 | 11 | +33 |
| BUY | 1 | 8 | +8 |
| SELL | 2 | 7 | -14 |

The position after these transactions was 7 shares and the signed flow was 77.
At the available close of 343.46, its end-of-day value was 2404.22.

On 2026-10-18, selling 1 share at the entered unit price of 4 left 6 shares.
Using the same available close, the value became 2060.76. In the existing
holdings-only convention, sales are treated as withdrawals and purchases as
contributions; a cash account is not modeled. The end-of-period flow-adjusted
return was `(2060.76 - (-4)) / 2404.22 - 1`, approximately -14.12%.
The later close of 342.94 gives a final value of 2057.64 and a linked return of
approximately -14.25%. Net signed flows are 73. The loss follows the entered
transaction prices; it is not evidence of a Sunday change in the stock price.

These test prices must not be interpreted as real executions. A genuine portfolio
with cash, fees, dividends or intraday cash-flow timing requires additional
modeling. This change preserves the current daily end-of-period convention.

## Bounded change to annualized metrics

Valuation dates are the union of transaction dates and stored market-price dates.
Previously every interval was passed to the 252-observation annualization formula,
including transaction-only dates without fresh prices. A neutral weekend
contribution could add an extra zero return and change annualized volatility.

Each valuation point now records whether that date contains a market-price update.
If a computed return ends on a transaction-only date, the series is marked
unsupported for the existing daily annualization convention. Annualized volatility
and downside deviation are returned as null with an explicit reason. Annualized
Sharpe/Sortino calculations raise a descriptive domain validation error.
Annualized risk also requires at least two return observations.

Period returns, linked return, cash flows, holdings, drawdown and event dates are
preserved. No weekend transaction is deleted or moved. Normal Friday-to-Monday
price observations remain supported. Equal closing prices are valid observations:
“fresh” refers to a dated price record, not a change in its numeric value.

This is a conservative availability check, not a complete exchange calendar,
missing-price detector, market-session resampling implementation, or support for
mixed-market/crypto annualization conventions. It does not promise reliable risk
estimates from a very short sample. A long sample containing any unsupported
transaction-only return interval is intentionally unavailable for annualization
until the sampling methodology is expanded.

The API exposes optional `annualization_available` and
`annualization_unavailable_reason` fields. The AI receives the reason and is
instructed to explain null metrics instead of estimating them.

## AI error messages

`AIProviderError` now carries a whitelisted diagnostic code and a fixed public
message. The report task persists that safe message and logs the report ID and
code. Incomplete output caused by `max_output_tokens`, other incomplete output,
empty output, invalid JSON, and missing configuration are distinguished from the
generic provider failure. Raw exception strings are never copied into the report.

No extra API calls, automatic task retries, model changes or token-limit increases
are introduced. Existing failed reports retain their saved messages. Without the
original worker log, the cause of report 4 remains undetermined: a later successful
report does not prove which failure occurred.

## Validation and next steps

14 regression tests cover the recorded demo transactions, unsupported event
sampling, normal market observations, a single-return sample, API serialization,
AI response error classification and safe report persistence. The 14 tests plus
21 existing related tests passed in an isolated review environment using Python
3.12, Django 5.2 and SQLite with the uploaded models (app migrations disabled for
this harness). External AI/market calls were mocked. This is not a PostgreSQL,
production-version, migration, HTTPS or live-model integration result.

Run the same tests in the project's Docker environment on the Mac, using its
actual Python, Django and PostgreSQL versions:

```bash
docker compose up -d --wait db redis
docker compose run --rm web python manage.py test \
  portfolios.tests.test_functional_validation_regressions \
  portfolios.tests.test_portfolio_performance \
  portfolios.tests.test_portfolio_risk \
  portfolios.tests.test_risk_adjusted_performance \
  portfolios.tests.test_performance_attribution \
  portfolios.tests.test_ai_openai_client \
  portfolios.tests.test_ai_report_task
```

After these pass, use the usual PR/CI/image-publication/registry-deploy flow.
The AWS instance can stay stopped during local validation. No migration or data
rewrite is needed. Existing reports are snapshots; validate new output by creating
one new report after deploying the reviewed image.
