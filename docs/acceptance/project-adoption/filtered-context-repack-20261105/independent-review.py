from pathlib import Path
import json,hashlib,stat,subprocess,re,sys,posixpath,datetime,os
R=Path('/Volumes/dev_src_case_sensitive/projects/patamaps');B=R/'.tools/owner-auth-endpoint-20261029/reachable-context-repack-20261105';C=Path('/Users/admin/Documents/Codex/.storage-control/heavy-builds')
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb')as f:return 'sha256:'+hashlib.file_digest(f,'sha256').hexdigest()
F=read(B/'frozen.json');assert all(sha(p)==h for p,h in F['inputs'].items())
r=read(B/'receipt.json');assert r['status']=='passed-existing-format-context-repack'and r['elapsedSeconds']<=1200 and read(B/'supervisor-exit.json')['exitCode']==0
assert len(r['fixtureControls'])==3 and r['filesDeleted']==r['applicationTestsRun']==0 and not r['completeBuildContextEstablished']and not r['actualAuthenticationAccepted']
commands={row['role']:row for row in r['commands']}
assert len(commands)==len(r['commands'])
for role,row in commands.items():
 assert (row['exitCode']==0)==(role!='fixture-corrupt-digest-refusal')
 for stream in ['stdout','stderr']:assert sha(B/(role+'.'+stream))==row[stream+'Digest']
assert b'PROJECT_CONTEXT'in(B/'fixture-corrupt-digest-refusal.stderr').read_bytes()
assert read(B/'original-context-verify.stdout')['status']=='verified-project-context'
staged=B/'fixture-staged'
assert(staged/'tool.bin').read_bytes()==bytes(range(256))*64 and stat.S_IMODE((staged/'tool.bin').stat().st_mode)==0o751
assert(staged/'empty').is_dir()and stat.S_IMODE((staged/'empty').stat().st_mode)==0o705 and(staged/'alias').is_symlink()and os.readlink(staged/'alias')=='tool.bin'
base=Path(F['baseSnapshot']);old=read(base/'manifest.json');snapshot=B/'snapshot';manifest=read(snapshot/'manifest.json');definition=read(B/'selection.json')
assert read(snapshot/'selection.json')==definition and manifest['entries']=={name:old['entries'][name]for name in definition['paths']}
assert manifest['digest']==r['contextDigest']==read(B/'actual-repacked-context-verify.stdout')['digest']
assert manifest['definitionDigest']==read(B/'actual-definition-digest.stdout')and manifest['digest']==read(B/'actual-manifest-digest.stdout')
entries=manifest['entries'];counts={};fileBytes=0
for name,row in entries.items():
 assert not Path(name).is_absolute()and '..'not in Path(name).parts
 p=snapshot/'data'/name;kind=row['kind'];counts[kind]=counts.get(kind,0)+1
 if kind=='symlink':
  try:p.lstat()
  except FileNotFoundError:pass
  else:raise AssertionError('VIRTUAL_LINK_MUST_NOT_BE_DATA_OBJECT')
 else:
  s=p.lstat();assert not p.is_symlink()
  if kind=='file':
   assert stat.S_ISREG(s.st_mode)and stat.S_IMODE(s.st_mode)==0o600 and s.st_size==row['byteLength']and sha(p)==row['digest'];fileBytes+=s.st_size
  else:assert kind=='directory'and stat.S_ISDIR(s.st_mode)and stat.S_IMODE(s.st_mode)==0o700
assert counts==dict(file=74842,directory=8752,symlink=4)and len(entries)==83598 and fileBytes==903619812
def resolve(name):
 done=[];todo=name.split('/');links=0
 while todo:
  part=todo.pop(0)
  if part in['','.']:continue
  if part=='..':assert done;done.pop();continue
  path='/'.join(done+[part]);row=entries.get(path)
  if row is None:return None
  if row['kind']=='symlink':links+=1;assert links<128;todo=row['target'].split('/')+todo
  else:done.append(part)
 return '/'.join(done)
def locate(name,where):
 cur=where
 while True:
  if cur.split('/')[-1]!='node_modules':
   candidate=(cur+'/'if cur else'')+'node_modules/'+name;real=resolve(candidate)
   if real and real+'/package.json'in entries:return real,candidate
  if not cur:return None
  cur=posixpath.dirname(cur)
graph=read(B/'package-resolution.json');assert len(graph['edges'])==4025
for edge in graph['edges']:assert locate(edge['name'],edge['fromDirectory'])==(edge['resolvedPackage'],edge['lookupPath'])
oldBuild=read(R/'.tools/owner-auth-endpoint-20261029/build-websocket-fourgb-20261105/receipt.json');priorFiles=0
for root,expected in oldBuild['previousStates'].items():
 root=Path(root);selected=read(root/'selected.json');attempt=root/selected['attempt']
 assert sha(root/'selected.json')==expected['pointer']and sha(attempt/'artifacts.json')==expected['manifest']
 for n,row in read(attempt/'artifacts.json').items():
  p=attempt/'candidate'/n;s=p.lstat();assert not p.is_symlink()and stat.S_IMODE(s.st_mode)==row['mode']
  if row['kind']=='file':assert s.st_size==row['bytes']and sha(p)==row['digest'];priorFiles+=1
  else:assert row['kind']=='directory'and stat.S_ISDIR(s.st_mode)
assert priorFiles==7446
stream=(B/'supervisor.stdout').read_text()+(B/'supervisor.stderr').read_text();ids=re.findall(re.escape(str(C))+'/runs/([0-9a-f-]{36})/run.json',stream);assert len(ids)==1
guard=read(C/'runs'/ids[0]/'run.json');request=read(C/'scheduler/requests'/f"{r['reservationId']}.json")
assert guard['completed']and guard['exitCode']==0 and guard['filesDeleted']==0 and guard['freeBytesAtStart']-guard['minimumFreeBytesObserved']<=2000000000
assert request['state']=='finished'and request['leaseReleaseCompleted']and request['enforcement']=='native-exclusive'and request['limits']['diskBytes']==2000000000
sys.path.insert(0,str(R/'scripts'));import native_inspection_guard as kernel
for pid in [request['owner']['pid'],request['processGroup']]:assert kernel.process_identity(pid)is None and not kernel.group_live(pid)
db=json.loads(subprocess.check_output(['/Applications/Docker.app/Contents/Resources/bin/docker','inspect',F['protectedDatabase']['id']],text=True,timeout=15))[0]
assert dict(id=db['Id'],running=db['State']['Running'],startedAt=db['State']['StartedAt'],restartCount=db['RestartCount'])==F['protectedDatabase']
out=dict(status='independently-accepted-existing-format-filtered-context-repack',sourceRevision=F['sourceRevision'],nativeCliDigest=sha(F['cli']),allFrozenInputsRehashed=len(F['inputs']),originalFullContextNativelyVerified=True,originalSourceStorageFormatRestored=True,mainSelectedEntries=83598,mainCounts=counts,all74842PayloadFilesIndependentlyRehashed=True,logicalFileBytes=fileBytes,originalModesAndVirtualLinksExactlyRetainedInManifest=True,sealedStorage0600Files0700DirectoriesReverified=True,all4025BaselineManifestResolutionsIndependentlyRechecked=True,fixtureNativeProducerReaderStagerPassed=True,fixtureOriginalExecutableAndEmptyDirectoryModesPassed=True,fixtureSpecificCorruptDigestRefusalPassed=True,priorSelectedArtifactFilesRehashed=7446,contextDigest=manifest['digest'],canonicalReservation=r['reservationId'],canonicalReservationReleased=True,maximumJobGrowthBytes=2000000000,observedConservativeGrowthBytes=max(0,guard['freeBytesAtStart']-guard['minimumFreeBytesObserved']),allObservedOwnedGroupsStopped=True,unrelatedDatabaseStartIdentityUnchanged=True,filesDeleted=0,applicationTestsRun=0,authenticationAccepted=False,completeBuildContextEstablished=False,fullGoalComplete=False,reviewerDigest=sha(__file__),frozenManifestDigest=sha(B/'frozen.json'),reviewedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat())
with(B/'independent-review.json').open('x')as f:json.dump(out,f,indent=2);f.write('\n')
print(json.dumps(out))
