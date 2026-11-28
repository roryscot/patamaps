"""Fresh installed source/native compilers rebuild the pinned real Rust owner."""
import argparse,hashlib,json,os,platform,shlex,shutil,subprocess,sys,time
from pathlib import Path
from cross_stack_package import install_archive
from installed_selected import verify_installed_source
from project_watch import stop
ROOT=Path(__file__).resolve().parent.parent
HARNESSES=[43,15,15,22,6,13,4,9,2,11,2,5,8,15,57,45,5,39,9]
HTTP=['pinned-version-startup','exact-get-body','head-length-and-empty-body','directory-listing','missing-document-refused','out-of-prefix-refused','invalid-port-refused','wrong-listener-readiness-refused']

def sha(path):
 with Path(path).open('rb') as source:return 'sha256:'+hashlib.file_digest(source,'sha256').hexdigest()

def write(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')

def case_result(result,execution,identity,engine,compiler_digest):
 assert result['status']=='passed-source-built-miniserve-linux-deployment' and result['sourceRevision'] is None,'INSTALLED_RUST_OWNER_STATUS'
 assert result['installedSourceIdentity']==identity and result['installedSourceInventoryUnchanged'] is True,'INSTALLED_RUST_SOURCE_BINDING'
 assert result['relocatedCompiler']['engine']==engine and 'sha256:'+result['relocatedCompiler']['sha256']==compiler_digest,'INSTALLED_RUST_COMPILER'
 for key in ['sourceBuild','upstreamSourceUnchanged','capturedSourceStageMatchesFrozenInventory','configuredSourceAndSnapshotUnavailableReplay','previousSelectionPreservedOnFourRefusals','staleRuntimeRefusedBeforeCommand','restoredSelectedRuntimePassed','runtimeVerificationBeforeSelection','actualHttp']:
  assert result[key] is True,'INSTALLED_RUST_OWNER_CONTROL'
 assert result['runtimeControls']==HTTP,'INSTALLED_RUST_HTTP'
 summaries=[[int(v) for v in row] for row in result['upstreamTestSummaries']]
 assert [r[0] for r in summaries]==HARNESSES and all(r[1:]==[0,0] for r in summaries),'INSTALLED_RUST_UPSTREAM_HARNESSES'
 registry=result['cargoRegistryContext']
 assert registry['status']=='passed-native-registry-context-execution' and registry['packageCount']==456 and registry['defaultTestsPassed']==325,'INSTALLED_RUST_REGISTRY'
 for key in ['configuredDownloadHomeUnavailable','immutableRegistryContext','generatedCargoPathsInsideQuota','snapshotCorruptionRefusedBeforeMarker','selectedRegistryCorruptionRefusedBeforeMarker','previousSelectionPreserved','restoredOfflineSelectedReplay','configuredOwnerAndSnapshotUnavailable','originalPublicArchives','originalSourceInputsUnchanged']:
  assert registry[key] is True,'INSTALLED_RUST_REGISTRY_CONTROL'
 assert execution['status']=='passed-real-cargo-registry-execution' and execution['defaultTestsPassed']==325,'INSTALLED_RUST_EXECUTION'
 assert [[int(v) for v in row] for row in execution['testSummaries']]==summaries,'INSTALLED_RUST_EXECUTION_TESTS'
 for key in ['hostConfigurationVerifiedBeforeStart','releaseBuildObserved','binaryCopiedBeforeOwnerTests','kernelLimitsVerified','externalRouteAbsent','loopbackAvailableForOwnerTests','ipv6LoopbackVerified','ipv6ExternalRouteAbsent','retainedArchiveIndexReadOnly','containerStopped','allOwnedContainersStopped','guardianCleanupConfirmed']:
  assert execution[key] is True,'INSTALLED_RUST_EXECUTION_CONTROL'
 assert execution['cpuAllowance']==2 and execution['memoryAllowance']==6*1024**3 and execution['memorySwapAllowance']==0 and execution['pidsAllowance']==512 and execution['workFilesystemBytes']==3*1024**3,'INSTALLED_RUST_ENFORCEMENT'
 assert execution['localAddressProvision']['helperStoppedBeforeCargo'] is True and execution['localAddressProvision']['workloadCapabilitiesDropped'] is True,'INSTALLED_RUST_SETUP'
 assert execution['originalConfiguredCacheMounted'] is False and registry['completeDependencyClosure'] is False and execution['ownerTestFixturesClosed'] is False,'INSTALLED_RUST_SCOPE'
 return dict(applicationRecompiled=True,upstreamCommit=result['upstreamCommit'],sourceFiles=len(result['upstreamInventory']),registryPackages=456,upstreamTestsPassed=325,testSummaries=summaries,httpControls=HTTP,selectionRefusalsPassed=4,registryCorruptionRefusedBeforeEffects=True,staleRuntimeRefusedBeforeEffects=True,restoredSelectedRuntimePassed=True,allOwnedContainersStopped=True,compilerDigest=compiler_digest,engine=engine,sourceInventoryDigest=identity['sourceInventoryDigest'],sourceWithoutGit=True,completeDependencyClosure=False)

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 for name in ['work','evidence']:parser.add_argument('--'+name,type=Path,required=True)
 args=parser.parse_args()
 assert platform.system()=='Linux' and platform.machine()=='x86_64' and os.environ.get('GITHUB_ACTIONS')=='true','Use focused Linux CI; Intel heavy work requires its guard'
 work,out=args.work.resolve(),args.evidence.resolve()
 assert not work.exists() and not out.exists()
 work.mkdir(parents=True);out.mkdir(parents=True);(work/'private-logs').mkdir()
 assert not any((p/'Cargo.toml').exists() for p in work.parents)
 assert subprocess.run(['git','diff','--quiet','HEAD','--'],cwd=ROOT).returncode==0,'Producing tracked source must be clean'
 baseline=shutil.disk_usage(ROOT).used;began=time.monotonic()
 env={k:v for k,v in os.environ.items() if k in ['PATH','HOME','CARGO_HOME','RUSTUP_HOME']}
 env.update(GITHUB_ACTIONS='true',PYTHONDONTWRITEBYTECODE='1',CARGO_INCREMENTAL='0',CARGO_BUILD_JOBS='2',CARGO_PROFILE_DEV_DEBUG='0',CARGO_PROFILE_TEST_DEBUG='0',CARGO_TERM_COLOR='never',RUST_TEST_THREADS='1',RUSTUP_TOOLCHAIN='1.99.0')
 record=dict(status='running',sourceRevision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),commands=[],cases={},filesDeleted=0,policyChanged=False,productionActivation=False,registryPublication=False,performanceAccepted=False,completeDependencyClosure=False,applicationRecompiled=False,maximumGrowthBytes=4000000000,maximumEvidenceBytes=320*1024**2)
 def save():write(out/'receipt.json',record)
 def capacity():
  disk=shutil.disk_usage(ROOT);growth=disk.used-baseline
  record['storageObservation']=dict(currentGrowthBytes=growth,peakGrowthBytes=max(growth,record.get('storageObservation',{}).get('peakGrowthBytes',0)),freeBytes=disk.free)
  assert disk.free>=500000000 and growth<=4000000000,'INSTALLED_RUST_STORAGE_BOUNDARY'
  assert time.monotonic()-began<3300,'INSTALLED_RUST_TOTAL_DEADLINE'
 def run(label,argv,cwd=None,expected=0,timeout=1200):
  capacity();start=time.monotonic()
  with (work/'private-logs'/(label+'.stdout')).open('xb') as stdout,(work/'private-logs'/(label+'.stderr')).open('xb') as stderr:
   child=subprocess.Popen([sys.executable,'-B',str(ROOT/'scripts/project_watch.py'),'__guard',*map(str,argv)],cwd=cwd or work,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
   try:
    while child.poll() is None:
     capacity();assert time.monotonic()-start<timeout,'INSTALLED_RUST_CHILD_DEADLINE'
     assert max(stdout.tell(),stderr.tell())<=8*1024**2,'INSTALLED_RUST_CHILD_LOG_BOUND'
     time.sleep(.5)
    code=child.returncode
   finally:stop(child)
  capacity();row=dict(label=label,exitCode=code,expectedExitCode=expected,elapsedMs=round((time.monotonic()-start)*1000))
  record['commands'].append(row);save();print(json.dumps(row),flush=True)
  assert code==expected,'INSTALLED_RUST_CHILD_FAILED'
  return (work/'private-logs'/(label+'.stdout')).read_text()
 checkout_cli=ROOT/'target/x86_64-unknown-linux-gnu/debug/patamaps'
 checkout_driver=ROOT/'scripts/qualify_miniserve_linux.py'
 cli_backup=work/'checkout-cli.unavailable';driver_backup=work/'checkout-driver.unavailable'
 source_output=work/'installed-source-build-output.retained'
 try:
  run('checkout-cli-for-package',['cargo','+1.99.0','build','--locked','--target','x86_64-unknown-linux-gnu','-p','patamaps-cli','--bin','patamaps'],cwd=ROOT)
  engine=json.loads(run('package-engine',[checkout_cli,'engine']))
  package=out/'package'
  run('package-current-exact-pair',[sys.executable,'-B',ROOT/'scripts/package.py','--binary',checkout_cli,'--build-profile','development','--output',package],cwd=ROOT,timeout=300)
  distribution=json.loads((package/'distribution.json').read_bytes())
  assert distribution['engines']==engine and distribution['binaryDigest']==sha(checkout_cli) and distribution['target']=='x86_64-unknown-linux-gnu'
  for name in ['sourceArchive','nativeArchive']:assert sha(package/distribution[name]['path'])==distribution[name]['digest']
  source=install_archive(package/distribution['sourceArchive']['path'],work/'source-installation',work)
  native=install_archive(package/distribution['nativeArchive']['path'],work/'native-installation',work)
  binding=distribution['sourceInventoryDigest'];identity=verify_installed_source(source,binding)
  assert not (source/'.git').exists()
  tracked=set(subprocess.check_output(['git','ls-files','-z'],cwd=ROOT,text=True).split('\0'))
  for entry in json.loads((source/'source-inventory.json').read_bytes()):
   assert entry['path'] in tracked and sha(ROOT/entry['path'])==entry['digest'],'INSTALLED_RUST_SOURCE_GIT_BYTES'
  native_cli=native/'bin/patamaps';assert sha(native_cli)==distribution['binaryDigest'] and os.access(native_cli,os.X_OK)
  checkout_cli.rename(cli_backup)
  env['CARGO_TARGET_DIR']=str(ROOT/'target')
  run('source-locked-fetch',['cargo','+1.99.0','fetch','--locked','--target','x86_64-unknown-linux-gnu'],cwd=source,timeout=300)
  prefix=work/'source-cli-installation'
  run('fresh-source-cargo-install',['cargo','+1.99.0','install','--path',source/'crates/patamaps-cli','--locked','--offline','--debug','--target','x86_64-unknown-linux-gnu','--root',prefix],cwd=source)
  compile_log=(work/'private-logs/fresh-source-cargo-install.stderr').read_text()
  for name in ['patamaps-cli','patamaps-workspace']:
   assert any('Compiling '+name+' v' in line and '('+str(source/'crates'/name)+')' in line for line in compile_log.splitlines()),'INSTALLED_RUST_SOURCE_COMPILATION_REQUIRED'
  source_cli=prefix/'bin/patamaps';assert sha(checkout_cli)==sha(source_cli)
  checkout_cli.rename(source_output);checkout_driver.rename(driver_backup)
  assert verify_installed_source(source,binding)==identity
  for label,compiler in [('native',native_cli),('source',source_cli)]:
   assert not checkout_cli.exists() and not checkout_driver.exists() and not (ROOT/'target/debug/patamaps').exists() and not (ROOT/'target/release/patamaps').exists()
   assert json.loads(run(label+'-installed-engine',[compiler,'engine']))==engine
   case_work,case_out=work/(label+'-owner'),out/label
   run(label+'-installed-owner-build',[sys.executable,'-B',source/'scripts/qualify_miniserve_linux.py','--cli',compiler,'--registry-context','--installed-inventory-digest',binding,'--work',case_work,'--evidence',case_out],timeout=2400)
   result=json.loads((case_out/'receipt.json').read_bytes());execution=json.loads((case_out/'registry/execution.json').read_bytes())
   record['cases'][label]=case_result(result,execution,identity,engine,sha(compiler))
   assert verify_installed_source(source,binding)==identity
   save()
  assert record['cases']['native']['upstreamCommit']==record['cases']['source']['upstreamCommit']
  assert record['cases']['native']['sourceFiles']==record['cases']['source']['sourceFiles']==60
  original=source/'docs/guides/rust-project-quickstart.md';backup=work/'installed-guide.original-retained'
  original.rename(backup);original.write_text('controlled installed source mutation\n')
  marker=work/'forbidden.marker';sentinel=work/'sentinel-compiler.sh'
  sentinel.write_text('#!/bin/sh\nprintf invoked > '+shlex.quote(str(marker))+'\nexit 91\n');sentinel.chmod(0o700)
  try:
   run('changed-source-before-compiler',[sys.executable,'-B',source/'scripts/qualify_miniserve_linux.py','--cli',sentinel,'--registry-context','--installed-inventory-digest',binding,'--work',work/'refused-owner','--evidence',out/'refused-owner'],expected=1,timeout=30)
   assert not marker.exists() and not (work/'refused-owner').exists() and not (out/'refused-owner').exists()
   assert 'INSTALLED_SOURCE_BYTES_CHANGED' in (work/'private-logs/changed-source-before-compiler.stderr').read_text()
  finally:
   original.rename(work/'installed-guide.changed-retained');backup.rename(original)
  assert verify_installed_source(source,binding)==identity and sha(native_cli)==distribution['binaryDigest']
  record.update(status='passed-installed-rust-owner-builds',applicationRecompiled=True,sourceIdentity=identity,distribution=distribution,sourceFilesMatchedProducingGit=True,checkoutCompilerAndDriverUnavailableDuringOwners=True,freshSourceCompilerBuiltFromInstalledPaths=True,sharedCargoDependencyArtifacts=True,changedSourceRefusedBeforeCompilerMarker=True,restoredSourceInventoryVerified=True,allOwnedContainersStopped=True)
 except BaseException as error:
  record.update(status='failed',errorClass=type(error).__name__);save();raise
 finally:
  if cli_backup.exists():
   if checkout_cli.exists():
    assert not source_output.exists()
    checkout_cli.rename(source_output)
   cli_backup.rename(checkout_cli)
   assert sha(checkout_cli)==distribution['binaryDigest'],'INSTALLED_RUST_CHECKOUT_RESTORATION'
   record['checkoutCompilerBytesRestored']=True
  if driver_backup.exists():
   assert not checkout_driver.exists();driver_backup.rename(checkout_driver);record['checkoutQualifierRestored']=True
  save()
 total=0
 for path in out.rglob('*'):
  assert not path.is_symlink(),'INSTALLED_RUST_EVIDENCE_SYMLINK'
  if path.is_file():total+=path.stat().st_size
 assert total<=320*1024**2,'INSTALLED_RUST_EVIDENCE_BOUND'
 record['evidenceBytesBeforeFinalReceipt']=total;save()
 print(json.dumps(dict(status=record['status'],cases=list(record['cases']),applicationRecompiled=True)),flush=True)

if __name__=='__main__':main()
