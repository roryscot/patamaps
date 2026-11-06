from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,time
ROOT=Path('/Volumes/dev_src_case_sensitive/projects/patamaps')
BASE=Path(__file__).resolve().parent
NODE=Path('/Users/admin/.nvm/versions/node/v22.23.3/bin/node')
GUARD=Path('/Users/admin/Documents/Codex/storage-safeguards/engine/scripts/guarded-run.mjs')
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
assert os.environ.get('WARGAME_STORAGE_RUN_TOKEN')
approval=json.loads((BASE/'APPROVAL.json').read_text())
assert digest(BASE/'scope.json')=='04efebca091cc974b5e6907ac58355aa6ced093a926f5d344cf76297b80c0644'
assert approval.get('approved')is True and approval.get('scopeSha256')=='04efebca091cc974b5e6907ac58355aa6ced093a926f5d344cf76297b80c0644'
assert digest(ROOT/'scripts/test_native_inspection_registration.mjs')=='aa90afabf646bca0f841bba258d562458ea6916ef1f97de2e89bf39add7245ce'
assert digest(ROOT/'scripts/native_inspection_registration.mjs')=='df5867deb62f21337538e8e1fba88097748ce00c3753fbb8c39272c782d35b3d'

assert digest(GUARD)=='3bfb9aeb901e02419a156538ddf78b09b134844e4bea1efe73235d6d4d7ed6b0'
names=['scripts/native_inspection_registration.mjs','scripts/native_registered_controller.py','scripts/test_native_inspection_registration.mjs','scripts/native_inspection_receiver.mjs','scripts/native_inspection_guard.py','scripts/native_inspection.py','scripts/project_watch.py']
saved=BASE/'source';saved.mkdir(mode=0o700);bindings={}
for name in names:
 p=ROOT/name;shutil.copy2(p,saved/p.name);bindings[name]=digest(p)
fixtures=BASE/'fixtures';fixtures.mkdir(mode=0o700)
origin=ROOT/'.tools/installed-original-owner-next-20261027/owner-native'
package=json.loads((ROOT/'.tools/installed-watch-policy-20261028/receipt.json').read_text())
state=Path(json.loads((origin/'receipt.json').read_text())['state'])
selected=json.loads((state/'selected.json').read_text())
prior=json.loads((ROOT/'.tools/native-live-ownership-20261028/real-unchanged/receipt.json').read_text())
inputs=dict(plan=str(origin/'plan.json'),source=str(origin/'owner'),context=str(origin/'binding.json'),preparation=str(origin/'preparation.json'),state=str(state))
supplied=dict(archive=str(ROOT/'.tools/intel-python-3.13.16-20261013/cpython-3.13.16+20261013-x86_64-apple-darwin-install_only_stripped.tar.gz'),native=str(Path(package['installedNative'])/'bin/patamaps'),inputs=inputs,protectedFiles=list(prior['statePreimages']),expectedState=prior['statePreimages'],engine=package['engine'],inputKey=selected['inputKey'])
assert {p:digest(p)for p in supplied['protectedFiles']}==supplied['expectedState']
spec=BASE/'inputs.json';spec.write_text(json.dumps(supplied,indent=2)+'\n')
env={**os.environ,'PATAMAPS_TEST_RETAIN_ROOT':str(fixtures),'PATAMAPS_REGISTERED_INPUTS':str(spec)}
(BASE/'live.json').write_text(json.dumps(dict(pid=os.getpid(),parentPid=os.getppid(),phase='tests',startedAt=time.time())))
with (BASE/'tests.stdout').open('xb')as out,(BASE/'tests.stderr').open('xb')as err:
 result=subprocess.run([str(NODE),'--test','--test-concurrency=1','--test-name-pattern=pinned archive builds complete|actual accepted CLI through closed registered unchanged-build',str(ROOT/'scripts/test_native_inspection_registration.mjs')],cwd=ROOT,env=env,stdout=out,stderr=err,timeout=1200)
unchanged=all(digest(ROOT/name)==sha for name,sha in bindings.items())
value=dict(status='passed' if result.returncode==0 and unchanged else 'failed',testExitCode=result.returncode,sourceBindings=bindings,sourcesUnchanged=unchanged,installedGuardUnchanged=digest(GUARD)=='3bfb9aeb901e02419a156538ddf78b09b134844e4bea1efe73235d6d4d7ed6b0',protectedStateUnchanged={p:digest(p)for p in supplied['protectedFiles']}==supplied['expectedState'],automaticReleaseActivated=False,parallelActivated=False,actualOwnerCrashRetried=False)
(BASE/'result.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value),flush=True)
sys.exit(0 if value['status']=='passed' else 1)
