import hashlib,json,stat,sys,tarfile,zipfile
from pathlib import Path,PurePosixPath
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/parity'))
from storage_guard import ensure_guarded
from identity import identities
ensure_guarded()
run_id=38663333929
revision='66ec7a0b1b66b24a539c24a68e4947550f451423'
base=ROOT/'.tools/capabilities'/f'linux-ci-{run_id}'
work=base/'artifacts'
out=ROOT/'docs/acceptance/capabilities'/f'linux-ci-{run_id}'
out.mkdir(exist_ok=False)
(out/'driver.py').write_bytes(Path(__file__).read_bytes())
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return 'sha256:'+h.hexdigest()
state_path=ROOT/'.tools/intel-ci-38663333929/run.json'
artifact_path=ROOT/'.tools/intel-ci-38663333929/artifacts.json'
state=json.loads(state_path.read_text())
artifacts=json.loads(artifact_path.read_text())
assert state['headSha']==revision and state['status']=='completed' and state['conclusion']=='success'
assert len(state['jobs'])==2 and all(j['conclusion']=='success' for j in state['jobs'])
assert artifacts['total_count']==2
(out/'github-run.json').write_bytes(state_path.read_bytes())
(out/'github-artifacts.json').write_bytes(artifact_path.read_bytes())
expected={'schemaVersion':'0.1.0','documentType':'executor-description',**identities(ROOT)}
rows=[]
for item in artifacts['artifacts']:
 assert not item['expired']
 architecture='aarch64' if 'aarch64' in item['name'] else 'x86_64'
 assert item['name']==f'native-linux-{architecture}-{revision}'
 archive_path=work/(item['name']+'.zip')
 assert archive_path.stat().st_size==item['size_in_bytes']
 assert sha(archive_path)==item['digest'],'Downloaded artifact differs from GitHub digest'
 saved=work/item['name'];saved.mkdir()
 with zipfile.ZipFile(archive_path) as archive:
  seen=set()
  for member in archive.infolist():
   path=PurePosixPath(member.filename)
   assert not path.is_absolute() and '..' not in path.parts and member.filename not in seen
   seen.add(member.filename)
   assert member.file_size<128*1024*1024 and not stat.S_ISLNK(member.external_attr>>16)
   if member.is_dir():continue
   target=saved.joinpath(*path.parts);target.parent.mkdir(parents=True,exist_ok=True)
   with target.open('xb') as dest,archive.open(member) as stream:
    for block in iter(lambda:stream.read(1024*1024),b''):dest.write(block)
 receipt_path=saved/'receipt.json';record=json.loads(receipt_path.read_bytes())
 assert record['status']=='passed' and record['sourceRevision']==revision
 assert record['host']['architecture']==architecture and record['host']['effectiveUid']==0
 assert record['engines']==expected and record['sourceUnchanged'] is True
 assert [c['label'] for c in record['commands']]==['build-debug','rustfmt','clippy','native-debug','build-release','release-host']
 assert all(c['exitCode']==0 for c in record['commands'])
 for source in record['sourceInventory']:assert sha(ROOT/source['path'])==source['digest'],source['path']
 doc=out/item['name'];doc.mkdir()
 for file in saved.iterdir():
  if file.is_file() and file.name!='fixtures.tar.gz':(doc/file.name).write_bytes(file.read_bytes())
 for command in record['commands']:
  for stream in ['stdout','stderr']:assert sha(saved/command[stream]['path'])==command[stream]['digest']
 fixture_archive=saved/'fixtures.tar.gz'
 with tarfile.open(fixture_archive,'r:gz') as archive:
  members=archive.getmembers();assert members
  index=[{'name':m.name,'bytes':m.size,'type':m.type.decode('ascii'),'linkname':m.linkname} for m in members]
 (doc/'fixture-member-list.json').write_text(json.dumps(index,indent=2)+'\n')
 rows.append({'architecture':architecture,'receipt':(doc/'receipt.json').relative_to(ROOT).as_posix(),'receiptDigest':sha(receipt_path),'engines':expected,'binaries':record['binaries'],'commands':[c['label'] for c in record['commands']],'sourceInventoryEntriesMatched':len(record['sourceInventory']),'artifactZip':archive_path.relative_to(ROOT).as_posix(),'artifactZipDigest':sha(archive_path),'archive':fixture_archive.relative_to(ROOT).as_posix(),'archiveDigest':sha(fixture_archive),'archiveMembers':len(members)})
 print(json.dumps({'retained':architecture,'sourceInputsMatched':len(record['sourceInventory']),'fixtureMembers':len(members)}),flush=True)
report={'status':'actual-two-architecture-acceptance-passed-retained','recordedAtUtc':datetime.now(timezone.utc).isoformat(),'sourceRevision':revision,'run':state['url'],'architectures':rows,'scope':'Six actual Linux stages per architecture, including full native workspace, fixed UID/locking/current-trust/concurrency/crash/lifecycle controls and debug/release production binaries. Complete source inventories and artifact/log digests matched.','transfer':'Authenticated Rory gh CLI on original Mac streamed public ZIP bytes directly to supervised Intel receiver; no credentials or ARM disk downloads. Intel uses captured public API metadata.','recoveryVerification':'Complete ZIP and retained gzip/tar bytes verified; fixture members listed without extraction. Restoration and production activation unrun.','deleted':[]}
(out/'local-retention.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'status':'passed','receipt':str(out.relative_to(ROOT))+'/local-retention.json'}),flush=True)

