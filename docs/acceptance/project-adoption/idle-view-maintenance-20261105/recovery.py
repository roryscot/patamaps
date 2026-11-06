"""One reversible delegated-maintenance window; no deletion or forced stop."""
from pathlib import Path
import json,os,sys,stat,hashlib,subprocess,plistlib,time,signal,datetime,traceback
B=Path(__file__).resolve().parent;R=Path('/Volumes/dev_src_case_sensitive/projects/patamaps');D='/Applications/Docker.app/Contents/Resources/bin/docker';C=Path('/Users/admin/Documents/Codex/.storage-control/heavy-builds')
read=lambda p:json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb')as f:return 'sha256:'+hashlib.file_digest(f,'sha256').hexdigest()
F=read(B/'frozen.json');assert all(sha(p)==h for p,h in F['inputs'].items())
DB=F['database']['id'];restoreOnly=sys.argv[1:]==['--restore-only']
report=read(B/'receipt.json')if restoreOnly else dict(status='preparing-delegated-nondeleting-maintenance',decisionAuthority='Latest owner delegated routine approvals and checks; no fabricated exact user approval.',startedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),commands=[],images=[],filesDeleted=0,imagesDeleted=0,containersDeleted=0,volumesDeleted=0,policyChanged=False,benchmarkRun=False,databaseStopAttempted=False,desktopStopAttempted=False)
def save():(B/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
def run(label,argv,timeout=90,check=True):
 report['phase']=label;save();print(json.dumps(dict(phase=label)),flush=True)
 prefix=f"{len(report['commands']):03d}-{label}"
 p=subprocess.run(argv,capture_output=True,timeout=timeout)
 for stream,value in [('stdout',p.stdout),('stderr',p.stderr)]:
  with(B/(prefix+'.'+stream)).open('xb')as out:os.fchmod(out.fileno(),0o600);out.write(value)
 row=dict(label=label,prefix=prefix,exitCode=p.returncode,stdoutDigest='sha256:'+hashlib.sha256(p.stdout).hexdigest(),stderrDigest='sha256:'+hashlib.sha256(p.stderr).hexdigest())
 report['commands'].append(row);save()
 if check:assert p.returncode==0,'NORMAL_MAINTENANCE_COMMAND_REFUSED:'+label
 return p
def inspect(cid):return json.loads(subprocess.check_output([D,'inspect',cid],text=True,timeout=15))[0]
def config(d):return dict(id=d['Id'],name=d['Name'],restartPolicy=d['HostConfig']['RestartPolicy'],ports=d['NetworkSettings']['Ports'],mounts=[{k:m.get(k)for k in ['Type','Name','Source','Destination','RW']}for m in d['Mounts']])
def database_query():
 sql="SELECT json_build_object('active_clients',(SELECT count(*) FROM pg_stat_activity WHERE pid<>pg_backend_pid() AND backend_type='client backend' AND state<>'idle'),'open_transactions',(SELECT count(*) FROM pg_stat_activity WHERE pid<>pg_backend_pid() AND xact_start IS NOT NULL),'replication_clients',(SELECT count(*) FROM pg_stat_replication),'cluster_id',(SELECT system_identifier::text FROM pg_control_system()));"
 cmd='export PGPASSWORD="$POSTGRES_PASSWORD"; exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "$1"'
 return json.loads(subprocess.check_output([D,'exec',DB,'sh','-c',cmd,'private-readiness',sql],text=True,timeout=20))
def attached(image):
 items=plistlib.loads(subprocess.check_output(['/usr/bin/hdiutil','info','-plist'],timeout=20)).get('images',[])
 matches=[x for x in items if x.get('image-path')==str(image)];assert len(matches)<=1
 return matches[0]if matches else None
def device(item,mount):
 entities=item['system-entities'];assert len([x for x in entities if x.get('mount-point')])==1 and any(x.get('mount-point')==str(mount)for x in entities)
 roots=[x['dev-entry']for x in entities if x.get('content-hint')=='GUID_partition_scheme'];assert len(roots)==1 and roots[0]!='/dev/disk2';return roots[0]
def identity(p):
 s=p.lstat();assert stat.S_ISREG(s.st_mode)and s.st_nlink==1
 return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mode=stat.S_IMODE(s.st_mode),uid=s.st_uid)
def inventory(root):
 rows={};cache={}
 def walk(p,rel,depth):
  assert depth<=128 and len(rows)<32768,'OWNED_VIEW_INVENTORY_LIMIT'
  before=p.lstat();kind='directory'if stat.S_ISDIR(before.st_mode)else'file'if stat.S_ISREG(before.st_mode)else'symlink'if stat.S_ISLNK(before.st_mode)else'special'
  row=dict(kind=kind,mode=stat.S_IMODE(before.st_mode),uid=before.st_uid,gid=before.st_gid,inode=before.st_ino,bytes=before.st_size,mtimeNs=before.st_mtime_ns)
  if kind=='file':
   assert not(p.name=='.env'or p.name.startswith('.env.')),'ENVIRONMENT_FILE_IN_VIEW_REFUSED'
   key=(before.st_dev,before.st_ino)
   if key not in cache:cache[key]=sha(p)
   row['digest']=cache[key]
  elif kind=='symlink':row['target']=os.readlink(p)
  else:assert kind=='directory','SPECIAL_MEMBER_REFUSED'
  rows[rel]=row
  if kind=='directory':
   for name in sorted(os.listdir(p)):walk(p/name,name if not rel else rel+'/'+name,depth+1)
  after=p.lstat();assert(before.st_dev,before.st_ino,before.st_mode,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_mode,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'VIEW_CHANGED_DURING_READ'
 walk(root,'',0);return rows
def restore():
 report['phase']='restoring-original-local-services';save()
 signal.signal(signal.SIGTERM,signal.SIG_IGN);signal.signal(signal.SIGINT,signal.SIG_IGN)
 p=subprocess.run([D,'info','--format','{{.ServerVersion}}'],capture_output=True,timeout=15)
 if p.returncode:run('restore-desktop-start',[D,'desktop','start','--timeout','90'],110)
 deadline=time.monotonic()+120
 while subprocess.run([D,'info','--format','{{.ServerVersion}}'],capture_output=True,timeout=15).returncode:
  assert time.monotonic()<deadline,'DOCKER_DAEMON_NOT_READY';time.sleep(2)
 if not inspect(DB)['State']['Running']:run('restore-same-database',[D,'start',DB],60)
 deadline=time.monotonic()+120
 while subprocess.run([D,'exec',DB,'pg_isready'],capture_output=True,timeout=15).returncode:
  assert time.monotonic()<deadline,'ORIGINAL_DATABASE_NOT_READY';time.sleep(2)
 assert config(inspect(DB))==F['database']['configuration'],'ORIGINAL_DATABASE_CONFIGURATION_CHANGED'
 now=database_query();assert now['cluster_id']==F['database']['clusterId'],'DATABASE_CLUSTER_ID_CHANGED'
 assert subprocess.check_output([D,'ps','-q','--no-trunc'],text=True,timeout=15).split()==[DB],'UNEXPECTED_RUNNING_CONTAINERS'
 report['serviceWindowReadyAtUtc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
 if report.get('serviceWindowStartedAtUtc'):report['stopRequestToVerifiedReadinessSeconds']=(datetime.datetime.fromisoformat(report['serviceWindowReadyAtUtc'])-datetime.datetime.fromisoformat(report['serviceWindowStartedAtUtc'])).total_seconds()
 report.update(databaseReady=True,dockerReady=True,originalDatabaseConfigurationPreserved=True,originalDatabaseClusterPreserved=True,restoredDatabaseStartedAt=inspect(DB)['State']['StartedAt']);save()
if restoreOnly:
 assert report.get('databaseStopAttempted')or report.get('desktopStopAttempted')
 restore();print('original-services-restored');raise SystemExit(0)
def interrupted(signum,frame):raise RuntimeError('MAINTENANCE_INTERRUPTED_'+str(signum))
for sig in [signal.SIGTERM,signal.SIGINT]:signal.signal(sig,interrupted)
owner=read(C/'active-run/owner.json');request=read(C/'scheduler/requests'/f"{owner['requestId']}.json")
assert owner['pid']==os.getppid()==int(os.environ['WARGAME_STORAGE_OWNER_PID'])and owner['token']==os.environ['WARGAME_STORAGE_RUN_TOKEN']and request['exclusive']and request['limits']['diskBytes']==1000000000
report['reservationId']=request['id'];failure=None;allVerified=False;save()
try:
 assert all(not any(Path(path).resolve(strict=True).is_relative_to(Path(item['mount']))for item in F['images'])for path in F['requiredApiPaths']),'API_DEPENDENCY_IN_CLOSING_VIEW'
 initial=inspect(DB);assert config(initial)==F['database']['configuration']and initial['State']['Running']and initial['Config'].get('StopSignal')=='SIGINT'
 assert subprocess.check_output([D,'ps','-q','--no-trunc'],text=True,timeout=15).split()==[DB]
 allids=subprocess.check_output([D,'ps','-aq','--no-trunc'],text=True,timeout=15).split();allcontainers=json.loads(subprocess.check_output([D,'inspect',*allids],text=True,timeout=20))
 assert all(x['HostConfig']['RestartPolicy']['Name']in['','no','unless-stopped']and not x['State']['Running']and not x['State']['Restarting']and not x['State']['Paused']for x in allcontainers if x['Id']!=DB),'OTHER_AUTOMATIC_RESTART_POLICY'
 plans=[]
 for item in F['images']:
  id=item['id'];r=read(C/'scheduler/requests'/(id+'.json'));assert r['state']=='finished'and r['ownershipSealed']and r['enforcement']=='container-fixed-volume'and r['releaseProof']['containerStopped']and r['releaseProof']['hostProcessGroupStopped']
  assert sha(C/'scheduler/requests'/(id+'.json'))==item['originalRequestDigest']
  for cid in r['containerIds']:
   d=inspect(cid);assert not d['State']['Running']and not d['State']['Restarting']and not d['State']['Paused']and d['State']['Pid']==0 and d['Config']['Labels']['buildctl.project']==str(R)and d['Config']['Labels']['buildctl.request']==id
  image=Path(item['image']);mount=Path(item['mount']);assert identity(image)==item['identity']and attached(image)['writeable']
  device(attached(image),mount);rows=inventory(mount);writepath=B/(id+'-before.json')
  with writepath.open('x')as out:os.fchmod(out.fileno(),0o600);json.dump(rows,out,sort_keys=True)
  plans.append((item,rows));print(json.dumps(dict(phase='owned-view-fingerprinted',id=id,entries=len(rows))),flush=True)
 activity=database_query();assert activity['cluster_id']==F['database']['clusterId']and activity['active_clients']==activity['open_transactions']==activity['replication_clients']==0,'LOCAL_DATABASE_IS_ACTIVE'
 report['quiescentDatabaseObservedImmediatelyBeforeStop']=True;report['databaseStopAttempted']=True;report['serviceWindowStartedAtUtc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
 run('stop-only-original-database',[D,'stop','--timeout=-1',DB],120);assert not inspect(DB)['State']['Running']
 report['desktopStopAttempted']=True;save();run('stop-desktop-normally',[D,'desktop','stop','--timeout','90'],110)
 for item,expected in plans:
  id=item['id'];image=Path(item['image']);mount=Path(item['mount']);assert identity(image)==item['identity']
  check=subprocess.run(['/usr/sbin/lsof','-nP','-Fpcfn','+D',str(mount)],capture_output=True,text=True,timeout=30)
  assert check.returncode==1 and not check.stdout.strip()and not check.stderr.strip(),'OWNED_VIEW_STILL_HAS_OPEN_HANDLES'
  run('detach-'+id,['/usr/bin/hdiutil','detach',device(attached(image),mount)],60);assert attached(image)is None and identity(image)==item['identity']
  closed=sha(image)
  run('readonly-restore-'+id,['/usr/bin/hdiutil','attach','-readonly','-nobrowse','-noautoopen','-mountpoint',str(mount),'-plist',str(image)],60)
  assert attached(image)['writeable']is False and os.statvfs(mount).f_flag&os.ST_RDONLY
  actual=inventory(mount)
  with(B/(id+'-readonly.json')).open('x')as out:os.fchmod(out.fileno(),0o600);json.dump(actual,out,sort_keys=True)
  assert actual==expected,'READONLY_GUEST_FILE_RECOVERY_MISMATCH'
  run('final-close-'+id,['/usr/bin/hdiutil','detach',device(attached(image),mount)],60)
  assert attached(image)is None and identity(image)==item['identity']and sha(image)==closed,'CLOSED_IMAGE_CHANGED'
  row=dict(id=id,image=str(image),mount=str(mount),closedImageDigest=closed,identity=item['identity'],entries=len(expected),files=sum(x['kind']=='file'for x in expected.values()),allGuestBytesModesOwnersInodesMtimesMatched=True,readonlyCycleImageBytesIdentical=True,normalFinalClosure=True,backingImagePreserved=True)
  report['images'].append(row);save()
 allVerified=True
except BaseException as error:
 failure=error;report.update(failureType=type(error).__name__,failureCode=str(error)if str(error).isupper()else'PRIVATE_DIAGNOSTIC_REQUIRED');(B/'failure.traceback').write_text(traceback.format_exc());save()
finally:
 if report.get('databaseStopAttempted')or report.get('desktopStopAttempted'):
  try:restore()
  except BaseException as error:
   failure=failure or error;report.update(restorationFailed=True,restorationFailureType=type(error).__name__);(B/'restoration-failure.traceback').write_text(traceback.format_exc());save()
   parent=int(os.environ.get('WARGAME_STORAGE_OWNER_PID','0'))
   if parent>1 and parent==os.getppid():os.kill(parent,signal.SIGTERM)
 report['status']='passed-delegated-nondeleting-maintenance'if allVerified and failure is None and report.get('databaseReady')else'failed-delegated-maintenance'
 report['finishedAtUtc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
print(json.dumps({k:report.get(k)for k in['status','databaseReady','originalDatabaseClusterPreserved','filesDeleted','failureCode']}))
if failure is not None:raise SystemExit(1)
