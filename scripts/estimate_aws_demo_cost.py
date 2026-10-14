"""Read AWS catalogue prices and estimate demo compute, disk, and public IPv4."""

import argparse
import json
import subprocess
import sys
from decimal import Decimal


PROFILE = "investmind"
ACCOUNT_ID = "990861495140"
REGION = "us-east-1"
INSTANCE_TYPE = "t4g.medium"
# AWS VPC public IPv4 list price; separate from EC2 compute.
IPV4_HOURLY_USD = Decimal("0.005")


def aws_json(*arguments):
    result = subprocess.run(
        [
            "aws", *arguments,
            "--profile", PROFILE,
            "--region", REGION,
            "--output", "json",
            "--no-cli-pager",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def catalogue_rate(attributes, unit):
    filters = [
        {"Type": "TERM_MATCH", "Field": field, "Value": value}
        for field, value in attributes.items()
    ]
    response = aws_json(
        "pricing", "get-products",
        "--service-code", "AmazonEC2",
        "--filters", json.dumps(filters),
    )
    rates = set()
    for entry in response.get("PriceList", []):
        product = json.loads(entry) if isinstance(entry, str) else entry
        for term in product.get("terms", {}).get("OnDemand", {}).values():
            for dimension in term.get("priceDimensions", {}).values():
                if (
                    dimension.get("unit") == unit
                    and dimension.get("beginRange", "0") == "0"
                    and dimension.get("endRange") == "Inf"
                ):
                    rate = Decimal(dimension["pricePerUnit"]["USD"])
                    if rate > 0:
                        rates.add(rate)
    if len(rates) != 1:
        raise RuntimeError(
            f"Expected one unambiguous positive {unit} price; found {len(rates)}. "
            "Do not use a guessed price."
        )
    return rates.pop()


def estimate(hours, disk_gb):
    identity = aws_json("sts", "get-caller-identity")
    if identity.get("Account") != ACCOUNT_ID:
        raise RuntimeError("The investmind profile points to a different AWS account.")

    compute_rate = catalogue_rate({
        "regionCode": REGION,
        "instanceType": INSTANCE_TYPE,
        "operatingSystem": "Linux",
        "tenancy": "Shared",
        "preInstalledSw": "NA",
        "capacitystatus": "Used",
    }, "Hrs")

    storage_rate = catalogue_rate({
        "regionCode": REGION,
        "productFamily": "Storage",
        "volumeApiName": "gp3",
    }, "GB-Mo")

    hours_value = Decimal(str(hours))
    disk_value = Decimal(disk_gb)
    compute = compute_rate * hours_value
    storage = storage_rate * disk_value
    ipv4 = IPV4_HOURLY_USD * hours_value

    print(f"Account: {ACCOUNT_ID}; region: {REGION}; instance: {INSTANCE_TYPE}")
    print(f"EC2 catalogue rate: USD {compute_rate}/hour")
    print(f"EBS gp3 catalogue rate: USD {storage_rate}/GB-month")
    print(f"Public IPv4 rate: USD {IPV4_HOURLY_USD}/hour")
    print(f"Scenario: {hours} running hours; {disk_gb} GB retained for a full month")
    print(f"EC2 compute: USD {compute:.2f}")
    print(f"EBS disk: USD {storage:.2f}")
    print(f"Public IPv4: USD {ipv4:.2f}")
    print(f"SUBTOTAL: USD {compute + storage + ipv4:.2f}/month")
    print(f"If EC2 stays stopped all month, this disk still costs USD {storage:.2f}.")
    print("Excludes taxes, currency conversion, backups, domain, traffic, and AI APIs.")
    print("No discounts or credits assumed; catalogue subtotal is not a spending cap.")
    print("This script only reads identity and prices; it creates no AWS resources.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=float, default=20)
    parser.add_argument("--disk-gb", type=int, default=20)
    args = parser.parse_args()
    if not 0 <= args.hours <= 744:
        parser.error("--hours must be between 0 and 744.")
    if not 20 <= args.disk_gb <= 60:
        parser.error("--disk-gb must be between 20 and 60.")

    try:
        estimate(args.hours, args.disk_gb)
    except subprocess.CalledProcessError as error:
        print(error.stderr.strip() or "AWS CLI failed.", file=sys.stderr)
        sys.exit(1)
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        print(f"Estimate failed: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
