from pathlib import Path
import json,os,hashlib,subprocess,datetime,time
R=Path('/Volumes/dev_src_case_sensitive/projects/patamaps')
N=R/'.tools/native-registered-inspection-20261028/retry-proposal-1'
P=N/'ownership-change-recovery-20261104';B=P/'review-1';B.mkdir()
C=Path('/Users/admin/Documents/Codex/.storage-control/heavy-builds')
target=C/'scheduler/requests/df47f504-2503-45cc-9f44-f7f02d6bc2b8.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,j):
 with p.open('x')as out:json.dump(j,out,indent=2);out.write('\n')
def private(p,data):
 with p.open('xb')as out:os.fchmod(out.fileno(),0o600);out.write(data)
def process_table():
 data=subprocess.check_output(['/bin/ps','-axo','pid=,ppid=,pgid=,stat=,lstart=,comm='],text=True,timeout=15)
 rows={}
 for line in data.splitlines():
  f=line.split(None,9)
  if len(f)==10:
   rows[int(f[0])]=dict(pid=int(f[0]),parent=int(f[1]),group=int(f[2]),status=f[3],started=' '.join(f[4:9]),command=f[9])
 return data,rows
r=json.loads(target.read_text());assert sha(target)==sha(P/'request.original.json')
assert r['state']=='running'and r['ownershipSealed']and r['processGroup']==43292 and r['owner']['pid']==42989
assert not(C/'active-run').exists()
native=json.loads((N/'result.json').read_text());assert native['status']=='failed'and native['protectedStateUnchanged']and native['sourcesUnchanged']and native['installedGuardUnchanged']
for name,h in native['sourceBindings'].items():assert sha(R/name)==h
supplied=json.loads((N/'inputs.json').read_text())
for name,h in supplied['expectedState'].items():assert sha(name)==h
terminal=next((N/'fixtures').glob('registered-inspection-*/real-unchanged-build/supervisor-status.json'))
st=json.loads(terminal.read_text());assert st['channelClosed']and st['failure']is None and st['controllerOutcome']['code']==2
assert json.loads((terminal.parent/'abort-cleanup.json').read_text())==dict(knownGroupsStopped=True,controlClosed=True,automaticRecoveryPerformed=False)
pids={42989,43292,43295,st['controllerIdentity']['pid']};groups={43292,st['controllerIdentity']['pgid']}
for call in st['calls']:
 assert call['finished']and call['controlComplete']and call['terminalFlags']==dict(stdoutClosed=True,stderrClosed=True,bindingsUnchanged=True)
 assert call['declaredCleanup']['confirmed']
 pids.update([call['guardianPid'],call['nativePid']]);groups.update([call['guardianIdentity']['pgid'],call['nativeIdentity']['pgid']])
queued=[]
for path in ['.tools/owner-auth-endpoint-20261029/services-managed-volume-paths-20261104','.tools/retained-dynamic-next-20261028/preflight-symbols-20261104']:
 queued.append(json.loads((R/path/'supervisor.json').read_text())['pid'])
initial=set(json.loads((P/'open-file-classification-0.json').read_text())['unclassifiedProjectPids'])
system_names={
 '/System/Library/PrivateFrameworks/DiskImages.framework/Resources/diskimages-helper',
 '/System/Library/Frameworks/Virtualization.framework/Versions/A/XPCServices/com.apple.Virtualization.VirtualMachine.xpc/Contents/MacOS/com.apple.Virtualization.VirtualMachine'}
raw,table=process_table();old_system={}
request_epoch=datetime.datetime.fromisoformat(r['createdAt'].replace('Z','+00:00')).timestamp()
for pid in initial:
 assert pid in table,'Initially observed infrastructure identity disappeared; review it separately'
 row=table[pid]
 assert row['command']in system_names and row['parent']==1 and row['group']==pid
 epoch=datetime.datetime.strptime(row['started'],'%a %b %d %H:%M:%S %Y').astimezone().timestamp()
 assert epoch<request_epoch-3600
 old_system[pid]=row
signatures=[]
for name in sorted(system_names):
 verified=subprocess.run(['/usr/bin/codesign','--verify','--strict',name],capture_output=True,timeout=20)
 assert verified.returncode==0,'System executable signature verification failed'
 signatures.append(dict(path=name,sha256=sha(name),signatureVerified=True))
save(B/'preexisting-system-identities.json',dict(processes=list(old_system.values()),executables=signatures,classification='Known exact kernel identities predate request; source-bound job has no Docker/VM launch path. Not a global release rule.'))
baseline=json.loads((R/'.tools/owner-auth-endpoint-20261029/services-managed-volume-paths-20261104/protected-service-before.json').read_text())
docker='/Applications/Docker.app/Contents/Resources/bin/docker'
observed=[]
for iteration in range(2):
 raw,table=process_table()
 assert all(pid not in table or table[pid]['status'].startswith('Z')for pid in pids)
 assert all(not any(row['group']==group and not row['status'].startswith('Z')for row in table.values())for group in groups)
 for pid,row in old_system.items():assert table.get(pid)==row
 opened=subprocess.run(['/usr/sbin/lsof','-nP','-u','admin','-Fpn'],capture_output=True,timeout=30)
 assert opened.returncode in [0,1]and len(opened.stdout)<=33554432
 private(B/('processes-'+str(iteration)+'.private'),raw.encode())
 private(B/('open-files-'+str(iteration)+'.private'),opened.stdout)
 _,after=process_table()
 roots=set(queued+[os.getpid()])
 ancestors=set()
 for start in roots:
  current=start;seen=set()
  while current in after and current not in seen:
   seen.add(current);ancestors.add(current);current=after[current]['parent']
   if current<=1:break
 def recognized(pid):
  if pid in old_system:return after.get(pid)==old_system[pid]
  if pid in ancestors:return True
  current=pid;seen=set()
  while current in after and current not in seen:
   if current in roots:return True
   seen.add(current);current=after[current]['parent']
  return False
 project_open=set();current=None
 for line in opened.stdout.decode(errors='replace').splitlines():
  if line.startswith('p')and line[1:].isdigit():current=int(line[1:])
  elif line.startswith('n')and(line[1:]==str(R)or line[1:].startswith(str(R)+'/')):project_open.add(current)
 unknown=sorted(pid for pid in project_open if pid in after and not recognized(pid))
 save(B/('classification-'+str(iteration)+'.json'),dict(projectOpenPids=sorted(project_open),unknownPids=unknown,preexistingSystemPids=sorted(old_system),ancestorPids=sorted(ancestors),descendantRoots=sorted(roots)))
 assert not unknown,'Unexpected project process remains unclassified'
 engine=subprocess.check_output([docker,'info','--format','{{.ID}}'],text=True,timeout=15).strip()
 running=subprocess.check_output([docker,'ps','-q','--no-trunc'],text=True,timeout=15).split()
 assert running==[baseline['id']]
 d=json.loads(subprocess.check_output([docker,'inspect',baseline['id']],text=True,timeout=15))[0]
 actual=dict(id=d['Id'],running=d['State']['Running'],startedAt=d['State']['StartedAt'],restartCount=d['RestartCount'])
 assert actual==baseline
 node="import {alive,workloadStopped}from'/Users/admin/Documents/Codex/storage-safeguards/buildctl.mjs';console.log(JSON.stringify({ownerStopped:alive(42989)===false,groupsStopped:"+json.dumps(sorted(groups))+".every(p=>workloadStopped(p))}));"
 canonical=json.loads(subprocess.check_output(['/Users/admin/.nvm/versions/node/v22.23.3/bin/node','--input-type=module','-e',node],text=True,timeout=15))
 assert canonical['ownerStopped']and canonical['groupsStopped']
 assert not(C/'active-run').exists()and sha(target)==sha(P/'request.original.json')
 observed.append(dict(observedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),processes=len(table),projectOpenPids=len(project_open),preexistingSystemProcesses=len(old_system),unclassifiedProjectProcesses=0,ownedProcessesStopped=True,canonicalGroupStopConfirmed=True,protectedDatabaseUnchanged=True,engineId=engine,runningContainerIds=running))
 if iteration==0:time.sleep(1)
assert observed[0]['engineId']==observed[1]['engineId']
proof=dict(requestId=r['id'],originalRequestSha256=sha(P/'request.original.json'),recoveryPlanSha256=sha(P/'RECOVERY_PLAN.md'),observerSha256=sha(__file__),ownerPid=42989,ownedPids=sorted(pids),ownedGroups=sorted(groups),sharedLeaseAlreadyMissing=True,originalGuardRecordUnavailable=True,registeredChannelsClosed=True,sourceBindingsAndProtectedStateUnchanged=True,observations=observed,preexistingInfrastructureClassified=True,failedTestAndSupervisorExit75Preserved=True,filesDeleted=0,servicesStopped=0)
save(B/'stop-proof.json',proof)
print(json.dumps(dict(stopProofPassed=True,observations=2,ownedPids=len(pids),ownedGroups=len(groups),preexistingSystemProcesses=len(old_system),unknownProjectProcesses=0,sharedLeaseAlreadyMissing=True)))
