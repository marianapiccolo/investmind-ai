"""Back up the AWS demo to this Mac; test restores in a disposable local database."""

import argparse
import hashlib
import ipaddress
import json
import os
import re
import shlex
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
BACKUP_DIR = Path.home() / ".local" / "share" / "investmind" / "backups"
EXPECTED_ACCOUNT = "990861495140"
AWS_PROFILE = "investmind"
AWS_REGION = "us-east-1"
KEY_PATH = Path.home() / ".ssh" / "investmind_demo"
DATABASE_IMAGE = "pgvector/pgvector:0.8.7-pg18-bookworm"
COMPOSE = [
    "sudo", "-n", "/usr/bin/docker", "compose",
    "--env-file", "/opt/investmind/shared/deployment.env",
    "--file", "/opt/investmind/current/compose.production.yaml",
]


def now():
    return datetime.now(timezone.utc).isoformat()


def run(arguments, *, stdin=None, stdout=None, timeout=60):
    return subprocess.run(
        arguments,
        stdin=stdin,
        stdout=subprocess.PIPE if stdout is None else stdout,
        stderr=subprocess.PIPE,
        check=True,
        timeout=timeout,
    )


def read_text(arguments, *, timeout=60):
    return run(arguments, timeout=timeout).stdout.decode("utf-8").strip()


def aws_json(*arguments):
    return json.loads(read_text([
        "aws", *arguments, "--profile", AWS_PROFILE,
        "--region", AWS_REGION, "--output", "json", "--no-cli-pager",
    ]))


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, data):
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(data, output, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def find_source():
    """Validate the account, Terraform resource and live instance before any SSH."""
    if aws_json("sts", "get-caller-identity").get("Account") != EXPECTED_ACCOUNT:
        raise RuntimeError("Unexpected AWS account; no connection was made to EC2.")
    outputs = json.loads(read_text([
        "terraform", f"-chdir={BASE_DIR / 'infra' / 'aws'}", "output", "-json",
    ]))
    instance_id = outputs.get("instance_id", {}).get("value", "")
    vpc_id = outputs.get("vpc_id", {}).get("value", "")
    if not re.fullmatch(r"i-[0-9a-f]{17}", instance_id) or not vpc_id:
        raise RuntimeError("Missing Terraform instance/VPC outputs. Preserve your Terraform state.")
    response = aws_json("ec2", "describe-instances", "--instance-ids", instance_id)
    instances = [item for reservation in response.get("Reservations", [])
                 for item in reservation.get("Instances", [])]
    if len(instances) != 1:
        raise RuntimeError("Expected exactly one InvestMind demo instance.")
    instance = instances[0]
    tags = {item["Key"]: item["Value"] for item in instance.get("Tags", [])}
    if (
        instance.get("InstanceId") != instance_id
        or instance.get("VpcId") != vpc_id
        or instance.get("KeyName") != "investmind-demo"
        or tags.get("Project") != "InvestMindAI"
        or tags.get("Environment") != "demo"
    ):
        raise RuntimeError("The instance does not match the InvestMind infrastructure.")
    if instance.get("State", {}).get("Name") != "running":
        raise RuntimeError("The demo EC2 must be running for a backup. This script does not start it.")
    address = ipaddress.ip_address(instance.get("PublicIpAddress", ""))
    if address.version != 4 or not address.is_global:
        raise RuntimeError("The demo has no valid public IPv4.")
    if not KEY_PATH.is_file():
        raise RuntimeError("Missing ~/.ssh/investmind_demo. The private key must stay on this Mac.")
    return instance_id, str(address)


def ssh(address, arguments, *, stdout=None, timeout=60):
    return run([
        "ssh", "-T", "-o", "StrictHostKeyChecking=yes", "-o", "IdentitiesOnly=yes",
        "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=3", "-i", str(KEY_PATH),
        f"ubuntu@{address}", shlex.join(arguments),
    ], stdout=stdout, timeout=timeout)


def backup():
    instance_id, address = find_source()
    print(f"Source: account {EXPECTED_ACCOUNT}; {AWS_REGION}; {instance_id}; {address}", flush=True)
    revision_path = ssh(address, ["sudo", "-n", "readlink", "-f", "/opt/investmind/current"])
    revision = Path(revision_path.stdout.decode().strip()).name
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise RuntimeError("The current EC2 release is not a versioned application release.")
    version_command = (
        'exec psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB" '
        '--tuples-only --no-align --command "SHOW server_version_num"'
    )
    version = ssh(address, COMPOSE + ["exec", "-T", "db", "sh", "-ceu", version_command])
    version_number = int(version.stdout.decode().strip())
    if version_number // 10000 != 18:
        raise RuntimeError("Expected PostgreSQL 18; review the restore image before backing up.")

    BACKUP_DIR.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(BACKUP_DIR, 0o700)
    folder = BACKUP_DIR / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    )
    folder.mkdir(mode=0o700)
    partial = folder / "database.dump.partial"
    archive = folder / "database.dump"
    started = now()
    try:
        print("Exporting PostgreSQL over SSH to a private file on this Mac...", flush=True)
        descriptor = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            result = ssh(address, COMPOSE + [
                "exec", "-T", "db", "sh", "-ceu",
                'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" '
                '--format=custom --no-privileges --lock-wait-timeout=30s',
            ], stdout=output, timeout=900)
            output.flush()
            os.fsync(output.fileno())
        if result.stderr:
            print(result.stderr.decode(errors="replace").strip(), file=sys.stderr)
        with partial.open("rb") as source:
            if source.read(5) != b"PGDMP" or partial.stat().st_size <= 5:
                raise RuntimeError("The export is not a PostgreSQL custom-format archive.")
        partial.replace(archive)
        write_json(folder / "metadata.json", {
            "schema_version": 1,
            "started_at": started,
            "completed_at": now(),
            "account": EXPECTED_ACCOUNT,
            "region": AWS_REGION,
            "instance_id": instance_id,
            "application_commit": revision,
            "postgres_version_num": version_number,
            "restore_image": DATABASE_IMAGE,
            "bytes": archive.stat().st_size,
            "sha256": sha256(archive),
            "scope": "single PostgreSQL database; no cluster roles or server environment files",
        })
    except BaseException:
        partial.unlink(missing_ok=True)
        if not archive.exists():
            folder.rmdir()
        raise
    print(f"Backup saved: {archive}")
    print("Export complete. A real restore test is still required.")
    print(shlex.join([sys.executable, "scripts/demo_database_backup.py", "verify", str(archive)]))
    return archive


def resolve_archive(argument):
    if argument == "latest":
        candidates = sorted(
            path for path in BACKUP_DIR.glob("*/database.dump")
            if (path.parent / "metadata.json").is_file()
        )
        if not candidates:
            raise RuntimeError("No backup found on this Mac. Run the backup command first.")
        return candidates[-1]
    return Path(argument).expanduser().absolute()


def verify(argument):
    archive = resolve_archive(argument)
    if archive.is_symlink() or not archive.is_file():
        raise RuntimeError("Expected an existing regular database.dump file.")
    metadata_path = archive.parent / "metadata.json"
    if metadata_path.is_symlink():
        raise RuntimeError("Expected a regular metadata.json file.")
    metadata = json.loads(metadata_path.read_text())
    if (
        metadata.get("schema_version") != 1
        or metadata.get("account") != EXPECTED_ACCOUNT
        or metadata.get("region") != AWS_REGION
        or metadata.get("restore_image") != DATABASE_IMAGE
        or metadata.get("bytes") != archive.stat().st_size
        or metadata.get("sha256") != sha256(archive)
    ):
        raise RuntimeError("Backup metadata/checksum mismatch. No database was started.")
    print(f"Checksum verified: {archive}", flush=True)
    read_text(["docker", "info", "--format", "{{.ServerVersion}}"])
    try:
        image_id = read_text(["docker", "image", "inspect", DATABASE_IMAGE, "--format", "{{.Id}}"])
    except subprocess.CalledProcessError:
        print(f"Downloading restore tools: {DATABASE_IMAGE}", flush=True)
        run(["docker", "pull", DATABASE_IMAGE], timeout=600)
        image_id = read_text(["docker", "image", "inspect", DATABASE_IMAGE, "--format", "{{.Id}}"])
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise RuntimeError("Docker returned an invalid restore image identity.")

    name = "investmind-restore-check-" + uuid.uuid4().hex
    container_id = None
    counts = None
    print("Starting a disposable LOCAL database with no network or published ports...", flush=True)
    try:
        container_id = read_text([
            "docker", "create", "--name", name,
            "--label", "investmind.restore-check=true", "--network", "none",
            "--memory", "1g", "--cpus", "1",
            "--env", "POSTGRES_HOST_AUTH_METHOD=trust",
            "--env", "POSTGRES_DB=restorecheck", "--env", "POSTGRES_USER=restorecheck",
            image_id,
        ])
        if not re.fullmatch(r"[0-9a-f]{64}", container_id):
            container_id = None
            raise RuntimeError("Docker returned an invalid temporary container ID.")
        run(["docker", "start", container_id])
        for attempt in range(120):
            try:
                run(["docker", "exec", container_id, "pg_isready", "-h", "127.0.0.1",
                     "-U", "restorecheck", "-d", "restorecheck"], timeout=10)
                break
            except subprocess.CalledProcessError:
                if attempt == 119:
                    raise RuntimeError("The temporary PostgreSQL did not become ready.") from None
                time.sleep(1)
        print("Restoring the archive and validating database constraints...", flush=True)
        with archive.open("rb") as source:
            run([
                "docker", "exec", "-i", container_id, "pg_restore",
                "--host=127.0.0.1", "--username=restorecheck", "--dbname=restorecheck",
                "--no-owner", "--no-privileges", "--exit-on-error", "--single-transaction",
            ], stdin=source, timeout=900)
        query = """SELECT json_build_object(
            'vector_version', (SELECT extversion FROM pg_extension WHERE extname = 'vector'),
            'migrations', (SELECT count(*) FROM public.django_migrations),
            'users', (SELECT count(*) FROM public.auth_user),
            'assets', (SELECT count(*) FROM public.portfolios_asset),
            'portfolios', (SELECT count(*) FROM public.portfolios_portfolio),
            'positions', (SELECT count(*) FROM public.portfolios_position),
            'transactions', (SELECT count(*) FROM public.portfolios_transaction),
            'knowledge_chunks', (SELECT count(*) FROM public.portfolios_knowledgechunk)
        )"""
        counts = json.loads(read_text([
            "docker", "exec", container_id, "psql", "-X", "-h", "127.0.0.1",
            "-U", "restorecheck", "-d", "restorecheck", "--no-align", "--tuples-only",
            "--set", "ON_ERROR_STOP=1", "--command", query,
        ]))
        if not counts.get("vector_version") or counts.get("migrations", 0) < 1:
            raise RuntimeError("Expected the vector extension and Django migrations in the restored database.")
    finally:
        if container_id:
            print("Removing the temporary container and its anonymous volumes...", flush=True)
            run(["docker", "rm", "--force", "--volumes", container_id])

    report = {
        "verified_at": now(), "sha256": metadata["sha256"],
        "restore_image_id": image_id, "restored_counts": counts,
        "method": "pg_restore --single-transaction into a disposable local PostgreSQL 18",
    }
    write_json(archive.parent / "verification.json", report)
    print("RESTORE TEST PASSED. The temporary database was removed.")
    for label, value in counts.items():
        print(f"{label}: {value}")
    print(f"Verification report: {archive.parent / 'verification.json'}")
    print("The AWS database and the project's local development database were not modified.")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("backup", help="Read the AWS demo database and save a private backup on this Mac.")
    restore = commands.add_parser("verify", help="Restore a backup in a disposable local PostgreSQL container.")
    restore.add_argument("archive", help="Path to database.dump, or 'latest' for the newest backup on this Mac.")
    arguments = parser.parse_args()
    try:
        if arguments.command == "backup":
            backup()
        else:
            verify(arguments.archive)
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or b"").decode(errors="replace").strip()
        print(f"Operation failed: {detail or str(error)}", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"Operation failed: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Operation interrupted.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
