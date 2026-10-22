# Number presentation

The dashboard, performance, risk, diversification and transaction pages use English (United States) number presentation. Commas separate thousands and periods separate decimal places.

| Value | Display |
| --- | --- |
| Positive return `33202.10` | `+33,202.10%` |
| Negative return `-1234.50` | `-1,234.50%` |
| Zero return `0` | `0.00%` |
| USD amount `2063.94` | `$2,063.94` |
| Quantity `1234.5678` | `1,234.5678` |
| Concentration index `0.4200` | `0.4200` |
| Unavailable annualized volatility | `Unavailable` |

Currency symbols continue to come from the existing page context. Money and percentages retain two decimal places. Displayed quantities, the concentration index and correlation retain four decimal places. Chart axes may omit unnecessary trailing zeroes. Existing sign conventions remain in place: signed return displays include `+` for positive values and `-` for negative values.

## Rendering

Django templates use the `g` suffix of `floatformat` to enable grouping while retaining the existing precision. These filters follow the active Django language; the current project sets `LANGUAGE_CODE = "en-us"`. A future language change requires a corresponding presentation review.

The shared `static/js/number_format.js` formatter uses `Intl.NumberFormat("en-US")` for chart labels and tooltips. Each chart page loads this file before its page-specific script. Percentage values are already expressed in percentage points, so the formatter appends `%` without multiplying the value by 100.

The dashboard displays `Unavailable` when annualized volatility is null and retains the supplied explanation in the tooltip. A valid zero remains `0.00%`.

Formatting applies to displayed values. Chart datasets, form input values, CSS allocation widths, financial calculations, API payloads and AI report evidence retain their existing representations. Generated report prose is outside this change.

## Local validation

Run from the repository directory on the Mac with Docker Desktop running:

```bash
docker compose run --rm web python manage.py test \
  portfolios.tests.test_number_presentation \
  portfolios.tests.test_risk_template \
  portfolios.tests.test_web_dashboard \
  portfolios.tests.test_web_performance \
  portfolios.tests.test_web_risk \
  portfolios.tests.test_web_diversification \
  portfolios.tests.test_web_transactions

docker compose up -d web
```

Open <http://127.0.0.1:8000/> and check the affected pages, including chart tooltips. Refresh the browser to load the updated JavaScript. Confirm that positive and negative returns, grouped amounts and unavailable metrics are readable. Check a narrow viewport and confirm that numeric transaction inputs still accept ordinary decimal values.

Before committing:

```bash
git diff --check
git status --short --branch
git diff --stat
```

## Validation scope

Package validation passed eight new presentation tests and five existing risk template tests using Django 6.1. The presentation tests render the supplied page templates with an isolated base template and controlled data. They cover grouping, signs, zero, null volatility, precision, script order, and preservation of chart JSON and form input values.

Ten JavaScript checks passed against the actual chart scripts using a stub DOM and Chart constructor. These checks exercise formatter output, chart callbacks, unchanged datasets and pages without charts. JavaScript syntax checks also passed.

The complete application, Docker environment and browser layout require the local checks above. No AWS deployment or AWS resource changes are part of this presentation patch.

## References

- [Django 6.1: floatformat](https://docs.djangoproject.com/en/6.1/ref/templates/builtins/#floatformat)
- [ECMAScript Internationalization API: NumberFormat objects](https://tc39.es/ecma402/#numberformat-objects)
