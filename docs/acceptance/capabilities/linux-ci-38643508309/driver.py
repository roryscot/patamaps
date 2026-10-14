import hashlib,json,subprocess,sys,tarfile,zipfile
from pathlib import Path,PurePosixPath
from datetime import datetime,timezone
root=Path('/Users/admin/dev/patamaps/patamaps');sys.path.insert(0,str(root/'scripts/parity'))
from storage_guard import ensure_guarded
from identity import identities
ensure_guarded()
gh='/opt/homebrew/bin/gh';run_id=38643508309;revision='0fe527e97c6973c6fdb68e2f0f7d05f1de4ebea8'
work=root/'.tools/capabilities'/f'linux-ci-{run_id}';work.mkdir(exist_ok=False)
out=root/'docs/acceptance/capabilities'/f'linux-ci-{run_id}';out.mkdir(exist_ok=False)
(out/'driver.py').write_bytes(Path(__file__).read_bytes())
def file_digest(path):
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
 return 'sha256:'+h.hexdigest()
state=json.loads(subprocess.check_output([gh,'run','view',str(run_id),'--repo','roryscot/patamaps','--json','status,conclusion,headSha,url,jobs']))
assert state['headSha']==revision and state['status']=='completed' and state['conclusion']=='success'
artifacts=json.loads(subprocess.check_output([gh,'api',f'repos/roryscot/patamaps/actions/runs/{run_id}/artifacts']))
assert artifacts['total_count']==2
(out/'github-run.json').write_text(json.dumps(state,indent=2)+'\n')
(out/'github-artifacts.json').write_text(json.dumps(artifacts,indent=2)+'\n')
expected={'schemaVersion':'0.1.0','documentType':'executor-description',**identities(root)}
rows=[]
for item in artifacts['artifacts']:
 assert not item['expired']
 architecture='aarch64' if 'aarch64' in item['name'] else 'x86_64'
 assert item['name']==f'native-linux-{architecture}-{revision}'
 archive_path=work/(item['name']+'.zip')
 with archive_path.open('xb') as stdout,(out/(architecture+'.download.stderr.log')).open('wb') as stderr:
  result=subprocess.run([gh,'api',f"repos/roryscot/patamaps/actions/artifacts/{item['id']}/zip"],stdout=stdout,stderr=stderr)
 assert result.returncode==0
 assert file_digest(archive_path)==item['digest'],'Downloaded artifact differs from GitHub digest'
 saved=work/item['name'];saved.mkdir()
 with zipfile.ZipFile(archive_path) as archive:
  for member in archive.infolist():
   path=PurePosixPath(member.filename)
   assert not path.is_absolute() and '..' not in path.parts
   assert member.file_size<128*1024*1024
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
 for source in record['sourceInventory']:assert file_digest(root/source['path'])==source['digest'],source['path']
 doc=out/item['name'];doc.mkdir()
 for file in saved.iterdir():
  if file.is_file() and file.name!='fixtures.tar.gz':(doc/file.name).write_bytes(file.read_bytes())
 for command in record['commands']:
  for stream in ['stdout','stderr']:assert file_digest(saved/command[stream]['path'])==command[stream]['digest']
 fixture_archive=saved/'fixtures.tar.gz'
 with tarfile.open(fixture_archive,'r:gz') as archive:
  members=archive.getmembers();assert members
  index=[{'name':m.name,'bytes':m.size,'type':m.type.decode('ascii'),'linkname':m.linkname} for m in members]
 (doc/'fixture-member-list.json').write_text(json.dumps(index,indent=2)+'\n')
 rows.append({'architecture':architecture,'receipt':(doc/'receipt.json').relative_to(root).as_posix(),'receiptDigest':file_digest(receipt_path),'engines':expected,'binaries':record['binaries'],'commands':[c['label'] for c in record['commands']],'sourceInventoryEntriesMatched':len(record['sourceInventory']),'artifactZip':archive_path.relative_to(root).as_posix(),'artifactZipDigest':file_digest(archive_path),'archive':fixture_archive.relative_to(root).as_posix(),'archiveDigest':file_digest(fixture_archive),'archiveMembers':len(members)})
 print(json.dumps({'retained':architecture,'sourceInputsMatched':len(record['sourceInventory']),'fixtureMembers':len(members)}),flush=True)
report={'status':'actual-two-architecture-acceptance-passed-retained','recordedAtUtc':datetime.now(timezone.utc).isoformat(),'sourceRevision':revision,'run':state['url'],'architectures':rows,'scope':'Six actual Linux stages per architecture: full native workspace, fixed UID/locking/current-trust/concurrency/crash/lifecycle controls and debug/release production binaries. Complete source inventories match current inputs and all artifact/log digests are verified.','recoveryVerification':'Complete downloaded ZIP and retained gzip/tar archives verified; members listed without extracting fixture material. Restoration and production activation unrun.','deleted':[]}
(out/'local-retention.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'status':'passed','receipt':str((out/'local-retention.json').relative_to(root))}),flush=True)
