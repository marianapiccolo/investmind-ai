"""Create a private local test environment without changing the original .env."""

import os
from pathlib import Path
import secrets


def main():
    source = Path(".env")
    destination = Path(".env.production-test")

    if not source.is_file():
        raise SystemExit("Run this script from the project root, where .env exists.")

    if destination.exists():
        print(".env.production-test already exists; it was kept unchanged.")
        return

    source_text = source.read_text(encoding="utf-8")
    overrides = {
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(64),
        "DJANGO_DEBUG": "false",
        "DJANGO_ALLOWED_HOSTS": "127.0.0.1,localhost",
        "DJANGO_LOCAL_PRODUCTION_TEST": "true",
        "DJANGO_TRUST_PROXY_HEADERS": "false",
        "OPENAI_API_KEY": "local-test-not-a-real-openai-key",
        "ALPHA_VANTAGE_API_KEY": "local-test-not-a-real-market-key",
    }

    content = source_text.rstrip() + "\n\n# Overrides for local production testing.\n"
    content += "".join(f"{name}={value}\n" for name, value in overrides.items())

    # Exclusive creation prevents overwriting an existing environment file.
    descriptor = os.open(
        destination,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(content)

    print("Created .env.production-test with a new key and file permissions 600.")
    print("Database credentials were retained; external API keys use test placeholders.")


if __name__ == "__main__":
    main()
