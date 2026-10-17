"""Deploy an image published by GitHub Actions, using a short-lived registry login."""

import argparse
import getpass
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

from demo_database_backup import find_source, ssh, write_json


BASE_DIR = Path(__file__).resolve().parent.parent
REPOSITORY = "marianapiccolo/investmind-ai"
IMAGE = "ghcr.io/" + REPOSITORY
RELEASE_PATH = Path.home() / ".cache" / "investmind" / "registry-release.json"
INVENTORY_PATH = Path.home() / ".config" / "investmind" / "ansible-inventory.json"
ANSIBLE = Path.home() / ".venvs" / "investmind-ansible" / "bin" / "ansible-playbook"


def validate_release(data):
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object from the GitHub Actions release artifact.")
    expected = {
        "schema_version": 1,
        "repository": REPOSITORY,
        "image": IMAGE,
        "platform": "linux/arm64",
    }
    if any(data.get(name) != value for name, value in expected.items()):
        raise ValueError("The release is not an InvestMind ARM64 image from the expected repository.")
    revision = data.get("revision", "")
    digest = data.get("digest", "")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Invalid application commit in the release.")
    if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError("Invalid registry digest in the release.")
    if data.get("ref") not in {"refs/heads/develop", "refs/heads/main"}:
        raise ValueError("Only releases published from develop or main can be deployed.")
    run_url = data.get("workflow_run_url", "")
    if not isinstance(run_url, str) or not re.fullmatch(
        r"https://github\.com/marianapiccolo/investmind-ai/actions/runs/[0-9]+", run_url
    ):
        raise ValueError("Invalid GitHub Actions run URL.")
    return {
        **expected,
        "revision": revision,
        "digest": digest,
        "reference": IMAGE + "@" + digest,
        "ref": data["ref"],
        "workflow_run_url": run_url,
    }


def git_output(*arguments):
    return subprocess.run(
        ["git", *arguments], cwd=BASE_DIR, check=True,
        capture_output=True, text=True, timeout=30,
    ).stdout.strip()


def prepare(path=None):
    source = Path(path).expanduser() if path is not None else RELEASE_PATH
    if source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as archive:
            member = archive.getinfo("published-release.json")
            if member.file_size > 16384:
                raise ValueError("The release metadata exceeds the expected size.")
            data = json.loads(archive.read(member))
    else:
        if source.stat().st_size > 16384:
            raise ValueError("The release metadata exceeds the expected size.")
        data = json.loads(source.read_text())
    release = validate_release(data)
    if git_output("rev-parse", "HEAD") != release["revision"]:
        raise RuntimeError(
            "The local checkout must match the published commit. Update develop or main "
            "and select its successful Actions artifact before deploying."
        )
    subprocess.run(["git", "diff", "--exit-code", "--quiet", "HEAD", "--"],
                   cwd=BASE_DIR, check=True, timeout=30)
    RELEASE_PATH.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    write_json(RELEASE_PATH, release)
    print(f"Application commit: {release['revision']}")
    print(f"Registry image: {release['reference']}")
    print(f"Source workflow: {release['workflow_run_url']}")
    return release


def deploy():
    if not ANSIBLE.is_file():
        raise RuntimeError("The dedicated InvestMind Ansible environment is missing.")
    instance_id, address = find_source()
    inventory = json.loads(INVENTORY_PATH.read_text())
    host = inventory["all"]["children"]["investmind"]["hosts"]["investmind_demo"]
    if (
        host.get("ansible_host") != address
        or host.get("ansible_user") != "ubuntu"
        or host.get("ansible_ssh_common_args") != "-o StrictHostKeyChecking=yes -o IdentitiesOnly=yes"
        or Path(host.get("ansible_ssh_private_key_file", "")).expanduser()
        != Path.home() / ".ssh" / "investmind_demo"
    ):
        raise RuntimeError("Refresh the Ansible inventory and verify the current EC2 SSH host key first.")
    ssh(address, ["true"])
    print(f"Target verified: {instance_id}; {address}")
    print("Enter a GitHub classic token with read:packages. The token is not saved by this script.")
    token = getpass.getpass("GitHub read:packages token: ").strip()
    if not token or any(character in token for character in "\r\n\0"):
        raise ValueError("A nonempty, single-line token is required.")
    environment = os.environ.copy()
    environment["INVESTMIND_GHCR_TOKEN"] = token
    try:
        subprocess.run([
            str(ANSIBLE), "-i", str(INVENTORY_PATH),
            str(BASE_DIR / "infra" / "ansible" / "deploy-registry.yml"),
        ], cwd=BASE_DIR, env=environment, check=True)
    finally:
        environment.pop("INVESTMIND_GHCR_TOKEN", None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release", nargs="?", help="Path to the Actions artifact ZIP or published-release.json; defaults to the last prepared release.")
    parser.add_argument("--prepare-only", action="store_true", help="Validate/cache release metadata without AWS, SSH or a token.")
    args = parser.parse_args()
    try:
        prepare(args.release)
        if args.prepare_only:
            print("Release metadata prepared. No AWS resources were accessed.")
        else:
            deploy()
    except subprocess.CalledProcessError as error:
        print(f"Operation failed (exit {error.returncode}). Review the preceding Git/Ansible message.", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.TimeoutExpired, zipfile.BadZipFile) as error:
        print(f"Operation failed: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Operation interrupted.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
