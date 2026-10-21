# Local production runtime verification

This guide verifies Gunicorn, WhiteNoise, collected static assets and production
settings on the Mac. The test publishes HTTP only on loopback and connects to the
existing development PostgreSQL and Redis services. It is separate from the AWS
HTTPS deployment.

Run all commands from the repository root in the **Mac terminal**, with Docker
Desktop running and the local Python environment available for helper scripts.

## Runtime files

| File | Purpose |
| --- | --- |
| `requirements-production.txt` | Adds production runtime dependencies to the application requirements |
| `config/settings_production.py` | Imports base settings and configures production security and static assets |
| `Dockerfile.production` | Builds the application image and runs `collectstatic` |
| `compose.production-test.yaml` | Runs the production web service on `127.0.0.1:8001` |
| `scripts/create_production_test_env.py` | Creates a private test environment without replacing `.env` |
| `.github/workflows/ci.yml` | Automates application tests and production runtime smoke checks |

Gunicorn runs Django through WSGI. WhiteNoise serves collected static files using
compressed, hashed assets. The production settings insert WhiteNoise into a copy
of the base middleware list rather than changing the development list.

The image contains application code and collected static assets; it has no
development source bind mount at `/app`. Source changes require rebuilding the
production image. Build-time `collectstatic` uses placeholder environment values;
actual runtime values are supplied when the container is created.

## Start the shared data services

```bash
docker compose up -d --wait db redis
```

This verification uses the development database rather than an isolated copy.
Use demonstration data and retain the existing database credentials. Apply any
pending application migrations using the development workflow before inspecting
database-backed pages.

## Prepare the private test environment

```bash
python scripts/create_production_test_env.py
```

The helper reads `.env` and creates `.env.production-test` with permissions `0600`.
It retains the database credentials, generates a new Django key, and supplies
placeholder provider keys. The source `.env` remains unchanged. If the test file
already exists, it is preserved rather than refreshed automatically.

Both environment files are excluded from Git and the Docker build context.
Keep the local production test environment separate from the server's production
environment files.

## Validate and build

```bash
docker compose --project-name investmind-ai-production-test -f compose.production-test.yaml config --quiet
docker compose --project-name investmind-ai-production-test -f compose.production-test.yaml build web
```

The build must complete successfully, including `collectstatic`. Inspect any build
failure before starting the container. Use `config --quiet` to validate without
printing resolved secret values.

## Start Gunicorn and inspect the runtime

```bash
docker compose --project-name investmind-ai-production-test -f compose.production-test.yaml up -d --wait --wait-timeout 120 web
docker compose --project-name investmind-ai-production-test -f compose.production-test.yaml ps
docker compose --project-name investmind-ai-production-test -f compose.production-test.yaml logs --tail=50 web
```

The web service should become healthy and the logs should show Gunicorn starting.
Gunicorn HTTP workers are separate from Celery workers.

Check the selected settings module and debug flag:

```bash
docker compose --project-name investmind-ai-production-test -f compose.production-test.yaml exec web python manage.py shell -c 'from django.conf import settings; print(settings.SETTINGS_MODULE); print("DEBUG:", settings.DEBUG)'
```

Expected values are `config.settings_production` and `DEBUG: False`.

## Verify the admin page and static assets

```bash
curl --fail --silent --show-error --output /dev/null http://127.0.0.1:8001/admin/login/
curl --fail --silent --show-error --output /dev/null http://127.0.0.1:8001/static/admin/css/base.css
```

These commands can finish without output on success. Open
[the local production admin](http://127.0.0.1:8001/admin/) to inspect the styles and
sign in with an existing development user.

The database is shared with development, so a second superuser is unnecessary.
The distinct Django key can invalidate a session when switching between the local
development and production-test services. Cookies also share the same hostname
across ports; a fresh login may be needed.

## Check strict production settings separately

```bash
docker compose --project-name investmind-ai-production-test -f compose.production-test.yaml run --rm --no-deps -e DJANGO_LOCAL_PRODUCTION_TEST=false web python manage.py check --deploy
```

This checks strict settings in a one-off container; it does not configure a TLS
endpoint for the local web service. Inspect errors and assess warnings rather
than treating every warning as an execution failure. The project retains
`SECURE_HSTS_INCLUDE_SUBDOMAINS=False` and `SECURE_HSTS_PRELOAD=False` until a
deliberate domain-wide HTTPS policy is established. Existing OpenAPI schema
warnings may also appear.

## Isolation and security boundaries

- `DJANGO_LOCAL_PRODUCTION_TEST=true` allows HTTP and non-secure cookies only for
  loopback hosts. The Compose file publishes the web port on `127.0.0.1`.
- Strict production defaults require HTTPS and secure cookies. The AWS helper
  explicitly sets local production testing to false.
- The local test does not trust forwarded proxy headers. The AWS deployment
  enables that trust behind Caddy, which controls the forwarded scheme header.
- Cache uses Redis database 3 and the broker uses database 4, separate from the
  development cache and broker databases 1 and 2.
- This Compose file starts only the production web service. It does not start
  matching Celery worker or Beat processes, and provider keys are placeholders.
  It does not validate live AI or background job execution.
- The default external Docker network is `investmind-ai-local_default`.
  `DEVELOPMENT_NETWORK` can select the temporary equivalent used in CI.

## CI behavior

The test job builds the development image, starts temporary PostgreSQL and Redis,
applies migrations, checks for missing migrations and runs the Django suite.
It also runs infrastructure helper tests, builds the production image, checks
strict production settings and performs Gunicorn/admin/static HTTP smoke checks.

The production smoke service joins the CI development network and uses CI
environment values. Those databases and volumes belong to the temporary runner;
the Mac's volumes do not participate. The workflow cleans up its temporary
resources after the checks.

The separate publish job builds and checks a native ARM64 image before publishing
eligible commits. See [registry delivery](registry-delivery.md) for triggers and
the operator-initiated deployment procedure.

## Stop the local verification service

```bash
docker compose --project-name investmind-ai-production-test -f compose.production-test.yaml down
```

The shared development database and Redis services remain available. This command
does not stop the AWS instance or remove development data volumes.

## Validation record

The production image build, `DEBUG=False`, Gunicorn startup and successful admin
and CSS responses have been verified on the Mac and in CI. Live HTTPS and provider
integration checks are recorded separately in
[functional validation](functional-validation-review.md).
