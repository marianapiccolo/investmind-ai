"""Create or update demo secrets on EC2 without printing their contents."""

import argparse
import getpass
import ipaddress
import json
import os
import secrets
import sys
from pathlib import Path


SHARED_DIR = Path('/opt/investmind/shared')


def read_env(path):
    if not path.exists():
        return {}
    values = {}
    for line in path.read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator or not key or key in values:
            raise RuntimeError(f'Invalid or duplicate environment entry in {path.name}.')
        values[key] = value
    return values


def write_env(path, values):
    text = ''.join(f'{key}={value}\n' for key, value in sorted(values.items()))
    if path.exists() and path.read_text() == text:
        os.chmod(path, 0o600)
        return False
    temporary = path.with_suffix('.tmp')
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(text)
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    return True


def prepare(host=None, configure_apis=False):
    SHARED_DIR.mkdir(parents=True, mode=0o700, exist_ok=True)
    app_path = SHARED_DIR / 'app.env'
    db_path = SHARED_DIR / 'db.env'
    app = read_env(app_path)
    db = read_env(db_path)
    if app_path.exists() and not app.get('DJANGO_SECRET_KEY'):
        raise RuntimeError('Existing app.env has no Django key; investigate instead of replacing it.')
    if db_path.exists() and not db.get('POSTGRES_PASSWORD'):
        raise RuntimeError('Existing db.env has no database password; investigate instead of replacing it.')
    if app_path.exists() and not app.get('POSTGRES_PASSWORD'):
        raise RuntimeError('Existing app.env has no database password; investigate instead of replacing it.')
    if app.get('POSTGRES_PASSWORD') and db.get('POSTGRES_PASSWORD'):
        if app['POSTGRES_PASSWORD'] != db['POSTGRES_PASSWORD']:
            raise RuntimeError('Database credentials disagree. No files were changed.')

    if host is None:
        host = app.get('DJANGO_ALLOWED_HOSTS', '').split(',')[0]
    address = ipaddress.ip_address(host)
    if address.version != 4 or not address.is_global:
        raise RuntimeError('The demo host must be the current public IPv4 of EC2.')

    password = app.get('POSTGRES_PASSWORD') or db.get('POSTGRES_PASSWORD') or secrets.token_urlsafe(36)
    db_name = db.get('POSTGRES_DB') or app.get('POSTGRES_DB') or 'investmind_demo'
    db_user = db.get('POSTGRES_USER') or app.get('POSTGRES_USER') or 'investmind'
    if db_path.exists() and app_path.exists():
        for name in ('POSTGRES_DB', 'POSTGRES_USER'):
            if app.get(name) != db.get(name):
                raise RuntimeError('Database name or user disagree. No files were changed.')
    app.setdefault('DJANGO_SECRET_KEY', secrets.token_urlsafe(64))
    app.update({
        'DJANGO_SETTINGS_MODULE': 'config.settings_production',
        'DJANGO_DEBUG': 'false',
        'DJANGO_LOCAL_PRODUCTION_TEST': 'false',
        'DJANGO_TRUST_PROXY_HEADERS': 'true',
        'DJANGO_ALLOWED_HOSTS': f'{address},localhost',
        'DJANGO_CSRF_TRUSTED_ORIGINS': f'https://{address}',
        'POSTGRES_DB': db_name,
        'POSTGRES_USER': db_user,
        'POSTGRES_PASSWORD': password,
        'POSTGRES_HOST': 'db',
        'POSTGRES_PORT': '5432',
        'REDIS_URL': 'redis://redis:6379/1',
        'CELERY_BROKER_URL': 'redis://redis:6379/2',
    })
    for name in ('OPENAI_API_KEY', 'ALPHA_VANTAGE_API_KEY'):
        app.setdefault(name, '')
        if configure_apis:
            value = getpass.getpass(f'{name} (Enter keeps the existing value): ').strip()
            if value:
                app[name] = value
    for value in app.values():
        if any(character in value for character in ('\r', '\n', '\x00')):
            raise RuntimeError('Environment values must be single-line text.')
    database = {'POSTGRES_DB': db_name, 'POSTGRES_USER': db_user, 'POSTGRES_PASSWORD': password}
    changed_db = write_env(db_path, database)
    changed_app = write_env(app_path, app)
    return changed_db or changed_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host')
    parser.add_argument('--configure-apis', action='store_true')
    arguments = parser.parse_args()
    changed = prepare(arguments.host, arguments.configure_apis)
    print(json.dumps({'changed': changed}))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print(f'Environment preparation failed: {error}', file=sys.stderr)
        sys.exit(1)
