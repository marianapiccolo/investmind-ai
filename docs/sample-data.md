# Sample portfolio data

The `prepare_sample_data` management command imports market observations and creates an optional sample portfolio for an existing user. It has three separate operations: `sync`, `preview` and `create`.

| Asset | Sector | Initial quantity | Currency |
| --- | --- | --- | --- |
| AAPL — Apple Inc. | Technology | 10 | USD |
| JNJ — Johnson & Johnson | Healthcare | 12 | USD |
| JPM — JPMorgan Chase & Co. | Financial Services | 8 | USD |

The quantities and purchases are hypothetical sample transactions. Execution prices come from stored Alpha Vantage daily closing prices, rounded to the transaction field's four decimal places. They are not fabricated market prices or records of actual trades. All three purchases share the same observation date.

## Import market observations

Run from the repository directory on the Mac, with Docker Desktop running and the Alpha Vantage key configured in the existing local environment:

```bash
docker compose run --rm web python manage.py prepare_sample_data sync
```

This operation makes up to six provider requests: one daily history request and one quote request for each asset. Requests are spaced two seconds apart; provider quotas and availability still apply. A failed request stops the operation without automatic retries. No OpenAI requests are made.

All responses are fetched and validated before importing database rows. Missing catalog assets are created. Existing assets must already have the expected USD currency, stock type and sector; their metadata is preserved. Historical prices are inserted only when absent. A different stored price or provider for the same asset and date causes the import to roll back, preserving existing prices. Such conflicts require review rather than an automatic overwrite.

After the database import, current quotes are cached through the existing cache configuration and timeout. A cache failure prints a warning while retaining imported historical prices. Cache expiry can cause subsequent page requests to contact the market provider through the application's existing behavior.

The import creates no users, portfolios, positions or transactions. It uses the database shared asset catalog and price history; newly imported observations are also available to existing portfolios holding these assets.

## Preview a new portfolio

Use the username belonging to the intended portfolio owner:

```bash
docker compose run --rm web python manage.py prepare_sample_data preview \
  --username mariana
```

The default name is `Sample Portfolio`. The default observation window contains the latest 60 shared historical observation dates. Supported window sizes range from 30 to 100:

```bash
docker compose run --rm web python manage.py prepare_sample_data preview \
  --username mariana \
  --name "Sample Portfolio" \
  --observations 60
```

The preview prints the owner, dates, quantities and purchase prices. It performs no provider requests and changes neither the database nor cache. Missing data, an inactive or nonexistent user, a conflicting portfolio name, invalid prices or misaligned history dates stop preparation with an explanatory error.

Observation dates come from provider data rather than a generated weekday calendar. Available dates for all three assets must match from the selected start date onward. This prevents a sample purchase from introducing an unsupported transaction-only interval. A 60-observation window is a limited historical sample; it does not establish the reliability of annualized estimates.

## Create the portfolio

After reviewing the preview, use the same owner, name and window:

```bash
docker compose run --rm web python manage.py prepare_sample_data create \
  --username mariana
```

This operation creates one USD portfolio, three purchases and three positions using the existing transaction service. No provider calls are made. Purchases use a UTC timestamp anchored to the selected date; this is a daily valuation convention, not intraday execution simulation. If a purchase fails, the new portfolio, its transactions and its positions are rolled back together.

A repeated creation with the same user and portfolio name is refused without modifying existing records. Existing portfolios, transactions and positions are preserved. A later import or a different observation window can produce a different preview because provider data advances over time. Reproducibility is relative to the stored observations and selected parameters.

## Application checks

Start the local application if necessary:

```bash
docker compose up -d web worker beat
```

Open <http://127.0.0.1:8000/> and select `Sample Portfolio`.

- Dashboard: three positions, current quotes, allocations and unrealized returns.
- Transactions: three initial purchases with matching historical prices and dates.
- Performance: historical portfolio values and time-weighted returns.
- Risk: period returns, drawdown and annualized metrics when supported by the existing calculation rules.
- Diversification: three assets and pairwise correlation results when sufficient comparable observations are available.
- AI features: reports and the analyst use the selected portfolio's context. OpenAI configuration, worker availability and indexed knowledge remain separate prerequisites.

The dashboard's quote-based valuation can differ from the latest historical closing valuation. Diversification calculations retain their existing use of stored asset history; this command does not change analytical methods or force every analysis to use the same window. No financial calculations, templates, APIs, scheduled jobs or database schema are changed.

## Tests

```bash
docker compose run --rm web python manage.py test \
  portfolios.tests.test_sample_data_command \
  portfolios.tests.test_transactions \
  portfolios.tests.test_portfolio_performance \
  portfolios.tests.test_portfolio_risk \
  portfolios.tests.test_portfolio_diversification
```

Command tests mock external requests and exercise import validation, pacing, cache behavior, transaction rollback, preview behavior, duplicate prevention and historical analytics. They require no live provider credentials. Package validation used Django 6.1 with an isolated SQLite database; the command and existing PostgreSQL behavior must also pass the Docker tests above. No AWS resources or live provider accounts were accessed during package validation.

## Deployment

Merge and publish the application change through the existing CI and registry workflow. Deploy the matching image before invoking the new command in EC2. Import and creation are explicit operator actions; neither runs at application startup, during migrations or automatically after deployment. Back up the AWS database before importing or creating sample records there. Local preparation does not copy database records to AWS.

## References

- [Alpha Vantage daily market data and quote API](https://www.alphavantage.co/documentation/)
- [Django database transactions](https://docs.djangoproject.com/en/6.1/topics/db/transactions/)
