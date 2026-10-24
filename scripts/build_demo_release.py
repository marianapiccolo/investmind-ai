"""Build the committed InvestMind version for ARM64 and export it on the Mac."""

import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = Path.home() / '.cache' / 'investmind'


def output(arguments):
    return subprocess.run(arguments, cwd=BASE_DIR, check=True, capture_output=True, text=True).stdout.strip()


def build():
    revision = output(['git', 'rev-parse', 'HEAD'])
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise RuntimeError('The repository must have a normal Git commit.')
    dirty = subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--'], cwd=BASE_DIR, check=False)
    if dirty.returncode != 0:
        raise RuntimeError('Tracked files have uncommitted changes. Review them before building a release.')
    image = f'investmind-ai:{revision}'
    CACHE_DIR.mkdir(parents=True, mode=0o700, exist_ok=True)
    archive = CACHE_DIR / f'{revision}.tar.gz'
    with tempfile.TemporaryDirectory(prefix='investmind-build-') as temporary:
        work = Path(temporary)
        source_archive = work / 'source.tar'
        context = work / 'source'
        context.mkdir()
        subprocess.run(['git', 'archive', '--format=tar', f'--output={source_archive}', revision], cwd=BASE_DIR, check=True)
        with tarfile.open(source_archive) as source:
            source.extractall(context, filter='data')
        if not (context / 'Dockerfile.production').is_file():
            raise RuntimeError('Dockerfile.production must be committed before building this release.')
        subprocess.run([
            'docker', 'build', '--platform', 'linux/arm64',
            '--file', str(context / 'Dockerfile.production'),
            '--label', f'org.opencontainers.image.revision={revision}',
            '--tag', image, str(context),
        ], cwd=BASE_DIR, check=True)
    image_id = output(['docker', 'image', 'inspect', '--format', '{{.Id}}', image])
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', image_id):
        raise RuntimeError('Docker did not return a valid image ID.')
    platform = output(['docker', 'image', 'inspect', '--format', '{{.Os}}/{{.Architecture}}', image])
    if platform != 'linux/arm64':
        raise RuntimeError('The image must target linux/arm64 for this EC2.')
    temporary_archive = archive.with_suffix('.gz.tmp')
    descriptor = os.open(temporary_archive, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    process = subprocess.Popen(['docker', 'image', 'save', image], stdout=subprocess.PIPE)
    try:
        with os.fdopen(descriptor, 'wb') as raw:
            with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as compressed:
                shutil.copyfileobj(process.stdout, compressed)
        process.stdout.close()
        if process.wait() != 0:
            raise RuntimeError('Docker image export failed.')
    except BaseException:
        if process.poll() is None:
            process.terminate()
        process.wait()
        temporary_archive.unlink(missing_ok=True)
        raise
    os.chmod(temporary_archive, 0o600)
    temporary_archive.replace(archive)
    with archive.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    release = {'revision': revision, 'image': image, 'image_id': image_id, 'platform': platform, 'archive': str(archive), 'sha256': digest}
    metadata = CACHE_DIR / 'release.json'
    descriptor = os.open(metadata, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        json.dump(release, stream, indent=2)
        stream.write('\n')
    os.chmod(metadata, 0o600)
    print(f'\nBuilt committed version: {revision}')
    print(f'Image: {image}; archive: {archive}')
    print('The image targets Linux ARM64. No AWS resources were accessed.')
    print('Uncommitted and untracked files were not included in the application image.')


if __name__ == '__main__':
    try:
        build()
    except (OSError, RuntimeError, subprocess.CalledProcessError, tarfile.TarError) as error:
        print(f'Release build failed: {error}', file=sys.stderr)
        sys.exit(1)
