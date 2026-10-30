"""Strict original crates.io archive inventory for explicit native opaque contexts."""
import hashlib
import json
import os
import re
import shutil
import tomllib
from pathlib import Path

REGISTRY = 'registry+https://github.com/rust-lang/crates.io-index'
MAXIMUM_BYTES = 256 * 1024 * 1024


def sha(path):
    with Path(path).open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()


def index_key(name):
    if len(name) == 1:
        return '1/' + name
    if len(name) == 2:
        return '2/' + name
    if len(name) == 3:
        return '3/' + name[0] + '/' + name
    return name[:2] + '/' + name[2:4] + '/' + name


def strict_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('CARGO_REGISTRY_CONFIGURATION_DUPLICATE')
        value[key] = item
    return value


def inventory(home, lock):
    """No execution/extraction; reject injection, ambiguity and checksum mismatch."""
    home, lock = Path(home), Path(lock)
    packages = {}
    for item in tomllib.loads(lock.read_text())['package']:
        if 'source' not in item:
            continue
        if item['source'] != REGISTRY:
            raise ValueError('CARGO_REGISTRY_SOURCE')
        name, version, checksum = item['name'], item['version'], item.get('checksum', '')
        if not re.fullmatch('[A-Za-z0-9_-]+', name) or not re.fullmatch('[A-Za-z0-9.+_-]+', version):
            raise ValueError('CARGO_REGISTRY_PACKAGE')
        if not re.fullmatch('[0-9a-f]{64}', checksum):
            raise ValueError('CARGO_REGISTRY_CHECKSUM')
        archive = name + '-' + version + '.crate'
        if archive in packages:
            raise ValueError('CARGO_REGISTRY_DUPLICATE')
        packages[archive] = dict(name=name, version=version, checksum='sha256:' + checksum)
    if not packages or len(packages) > 8192:
        raise ValueError('CARGO_REGISTRY_PACKAGE_COUNT')
    allowed = {'registry', '.global-cache', '.global-cache-wal', '.global-cache-shm',
               '.package-cache', '.package-cache-mutate'}
    if home.is_symlink() or not home.is_dir() or set(p.name for p in home.iterdir()) - allowed:
        raise ValueError('CARGO_HOME_INJECTION')
    for p in home.iterdir():
        if p.is_symlink() or (p.name != 'registry' and (not p.is_file() or p.stat().st_size > 16777216)):
            raise ValueError('CARGO_HOME_MEMBER')
    registry = home / 'registry'
    if not registry.is_dir() or set(p.name for p in registry.iterdir()) - {'cache', 'index', 'src', 'CACHEDIR.TAG'}:
        raise ValueError('CARGO_REGISTRY_LAYOUT')
    if any(p.is_symlink() for p in registry.iterdir()):
        raise ValueError('CARGO_REGISTRY_SYMLINK')
    files = {}
    total = 0
    for kind in ['cache', 'index']:
        folder = registry / kind
        if not folder.is_dir() or folder.is_symlink():
            raise ValueError('CARGO_REGISTRY_LAYOUT')
        roots = list(folder.iterdir())
        if len(roots) != 1 or not re.fullmatch('index[.]crates[.]io-[0-9a-f]{16}', roots[0].name):
            raise ValueError('CARGO_REGISTRY_LAYOUT')
        for parent, dirs, names in os.walk(folder, followlinks=False):
            for name in dirs + names:
                p = Path(parent) / name
                if p.is_symlink() or not (p.is_dir() or p.is_file()):
                    raise ValueError('CARGO_REGISTRY_SYMLINK_OR_SPECIAL')
            for name in names:
                p = Path(parent) / name
                size = p.stat().st_size
                total += size
                if size > 67108864 or total > MAXIMUM_BYTES:
                    raise ValueError('CARGO_REGISTRY_BYTE_LIMIT')
                files[p.relative_to(home).as_posix()] = dict(digest=sha(p), bytes=size)
        if kind == 'cache':
            cache_root = roots[0]
        else:
            index_root = roots[0]
    if cache_root.name != index_root.name:
        raise ValueError('CARGO_REGISTRY_IDENTITY')
    if {p.name for p in cache_root.iterdir()} != set(packages) or any(not p.is_file() for p in cache_root.iterdir()):
        raise ValueError('CARGO_REGISTRY_ARCHIVE_SET')
    config_path = index_root / 'config.json'
    config = json.loads(config_path.read_text(), object_pairs_hook=strict_object)
    if (set(config) - {'dl', 'api', 'auth-required'} or
            config.get('dl') != 'https://static.crates.io/crates' or
            config.get('api') != 'https://crates.io' or config.get('auth-required', False) is not False):
        raise ValueError('CARGO_REGISTRY_CONFIGURATION')
    for p in index_root.rglob('*'):
        if p.is_file() and p != config_path:
            name = p.name
            if (not re.fullmatch('[a-z0-9_-]+', name) or
                    p.relative_to(index_root).as_posix() != '.cache/' + index_key(name)):
                raise ValueError('CARGO_REGISTRY_INDEX_MEMBER')
    for archive, package in packages.items():
        if sha(cache_root / archive) != package['checksum']:
            raise ValueError('CARGO_REGISTRY_ARCHIVE_CHECKSUM')
        if not (index_root / '.cache' / index_key(package['name'].lower())).is_file():
            raise ValueError('CARGO_REGISTRY_INDEX_MISSING')
    return dict(profile='patamaps-crates-io-context-1', lockDigest=sha(lock),
                registry=REGISTRY, registryDirectory=cache_root.name,
                packageCount=len(packages), fileCount=len(files), fileBytes=total,
                maximumBytes=MAXIMUM_BYTES, packages=packages, files=files,
                originalPublicDistributionArchives=True, extractedSourceCaptured=False,
                toolchainClosed=False, ownerTestFixturesClosed=False)


def stage(home, destination, record):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    for relative, expected in sorted(record['files'].items()):
        source = Path(home) / relative
        if source.is_symlink() or sha(source) != expected['digest']:
            raise ValueError('CARGO_REGISTRY_SOURCE_CHANGED')
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if sha(target) != expected['digest']:
            raise ValueError('CARGO_REGISTRY_COPY_CHANGED')
