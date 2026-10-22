# Report evidence validation

AI report evidence is checked against the context supplied to the model. A report is accepted only when all configured checks pass: required content, evidence grounding, unavailable sections and language rules.

## Boolean representation

The report context is serialized as JSON before generation. Python's `True` and `False` therefore appear as JSON `true` and `false`. An evidence string containing the JSON spelling represents the same boolean as the original context value.

Evidence comparison accepts the following spellings only when the context value is a boolean:

| Context value | Accepted evidence strings |
| --- | --- |
| Python `True` | `true`, `True` |
| Python `False` | `false`, `False` |

The capitalized Python spellings remain accepted for compatibility with existing reports. The alternative spellings are not applied to ordinary context strings. Boolean values are not treated as numbers or generalized truthy values.

For example, `sections.risk.data.annualization_available = True` matches evidence `true`. It does not match `false`, `1`, `yes` or whitespace-padded variants. A context string `True` still requires the exact string `True`.

Other evidence comparisons retain their existing behavior. Financial value and precision differences, unknown paths and object or array evidence remain rejected. The change does not alter financial calculations, generated text, context snapshots, output schemas, model configuration or other evaluation checks.

## Tests

Run in the local Docker environment:

```bash
docker compose run --rm web python manage.py test \
  portfolios.tests.test_ai_evals \
  portfolios.tests.test_ai_evidence_booleans \
  portfolios.tests.test_ai_report_task
```

The regression tests reproduced rejection of JSON boolean spellings before the fix. Fifteen evaluator tests passed after the fix in an isolated Django 6.1 environment, without a database or provider requests. The Docker command also exercises the existing report task integration.

## Existing reports

Deploy the corrected application image before reevaluating saved reports. Use each report's original `context_snapshot` and stored `report`, rather than rebuilding a context from current portfolio values. A reevaluation of these saved inputs does not require another model request.

An existing rejection must not be changed to a completed status unless every evaluation check passes. Preserve the generated content and original context. A report rejected for any additional reason remains rejected. Existing database records are not automatically changed by this patch.
