"""Prepare exact .crate candidates and rehearse installation; never publishes or deletes."""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import time
import tomllib
import urllib.request

ALPHA = '0.1.0-alpha.1'
FORK = 'patamaps-icu-collator'
FORK_VERSION = '2.2.1-patamaps.1'
ORDER = [FORK, 'patamaps-contracts', 'patamaps-core', 'patamaps-projection',
         'patamaps-governance', 'patamaps-workspace', 'patamaps-scientific',
         'patamaps-inspect', 'patamaps-cli', 'patamaps-activator']
USER_AGENT = 'patamaps-alpha-preparation (https://github.com/roryscot/patamaps)'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def slug(name):
    name = name.lower()
    if len(name) <= 2:
        return f'{len(name)}/{name}'
    if len(name) == 3:
        return f'3/{name[0]}/{name}'
    return f'{name[:2]}/{name[2:4]}/{name}'


def download(url, destination, expected=None):
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=90) as response, destination.open('xb') as stream:
        shutil.copyfileobj(response, stream)
    if expected:
        assert digest(destination) == expected, f'upstream checksum mismatch: {destination.name}'


def metadata_from_cache(home, package, destination):
    path = slug(package['name'])
    for index in (home / 'registry/index').glob('*'):
        candidate = index / '.cache' / path
        if not candidate.is_file():
            continue
        for part in candidate.read_bytes().split(b'\0'):
            if not part.startswith(b'{'):
                continue
            value = json.loads(part)
            if value.get('vers') == package['version']:
                assert value['cksum'] == package['checksum']
                return value
    temporary = destination / f"{package['name']}-{package['version']}.index-response"
    download('https://index.crates.io/' + path, temporary)
    for line in temporary.read_text().splitlines():
        value = json.loads(line)
        if value['vers'] == package['version']:
            assert value['cksum'] == package['checksum']
            return value
    raise AssertionError(f"locked upstream version absent: {package['name']} {package['version']}")


def index_write(registry, entry):
    path = registry / 'index' / slug(entry['name'])
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        records = [json.loads(line) for line in path.read_text().splitlines()]
        same = [value for value in records if value['vers'] == entry['vers']]
        if same:
            assert same == [entry], f'changed registry entry: {entry["name"]}'
            return
    with path.open('a') as stream:
        stream.write(json.dumps(entry, separators=(',', ':')) + '\n')


def index_entry(manifest, checksum):
    dependencies = []
    groups = [(None, manifest)] + list(manifest.get('target', {}).items())
    for target, group in groups:
        for table, kind in [('dependencies', 'normal'), ('dev-dependencies', 'dev'), ('build-dependencies', 'build')]:
            for alias, value in group.get(table, {}).items():
                value = {'version': value} if isinstance(value, str) else value
                assert 'workspace' not in value and 'path' not in value and 'git' not in value, (alias, value)
                assert value.get('registry') in {None, 'crates-io'}
                dependencies.append({'name': alias, 'req': value['version'],
                                     'features': value.get('features', []),
                                     'optional': value.get('optional', False),
                                     'default_features': value.get('default-features', True),
                                     'target': target, 'kind': kind, 'registry': None,
                                     'package': value.get('package')})
    package = manifest['package']
    return {'name': package['name'], 'vers': package['version'], 'deps': dependencies,
            'cksum': checksum, 'features': {}, 'features2': manifest.get('features', {}),
            'v': 2, 'yanked': False, 'links': package.get('links'),
            'rust_version': package.get('rust-version')}


def inspect_archive(path, name, version, extraction=None):
    assert path.stat().st_size < 10_000_000, f'crate exceeds alpha registry size limit: {name}'
    prefix = f'{name}-{version}'
    members = []
    manifests = {}
    seen = set()
    with tarfile.open(path, 'r:gz') as archive:
        for member in archive:
            relative = PurePosixPath(member.name)
            assert relative.parts and relative.parts[0] == prefix
            assert not relative.is_absolute() and '..' not in relative.parts
            assert member.name not in seen
            seen.add(member.name)
            assert member.isfile() or member.isdir(), f'nonordinary archive member: {member.name}'
            if member.isdir():
                continue
            tail = PurePosixPath(*relative.parts[1:])
            assert tail.parts
            raw = archive.extractfile(member).read()
            members.append({'path': tail.as_posix(), 'bytes': len(raw),
                            'sha256': hashlib.sha256(raw).hexdigest()})
            if tail.as_posix() == 'Cargo.toml':
                manifests = tomllib.loads(raw.decode())
            if extraction:
                target = extraction.joinpath(*tail.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as stream:
                    stream.write(raw)
    assert manifests['package']['name'] == name and manifests['package']['version'] == version
    assert set(manifests.get('workspace', {})) <= {'resolver'}
    assert manifests['package']['license'] == ('Unicode-3.0' if name == FORK else 'Apache-2.0')
    assert any(value['path'] == 'LICENSE' for value in members)
    if name != FORK:
        assert any(value['path'] == 'NOTICE' for value in members)
    index_entry(manifests, digest(path))
    return manifests, members


class Gate:
    def __init__(self, args):
        self.args = args
        self.source = args.source.resolve(strict=True)
        self.state = args.state.resolve()
        self.state.mkdir(parents=True, exist_ok=True)
        self.output = self.state / args.record
        self.output.mkdir(exist_ok=False)
        self.registry = self.state / 'candidate-registry'
        self.original_home = Path(os.environ.get('CARGO_HOME', str(Path.home() / '.cargo')))
        self.environment = {key: os.environ[key] for key in [
            'PATH', 'HOME', 'USER', 'TMPDIR', 'RUSTUP_HOME', 'RUSTUP_TOOLCHAIN',
            'DEVELOPER_DIR', 'SDKROOT', 'MACOSX_DEPLOYMENT_TARGET'] if key in os.environ}
        self.environment.update(CARGO_BUILD_JOBS='2', RUST_TEST_THREADS='1', CARGO_INCREMENTAL='0',
                                CARGO_PROFILE_DEV_DEBUG='0', CARGO_PROFILE_TEST_DEBUG='0')
        self.receipt = {'profile': 'patamaps-crates-alpha-package-1', 'stage': args.stage,
                        'source': str(self.source), 'sourceCommit': args.expected_source,
                        'state': str(self.state), 'commands': [], 'status': 'running',
                        'publicRegistryUpload': False, 'publicRegistryDownload': False,
                        'candidateSourceReplacement': True, 'pathDependencyOverrides': 0,
                        'filesDeleted': 0, 'startedAt': time.time(),
                        'driverDigest': digest(Path(__file__))}
        self.check_source()
        self.receipt['cargoVersion'] = subprocess.check_output(['cargo', '--version'], env=self.environment, text=True).strip()
        self.receipt['rustcVersionVerbose'] = subprocess.check_output(['rustc', '-vV'], env=self.environment, text=True)
        self.receipt['pythonVersion'] = sys.version

    def check_source(self):
        observed = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=self.source, text=True).strip()
        assert observed == self.args.expected_source
        status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=self.source, text=True)
        assert not status, 'publishing source must be clean and frozen'

    def home(self, name, registry=None):
        home = self.state / name
        home.mkdir(exist_ok=False)
        (home / 'config.toml').write_text('[source.crates-io]\nreplace-with = "alpha-candidate"\n'
            '[source.alpha-candidate]\nlocal-registry = ' + json.dumps(str(registry or self.registry)) + '\n'
            '[net]\noffline = true\n')
        return home

    def command(self, identifier, command, cwd=None, home=None, target=None, sandbox=None,
                expected=0, required_error=None, stdin=None, minimal_path=False):
        environment = dict(self.environment)
        if home:
            environment['CARGO_HOME'] = str(home)
        if target:
            environment['CARGO_TARGET_DIR'] = str(target)
        if minimal_path:
            environment['PATH'] = '/usr/bin:/bin'
        if sandbox:
            command = ['/usr/bin/sandbox-exec', '-f', str(sandbox), *map(str, command)]
        command = list(map(str, command))
        stdout, stderr = self.output / f'{identifier}.stdout', self.output / f'{identifier}.stderr'
        started = time.monotonic()
        with stdout.open('xb') as out, stderr.open('xb') as err:
            result = subprocess.run(command, cwd=cwd or self.source, env=environment,
                                    input=stdin, stdout=out, stderr=err, timeout=3600)
        record = {'id': identifier, 'command': command, 'cwd': str(cwd or self.source),
                  'exitCode': result.returncode, 'expectedExitCode': expected,
                  'elapsedSeconds': time.monotonic() - started,
                  'stdout': str(stdout), 'stderr': str(stderr),
                  'stdoutDigest': digest(stdout), 'stderrDigest': digest(stderr)}
        self.receipt['commands'].append(record)
        save(self.output / f'{identifier}.receipt.json', record)
        print(json.dumps({'command': identifier, 'exitCode': result.returncode,
                          'seconds': round(record['elapsedSeconds'], 3)}), flush=True)
        valid = result.returncode == expected if expected is not None else result.returncode != 0
        if required_error:
            diagnostic = (stdout.read_text(errors='replace') + stderr.read_text(errors='replace')).lower()
            valid = valid and all(value.lower() in diagnostic for value in required_error)
        if not valid:
            print(stderr.read_text(errors='replace')[-7000:], flush=True)
            raise AssertionError(f'{identifier}: unexpected command outcome')
        return stdout.read_text(errors='replace')

    def seed(self):
        self.registry.mkdir(exist_ok=False)
        (self.registry / 'index').mkdir()
        save(self.registry / 'index/config.json', {'dl': self.registry.as_uri() + '/{crate}-{version}.crate'})
        locked = {}
        for lock in [self.source / 'Cargo.lock', self.source / 'vendor/icu_collator/Cargo.lock']:
            for package in tomllib.loads(lock.read_text())['package']:
                if 'source' not in package:
                    continue
                assert package['source'] == 'registry+https://github.com/rust-lang/crates.io-index'
                key = package['name'], package['version']
                # A lockfile records the enabled dependency graph as well as
                # archive identity. Optional features can change that graph
                # between the workspace and standalone fork without changing
                # the upstream archive or its verified checksum.
                identity = {field: package[field] for field in ['name', 'version', 'source', 'checksum']}
                if key in locked:
                    assert locked[key] == identity
                locked[key] = identity
        records = []
        for package in sorted(locked.values(), key=lambda p: (p['name'], p['version'])):
            name = f"{package['name']}-{package['version']}.crate"
            candidates = sorted((self.original_home / 'registry/cache').glob('*/' + name))
            destination = self.registry / name
            if candidates:
                assert digest(candidates[0]) == package['checksum']
                with candidates[0].open('rb') as source, destination.open('xb') as output:
                    shutil.copyfileobj(source, output)
                provenance = 'verified-existing-public-registry-cache'
            else:
                download(f"https://static.crates.io/crates/{package['name']}/{name}", destination, package['checksum'])
                provenance = 'locked-public-registry-download'
            entry = metadata_from_cache(self.original_home, package, self.output)
            index_write(self.registry, entry)
            records.append({'name': package['name'], 'version': package['version'],
                            'sha256': digest(destination), 'bytes': destination.stat().st_size,
                            'provenance': provenance})
        save(self.state / 'upstream-inventory.json', records)
        self.home('package-home')
        self.receipt['upstreamArchives'] = len(records)
        self.receipt['upstreamArchiveBytes'] = sum(value['bytes'] for value in records)

    def package(self):
        home = self.state / 'package-home'
        assert home.is_dir()
        target = self.state / 'package-target'
        record_root = self.state / 'package-records'
        record_root.mkdir(exist_ok=True)
        accepted = []
        for name in ORDER:
            version = FORK_VERSION if name == FORK else ALPHA
            record_path = record_root / f'{name}.json'
            archive = self.registry / f'{name}-{version}.crate'
            if record_path.exists():
                record = json.loads(record_path.read_text())
                assert record['sourceCommit'] == self.args.expected_source
                assert digest(archive) == record['sha256']
                accepted.append(record)
                continue
            command = ['cargo', 'package', '--locked', '--offline']
            command += ['--manifest-path', 'vendor/icu_collator/Cargo.toml'] if name == FORK else ['-p', name]
            self.command('package-' + name, command, home=home, target=target)
            built = target / 'package' / archive.name
            manifest, members = inspect_archive(built, name, version)
            with built.open('rb') as source, archive.open('xb') as destination:
                shutil.copyfileobj(source, destination)
            index_write(self.registry, index_entry(manifest, digest(archive)))
            record = {'name': name, 'version': version, 'sourceCommit': self.args.expected_source,
                      'path': str(archive), 'sha256': digest(archive), 'bytes': archive.stat().st_size,
                      'members': members, 'cargoPackageVerification': True,
                      'commandReceipt': str(self.output / f'package-{name}.receipt.json')}
            save(record_path, record)
            accepted.append(record)
            self.check_source()
        save(self.output / 'candidate-inventory.json', accepted)
        self.receipt['candidateArchives'] = len(accepted)
        self.receipt['candidateArchiveBytes'] = sum(value['bytes'] for value in accepted)

    def profile(self, name, extra=()):
        roots = {str(self.source), str(Path(__file__).resolve().parents[1])}
        original = Path(os.environ['PATAMAPS_DEV_ROOT']).resolve()
        for directory in ['crates', 'fixtures', 'relation-packs', 'schemas', 'vendor', 'sdk', 'adapters', 'scripts', '.git', '.cargo']:
            roots.add(str(original / directory))
        literals = [original / name for name in ['Cargo.toml', 'Cargo.lock', 'rust-toolchain.toml']]
        statements = ['(version 1)', '(allow default)', '(deny network-outbound)']
        statements += ['(deny file-read* (subpath ' + json.dumps(root) + '))' for root in sorted(roots)]
        statements += ['(deny file-read* (literal ' + json.dumps(str(path)) + '))' for path in [*literals, *extra]]
        profile = self.output / name
        profile.write_text('\n'.join(statements) + '\n')
        return profile

    def clean(self):
        records = [json.loads((self.state / 'package-records' / f'{name}.json').read_text()) for name in ORDER]
        for record in records:
            assert digest(Path(record['path'])) == record['sha256']
        unpacked = self.state / 'unpacked-candidates'
        unpacked.mkdir(exist_ok=False)
        for record in records:
            destination = unpacked / ('vendor/icu_collator' if record['name'] == FORK else f"crates/{record['name']}")
            inspect_archive(Path(record['path']), record['name'], record['version'], destination)
        verifier = self.state / 'identity-verifier.py'
        with (self.source / 'scripts/parity/identity.py').open('rb') as source, verifier.open('xb') as destination:
            shutil.copyfileobj(source, destination)
        home = self.home('clean-home')
        target = self.state / 'clean-target'
        installation = self.state / 'installation'
        consumer = self.state / 'rust-consumer'
        (consumer / 'src').mkdir(parents=True)
        libraries = [name for name in ORDER if name not in {FORK, 'patamaps-cli', 'patamaps-activator'}]
        (consumer / 'Cargo.toml').write_text('[package]\nname = "alpha-independent-consumer"\nversion = "0.0.0"\nedition = "2024"\n'
            '[dependencies]\n' + ''.join(name + ' = "=' + ALPHA + '"\n' for name in libraries) +
            'serde_json = "=1.0.151"\n[workspace]\n')
        (consumer / 'src/main.rs').write_text('fn main() {}\n')
        profile = self.profile('source-unavailable.sb')
        python = Path(sys.executable).resolve()
        denial = 'from pathlib import Path\nimport errno\nfor name in ' + repr([str(self.source / 'Cargo.toml'),
            str(Path(os.environ['PATAMAPS_DEV_ROOT']).resolve() / 'crates/patamaps-core/src/lib.rs')]) + ''':
 try: Path(name).read_bytes()
 except PermissionError: continue
 raise AssertionError("development source was readable")
print("development source reads denied")
'''
        self.command('source-denial', [python, '-c', denial], cwd=consumer, sandbox=profile)
        self.command('install-cli', ['cargo', 'install', 'patamaps-cli', '--version', ALPHA,
                     '--locked', '--offline', '--root', installation], cwd=consumer, home=home, target=target, sandbox=profile)
        cli = installation / 'bin/patamaps'
        engines = json.loads(self.command('installed-engine', [cli, 'engine'], cwd=consumer, sandbox=profile, minimal_path=True))
        code = 'import importlib.util,json; from pathlib import Path; s=importlib.util.spec_from_file_location("identity",' + repr(str(verifier)) + '); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(json.dumps(m.identities(Path(' + repr(str(unpacked)) + '))))'
        expected = json.loads(self.command('archive-identities', [python, '-c', code], cwd=consumer, sandbox=profile))
        assert engines == {'schemaVersion': '0.1.0', 'documentType': 'executor-description', **expected}
        self.receipt['engines'] = engines
        self.receipt['independentArchiveIdentityMatched'] = True
        self.receipt['installedBinaryDigest'] = digest(cli)
        self.receipt['identityVerifierDigest'] = digest(verifier)
        self.runtime_consumer(consumer, cli, home, target, profile, unpacked)
        self.command('consumer-lock', ['cargo', 'generate-lockfile', '--offline'], cwd=consumer, home=home, target=target, sandbox=profile)
        self.command('library-consumer', ['cargo', 'run', '--locked', '--offline', '--', str(consumer / 'cases/after')],
                     cwd=consumer, home=home, target=target, sandbox=profile)
        metadata = json.loads(self.command('consumer-metadata', ['cargo', 'metadata', '--locked', '--offline', '--format-version', '1'],
                              cwd=consumer, home=home, target=target, sandbox=profile))
        owned = []
        for package in metadata['packages']:
            if package['name'] not in ORDER:
                continue
            path = Path(package['manifest_path']).resolve()
            assert package['source'] and package['source'].startswith('registry+')
            assert path.is_relative_to(self.state) and not path.is_relative_to(self.source)
            assert package['version'] == (FORK_VERSION if package['name'] == FORK else ALPHA)
            owned.append({'name': package['name'], 'source': package['source'], 'manifestPath': str(path)})
        assert {value['name'] for value in owned} == set(libraries) | {FORK}
        self.receipt['registryLibraryOrigins'] = owned
        self.receipt['sourceUnavailableCleanInstall'] = True
        self.tamper_control(consumer, profile)
        self.receipt['activationAttempted'] = False

    def runtime_consumer(self, consumer, cli, home, target, profile, unpacked):
        def write(path, value):
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        def graph(identity, entities, mappings=None, authorities=None):
            return {'schemaVersion': '0.1.0', 'documentType': 'graph', 'id': identity, 'namespace': 'alpha-independent',
                    'entities': entities, 'mappings': mappings or [], 'authorities': authorities or []}
        def authority(identity, concept, fact, owner):
            return {'id': identity, 'concept': concept, 'source': concept, 'facts': [fact], 'mode': 'canonical',
                    'provenance': {'status': 'declared', 'assertedBy': owner}}
        operation, handler, schema = 'urn:operation:greet', 'urn:service:greeting-handler', 'urn:contract:name'
        pack = unpacked / 'crates/patamaps-core/package-inputs/relation-packs/routing.json'
        rustc = subprocess.check_output(['rustup', 'which', 'rustc'], env=self.environment, text=True).strip()
        artifacts = []
        for moved in [False, True]:
            label = 'after' if moved else 'before'
            work = consumer / 'cases' / label
            work.mkdir(parents=True)
            (work / 'routing.json').write_bytes(pack.read_bytes())
            (work / 'service.rs').write_text('pub fn greet(input: &str) -> String { format!("Hello, {}!", input) }\n')
            module = 'moved' if moved else 'service'
            if moved:
                (work / 'service.rs').rename(work / 'moved.rs')
            (work / 'main.rs').write_text('mod ' + module + '; mod bindings; fn main() { let id = bindings::SemanticId::parse("urn:operation:greet").unwrap(); assert_eq!(id.as_str(), "urn:operation:greet"); println!("{}", bindings::dispatch(id, "Ada")); }\n')
            contract = graph('urn:shard:contract', [{'id': operation, 'kind': 'routing:command'}, {'id': schema, 'kind': 'routing:schema'}],
                             authorities=[authority('urn:authority:contract', operation, 'routing-identity', 'team:contract')])
            service = graph('urn:shard:service', [{'id': handler, 'kind': 'routing:handler',
                            'locators': [{'uri': 'rust:crate::' + module + '::greet'}]}],
                            authorities=[authority('urn:authority:service', handler, 'implementation', 'team:service')])
            links = graph('urn:shard:consumer', [], mappings=[
                {'id': 'urn:map:handler', 'relation': 'routing:handled_by', 'sources': [operation], 'targets': [handler],
                 'cardinality': 'one-to-one', 'lossiness': 'lossless', 'provenance': {'status': 'declared', 'assertedBy': 'team:consumer'}},
                {'id': 'urn:map:input', 'relation': 'routing:accepts', 'sources': [operation], 'targets': [schema],
                 'cardinality': 'one-to-one', 'lossiness': 'lossless', 'provenance': {'status': 'declared', 'assertedBy': 'team:consumer'}}])
            spec = {'schemaVersion': '0.1.0', 'documentType': 'projection-spec', 'id': 'urn:projection:alpha',
                    'select': {'ids': [operation]}, 'slots': [{'name': 'handler', 'relation': 'routing:handled_by',
                    'direction': 'outgoing', 'cardinality': 'exactly-one', 'targetKinds': ['routing:handler']}]}
            for name, value in [('contract', contract), ('service', service), ('links', links), ('spec', spec)]:
                write(work / f'{name}.json', value)
            common = dict(cwd=work, sandbox=profile, minimal_path=True)
            self.command(label + '-compose', [cli, 'compose', 'contract.json', 'service.json', 'links.json', '--id',
                         'urn:graph:alpha', '--namespace', 'alpha', '--relation-pack', 'routing.json', '--output', 'graph.json'], **common)
            binding = json.loads(self.command(label + '-validate', [cli, 'validate', 'graph.json', '--relation-pack', 'routing.json'], **common))['graph']
            policy = {'schemaVersion': '0.1.0', 'documentType': 'policy', 'id': 'urn:policy:alpha',
                      'graph': {'id': 'urn:graph:alpha', 'digest': binding},
                      'mappings': [{'mapping': m['id'], 'coverage': 'total', 'determinism': 'deterministic',
                                   'reversibility': 'irreversible'} for m in links['mappings']],
                      'constraints': [{'id': 'urn:constraint:authority', 'kind': 'core:requires-authority',
                                       'subjects': [operation], 'parameters': {'fact': 'routing-identity'}}], 'evidence': []}
            write(work / 'policy.json', policy)
            self.command(label + '-compile', [cli, 'compile', 'graph.json', 'policy.json', '--as-of', '2026-10-19T12:00:00Z',
                         '--relation-pack', 'routing.json', '-o', 'generation.json'], **common)
            self.command(label + '-link', [cli, 'link', 'graph.json', 'policy.json', 'spec.json', '--as-of',
                         '2026-10-19T12:00:00Z', '--relation-pack', 'routing.json', '--generation', 'generation.json',
                         '--binding-slot', 'handler', '--format', 'rust', '-o', 'bindings.rs'], **common)
            self.command(label + '-rustc', [rustc, '--edition=2024', 'main.rs', '-o', 'generated-consumer'], **common)
            tools = [cli.resolve(), Path(rustc).resolve()]
            runtime_profile = self.profile(label + '-runtime.sb', extra=tools)
            calibration = 'from pathlib import Path\nfor name in ' + repr(list(map(str, tools))) + ''':
 try: Path(name).read_bytes()
 except PermissionError: continue
 raise AssertionError("selected compiler was readable")
print("selected graph and Rust compiler reads denied")
'''
            self.command(label + '-compiler-denial', [Path(sys.executable).resolve(), '-c', calibration],
                         cwd=work, sandbox=runtime_profile, minimal_path=True)
            text = self.command(label + '-runtime', [work / 'generated-consumer'], cwd=work, sandbox=runtime_profile, minimal_path=True)
            assert text.strip() == 'Hello, Ada!'
            artifacts.append(digest(work / 'bindings.rs'))
        assert artifacts[0] != artifacts[1]
        self.receipt['generatedRuntimeWithoutCompiler'] = True
        self.receipt['stableIdentityAcrossActualModuleMove'] = True
        self.receipt['generatedRustArtifactDigests'] = artifacts
        source = r'''use patamaps_contracts::{parse, GraphDocument, RelationPack, PolicyDocument, ProjectionSpec};
use patamaps_projection::{capture, replay, CaptureInputs};
use std::{fs, path::PathBuf};
fn main() {
 let root=PathBuf::from(std::env::args().nth(1).expect("case root"));
 let graph:GraphDocument=parse(&fs::read(root.join("graph.json")).unwrap()).unwrap();
 let pack:RelationPack=parse(&fs::read(root.join("routing.json")).unwrap()).unwrap();
 let policy:PolicyDocument=parse(&fs::read(root.join("policy.json")).unwrap()).unwrap();
 let spec:ProjectionSpec=parse(&fs::read(root.join("spec.json")).unwrap()).unwrap();
 let record=capture(CaptureInputs { graph, packs:vec![pack], policy, context:Default::default(),
   evaluated_at:"2026-10-19T12:00:00Z".into(), projection_spec:Some(spec), projection_specs:vec![] },vec![]).unwrap();
 replay(&record).expect("fresh capture replay");
 fs::write(root.join("capture.json"),serde_json::to_vec_pretty(&record).unwrap()).unwrap();
 let mut forged=record.clone(); forged.result=serde_json::json!({"forged":true});
 assert!(replay(&forged).is_err(),"tampered capture must refuse");
 println!("alpha library capture/replay and tamper refusal passed");
}
'''
        (consumer / 'src/main.rs').write_text(source)

    def tamper_control(self, consumer, profile):
        name = 'patamaps-contracts'
        archive = self.registry / f'{name}-{ALPHA}.crate'
        bad = self.state / 'tampered-candidate-registry'
        bad.mkdir(exist_ok=False)
        shutil.copytree(self.registry / 'index', bad / 'index')
        for candidate in self.registry.glob('*.crate'):
            if candidate.name == archive.name:
                raw = bytearray(candidate.read_bytes())
                raw[len(raw) // 2] ^= 1
                with (bad / candidate.name).open('xb') as destination:
                    destination.write(raw)
            else:
                with candidate.open('rb') as source, (bad / candidate.name).open('xb') as destination:
                    shutil.copyfileobj(source, destination)
        assert digest(bad / archive.name) != digest(archive)
        home = self.home('tamper-home', registry=bad)
        self.command('archive-checksum-refusal', ['cargo', 'fetch', '--locked', '--offline'],
                     cwd=consumer, home=home, sandbox=profile, expected=None,
                     required_error=['checksum', name])
        self.receipt['tamperedArchiveRefused'] = True
        assert digest(archive) == json.loads((self.state / 'package-records' / f'{name}.json').read_text())['sha256']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['seed', 'package', 'clean'], required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--expected-source', required=True)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--record', required=True)
    args = parser.parse_args()
    assert Path(args.record).name == args.record
    gate = Gate(args)
    try:
        getattr(gate, args.stage)()
        gate.check_source()
        gate.receipt['sourceUnchanged'] = True
        gate.receipt['status'] = 'passed'
    except BaseException as error:
        gate.receipt['status'] = 'failed'
        gate.receipt['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        gate.receipt['finishedAt'] = time.time()
        save(gate.output / 'receipt.json', gate.receipt)


if __name__ == '__main__':
    main()
