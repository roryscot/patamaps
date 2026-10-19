"""Retained Intel verification for the crates.io alpha; never uploads or cleans."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with Path(path).open('rb') as source:
        return 'sha256:' + hashlib.file_digest(source, 'sha256').hexdigest()


def inventory():
    paths = [ROOT / name for name in ['Cargo.toml', 'Cargo.lock', 'rust-toolchain.toml', '.patamaps-crate-inputs']]
    paths.extend(ROOT / name for name in ['scripts/crates_alpha_native.py',
                 'scripts/sync_crate_inputs.py', 'scripts/crate_package_build.rs',
                 'scripts/parity/identity.py'])
    for folder in ['crates', 'vendor/icu_collator']:
        paths.extend(p for p in (ROOT / folder).rglob('*') if p.is_file() and
                     not any(c in {'target', '__pycache__', '.git'} for c in p.relative_to(ROOT).parts))
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(paths)}


def includes():
    count = 0
    for crate in sorted((ROOT / 'crates').iterdir()):
        if not (crate / 'Cargo.toml').is_file():
            continue
        for path in crate.rglob('*.rs'):
            for match in re.finditer(r'include_(?:str|bytes)!\(\s*"([^"]+)"', path.read_text()):
                target = (path.parent / match[1]).resolve(strict=True)
                if not target.is_relative_to(crate):
                    raise AssertionError(f'external Rust include: {path}: {target}')
                count += 1
    return {'checkedLiteralIncludes': count, 'externalIncludes': 0}


def source_coverage():
    recipes = {
        'patamaps-contracts': ('patamaps-projection', 'capture.rs'),
        'patamaps-core': ('patamaps-projection', 'capture.rs'),
        'patamaps-projection': ('patamaps-projection', 'capture.rs'),
        'patamaps-governance': ('patamaps-governance', 'proposal.rs'),
        'patamaps-workspace': ('patamaps-workspace', 'lib.rs'),
        'patamaps-scientific': ('patamaps-scientific', 'crate_export.rs'),
    }
    report = {}
    for crate, (recipe_crate, filename) in recipes.items():
        owner = ROOT / 'crates' / crate
        recipe = ROOT / 'crates' / recipe_crate / 'src' / filename
        text = recipe.read_text()
        bound = {(recipe.parent / p).resolve() for p in
                 re.findall(r'include_str!\(\s*"([^"]+)"', text)}
        for dependency, constant in re.findall(r'(patamaps_contracts|patamaps_core)::source_identity::([A-Z_]+)', text):
            source = ROOT / 'crates' / dependency.replace('_', '-') / 'src/source_identity.rs'
            matches = re.findall(r'pub const ' + constant + r': &str\s*=\s*include_str!\(\s*"([^"]+)"\s*\);', source.read_text())
            bound.update((source.parent / p).resolve() for p in matches)
        test_modules = set()
        for path in (owner / 'src').glob('*.rs'):
            for condition, explicit, name in re.findall(
                    r'#\[cfg\((.*?)\)\]\s*(?:#\[path\s*=\s*"([^"]+)"\]\s*)?mod ([a-z_]+);', path.read_text()):
                if re.sub(r'\s+', '', condition) in {'test', 'all(test,unix)', 'all(unix,test)'}:
                    test_modules.add(path.parent / (explicit or name + '.rs'))
        production = {p.resolve() for p in (owner / 'src').rglob('*.rs') if p not in test_modules}
        missing = sorted(str(p.relative_to(owner)) for p in production - bound)
        assert not missing, (crate, missing)
        report[crate] = {'productionFiles': len(production), 'missingBindings': missing,
                         'explicitTestModuleExclusions': sorted(str(p.relative_to(owner)) for p in test_modules)}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['prepare', 'native'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--start-at', help='Resume at a named command in a fresh retained record')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    environment = dict(os.environ, CARGO_TARGET_DIR=str(args.target.resolve()),
                       CARGO_PROFILE_DEV_DEBUG='0', CARGO_PROFILE_TEST_DEBUG='0',
                       CARGO_INCREMENTAL='0', CARGO_BUILD_JOBS='2', RUST_TEST_THREADS='1')
    receipt = {'profile': 'patamaps-crates-alpha-native-1', 'stage': args.stage,
               'root': str(ROOT), 'commands': [], 'status': 'running',
               'publicRegistryUpload': False, 'filesDeleted': 0,
               'target': environment['CARGO_TARGET_DIR'], 'startedAt': time.time()}
    native = [
        ('inputs', [sys.executable, 'scripts/sync_crate_inputs.py', '--check']),
        ('format', ['cargo', 'fmt', '--all', '--', '--check']),
        ('check', ['cargo', 'check', '--workspace', '--all-targets', '--locked', '--offline']),
        ('clippy', ['cargo', 'clippy', '--workspace', '--all-targets', '--locked', '--offline', '--', '-D', 'warnings']),
        ('tests', ['cargo', 'test', '--workspace', '--locked', '--offline']),
        ('doc-tests', ['cargo', 'test', '--workspace', '--doc', '--locked', '--offline']),
        ('cli', ['cargo', 'build', '-p', 'patamaps-cli', '--locked', '--offline']),
    ]
    prepare = [
        ('template-format', ['rustfmt', '--edition', '2024', 'scripts/crate_package_build.rs']),
        ('fork-format', ['rustfmt', '--edition', '2021', 'vendor/icu_collator/build.rs']),
        ('lock', ['cargo', 'generate-lockfile', '--offline']),
        ('source-format', ['cargo', 'fmt', '--all']),
        ('sync', [sys.executable, 'scripts/sync_crate_inputs.py']),
        ('inputs', [sys.executable, 'scripts/sync_crate_inputs.py', '--check']),
        ('diff', ['git', 'diff', '--check']),
    ]
    commands = prepare if args.stage == 'prepare' else native
    if args.start_at:
        index = next(i for i, item in enumerate(commands) if item[0] == args.start_at)
        receipt['precedingCommandsNotRepeated'] = [item[0] for item in commands[:index]]
        commands = commands[index:]
    before = inventory()
    (output / 'source-before.json').write_text(json.dumps(before, indent=2) + '\n')
    try:
        for identifier, command in commands:
            started = time.monotonic()
            stdout, stderr = output / f'{identifier}.stdout', output / f'{identifier}.stderr'
            with stdout.open('xb') as out, stderr.open('xb') as err:
                result = subprocess.run(command, cwd=ROOT, env=environment, stdout=out, stderr=err, timeout=3600)
            record = {'id': identifier, 'command': command, 'exitCode': result.returncode,
                      'elapsedSeconds': time.monotonic() - started,
                      'stdout': str(stdout), 'stderr': str(stderr),
                      'stdoutDigest': sha(stdout), 'stderrDigest': sha(stderr)}
            receipt['commands'].append(record)
            print(json.dumps({'command': identifier, 'exitCode': result.returncode,
                              'seconds': round(record['elapsedSeconds'], 3)}), flush=True)
            if result.returncode:
                print(stderr.read_text(errors='replace')[-5000:], flush=True)
                raise AssertionError(f'{identifier} exited {result.returncode}')
        receipt['includeCheck'] = includes()
        receipt['engineSourceCoverage'] = source_coverage()
        if args.stage == 'native':
            binary = args.target.resolve() / 'debug/patamaps'
            observed = json.loads(subprocess.check_output([str(binary), 'engine'], cwd=output, env=environment))
            spec = importlib.util.spec_from_file_location('alpha_identity', ROOT / 'scripts/parity/identity.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            expected = module.identities(ROOT)
            assert observed == expected, (observed, expected)
            receipt['engines'] = observed
            receipt['binaryDigest'] = sha(binary)
            receipt['independentEngineIdentityMatched'] = True
        after = inventory()
        (output / 'source-after.json').write_text(json.dumps(after, indent=2) + '\n')
        receipt['sourceUnchanged'] = before == after
        if args.stage == 'native':
            assert receipt['sourceUnchanged'], 'verification changed source inputs'
        receipt['status'] = 'passed'
    except BaseException as error:
        receipt['status'] = 'failed'
        receipt['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        receipt['finishedAt'] = time.time()
        (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    main()
