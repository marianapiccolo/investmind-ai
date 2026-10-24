"""Read the demo EC2 address and prepare a local Ansible inventory on the Mac."""

import ipaddress
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
TF_DIR = BASE_DIR / "infra" / "aws"
EXPECTED_ACCOUNT = "990861495140"
AWS_PROFILE = "investmind"
AWS_REGION = "us-east-1"
KEY_PATH = Path.home() / ".ssh" / "investmind_demo"
LOCAL_DIR = Path.home() / ".config" / "investmind"
INVENTORY_PATH = LOCAL_DIR / "ansible-inventory.json"


def run_command(arguments, *, input_text=None):
    result = subprocess.run(
        arguments,
        input=input_text,
        check=True,
        capture_output=True,
        text=True,
        timeout=45,
    )
    return result.stdout


def aws_json(*arguments):
    output = run_command([
        "aws", *arguments,
        "--profile", AWS_PROFILE,
        "--region", AWS_REGION,
        "--output", "json",
        "--no-cli-pager",
    ])
    return json.loads(output)


def trusted_fingerprints(addresses):
    """Show fingerprints already trusted by the Mac; never accept new keys."""
    known_hosts = Path.home() / ".ssh" / "known_hosts"
    if not known_hosts.is_file():
        return ""
    for candidate in dict.fromkeys(addresses):
        try:
            address = ipaddress.ip_address(candidate)
            if address.version != 4 or not address.is_global:
                continue
            entries = run_command([
                "ssh-keygen", "-F", str(address), "-f", str(known_hosts),
            ])
            fingerprints = run_command(["ssh-keygen", "-l", "-f", "-"], input_text=entries)
            if fingerprints.strip():
                return fingerprints.strip()
        except (ValueError, OSError, subprocess.SubprocessError):
            continue
    return ""


def prepare():
    if not (TF_DIR / "versions.tf").is_file():
        raise RuntimeError("Run this script from the InvestMind repository with infra/aws present.")
    if not KEY_PATH.is_file():
        raise RuntimeError("The dedicated SSH private key is missing from ~/.ssh/investmind_demo.")

    identity = aws_json("sts", "get-caller-identity")
    if identity.get("Account") != EXPECTED_ACCOUNT:
        raise RuntimeError("Unexpected AWS account. No inventory was changed.")

    tf_outputs = json.loads(run_command([
        "terraform", f"-chdir={TF_DIR}", "output", "-json",
    ]))
    instance_id = tf_outputs.get("instance_id", {}).get("value", "")
    vpc_id = tf_outputs.get("vpc_id", {}).get("value", "")
    if not re.fullmatch(r"i-[0-9a-f]{17}", instance_id):
        raise RuntimeError("Terraform has no valid demo instance ID. Keep the existing Terraform state.")
    if not vpc_id:
        raise RuntimeError("Terraform has no VPC output. Keep the existing Terraform state.")

    response = aws_json("ec2", "describe-instances", "--instance-ids", instance_id)
    instances = [
        instance
        for reservation in response.get("Reservations", [])
        for instance in reservation.get("Instances", [])
    ]
    if len(instances) != 1:
        raise RuntimeError("Expected exactly one demo instance. No inventory was changed.")
    instance = instances[0]
    tags = {tag["Key"]: tag["Value"] for tag in instance.get("Tags", [])}
    if (
        instance.get("InstanceId") != instance_id
        or instance.get("VpcId") != vpc_id
        or instance.get("KeyName") != "investmind-demo"
        or tags.get("Project") != "InvestMindAI"
        or tags.get("Environment") != "demo"
    ):
        raise RuntimeError("The instance does not match the InvestMind Terraform configuration.")
    state = instance.get("State", {}).get("Name")
    if state != "running":
        raise RuntimeError(f"The demo instance is {state!r}. Start it before preparing the inventory.")
    address = ipaddress.ip_address(instance.get("PublicIpAddress", ""))
    if address.version != 4 or not address.is_global:
        raise RuntimeError("The instance does not have a valid public IPv4 address.")

    inventory = {
        "all": {
            "children": {
                "investmind": {
                    "hosts": {
                        "investmind_demo": {
                            "ansible_host": str(address),
                            "ansible_user": "ubuntu",
                            "ansible_ssh_private_key_file": str(KEY_PATH),
                            "ansible_python_interpreter": "/usr/bin/python3",
                            "ansible_ssh_common_args": (
                                "-o StrictHostKeyChecking=yes -o IdentitiesOnly=yes"
                            ),
                        },
                    },
                },
            },
        },
    }
    LOCAL_DIR.mkdir(parents=True, mode=0o700, exist_ok=True)
    temporary_path = INVENTORY_PATH.with_suffix(".json.tmp")
    descriptor = os.open(temporary_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write(json.dumps(inventory, indent=2) + "\n")
    os.chmod(temporary_path, 0o600)
    temporary_path.replace(INVENTORY_PATH)

    print(f"Account: {EXPECTED_ACCOUNT}; region: {AWS_REGION}; instance: {instance_id}")
    print(f"Current EC2 IPv4: {address}")
    print(f"Prepared {INVENTORY_PATH} with file permissions 600.")
    print("The private key was not read or copied. No AWS resources were changed.")
    previous_address = tf_outputs.get("public_ip", {}).get("value", "")
    fingerprints = trusted_fingerprints([str(address), previous_address])
    if fingerprints:
        print("\nHost fingerprints already trusted by this Mac (compare with the SSH prompt):")
        print(fingerprints)
    else:
        print("\nBefore accepting a new host key, obtain the EC2 host fingerprints from AWS:")
        print(shlex.join([
            "aws", "ec2", "get-console-output", "--profile", AWS_PROFILE,
            "--region", AWS_REGION, "--instance-id", instance_id, "--latest",
            "--query", "Output", "--output", "text", "--no-cli-pager",
        ]))
    print("\nConnect manually first; compare the fingerprint before accepting a new host:")
    print(shlex.join([
        "ssh", "-o", "StrictHostKeyChecking=ask", "-o", "IdentitiesOnly=yes",
        "-i", str(KEY_PATH), f"ubuntu@{address}",
    ]))
    print("Inside the server, run exit to return to the Mac before running Ansible.")


if __name__ == "__main__":
    try:
        prepare()
    except subprocess.CalledProcessError as error:
        message = (error.stderr or "").strip() or str(error)
        print(f"Preparation failed: {message}", file=sys.stderr)
        sys.exit(1)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"Preparation failed: {error}", file=sys.stderr)
        sys.exit(1)
