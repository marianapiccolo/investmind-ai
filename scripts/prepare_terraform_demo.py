"""Prepare local Terraform inputs using a dedicated SSH public key and IPv4."""

import ipaddress
import json
import os
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
TF_DIR = BASE_DIR / "infra" / "aws"
KEY_PATH = Path.home() / ".ssh" / "investmind_demo"
PUBLIC_KEY_PATH = KEY_PATH.with_suffix(".pub")
VARIABLES_PATH = TF_DIR / "local.auto.tfvars.json"


def prepare():
    if not (TF_DIR / "versions.tf").is_file():
        raise RuntimeError("Copy the Terraform files into infra/aws first.")

    KEY_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)

    if not PUBLIC_KEY_PATH.exists():
        if KEY_PATH.exists():
            raise RuntimeError(
                "The private key already exists but its public key is missing. "
                "Keep the existing key and ask for help recovering its public key."
            )
        print("Creating a dedicated SSH key. Choose a passphrase when prompted.")
        subprocess.run(
            [
                "ssh-keygen", "-t", "ed25519",
                "-f", str(KEY_PATH),
                "-C", "investmind-demo",
            ],
            check=True,
        )

    public_key = PUBLIC_KEY_PATH.read_text().strip()
    if not public_key.startswith("ssh-ed25519 "):
        raise RuntimeError("The public key must be an Ed25519 key.")

    result = subprocess.run(
        [
            "curl",
            "--disable",
            "--ipv4",
            "--fail",
            "--silent",
            "--show-error",
            "--connect-timeout", "10",
            "--max-time", "20",
            "https://checkip.amazonaws.com/",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    address = ipaddress.ip_address(result.stdout.strip())
    if address.version != 4 or not address.is_global:
        raise RuntimeError("AWS checkip must return your public IPv4 address.")

    values = {}
    if VARIABLES_PATH.exists():
        values = json.loads(VARIABLES_PATH.read_text())
        if not isinstance(values, dict):
            raise RuntimeError("The local Terraform inputs must be a JSON object.")

    values.update({
        "ssh_public_key": public_key,
        "ssh_allowed_cidr": f"{address}/32",
    })
    temporary_path = VARIABLES_PATH.with_suffix(".json.tmp")
    descriptor = os.open(
        temporary_path,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        0o600,
    )
    with os.fdopen(descriptor, "w") as output:
        output.write(json.dumps(values, indent=2) + "\n")
    os.chmod(temporary_path, 0o600)
    temporary_path.replace(VARIABLES_PATH)

    print("Prepared infra/aws/local.auto.tfvars.json.")
    print("SSH is restricted to your current public IPv4.")
    print("Only the public key was copied; the private key remains in ~/.ssh.")
    print("No AWS resources were created or changed.")


if __name__ == "__main__":
    try:
        prepare()
    except subprocess.CalledProcessError as error:
        message = (error.stderr or "").strip() or str(error)
        print(f"Preparation failed: {message}", file=sys.stderr)
        sys.exit(1)
    except (
        OSError, ValueError, RuntimeError,
        subprocess.TimeoutExpired,
    ) as error:
        print(f"Preparation failed: {error}", file=sys.stderr)
        sys.exit(1)
