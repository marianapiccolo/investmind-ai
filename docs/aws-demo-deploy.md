# AWS deployment by image archive

This guide documents the alternative deployment method that builds an application
image on the Mac and transfers an archive over SSH. The primary delivery method is
now [private registry delivery](registry-delivery.md). Routine access and shutdown
procedures are maintained in [AWS operations](aws-demo-operations.md).

## Deployment architecture

The production image runs Django through Gunicorn. Celery worker and Beat use the
same application image with separate commands. PostgreSQL/pgvector and Redis store
data in named Docker volumes. Caddy receives HTTPS on the public address and
forwards requests to `web:8000`.

Only Caddy publishes host ports for the web entry point. Database and Redis ports
remain internal. Django uses strict production settings with `DEBUG=False`, secure
cookies, HTTPS redirection and proxy-header trust enabled for the controlled
Caddy proxy.

The AWS database is separate from the Mac database. First deployment initializes
an empty database; subsequent deployments retain its existing records and users.

## HTTPS on the public IP

The demo uses `https://CURRENT_PUBLIC_IP/` without a purchased domain or reserved
Elastic IP. Caddy requests a Let's Encrypt IP certificate using the `shortlived`
profile. That profile has a 160-hour certificate lifetime, so a long stopped period
may require new issuance after startup.

The Caddyfile sets `default_sni` to the demo public address for TLS clients that
omit SNI. When the address changes, redeployment updates Caddy, Django allowed
hosts and CSRF origins. Updating only the browser URL does not update those
settings. Certificate validation remains enabled during HTTPS checks.

## Prerequisites

- A committed, clean application checkout.
- Docker Desktop on the Mac.
- The configured AWS profile, Terraform state and dedicated SSH key.
- Ansible installed in `~/.venvs/investmind-ansible`.
- An Ubuntu ARM64 EC2 host prepared by `infra/ansible/prepare-server.yml`.

The deployment files are already part of the repository. No historical ZIP
installation or feature-branch bootstrap is required.

## Build the committed application

Run from the repository root in the **Mac terminal**:

```bash
source .venv/bin/activate
git status --short --branch
python scripts/build_demo_release.py
```

The script builds from `git archive HEAD`; uncommitted and untracked application
files are not included. Tracked changes cause the build helper to stop. Commit
application changes before preparing a release, and keep deployment configuration
consistent with the selected revision.

The build uses `Dockerfile.production` and targets `linux/arm64`. The image tag
contains the full commit SHA. Its compressed archive and `release.json` are stored
under `~/.cache/investmind`, outside Git. This flow does not publish an image to a
registry or access AWS during the build.

## Prepare access

Follow [AWS operations](aws-demo-operations.md) to authenticate, start EC2, refresh
the inventory before applying the Terraform access plan, verify the host key and
return to the Mac. Load the SSH key into the local agent:

```bash
ssh-add "$HOME/.ssh/investmind_demo"
```

Do not substitute a stale public IP. The inventory helper queries AWS for the
current address and validates the configured target.

## Deploy from the Mac

```bash
"$HOME/.venvs/investmind-ansible/bin/ansible-playbook" -i "$HOME/.config/investmind/ansible-inventory.json" infra/ansible/deploy-demo.yml --syntax-check
"$HOME/.venvs/investmind-ansible/bin/ansible-playbook" -i "$HOME/.config/investmind/ansible-inventory.json" infra/ansible/deploy-demo.yml
```

Ansible transfers the archive, checks its checksum and image identity, loads the
image, prepares or preserves environment values, starts data services, applies
migrations and starts the application and proxy. HTTPS/admin CSS and Celery checks
run before `/opt/investmind/current` is linked to the verified release.

Archive transfer and certificate issuance can take several minutes. Public HTTPS
checks use the Mac's `curl` with certificate verification enabled.

A deployment can report `changed>0` on repeated runs. It restarts processes and
has a downtime window; it is not a zero-downtime or high-availability deployment.
An interrupted or failed deployment requires inspection of the failed task and
the actual service state. The `current` link is not an automatic rollback.

## First-time user and asset setup

For a newly initialized AWS database only, connect through the verified SSH
command. Run the following **inside EC2**:

```bash
sudo docker compose --env-file /opt/investmind/shared/deployment.env --file /opt/investmind/current/compose.production.yaml exec web python manage.py createsuperuser
```

Use a strong password and sign in through the printed HTTPS admin URL. Register
demo assets through the Asset admin before selecting them in transaction forms.
Create portfolios and transactions through the application. The Mac's local user
and records are not copied by deployment. Existing AWS users do not need to be
recreated for each release or restart.

## Configure provider keys

The environment helper generates the Django secret key and PostgreSQL password
on first initialization and preserves them in later deployments. The files
`/opt/investmind/shared/app.env` and `db.env` are root-owned with permissions
`0600` and remain outside release directories.

OpenAI and Alpha Vantage keys start empty on a new host. To configure them,
run **inside an interactive EC2 SSH session**:

```bash
sudo python3 /opt/investmind/bin/manage_demo_env.py --configure-apis
```

The hidden prompts preserve an existing value when Enter is pressed. The helper
does not create provider credentials or make external API calls. Recreate the
application services to load changed environment values:

```bash
sudo docker compose --env-file /opt/investmind/shared/deployment.env --file /opt/investmind/current/compose.production.yaml up -d --no-deps --force-recreate --wait --wait-timeout 180 web worker beat
```

API requests, knowledge ingestion and live report tests use provider quotas or
credits. The report output budget is separately documented in the
[output-limit guide](demo-report-output-limit.md). SMTP configuration and real
email delivery have not been validated for this demo.

## Inspect and recover

Run **inside EC2**:

```bash
sudo docker compose --env-file /opt/investmind/shared/deployment.env --file /opt/investmind/current/compose.production.yaml ps
sudo docker compose --env-file /opt/investmind/shared/deployment.env --file /opt/investmind/current/compose.production.yaml logs --tail=80 web worker beat proxy
sudo docker stats --no-stream
df -h /
```

If deployment failed before the new `current` link was recorded, inspect the
intended release using its actual directory under `/opt/investmind/releases/`.
Use `config --quiet` when validating Compose without exposing environment values.

Named volumes belong to the `investmind-ai-demo` project. Avoid
`docker compose down --volumes` when retaining records. Persistence is not a
backup; use the [database backup procedure](aws-demo-backup.md).

Image selection does not reverse migrations or recover data. In the configured
Terraform environment, instance termination deletes the root volume; ordinary
demo shutdown uses EC2 stop, not terminate or `terraform destroy`.

## Reopen and shut down

For the same application version, reuse the prepared archive after refreshing
access and redeploying the host configuration. Rebuild when selecting a different
committed application version. Registry metadata and archive metadata are
independent and may identify different revisions.

Return to the Mac with `exit`, then stop and confirm the instance using
[AWS operations](aws-demo-operations.md#stop-and-confirm). Retained storage still
incurs charges while the instance is stopped.

Both the archive method and the later registry method have been exercised against
the demo host. [Functional validation](functional-validation-review.md) records
the application checks separately from deployment smoke tests.

## References

- [Let's Encrypt IP certificates and the shortlived profile](https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability/)
- [Caddy global options including default_sni](https://caddyserver.com/docs/caddyfile/options)
