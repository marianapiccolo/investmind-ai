# Report output budget and risk presentation

## Observed failure and confirmed result

On 21 October 2026, the AWS application reported model `gpt-5.6-terra`,
`OPENAI_MAX_OUTPUT_TOKENS=1200` and `OPENAI_TIMEOUT_SECONDS=30`. Report 6 failed
with the output-limit-specific public message. This identifies that failure;
it does not establish the cause of the earlier report 4 failure.

The server output limit was changed to `4096`, the application services were
recreated, and Django reported the new value. Report 7 then completed and passed
the automated evaluation. Its risk section preserved period return and maximum
drawdown and explained the absence of annualized risk metrics.

The successful request validates the observed case. It does not guarantee that
every future response will fit the configured budget or pass evaluation.

## Configuration behavior

`OPENAI_MAX_OUTPUT_TOKENS` is a generation ceiling rather than a required response
length. The API output budget includes generated reasoning tokens and visible
output. Reaching it can produce an incomplete response before a complete report
is available. A larger limit permits more output consumption.

The value is stored in `/opt/investmind/shared/app.env`, separate from the image.
The model and timeout were not changed during this adjustment. The environment
helper preserves this additional entry during subsequent deployments, but a new
or replacement host needs its own configuration.

Changing the file does not update the environment of existing containers.
Recreate `web`, `worker` and `beat` after editing; a process restart alone does not
replace the container's configured environment values.

## Update an existing host

Follow [AWS operations](aws-demo-operations.md) to establish a verified SSH
connection. Run the following **inside EC2**, not in the Mac shell. The command
uses the installed helper to preserve other entries and its atomic-write and
`0600` permission behavior:

```bash
sudo python3 - <<'PY'
from pathlib import Path
import runpy

helper = runpy.run_path('/opt/investmind/bin/manage_demo_env.py')
path = Path('/opt/investmind/shared/app.env')
if not path.is_file():
    raise SystemExit('Existing app.env not found.')

values = helper['read_env'](path)
values['OPENAI_MAX_OUTPUT_TOKENS'] = '4096'
helper['write_env'](path, values)
print('Report output budget set to 4096.')
PY
```

Recreate the application services, also **inside EC2**:

```bash
sudo docker compose --env-file /opt/investmind/shared/deployment.env --file /opt/investmind/current/compose.production.yaml up -d --no-deps --force-recreate --wait --wait-timeout 180 web worker beat
```

Check the effective setting without printing secrets:

```bash
sudo docker compose --env-file /opt/investmind/shared/deployment.env --file /opt/investmind/current/compose.production.yaml exec -T web python manage.py shell -c 'from django.conf import settings; print("Output limit:", settings.OPENAI_MAX_OUTPUT_TOKENS)'
```

The expected value is `4096`. The database, Redis and proxy services do not need
to be recreated for this setting. Generate one new report to validate the change;
existing failed reports retain their original saved state and message. Review a
new failure and its worker logs before repeatedly retrying.

## Risk presentation

The risk template now:

- Displays `Unavailable` for null annualized metrics rather than a bare `%`.
- Shows the backend's reason for unavailable annualization.
- Preserves numeric zero as `0.00%`.
- Chooses the sign and CSS class of the best/worst period cards from their values.
- Preserves the portfolio selector, chart data, script includes and empty states.

The template change does not alter calculations or database records. The existing
chart JavaScript was not changed; card formatting and chart styling are separate
presentation responsibilities.

Five template tests cover null metrics, zero metrics, a negative best period,
a positive worst period and neutral zero periods. They render the real template
with a small base-template stub. They do not execute chart JavaScript or verify
the complete browser layout.

Run the targeted suite **on the Mac**:

```bash
docker compose run --rm web python manage.py test \
  portfolios.tests.test_risk_template \
  portfolios.tests.test_web_risk
```

Nine targeted tests passed in the project environment. After merge, publication
and registry deployment, browser inspection confirmed the unavailable labels,
explanatory banner, negative best-period card and preserved return/drawdown.

## Publication and remaining presentation work

Template changes follow the normal branch, pull request, CI, image publication
and registry deployment workflow. Editing a local template does not modify an
already deployed image. Runtime configuration changes and image releases have
separate lifecycles.

Locale-consistent grouping and decimal separators for large return values remain
a separate pending presentation task. The current demo uses test transaction
prices; formatting changes do not validate or change the computed magnitude.

## Reference

- [OpenAI output-budget and incomplete-response behavior](https://developers.openai.com/api/docs/guides/reasoning#controlling-costs)
