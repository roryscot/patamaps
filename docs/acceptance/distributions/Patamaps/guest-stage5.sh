#!/bin/bash
set -euo pipefail
unset HOME SDKROOT
export RUSTUP_HOME=/usr/local/rustup CARGO_HOME=/usr/local/cargo
export RUSTUP_TOOLCHAIN=1.99.0-aarch64-unknown-linux-gnu
export PATH=/opt/bindloom-python/bin:/usr/local/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 CARGO_TERM_COLOR=never
mkdir -p /output /results/Patamaps
mount -t virtiofs bindloom-results /output
trap 'status=$?; cp -R /results/Patamaps /output/; exit "$status"' EXIT
cp /share/guest-stage5.sh /results/Patamaps/guest-stage5.sh
python3 - <<'PY'
import hashlib,json,pathlib,tarfile
p=pathlib.Path('/share/patamaps-source.tar.gz')
j=json.loads(pathlib.Path('/share/patamaps-source.json').read_text())
assert 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()==j['sourceArchive']['digest']
r=pathlib.Path('/patamaps-rename-source');r.mkdir()
with tarfile.open(p) as t:t.extractall(r,filter='data')
s=next(r.glob('patamaps-draft-*'))
assert 'sha256:'+hashlib.sha256((s/'source-inventory.json').read_bytes()).hexdigest()==j['sourceInventoryDigest']
for e in json.loads((s/'source-inventory.json').read_text()):
 b=(s/e['path']).read_bytes()
 assert len(b)==e['bytes'] and 'sha256:'+hashlib.sha256(b).hexdigest()==e['digest']
pathlib.Path('/results/Patamaps/tested-source.json').write_text(json.dumps(j,indent=2)+'\n')
print('PATAMAPS_INPUT_VERIFIED',j['sourceInventoryDigest'])
PY
cd /patamaps-rename-source/patamaps-draft-f5e64903ab9a
export CARGO_TARGET_DIR=/source/target
python3 - <<'PY'
import datetime,hashlib,json,os,pathlib,re,subprocess
out=pathlib.Path('/results/Patamaps');cargo=pathlib.Path('/usr/local/cargo/bin/cargo')
commands=[['fmt','--all','--','--check'],['build','--workspace','--locked','--offline'],['clippy','--workspace','--all-targets','--locked','--offline','--','-D','warnings'],['test','--workspace','--locked','--offline','--','--test-threads=1'],['build','--release','--workspace','--locked','--offline']]
env={**os.environ,'PATAMAPS_TEST_COMPILER_BINARY':'/source/target/debug/patamaps','PATAMAPS_TEST_ACTIVATOR_BINARY':'/source/target/debug/patamaps-activator'}
records=[]
for argv in commands:
 print('RUN',str(cargo),' '.join(argv),flush=True)
 p=subprocess.run([str(cargo),*argv],env=env,capture_output=True,text=True)
 records.append({'argv':[str(cargo),*argv],'exitCode':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
 (out/'native-linux-commands.json').write_text(json.dumps(records,indent=2)+'\n')
 print(p.stdout,p.stderr,flush=True)
 assert p.returncode==0
stdout=records[3]['stdout'];total=sum(int(x) for x in re.findall(r'test result: ok\. (\d+) passed;',stdout));docs=len(re.findall(r'- compile fail .* ok',stdout));assert total==123 and docs==13,(total,docs)
engine=json.loads(subprocess.check_output(['/source/target/release/patamaps','engine']))
source=json.loads((out/'tested-source.json').read_text())['sourceArchive']
log=out/'native-linux.log';log.write_text(stdout+'\nSTDERR\n'+records[3]['stderr'])
receipt={'verifiedAtUtc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'passed','nativeTests':total-docs,'compileFailDocumentationTests':docs,'linuxTestFunctions':10,'engine':engine,'commands':records,'sourceArchive':source,'platform':'aarch64-unknown-linux-gnu','filesystem':'Private ext4 raw disk, ordered data mode','rawConsole':log.name,'rawConsoleDigest':'sha256:'+hashlib.sha256(log.read_bytes()).hexdigest(),'features':'default'}
(out/'native-linux.json').write_text(json.dumps(receipt,indent=2)+'\n')
env.update(PATAMAPS_TEST_COMPILER_BINARY='/source/target/release/patamaps',PATAMAPS_TEST_ACTIVATOR_BINARY='/source/target/release/patamaps-activator')
argv=[str(cargo),'test','-p','patamaps-activator','--lib','--locked','--offline','--','--test-threads=1']
p=subprocess.run(argv,env=env,capture_output=True,text=True);print(p.stdout,p.stderr,flush=True)
log=out/'release-linux.log';log.write_text(p.stdout+'\nSTDERR\n'+p.stderr)
assert p.returncode==0 and 'test result: ok. 10 passed;' in p.stdout
release={'status':'passed','argv':argv,'exitCode':p.returncode,'linuxTestFunctions':10,'compilerBinaryDigest':'sha256:'+hashlib.sha256(pathlib.Path('/source/target/release/patamaps').read_bytes()).hexdigest(),'activatorBinaryDigest':'sha256:'+hashlib.sha256(pathlib.Path('/source/target/release/patamaps-activator').read_bytes()).hexdigest(),'rawConsole':log.name,'rawConsoleDigest':'sha256:'+hashlib.sha256(log.read_bytes()).hexdigest(),'buildProfile':'release'}
(out/'release-linux.json').write_text(json.dumps(release,indent=2)+'\n')
print('PATAMAPS_LINUX_NATIVE_PASS',flush=True)
PY
unset CARGO_TARGET_DIR
python3 scripts/package.py --binary /source/target/release/patamaps --activator-binary /source/target/release/patamaps-activator --build-profile release --output /results/Patamaps/Linux
python3 scripts/test_distribution.py /results/Patamaps/Linux --node /usr/local/node/bin/node --tsc /reference/node_modules/typescript/lib/tsc.js --reference /reference --output /results/Patamaps/Linux/installation.json
printf 'PATAMAPS_LINUX_STAGE5_PASS\n'
