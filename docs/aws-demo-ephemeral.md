# Ephemeral AWS demo and verified recovery

Terraform can remove the demo between sessions. Ansible and the saved image can
rebuild the application, but infrastructure recreation alone does not recover
application data. This is a manual demonstration procedure.

## Stop or destroy

| Operation | Result |
| --- | --- |
| EC2 stop | Preserves the disk and data. EBS storage remains billable. |
| Terraform destroy | Removes managed infrastructure, including this instance and its root disk. Recovery requires the separate backup and configuration. |

The instance no longer has `prevent_destroy`. Its AMI `ignore_changes` rule
remains. Review the account and resources in every saved plan. Terraform removes
resources in its state, not everything in the AWS account. Past charges remain.

## Recovery files

Keep the following private and outside Git:

- `database.dump`, `metadata.json` and successful `verification.json`.
- A separate archive of `/opt/investmind/shared/app.env`, `db.env` and
  `deployment.env`, preserving the API keys, database credentials and Django key.
- Registry release metadata matching the backup's `application_commit`.
- The dedicated SSH key in `~/.ssh/investmind_demo` and its public key.
- Current Terraform state, local inputs and the provider lock file. Historical
  state copies must remain separate from the current state.

The verified exercise saved recovery configuration and release metadata in a
`recovery/` subdirectory of the selected backup under
`~/.local/share/investmind/backups/`. Private directories used mode `0700` and
files used `0600`. Permissions do not encrypt these files. The database dump does
not include configuration, Terraform state, SSH keys, Redis pending work or
filesystem uploads. Preserve additional files required by future versions.

## 1 Export and verify

Follow [AWS operations](aws-demo-operations.md) to authenticate, start the source
if needed and verify SSH access. Resolve live instance IDs and IPs from Terraform
and AWS instead of reusing historical examples. On the Mac:

```bash
python scripts/demo_database_backup.py backup
python scripts/demo_database_backup.py verify latest
```

Require `RESTORE TEST PASSED`. Keep the exact backup path and the separate server
configuration and image metadata. Verification needs Docker Desktop and its CLI
on the Mac. Avoid writes after selecting the snapshot if they must be recovered.

## 2 Destroy through a reviewed plan

After the backup, restore test and configuration export succeed:

```bash
terraform -chdir=infra/aws plan -destroy -input=false -out=demo-destroy.tfplan
```

Inspect account and resources before applying. The verified configuration had 12
managed resources and two data sources. Its plan showed 12 resources to destroy;
future configuration changes can change this number.

```bash
terraform -chdir=infra/aws apply demo-destroy.tfplan
terraform -chdir=infra/aws state list
```

Confirm destruction, empty state, termination of the old instance and removal of
its root volume. The following query checks only the named disk in this region:

```bash
aws ec2 describe-volumes --profile investmind --region us-east-1 \
  --filters 'Name=tag:Name,Values=investmind-demo-root' \
  --query 'Volumes[].{ID:VolumeId,State:State,SizeGB:Size}' \
  --output json --no-cli-pager
```

Review other retained resources and Billing separately. Preserve the state
updated by destruction. Never replace it with the historical pre-destruction copy.

## 3 Recreate infrastructure

On the infrastructure branch, with the current state:

```bash
aws sso login --profile investmind
python scripts/prepare_terraform_demo.py
terraform -chdir=infra/aws fmt -check
terraform -chdir=infra/aws validate
terraform -chdir=infra/aws plan -input=false -out=demo-create.tfplan
```

Review and apply only the intended creation plan:

```bash
terraform -chdir=infra/aws apply demo-create.tfplan
terraform -chdir=infra/aws output
```

The verified exercise created 12 resources, including an ARM64 `t4g.medium` in
`us-east-1`, an encrypted 20 GB `gp3` root disk and supporting network. SSH was
restricted to the operator's current IPv4 `/32`.

Wait for status checks, load the SSH key into the Mac agent and run
`python scripts/prepare_ansible_inventory.py`. Obtain the new host fingerprints
using its printed AWS `get-console-output` command. Compare the same key type at
the first SSH connection before accepting it. Do not reuse the old host key or
disable verification.

Follow the [Ansible guide](../infra/ansible/README.md) for syntax check, ping and
`prepare-server.yml`, using live IDs and the new inventory instead of historical
example IDs. Run Ansible on the Mac.

## 4 Recover configuration and deploy

Recover the archived environment files before initializing PostgreSQL. The
root-owned `/opt/investmind/shared/` directory uses `0700`, and files use `0600`.
Do not print their values. Application and database credentials must agree.

Match the backup's `application_commit` to the saved registry release revision.
The image must remain available by its immutable digest. The deployment helper
requires a clean checkout at that published commit. Preserve the infrastructure
branch, temporarily use `git switch --detach COMMIT`, then run
`python scripts/deploy_registry_demo.py PATH_TO_SAVED_RELEASE_METADATA`.
The helper requests the registry token through a hidden prompt. Ansible updates
host settings for the new IP and deploys the original image.

Return to `infra/ephemeral-demo` afterward. Do not apply infrastructure changes
from the historical checkout, which may contain different lifecycle protection.
Deployment creates the initial database; it does not recover the old records.

## 5 Restore the database

Stop `proxy`, `beat`, `worker` and `web` with the deployed Compose configuration;
keep only `db` and `redis` running. Check the replacement database has no users,
portfolios, transactions or knowledge chunks before replacing its initial schema.
Investigate any existing application data instead of overwriting it.

Recheck the dump's size and SHA-256 against metadata and the verification report.
Validate the live account, replacement instance and application revision. The
verified import streamed the Mac dump over host-key-checked SSH into
`docker compose exec -T db`, with `pg_restore` using the container's database user
and name and these options:

```text
--clean --if-exists --no-owner --no-privileges --single-transaction --exit-on-error
```

This replaces the initial schema in the verified empty destination. A PostgreSQL
error rolls back the restore transaction. Keep the app paused and inspect the
result after any error or interrupted transfer. The existing repository `verify`
subcommand tests a disposable local database; it is not an AWS restore command.

## 6 Validate and reopen

Compare extension, migration and application counts against the selected backup's
`verification.json`. Start `web`, `worker`, `beat` and `proxy` with Compose
`up -d --wait`, check Celery `inspect ping` and open the new HTTPS address.
Confirm the original user can log in and see the restored portfolios.

The complete exercise successfully destroyed and recreated infrastructure,
recovered configuration and the image, restored data and reopened the portal.
The operator confirmed the portal worked with the previous data. Image identity:

- Commit: `1e9924871f8dd2cd9275f7640ebe86c2f7fbb10e`
- Digest: `sha256:09cf33e3bc6a06d1462e47da47c185e11f8b8e7949ff8b316c70b39341775212`

| Check | Restored snapshot |
| --- | --- |
| pgvector | 0.8.7 |
| Migration records | 26 |
| Users | 1 |
| Assets | 3 |
| Portfolios | 3 |
| Positions | 5 |
| Transactions | 11 |
| Knowledge chunks | 31 |

Counts describe this snapshot, not fixed requirements for later backups, and do
not prove every application flow works. This is manual recovery without PITR,
automatic retention or high availability.

The exercise leaves EC2 running. Closing the terminal does not stop it. After
use, choose stop or a reviewed teardown according to whether the disk and newer
data need to be retained.

## References

- [Terraform destroy](https://developer.hashicorp.com/terraform/cli/commands/destroy)
- [EC2 states and billing](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html)
- [PostgreSQL 18 pg_restore](https://www.postgresql.org/docs/18/app-pgrestore.html)
