# Database backup and restore verification

The database backup tool exports the AWS demo PostgreSQL database to the Mac and
tests restoration in a disposable local database. Run all commands in this guide
from the repository root in the **Mac terminal**.

`backup` connects to EC2 over SSH. `verify` uses local Docker and does not query or
modify AWS. A first-time download of the local database image may require internet
access before the isolated restoration container is started.

## Protected data and prerequisites

Git stores application code; PostgreSQL stores users, assets, portfolios,
positions, transactions, reports, conversations and financial knowledge. A Docker
volume retains records across container recreation. A database backup provides a
separate recovery copy.

The tool uses the Python standard library together with AWS CLI, Terraform, SSH
and Docker. Its files are:

- `scripts/demo_database_backup.py` for export and restoration verification.
- `scripts/tests/test_demo_database_backup.py` for offline helper tests.

The export uses `pg_dump --format=custom`. Do not run deployment migrations at the
same time as the export. Follow [AWS operations](aws-demo-operations.md) to start
the instance, update access and verify its SSH host key. PostgreSQL must be running;
HTTPS and image rebuilding are not required for backup.

## Export the database

```bash
python scripts/demo_database_backup.py backup
```

The script verifies account `990861495140`, region `us-east-1`, Terraform outputs,
instance identity, VPC, tags, registered SSH key and running state. The SSH host key
must already be trusted. The script does not accept a new host key automatically.

The export uses PostgreSQL 18 and the release referenced by
`/opt/investmind/current`. The dump streams from the database container through
SSH to the Mac; no large intermediate dump is written to the EC2 disk. Database
credentials remain in the container environment. The tool does not print or copy
the server's environment files.

Each export creates a new directory under:

```text
~/.local/share/investmind/backups/TIMESTAMP-IDENTIFIER/
```

The directory contains `database.dump` and `metadata.json`. Directory permissions
are `0700`; file permissions are `0600`. Backups remain outside Git and outside
the cache directory.

The dump includes password hashes and may include private conversations. File
permissions restrict local access but do not encrypt the archive. Keep the full
backup private and do not attach it to issues or public support messages.

Metadata records the source, application revision, archive size and SHA-256
checksum. The checksum detects accidental changes; it is not a digital signature
and does not prevent coordinated modification of both files.

The script removes an incomplete export on a handled failure. A completed export
must still pass an actual restoration test.

## Verify restoration locally

Keep Docker Desktop running:

```bash
python scripts/demo_database_backup.py verify latest
```

`latest` selects the newest complete backup in the local backup directory. A
specific `database.dump` path can be supplied instead. The script verifies the
archive size and checksum before starting a container.

The restoration uses `pgvector/pgvector:0.8.7-pg18-bookworm`, matching the deployed
database image. The temporary container:

- Has a unique name, network mode `none` and no published ports.
- Uses a new database named `restorecheck`, separate from development and AWS.
- Has a one-CPU and 1 GB memory limit for the small demo database.
- Receives the archive through standard input, without mounting Mac directories.
- Runs `pg_restore --single-transaction --exit-on-error --no-owner --no-privileges`.
- Checks the vector extension, migrations and readability of the main tables.
- Is removed with its anonymous volumes after completion or a handled failure.

The archive's constraints and indexes are restored by PostgreSQL. Printed record
counts describe the restored snapshot; they are not a comparison with the live
AWS database, which may have changed after the export began.

Expected success message:

```text
RESTORE TEST PASSED. The temporary database was removed.
```

The backup directory then contains `verification.json` with the date, image and
restored counts. The original dump remains unchanged. The test does not start
Django or exercise web login, AI or Celery against the restored database.

If Docker or the Mac is forcibly stopped, cleanup may not run. Identify test
containers by their label:

```bash
docker ps -a --filter label=investmind.restore-check=true
```

If cleanup is needed, remove only the confirmed test container ID with
`docker rm -f -v TEST_CONTAINER_ID`. Do not remove the project's Compose containers
or volumes as part of restoration-test cleanup.

## Stop the AWS source

After the export succeeds, EC2 can be stopped using the commands in
[AWS operations](aws-demo-operations.md#stop-and-confirm). The local `verify`
command works while EC2 is stopped. Ending an SSH connection alone does not stop
the instance.

## Helper tests

```bash
python -m unittest discover -s scripts/tests -p test_demo_database_backup.py -v
python scripts/demo_database_backup.py --help
```

These tests simulate AWS, SSH and Docker operations. They validate helper behavior
and failure paths; they do not perform a real database export or restoration.
The current CI workflow includes the infrastructure helper tests.

## Recovery scope and limitations

This is a manual logical backup of one database. It does not provide continuous
recovery, point-in-time recovery (PITR), scheduled backups or automatic retention.
It excludes PostgreSQL cluster roles, environment files, API keys, the Django
secret key, SSH keys, Terraform state, filesystem uploads and pending Redis data.

Django users and password hashes are table data and are included. PostgreSQL
cluster roles are separate objects. Restoration uses the destination owner, which
is why original ownership and privileges are not reapplied.

A real recovery requires a suitable destination, restoration of the selected
archive, independent secret configuration and application validation before
traffic is switched. The tool deliberately provides no command to overwrite the
live AWS database. Returning to an older application image does not restore data
or reverse migrations.

The Mac backup separates the copy from EC2 but still depends on that computer.
An additional private encrypted copy can preserve `database.dump`, `metadata.json`
and, when available, `verification.json` together. Retention and deletion remain
operator responsibilities.

## Recorded validation

The local restoration test completed successfully for the 21 October 2026 demo
snapshot, including PostgreSQL/pgvector, 26 migration records, one user, one asset,
two portfolios, two positions, seven transactions and 31 knowledge chunks. These
counts describe that snapshot, not required counts for future backups.

## References

- [PostgreSQL 18 pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html)
- [PostgreSQL 18 pg_restore](https://www.postgresql.org/docs/18/app-pgrestore.html)
