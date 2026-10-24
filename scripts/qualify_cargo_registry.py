"""Compose existing opaque context and retained build contracts for real Cargo."""
import copy
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

from cargo_registry_context import inventory, sha, stage
from cargo_registry_container import IMAGE


def restore_compiler(root, destination):
    """Reuse exact current-engine output; no installation or fresh-build claim."""
    artifact = 12531199013
    producer = '163b1235c9eb4996268e49899aba3b2de3d258aa'
    digest = 'sha256:d2fe67d0d209481bcb2c5500f6d2c58bafee81bf15c1ff2ebe4aba9912f33cb9'
    meta = json.loads(subprocess.check_output(['gh','api',f'repos/roryscot/patamaps/actions/artifacts/{artifact}'],timeout=30))
    assert not meta['expired'] and meta['workflow_run']['id']==40024281589 and meta['workflow_run']['head_sha']==producer
    assert meta['digest']==digest and meta['size_in_bytes']==10395729
    raw = subprocess.check_output(['gh','api',f'repos/roryscot/patamaps/actions/artifacts/{artifact}/zip'],timeout=60)
    assert len(raw)==10395729 and 'sha256:'+hashlib.sha256(raw).hexdigest()==digest
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        receipt = json.loads(archive.read('receipt.json'))
        info = archive.getinfo('artifacts/patamaps')
        assert info.file_size<=33554432
        binary = archive.read(info)
        assert hashlib.sha256(binary).hexdigest()==receipt['relocatedCompiler']['sha256']
    destination = Path(destination).resolve()
    assert not destination.exists()
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('xb') as stream:
        stream.write(binary)
    destination.chmod(0o755)
    engine = json.loads(subprocess.check_output([destination,'engine'],env={'PATH':'/usr/bin:/bin'},timeout=10))
    sys.path.insert(0,str(root/'scripts/parity'))
    from identity import identities
    assert engine==receipt['relocatedCompiler']['engine']==dict(schemaVersion='0.1.0',documentType='executor-description',**identities(root))
    return dict(artifactId=artifact,artifactDigest=digest,producerRevision=producer,binaryDigest=sha(destination),
                currentEngineVerified=True,freshCompilerBuild=False,installedPackageClaim=False)


def qualify(root, work, out, source, staged, names, cargo, cli, env, run, native, command, record):
    base = work/'registry-build'
    base.mkdir()
    evidence = out/'registry'
    evidence.mkdir()

    def write(path, value):
        path.write_text(json.dumps(value, indent=2)+'\n')

    download = base/'download-home'
    download.mkdir()
    previous = dict(env)
    try:
        env.update(HOME=str(download), CARGO_HOME=str(download),
                   CARGO_REGISTRIES_CRATES_IO_PROTOCOL='sparse', RUSTC=str(cargo.with_name('rustc')))
        assert not any((p/'.cargo/config.toml').exists() or (p/'.cargo/config').exists() for p in source.parents)
        run('fresh-registry-locked-fetch', [cargo, 'fetch', '--locked'], cwd=source)
    finally:
        env.clear(); env.update(previous)
    registry = inventory(download, source/'Cargo.lock')
    write(evidence/'inventory.json', registry)
    context_owner = base/'context-owner'
    context_owner.mkdir()
    stage(download, context_owner/'.cargo-home', registry)
    for name in names:
        target = context_owner/'application'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        assert not (staged/name).is_symlink(), 'Review upstream context symlink'
        shutil.copy2(staged/name, target)
    download.rename(base/'download-home.retained-unavailable')
    run('registry-image-pull', ['docker', 'pull', '--platform', 'linux/amd64', IMAGE], timeout=120)
    paths = sorted(p.relative_to(context_owner).as_posix() for p in context_owner.rglob('*') if p.is_file())
    selection = base/'selection.json'
    write(selection, dict(profile='patamaps-project-context-selection-1', id='urn:qualification:miniserve:registry',
                          nonsecretInputs=True, paths=paths, symlinks='refuse'))
    snapshot = base/'snapshot'
    captured = native('registry-context-capture', ['project-context-capture', selection, '--root', context_owner, '--destination', snapshot])
    binding_path = base/'binding.json'
    write(binding_path, dict(profile='patamaps-project-build-context-1', snapshot=str(snapshot), digest=captured['digest'],
                             overlays={}, writablePaths=['bundle']))
    owner = base/'owner'
    owner.mkdir()
    scripts = ['cargo_registry_container.py', 'project_watch.py', 'deployment_miniserve_image.py']
    for name in scripts:
        shutil.copyfile(root/'scripts'/name, owner/name)
    shutil.copyfile(root/'scripts/deployment/miniserve/registry-build.sh', owner/'registry-build.sh')
    shutil.copyfile(root/'scripts/deployment/miniserve/registry-nsswitch.conf', owner/'network-nsswitch.conf')
    shutil.copyfile(root/'scripts/deployment/miniserve/registry-hosts.conf', owner/'network-hosts.conf')
    write(owner/'registry-record.json', registry)
    tool_identities = {str(path):sha(path) for path in [cargo, cargo.with_name('rustc'), Path(shutil.which('docker')).resolve()]}
    write(owner/'registry-executor.json', dict(cargo=str(cargo), ownerTestSource=str(source),
                                             privateLogs=str(base/'private-execution'), toolIdentities=tool_identities))
    identity = 'urn:qualification:miniserve:registry-build'
    graph = dict(schemaVersion='0.1.0', documentType='graph', id=identity+':source', namespace='miniserve-registry', revision='1',
                 entities=[dict(id=identity+':application', kind='cargo-registry-build', label='Miniserve registry execution',
                                attributes=dict(registryContext=captured['digest'], upstreamLock=sha(source/'Cargo.lock')))], mappings=[], authorities=[])
    policy = dict(schemaVersion='0.1.0', documentType='policy', id=identity+':policy', graph=dict(id=identity, revision='1'), mappings=[], constraints=[], evidence=[])
    projection = dict(schemaVersion='0.1.0', documentType='projection-spec', id=identity+':projection', select=dict(kinds=['cargo-registry-build']), slots=[])
    for name, value in [('graph.json',graph), ('policy.json',policy), ('projection.json',projection)]:
        write(owner/name, value)
    inputs = sorted(p.name for p in owner.iterdir())
    project = dict(profile='patamaps-project-inputs-1', id=identity+':inputs', nonsecretInputs=True, inputs=inputs,
                   components=[dict(id='application', kind='deployment', root='.', entrypoints=['registry-executor.json'])],
                   nonsecretConfiguration=dict(path='/usr/bin:/bin'), secretReferences={})
    workspace = dict(schemaVersion='0.1.0', documentType='workspace-config', id=identity, namespace='miniserve-registry', revision='1',
                     sources=[dict(adapter='portable-shard',id=identity+':source',path='graph.json')], packs=[], policy='policy.json',
                     projections=[dict(path='projection.json',emissions=[dict(path='generated/registry.json',language='json')])],
                     context=dict(scope='explicit original crates.io input qualification'),evaluatedAt='2026-10-23T00:00:00Z')
    def invocation(verify=False):
        return command(sys.executable, ['-B','cargo_registry_container.py','--spec','registry-executor.json',*(['--verify'] if verify else [])],
                       refs=dict(PATH='path'), inputs=[*scripts,'registry-build.sh'], maximum=2400000 if not verify else 60000)
    plan = dict(profile='patamaps-project-build-1', maximumRetainedAttempts=8, project=project, workspace=workspace,
                buildSteps=[invocation()], verificationSteps=[invocation(True)], outputs=[dict(path='bundle',kind='tree')])
    plan_path, state = base/'plan.json', base/'state'
    write(plan_path, plan)
    try:
        selected = json.loads(run('registry-native-real-build', [cli,'project-build',plan_path,'--source',owner,'--state',state,'--context',binding_path], timeout=2400))
    finally:
        # Keep bounded executor diagnostics even when native selection refuses.
        # These helpers never emit the raw owner test logs or fixture contents.
        diagnostics = {}
        if (state/'attempts').exists():
            for attempt in (state/'attempts').iterdir():
                row = {}
                for item in attempt.glob('*.json'):
                    if item.name.startswith(('build-', 'verify-')) or item.name=='failure.json':
                        assert item.stat().st_size<2097152
                        row[item.name] = json.loads(item.read_text())
                execution_path = attempt/'candidate/bundle/registry-execution.json'
                if execution_path.is_file():
                    assert execution_path.stat().st_size<65536
                    row['registry-execution.json'] = json.loads(execution_path.read_text())
                diagnostics[attempt.name] = row
        write(evidence/'native-attempt-records.json', diagnostics)
    assert selected['status']=='selected-project-build' and selected['verification']=='commands-executed'
    pointer = (state/'selected.json').read_bytes()
    candidate = state/selected['attempt']/'candidate'
    execution = json.loads((candidate/'bundle/registry-execution.json').read_text())
    assert execution['status']=='passed-real-cargo-registry-execution' and execution['defaultTestsPassed']==325
    assert execution['binaryCopiedBeforeOwnerTests'] and execution['containerStopped'] and not download.exists()
    write(evidence/'execution.json', execution)
    archive_relative = '.cargo-home/'+next(p for p in sorted(registry['files']) if p.endswith('.crate'))
    original = snapshot/'data'/archive_relative
    retained = base/'original-registry-member.retained'
    original.rename(retained); original.write_bytes(b'controlled registry snapshot corruption')
    changed = copy.deepcopy(plan)
    changed['buildSteps'] = [command('/bin/sh',['-c','mkdir -p bundle; printf invoked > bundle/forbidden.marker'])]
    changed_path = base/'marker-plan.json'
    write(changed_path, changed)
    refusal = native('registry-snapshot-before-effects', ['project-build',changed_path,'--source',owner,'--state',state,'--context',binding_path], expected=1)
    assert refusal['previousSelectionPreserved'] and (state/'selected.json').read_bytes()==pointer
    assert not any((p/'candidate/bundle/forbidden.marker').exists() for p in (state/'attempts').iterdir())
    original.rename(base/'corrupt-registry-member.retained'); retained.rename(original)
    chosen = candidate/archive_relative
    backup = base/'selected-registry-member.retained'
    chosen.rename(backup); chosen.write_bytes(b'controlled selected registry corruption')
    selected_command = base/'marker-command.json'
    write(selected_command, command('/bin/sh',['-c','printf invoked > bundle/forbidden.marker']))
    run('registry-selected-before-effects', [cli,'project-exec-selected',state,selected_command], expected=2)
    assert not (candidate/'bundle/forbidden.marker').exists() and (state/'selected.json').read_bytes()==pointer
    assert 'PROJECT_CONTEXT' in (out/'logs/registry-selected-before-effects.stderr').read_text()
    chosen.rename(base/'corrupt-selected-member.retained'); backup.rename(chosen)
    owner.rename(base/'owner.retained-unavailable')
    snapshot.rename(base/'snapshot.retained-unavailable')
    replay = native('registry-offline-selected-replay', ['project-build-verify',state])
    assert replay['status']=='verified-selected-build-bindings'
    # One successful selected state retains each archive once. Do not also
    # publish the fresh download/extraction home, original clone or snapshot.
    archive = out/'artifacts/registry-selected-state.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:
        for name in ['driver.lock','selected.json',selected['attempt']]:
            tar.add(state/name, arcname='registry-state/'+name)
    assert archive.stat().st_size<=320*1024**2
    result = dict(status='passed-native-registry-context-execution', snapshotDigest=captured['digest'], inputKey=selected['inputKey'],
                  packageCount=registry['packageCount'], registryFileBytes=registry['fileBytes'], defaultTestsPassed=325,
                  configuredDownloadHomeUnavailable=True, immutableRegistryContext=True, generatedCargoPathsInsideQuota=True,
                  snapshotCorruptionRefusedBeforeMarker=True, selectedRegistryCorruptionRefusedBeforeMarker=True,
                  previousSelectionPreserved=True, restoredOfflineSelectedReplay=True,
                  configuredOwnerAndSnapshotUnavailable=True, selectionDigest=sha(state/'selected.json'),
                  retainedStateArchive=dict(digest=sha(archive),bytes=archive.stat().st_size),
                  completeDependencyClosure=False, ownerTestFixturesClosed=False, toolchainClosed=False,
                  originalPublicArchives=True, originalSourceInputsUnchanged=True, filesDeleted=0)
    write(evidence/'receipt.json', result)
    record['cargoRegistryContext'] = result
    record['upstreamTestSummaries'] = execution['testSummaries']
    return candidate/'bundle/miniserve'
