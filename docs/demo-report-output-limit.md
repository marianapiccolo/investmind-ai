# Demo report output budget and risk presentation

## Observed configuration

On 2026-10-21 the AWS application reported:

- Model: `gpt-5.6-terra`
- `OPENAI_MAX_OUTPUT_TOKENS=1200`
- `OPENAI_TIMEOUT_SECONDS=30`

Report 6 was marked FAILED with the new output-limit-specific public message.
This identifies this particular failure; it does not establish the cause of the
older report 4 failure.

## Runtime adjustment

Test `OPENAI_MAX_OUTPUT_TOKENS=4096` in `/opt/investmind/shared/app.env`.
This remains a generation ceiling, not a requirement to generate that many tokens.
A higher ceiling permits greater token consumption. Test one new report before
making further changes. Keep the model and timeout unchanged for this experiment.

Validation result on 2026-10-21: the application loaded `4096` after recreating
the three application services. Report 7 completed and passed its automated
evaluation. Its risk section preserved the period return and maximum drawdown
and explained why annualized risk metrics were unavailable. This validates the
observed case; it does not guarantee every future report will fit this budget.

Use the existing root-owned environment helper's `read_env` and `write_env`
functions to preserve other environment values and its atomic write/0600 behavior.
Recreate `web`, `worker` and `beat` after changing the file: existing processes do
not reload a container's environment just because the file on disk changed.
The database, Redis and proxy services do not need to be recreated for this setting.

The existing deployment helper preserves this extra environment entry on later
deploys. This is per-environment runtime configuration; it is not baked into a new
image. Configure it independently on any replacement host or new environment.

Official reference:
https://developers.openai.com/api/docs/guides/reasoning#controlling-costs

The output budget includes generated reasoning tokens and visible output. A report
with structured JSON/evidence can hit the budget before it is complete. Raising
the budget is a testable adjustment, not a guarantee that every report will fit.

## Template changes

The complete `portfolios/templates/portfolios/risk.html` file now:

- Shows `Unavailable` instead of a bare percent sign for null annualized metrics.
- Displays the backend-provided reason for unavailable annualization.
- Preserves zero as a numeric value (`0.00%`).
- Chooses the sign and CSS class of best/worst period cards from the actual value.
- Preserves the portfolio selector, chart data, script includes and empty states.

No backend calculations or database records are changed by this template patch.

Five template tests cover null metrics, zero metrics, negative best periods,
positive worst periods, and neutral zero periods. They render the real template
with a small base-template stub. They do not assert the complete app's visual
layout or execute the existing chart JavaScript.

Run in the project's Docker environment:

```bash
docker compose run --rm web python manage.py test \
  portfolios.tests.test_risk_template \
  portfolios.tests.test_web_risk
```

For publication use a separate branch, PR and the normal CI/image/deploy flow.
A locally edited template does not change the existing AWS image. Confirm the
updated display after deploying the newly published image.
