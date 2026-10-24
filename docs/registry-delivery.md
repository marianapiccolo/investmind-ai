# Private registry delivery and deployment

GitHub Actions tests the application and publishes eligible production images to
the private GitHub Container Registry (GHCR). The operator selects a published
release and initiates deployment from the Mac. The EC2 instance pulls the selected
image directly from GHCR by digest.

This is an automated image delivery workflow with an operator-initiated deployment
step. Successful publication does not start or update EC2 automatically.

## Pipeline behavior

| Event or job | Behavior |
| --- | --- |
| Pull request into `develop` or `main` | Runs CI checks; publication is skipped |
| Eligible push to `develop` or `main` | Runs checks, then publishes if the test job succeeds |
| Test job | Runs infrastructure helper tests, Docker/Django checks, migrations, tests and production HTTP/static smoke checks |
| Publish job | Builds on a native ARM64 runner, checks production settings and publishes the image |
| Release artifact | Stores JSON metadata identifying the commit, digest, platform and workflow run |
| Deployment script | Validates metadata and the AWS target, then invokes Ansible from the Mac |

The publication job runs on a GitHub-hosted ARM64 runner rather than the demo EC2.
The workflow uses no production AWS, SSH or application API credentials. The
instance can remain stopped during CI and publication.

The image reference is `ghcr.io/marianapiccolo/investmind-ai:FULL_COMMIT_SHA`.
The artifact is named `investmind-release-FULL_COMMIT_SHA` and contains
`published-release.json`. The image is in GHCR; the artifact contains only its
selection metadata.

## Relevant files

- `.github/workflows/ci.yml`
- `scripts/deploy_registry_demo.py`
- `scripts/tests/test_deploy_registry_demo.py`
- `infra/ansible/deploy-registry.yml`
- `scripts/demo_database_backup.py`, which provides shared identity and SSH helpers

The selector uses the Python standard library and the existing project tools.

## Validate the delivery tooling locally

Run from the repository root in the **Mac terminal**, with the local Python
environment active:

```bash
python -m unittest discover -s scripts/tests -p 'test_*.py' -v
python scripts/deploy_registry_demo.py --help
"$HOME/.venvs/investmind-ansible/bin/ansible-playbook" -i "$HOME/.config/investmind/ansible-inventory.json" infra/ansible/deploy-registry.yml --syntax-check
```

Helper tests use simulated external operations. A syntax check does not deploy
the application or validate live registry access.

## Select a published release

After a pull request is merged, open the successful push execution under
**Actions > InvestMind AI CI/CD**. Confirm that the test and publication jobs passed.
Download the artifact matching the integrated commit. A merge or squash commit
can differ from the original feature-branch commit.

Before selecting a `develop` release, update a clean local checkout:

```bash
git status --short --branch
git switch develop
git pull --ff-only origin develop
git rev-parse HEAD
```

Select its downloaded ZIP, replacing `FULL_COMMIT_SHA` with the actual filename:

```bash
python scripts/deploy_registry_demo.py "$HOME/Downloads/investmind-release-FULL_COMMIT_SHA.zip" --prepare-only
```

The selector also accepts `published-release.json` directly. It requires local
`HEAD` to match the metadata revision and rejects tracked working-tree changes.
Untracked files are not checked by that Git comparison; inspect `git status`
separately and keep deployment inputs committed.

Preparation writes `~/.cache/investmind/registry-release.json` with permissions
`0600`. It does not access AWS, SSH or Docker and does not request a token.
Expected output identifies the application commit, registry image and source
workflow, followed by:

```text
Release metadata prepared. No AWS resources were accessed.
```

Use an artifact downloaded from the matching workflow in this repository. Format
validation and image labels are consistency checks, not a cryptographic signature
of provenance. The configured artifact retention is 14 days. Keep the selected
metadata available or select another published version if the cache is lost.

The workflow also declares `workflow_dispatch`. Availability of the GitHub
**Run workflow** control depends on that workflow definition being present on the
repository's default branch. Normal eligible pushes do not depend on that control.

## Authentication

The publish job uses the workflow's automatic `GITHUB_TOKEN` with
`packages: write`. No manually created token is required for that publication job.

The operator-initiated pull of the private image uses a **personal access token
(classic)** with `read:packages`, a suitable expiry and access to the package.
Create it under [GitHub token settings](https://github.com/settings/tokens) and
store it privately. Package visibility must remain private for the current setup.

The deployment script requests the token through a hidden prompt. Do not put its
literal value in commands, source files, release JSON or documentation. A valid
login alone does not prove that the token can pull the package; check scope,
expiry and package access if the pull is denied.

## Prepare the AWS target

Follow [AWS operations](aws-demo-operations.md) to authenticate with SSO, confirm
the configured account, start EC2, prepare the inventory before the Terraform
access update, and verify the SSH host key. Return to the Mac after the manual SSH
check and load the dedicated key:

```bash
ssh-add "$HOME/.ssh/investmind_demo"
```

Create a database backup before deploying migrations. The deployment preserves
existing database volumes; it does not copy the development database to AWS.

## Deploy the selected release

With the checkout still matching the prepared release, run **on the Mac**:

```bash
python scripts/deploy_registry_demo.py
```

The script revalidates release metadata, account, instance tags, VPC, live public
address, inventory and SSH access before requesting the registry token.

Ansible creates a private temporary Docker configuration on EC2 and authenticates
using `docker login --password-stdin`. The token is supplied through the Ansible
process environment, and the authentication task has `no_log: true`. The temporary
Docker configuration is removed in an `always` block on success or a handled task
failure. Forced termination may interrupt cleanup; investigate remaining
`/tmp/investmind-ghcr-*` directories if necessary.

The server temporarily receives the token during authentication. Do not disable
`no_log` or share unredacted debug output. Application secrets remain in the
separate root-owned server environment files.

After pulling the image, Ansible verifies Linux ARM64 and the source/revision
labels. The exact digest is also stored in `APP_IMAGE`. Application services use
`pull_policy: never` because the authenticated pull has already completed.

The playbook then updates the host configuration, validates Compose and Caddy,
starts PostgreSQL and Redis, stops the application services, checks production
settings, applies migrations, and starts the application and proxy. It verifies
Celery connectivity and public HTTPS/admin CSS before recording the `current`
release link.

This deployment has a downtime window. A failed run can leave application
processes stopped or partially updated; retaining the previous `current` link is
not an automatic rollback mechanism. Review the failed task and actual service
state before recovery.

## Validate and shut down

After `failed=0` and `unreachable=0`, use the printed URL to check the intended
user flows. Container health and HTTPS smoke checks do not replace functional
validation. See [recorded validation](functional-validation-review.md) for the
verified application behavior and analytical limits.

Stop EC2 and confirm `stopped` using the
[operating procedure](aws-demo-operations.md#stop-and-confirm) after the demo.

## Reuse and rollback limits

The cached metadata can select the same release again if the matching checkout
and a valid pull token are available. Refresh live access before each deployment.
An older release requires its corresponding source checkout and metadata.

An image rollback does not undo migrations, restore lost records or ensure schema
compatibility. Database recovery is a separate process described in
[backup and restore verification](aws-demo-backup.md).

The alternative archive-transfer method uses
`~/.cache/investmind/release.json`, separate from the registry metadata. Preparing
one flow does not select the same version in the other.

GitHub Actions, artifacts, caches and package storage are subject to account
quotas and billing settings. No automatic GHCR image retention or deletion is
configured. Review account usage rather than treating publication as a spending
cap or assuming an unlimited allowance.

## Reference

- [GitHub Container Registry authentication and image references](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
