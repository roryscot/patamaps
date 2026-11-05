from pathlib import Path
import os,sys,json,hashlib,stat,subprocess,time,signal,datetime
B=Path(__file__).resolve().parent;R=Path('/Volumes/dev_src_case_sensitive/projects/patamaps');C=Path('/Users/admin/Documents/Codex/.storage-control/heavy-builds')
read=lambda p:json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb')as f:return 'sha256:'+hashlib.file_digest(f,'sha256').hexdigest()
def write(p,value):
 with Path(p).open('x')as f:os.fchmod(f.fileno(),0o600);json.dump(value,f,ensure_ascii=False,sort_keys=True);f.write('\n')
F=read(B/'frozen.json');assert all(sha(p)==h for p,h in F['inputs'].items()),'REPACK_INPUT_CHANGED'
owner=read(C/'active-run/owner.json');req=read(C/'scheduler/requests'/f"{owner['requestId']}.json")
assert owner['pid']==os.getppid()==int(os.environ['WARGAME_STORAGE_OWNER_PID'])and owner['token']==os.environ['WARGAME_STORAGE_RUN_TOKEN']
assert req['state']=='running'and req['exclusive']and req['enforcement']=='native-exclusive'and req['limits']['diskBytes']==2000000000
CLI=F['cli'];began=time.monotonic();report=dict(status='running-existing-format-context-repack',reservationId=req['id'],sourceRevision=F['sourceRevision'],nativeCliDigest=sha(CLI),commands=[],fixtureControls=[],filesDeleted=0,applicationTestsRun=0,completeBuildContextEstablished=False,actualAuthenticationAccepted=False,policyChanged=False)
def save():
 (B/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
def interrupted(*_):raise RuntimeError('CONTEXT_REPACK_INTERRUPTED')
for sig in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]:signal.signal(sig,interrupted)
signal.alarm(1200)
def command(name,argv,timeout=30,inputBytes=None,success=True):
 report['phase']=name;save();before=time.monotonic()
 with(B/(name+'.stdout')).open('xb')as out,(B/(name+'.stderr')).open('xb')as err:
  p=subprocess.run(argv,input=inputBytes,stdout=out,stderr=err,timeout=timeout)
 row=dict(role=name,exitCode=p.returncode,elapsedSeconds=time.monotonic()-before,stdoutDigest=sha(B/(name+'.stdout')),stderrDigest=sha(B/(name+'.stderr')));report['commands'].append(row);save()
 assert (p.returncode==0)==success,'NATIVE_CONTEXT_OPERATION_UNEXPECTED_OUTCOME'
 return (B/(name+'.stdout')).read_bytes(),(B/(name+'.stderr')).read_bytes()
def digest(name,value):
 raw,_=command(name,[CLI,'json','digest'],30,json.dumps(value,ensure_ascii=False).encode())
 result=json.loads(raw);assert result.startswith('sha256:')and len(result)==71;return result
def open_source(rootfd,name):
 parts=name.split('/');assert parts and all(p not in['','.','..']for p in parts)
 parent=os.dup(rootfd)
 try:
  for part in parts[:-1]:
   new=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent);os.close(parent);parent=new
  return os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent)
 finally:os.close(parent)
def repack(source,definition,destination,label):
 assert not destination.exists()
 original=read(source/'manifest.json');entries={name:original['entries'][name]for name in definition['paths']}
 for name in entries:
  for i in range(1,len(name.split('/'))):assert entries['/'.join(name.split('/')[:i])]['kind']=='directory'
 destination.mkdir(mode=0o700);data=destination/'data';data.mkdir(mode=0o700);rootfd=os.open(source/'data',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 initial=os.fstat(rootfd);copied=0
 try:
  for name,row in sorted(entries.items(),key=lambda item:(len(item[0].split('/')),item[0])):
   p=data/name
   if row['kind']=='directory':p.mkdir(mode=0o700)
   elif row['kind']=='file':
    fd=open_source(rootfd,name);before=os.fstat(fd);assert stat.S_ISREG(before.st_mode)
    h=hashlib.sha256();total=0
    with os.fdopen(fd,'rb')as sourceFile,p.open('xb')as target:
     os.fchmod(target.fileno(),0o600)
     while chunk:=sourceFile.read(1048576):target.write(chunk);h.update(chunk);total+=len(chunk)
     after=os.fstat(sourceFile.fileno());assert(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)
    assert 'sha256:'+h.hexdigest()==row['digest']and total==row['byteLength'],'REPACK_SOURCE_BYTES_CHANGED'
    copied+=1
    if copied%5000==0:report.update(phase=label+'-copying-sealed-bytes',copiedFiles=copied);save();print(json.dumps(dict(phase=report['phase'],copiedFiles=copied)),flush=True)
   else:assert row['kind']=='symlink' # Virtual: no link object belongs in data/.
  visible=os.stat(source/'data',follow_symlinks=False);assert(initial.st_dev,initial.st_ino)==(visible.st_dev,visible.st_ino)
 finally:os.close(rootfd)
 unsigned=dict(profile='patamaps-project-context-1',definitionDigest=digest(label+'-definition-digest',definition),entries=entries)
 manifest={**unsigned,'digest':digest(label+'-manifest-digest',unsigned)}
 write(destination/'selection.json',definition);write(destination/'manifest.json',manifest)
 return manifest
save()
try:
 raw,_=command('original-context-verify',[CLI,'project-context-verify',F['baseSnapshot']],300);assert json.loads(raw)['status']=='verified-project-context'
 # Existing native producer/reader defines fixture truth, including virtual links and original modes.
 source=B/'fixture-source';source.mkdir(mode=0o700);payload=bytes(range(256))*64
 (source/'tool.bin').write_bytes(payload);(source/'tool.bin').chmod(0o751);(source/'empty').mkdir(mode=0o705);os.symlink('tool.bin',source/'alias')
 definition=dict(profile='patamaps-project-context-selection-1',id='urn:patamaps:context-repack:producer-fixture',nonsecretInputs=True,paths=['alias','empty','tool.bin'],symlinks='internal-closed')
 write(B/'fixture-selection.json',definition)
 command('fixture-native-capture',[CLI,'project-context-capture',str(B/'fixture-selection.json'),'--root',str(source),'--destination',str(B/'fixture-native')])
 assert not(B/'fixture-native/data/alias').exists()and not(B/'fixture-native/data/alias').is_symlink()
 assert stat.S_IMODE((B/'fixture-native/data/tool.bin').stat().st_mode)==0o600
 definition['id']='urn:patamaps:context-repack:consumer-fixture';m=repack(B/'fixture-native',definition,B/'fixture-repacked','fixture')
 command('fixture-repacked-verify',[CLI,'project-context-verify',str(B/'fixture-repacked')])
 command('fixture-repacked-stage',[CLI,'project-context-stage',str(B/'fixture-repacked'),'--destination',str(B/'fixture-staged')])
 staged=B/'fixture-staged'
 assert(staged/'tool.bin').read_bytes()==payload and stat.S_IMODE((staged/'tool.bin').stat().st_mode)==0o751 and stat.S_IMODE((staged/'empty').stat().st_mode)==0o705
 assert(staged/'alias').is_symlink()and os.readlink(staged/'alias')=='tool.bin'
 bad=B/'fixture-bad-digest';bad.mkdir();(bad/'data').mkdir();write(bad/'selection.json',definition);write(bad/'manifest.json',{**m,'digest':'sha256:'+'0'*64})
 _,err=command('fixture-corrupt-digest-refusal',[CLI,'project-context-verify',str(bad)],success=False)
 assert b'PROJECT_CONTEXT'in err,'WRONG_REFUSAL_REASON'
 report['fixtureControls']=['native-producer-virtual-link-and-storage-mode-established','repacked-native-consumer-preserves-original-bytes-executable-mode-empty-directory-and-link','corrupt-manifest-refused-before-payload'];save()
 definition=read(B/'selection.json');manifest=repack(Path(F['baseSnapshot']),definition,B/'snapshot','actual')
 assert len(manifest['entries'])==83598 and sum(row.get('byteLength',0)for row in manifest['entries'].values())==903619812
 raw,_=command('actual-repacked-context-verify',[CLI,'project-context-verify',str(B/'snapshot')],300)
 assert json.loads(raw)['status']=='verified-project-context'and json.loads(raw)['digest']==manifest['digest']
 assert all(sha(p)==h for p,h in F['inputs'].items()),'REPACK_INPUT_CHANGED_AFTER'
 d=json.loads(subprocess.check_output(['/Applications/Docker.app/Contents/Resources/bin/docker','inspect',F['protectedDatabase']['id']],text=True,timeout=15))[0]
 assert dict(id=d['Id'],running=d['State']['Running'],startedAt=d['State']['StartedAt'],restartCount=d['RestartCount'])==F['protectedDatabase']
 report.update(status='passed-existing-format-context-repack',snapshot=str(B/'snapshot'),contextDigest=manifest['digest'],entries=83598,logicalFileBytes=903619812,originalModesAndVirtualLinksRetainedInManifest=True,allSelectedEntriesExactlyMatchOriginalManifest=True,originalFullContextNativelyVerified=True,allFrozenInputsMatched=True,protectedDatabaseStartIdentityUnchanged=True)
except BaseException as error:
 report.update(status='failed-existing-format-context-repack',failureType=type(error).__name__,failureCode=str(error)if str(error).isupper()else'PRIVATE_DIAGNOSTIC_REQUIRED');raise
finally:
 signal.alarm(0);report.update(elapsedSeconds=time.monotonic()-began,finishedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat());save()
print(json.dumps({k:v for k,v in report.items()if k not in['commands']}))
