# Release process

A release identifies approved source and a tested application image. Source
versioning, image publication and EC2 deployment are separate operations.

| Identifier | Meaning |
| --- | --- |
| Git commit | Exact source revision |
| Annotated Git tag | Human-readable version pointing to a source commit |
| GHCR image digest | Immutable image manifest selected for deployment |
| Release metadata artifact | Commit, digest, platform, source ref and workflow identity |
| Deployed revision | Application image currently selected on EC2 |

## Branch policy

`develop` is the integration and validation branch. Approved stable release source
is promoted to `main` through a pull request. Stable production deployment selects
the image published for the resulting `main` commit. Development work continues
through feature and fix branches targeting `develop`.

The current workflow publishes eligible images from both `develop` and `main`.
The deployment helper accepts both refs. Branch separation is an operator release
policy, not an automatic environment gate: verify that production metadata has
`ref` equal to `refs/heads/main` and identifies the intended revision.

A merge can produce a new SHA. An earlier `develop` artifact must not be assumed
to identify the final `main` commit, even when the application content is similar.

## Integrate the release documentation

Update the README, changelog and validation record to describe the approved scope.
Use formal technical English and distinguish implementation, observed checks and
remaining limitations. Integrate documentation through a pull request to
`develop`, then promote the reviewed source through a pull request to `main`.
For the initial promotion, a normal merge commit preserves the existing branch
history.

Wait for the resulting `main` commit's checks and image publication. Pull request
checks alone do not publish an image. A merge or successful publication does not
start EC2 or deploy the application.

## Select the stable source and image

Run on the Mac from the repository directory after the promotion has merged:

```bash
git fetch origin --tags
git switch main
git pull --ff-only origin main
git status --short --branch
git log -1 --oneline
git rev-parse HEAD
git tag --list
```

Require a clean working tree. Check existing tags before selecting `v1.0.0`.
Never replace a release tag or force-push it to a different commit.

Download the metadata artifact from the successful `main` workflow for the full
SHA printed above. Confirm `published-release.json` identifies that SHA and
`refs/heads/main`. Prepare the artifact with the local helper:

```bash
python scripts/deploy_registry_demo.py \
  "$HOME/Downloads/investmind-release-$(git rev-parse HEAD).zip" \
  --prepare-only
```

Preparation validates and caches metadata; it does not contact AWS. The helper
requires the checkout's `HEAD` to match the artifact's application commit and
requires tracked source changes to be committed.

## Deploy and verify the main image

Use the [AWS operations guide](aws-demo-operations.md) to authenticate to the
intended account, start EC2, update restricted SSH access and the inventory, and
verify the host key. Keep the checkout on the selected `main` commit.

Deploy the prepared release explicitly from the Mac:

```bash
python scripts/deploy_registry_demo.py
```

The [registry delivery guide](registry-delivery.md) documents authentication and
Ansible deployment. Keep runtime secrets private. Deployment retains the runtime
environment; it does not copy the Mac's development database into AWS.

After Ansible succeeds, check the actual HTTPS application:

- Sign-in, author attribution and access to the expected account.
- Portfolio selection retained when navigating between application pages.
- Dashboard Refresh reloads the selected portfolio; the AI Analyst shortcut opens
  the same portfolio.
- Portfolio, transaction, performance, risk and diversification pages display the
  expected stored data and explicit unavailable-data states.
- The risk chart shows the best and worst period end dates with unchanged values.
- Stored AI reports remain available and their evaluation status is visible.
- Any live AI/provider check is recorded separately from tests with mocked calls.

Record the actual commit, digest, workflow URL and check results. The historical
[functional validation record](functional-validation-review.md) identifies earlier
AWS results; those are not proof that the final `main` image was checked.

If verification fails, correct the problem through the source review process or
an appropriate runtime configuration change, and repeat the affected checks.
Keep `v1.0.0` untagged until the selected image meets the release requirements.
Automatic rollback and zero-downtime deployment are not implemented guarantees.

## Back up and stop the environment

While EC2 is running, create a fresh database backup on the Mac:

```bash
python scripts/demo_database_backup.py backup
```

Record the produced backup identifier. Stop EC2 using the explicit account,
region and instance in the [operations guide](aws-demo-operations.md), wait until
its state is `stopped`, then verify the backup locally with Docker running:

```bash
python scripts/demo_database_backup.py verify latest
```

Require a successful restore test and retain its verification report. The
[backup guide](aws-demo-backup.md) describes the checks and retention limits.
Terraform state and runtime secrets require separate protection.

## Tag and publish the release record

After the selected `main` image has passed verification and its backup has passed
restoration, confirm the checkout still identifies the selected commit:

```bash
git status --short --branch
git log -1 --oneline
git rev-parse HEAD
git tag --list
```

Only when the working tree is clean, `HEAD` is the verified `main` revision, and
`v1.0.0` does not exist, create the annotated tag:

```bash
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
git show --no-patch v1.0.0
```

Create the GitHub Release from the existing `v1.0.0` tag. Use the
[changelog](../CHANGELOG.md) to summarize implemented capabilities. Include the
verified source SHA, immutable image digest, workflow URL, functional check
summary and successful backup/restore result. Keep private filesystem paths,
credentials, host access details and database dumps out of release attachments.

The current Actions workflow runs for pull requests, eligible pushes to `develop`
or `main`, and manual dispatch. A tag push alone does not trigger its current
checks/publication workflow. The selected commit must already have successful
checks and a publication record.

A Git tag or GitHub Release does not start EC2, deploy an image, create sample
data, restore a database or roll back migrations. Those remain explicit operator
actions. A custom domain is deferred and is not required for the first release.
