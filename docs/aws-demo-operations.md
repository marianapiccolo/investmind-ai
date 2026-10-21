# AWS demo operations

This guide covers routine operation of the existing InvestMind demo environment.
Run commands from the repository root in the **Mac terminal**, except commands
explicitly marked for an interactive SSH session on EC2.

## Environment

| Setting | Configured value |
| --- | --- |
| AWS account | `990861495140` |
| AWS CLI profile | `investmind` |
| Region | `us-east-1` |
| Existing instance | `i-0bb284d740d01bbd5` |
| SSH key on the Mac | `~/.ssh/investmind_demo` |
| Local Ansible inventory | `~/.config/investmind/ansible-inventory.json` |
| Deployment method | Private GHCR image pulled by digest through Ansible |

The scripts enforce the configured account and instance identity. The account,
instance ID and fingerprint in this guide describe the existing environment;
a replacement environment requires deliberate configuration and verification.

Prerequisites include the AWS CLI, Terraform state in `infra/aws`, the dedicated
SSH key and the Ansible environment at `~/.venvs/investmind-ansible`. Activate the
project's local Python environment before using commands named `python`:

```bash
source .venv/bin/activate
```

The application can remain stopped during local development, CI checks and image
publication.

## Authenticate and check the instance

```bash
aws sso login --profile investmind
aws sts get-caller-identity --profile investmind --region us-east-1 --query Account --output text --no-cli-pager
aws ec2 describe-instances --profile investmind --region us-east-1 --instance-ids i-0bb284d740d01bbd5 --query 'Reservations[0].Instances[0].{State:State.Name,IP:PublicIpAddress}' --output table --no-cli-pager
```

The account must be `990861495140`. Resolve an identity mismatch before operating
EC2. Use the dedicated profile rather than credentials belonging to another
project. If an SSO session expires, repeat the login before retrying the command.

## Start the instance

If the instance is stopped:

```bash
aws ec2 start-instances --profile investmind --region us-east-1 --instance-ids i-0bb284d740d01bbd5 --no-cli-pager
aws ec2 wait instance-status-ok --profile investmind --region us-east-1 --instance-ids i-0bb284d740d01bbd5
```

The waiter may remain silent until the instance status checks pass. The public
IPv4 address can change after a stop/start cycle; use the live address rather
than a previous browser bookmark or terminal command.

## Refresh SSH access

Run the inventory helper **before applying an updated Terraform plan**. It reads
the live AWS address and can use the previous address in Terraform state to find
an already trusted host fingerprint on the Mac.

```bash
python scripts/prepare_terraform_demo.py
python scripts/prepare_ansible_inventory.py
terraform -chdir=infra/aws plan -input=false -out=demo-access.tfplan
```

The Terraform preparation helper updates local inputs for the SSH public key and
the operator's current public IPv4 `/32`. It does not update AWS network rules.
The inventory helper validates the AWS target and writes the current server
address locally; it does not copy the private key.

Review the plan. For routine access maintenance, the expected changes are updated
public-address outputs and, if the operator's internet address changed, the SSH
ingress rule. Apply that reviewed plan:

```bash
terraform -chdir=infra/aws apply demo-access.tfplan
```

Investigate instance replacement, disk deletion or unrelated changes before
applying. Preserve Terraform state and the dedicated private key.

Execute the SSH command printed by the inventory helper. Compare a new-address
prompt with a previously trusted fingerprint. The ED25519 fingerprint verified
for the existing instance is:

```text
SHA256:80v5mPhAYqFx/I7Pwc6o939ynHtmHUVcz+pYu4V/mQQ
```

If no trusted reference exists, use the AWS console-output command printed by the
helper to obtain and compare host fingerprints. Investigate mismatches rather
than disabling host-key checking. A legitimately replaced instance requires a new
independent verification.

After the connection succeeds, run the following **inside EC2** to return to the
Mac before invoking deployment tools:

```bash
exit
```

## Deploy or reopen the demo for a presentation

Select a successful release artifact and ensure that the local checkout matches
its commit, as described in [registry delivery](registry-delivery.md).
With the release prepared and SSH access verified, run on the Mac:

```bash
ssh-add "$HOME/.ssh/investmind_demo"
python scripts/deploy_registry_demo.py
```

The script requests a GitHub classic token with `read:packages` permission through
a hidden prompt. Ansible pulls the image by digest, updates the current public
host configuration, applies migrations and verifies the services and HTTPS.
Use the URL printed after successful deployment.

A stop/start cycle may require reissuing an IP certificate and refreshing Django
and Caddy host settings. Prepare the demo before an interview rather than starting
it immediately before the presentation.

Check the intended demonstration flows: login, portfolio selection, an asset in
the catalog, transactions, market data and the relevant AI features. Provider
keys, indexed knowledge and historical prices are independent prerequisites.
Live provider checks can consume quotas or credits. The
[functional review](functional-validation-review.md) records the completed checks.

The deployed report output budget was set to `4096` in the server environment.
The [output-limit guide](demo-report-output-limit.md) documents verification and
configuration of that value; it is not embedded in the application image.

## Publish an application update

Run relevant tests, commit changes and open a pull request. After eligible changes
are merged into `develop` or `main` and the checks succeed, GitHub Actions publishes
the image and release metadata. Select that artifact from the matching commit and
run the deployment script.

Publication does not start EC2 or deploy automatically. Before a deployment with
migrations, create a database backup. Selecting an older image does not reverse
migrations or restore records.

The alternative Mac build and archive-transfer method remains available in
[archive deployment](aws-demo-deploy.md). It uses `release.json`; the registry flow
uses `registry-release.json`. Preparing one does not update the other.

## Create and verify a backup

With EC2 running, PostgreSQL available and the host key trusted:

```bash
python scripts/demo_database_backup.py backup
```

HTTPS and a fresh application deployment are unnecessary for this export. After
the export completes, EC2 can be stopped before running the local restoration:

```bash
python scripts/demo_database_backup.py verify latest
```

Keep Docker Desktop running on the Mac. The
[backup guide](aws-demo-backup.md) describes the archive, verification and recovery
limits.

## Inspect the running services

The following commands run **inside an interactive EC2 SSH session**:

```bash
sudo docker compose --env-file /opt/investmind/shared/deployment.env --file /opt/investmind/current/compose.production.yaml ps
sudo docker compose --env-file /opt/investmind/shared/deployment.env --file /opt/investmind/current/compose.production.yaml logs --tail=80 web worker beat proxy
sudo docker stats --no-stream
df -h /
```

The same Compose prefix can execute management commands in `web`. For example,
knowledge ingestion requires a configured OpenAI key and makes external requests:

```bash
sudo docker compose --env-file /opt/investmind/shared/deployment.env --file /opt/investmind/current/compose.production.yaml exec web python manage.py ingest_knowledge_base
```

Avoid printing environment files or running `compose config` without `--quiet`.
Logs and report output can contain user data; share only the relevant redacted
diagnostic information.

## Common access and runtime failures

| Symptom | First checks |
| --- | --- |
| SSO authorization failure | Renew `aws sso login --profile investmind`; verify the account |
| SSH timeout | Check instance state and live IP, then review the current SSH `/32` rule |
| Host-key mismatch | Compare against the verified reference or AWS console output |
| Private image pull denied | Check token type, expiry, `read:packages` scope and package access |
| Transaction asset list empty | Check the asset catalog in the AWS database |
| AI output-limit failure | Inspect the configured output budget and diagnostic code |
| Provider rate limit | Review logs and provider limits before submitting another request |
| Healthy containers but a broken feature | Inspect the relevant application flow and dependencies |

## Stop and confirm

If currently connected to EC2, run `exit` first. Then run **on the Mac**:

```bash
aws ec2 stop-instances --profile investmind --region us-east-1 --instance-ids i-0bb284d740d01bbd5 --no-cli-pager
aws ec2 wait instance-stopped --profile investmind --region us-east-1 --instance-ids i-0bb284d740d01bbd5
aws ec2 describe-instances --profile investmind --region us-east-1 --instance-ids i-0bb284d740d01bbd5 --query 'Reservations[0].Instances[0].State.Name' --output text --no-cli-pager
```

The final result must be `stopped`. Closing the browser, ending SSH or shutting
down the Mac does not stop EC2. Stopping preserves the EBS-backed data; retained
storage still incurs charges. Termination and `terraform destroy` are not normal
demo shutdown operations.

## Reference

- [AWS EC2 stop and start behavior](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html)
