#!/usr/bin/env python3
"""Verify retained facts after failed registration qualification; not acceptance."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,importlib.util,json,os,posixpath,re,stat,subprocess,tarfile
ARCHIVE='f507ae04eb7747cd97cb484e8c5d83936cbfc52d9b08a1f35c00b47c707b1ae1'
NATIVE='cd9a15943eb96e6a45df582cc92ceda0316f222c695205888d9e47b2d419a355'
GUARD='3bfb9aeb901e02419a156538ddf78b09b134844e4bea1efe73235d6d4d7ed6b0'
REQUESTS=['65cd73ba-5bd3-487a-98fc-705b48aba0ee','8d27b0c0-f6ae-44d9-8183-798900609097','a59f9586-a170-4cf0-9017-26cd9765ece8']
MAGIC={'cffaedfe','cefaedfe','feedfacf','feedface','cafebabe','bebafeca','cafebabf','bfbafeca'}
def need(value,message):
 if not value:raise RuntimeError(message)
def read(path):return json.loads(path.read_text())
def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb')as f:
  while chunk:=f.read(1048576):h.update(chunk)
 return h.hexdigest()
def same(a,b):return all(a[k]==b[k]for k in ['pid','pgid','startSeconds','startMicroseconds'])
def main():
 p=argparse.ArgumentParser()
 p.add_argument('--root',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True)
 p.add_argument('--scheduler',type=Path,required=True);p.add_argument('--guard-records',type=Path,nargs=3,required=True)
 o=p.parse_args();latest=o.evidence/'repair-2'
 result=read(latest/'result.json');need(result['status']=='failed'and result['testExitCode']==1,'Failed final outcome changed')
 need(result['sourcesUnchanged']and result['installedGuardUnchanged']and result['protectedStateUnchanged'],'Source/state/guard mismatch')
 for flag in ['automaticReleaseActivated','parallelActivated','actualOwnerCrashRetried']:need(result[flag]is False,'Scope changed')
 for name,sha in result['sourceBindings'].items():
  need(digest(o.root/name)==sha and digest(latest/'source'/Path(name).name)==sha,'As-run/current source mismatch')
 tap=(latest/'tests.stdout').read_text()
 for key,n in [('tests',15),('pass',14),('fail',0),('cancelled',1),('skipped',0)]:
  need(re.search(r'^# '+key+' '+str(n)+r'$',tap,re.M),'Wrong TAP result '+key)
 need('test timed out after 180000ms'in tap,'Original timeout missing')
 need(not (latest/'tests.stderr').read_text().strip(),'Unexpected stderr')
 for folder,reason in [('attempt-0','unknown-runtime-rpath'),('repair-1','incomplete-native-runtime-audit')]:
  base=o.evidence/folder;failed=read(base/'result.json')
  need(failed['status']=='failed' and failed['testExitCode']==1 and failed['protectedStateUnchanged'],'Failed attempt lost/relabeled')
  need(reason in (base/'tests.stdout').read_text(),'Failure cause lost')
  for name,sha in failed['sourceBindings'].items():need(digest(base/'source'/Path(name).name)==sha,'Failed source lost')
 roots=list((latest/'fixtures').iterdir());need(len(roots)==1,'Ambiguous fixture root');case=roots[0]
 registration=case/'registration';manifest=read(registration/'registration.json')
 supplied=read(latest/'inputs.json')
 need(digest(supplied['archive'])==ARCHIVE and digest(registration/'native/patamaps')==NATIVE,'Unapproved archive/native')
 for part,rows in manifest['inventory'].items():
  base=registration/part
  paths={row['path']for row in rows}
  actual={'.'}|{str(path.relative_to(base))for path in base.rglob('*')}
  need(paths==actual,'Incomplete inventory '+part)
  for row in rows:
   file=base/row['path'];info=file.lstat()
   need(info.st_uid==row['uid']==os.getuid()and info.st_dev==row['dev']and info.st_ino==row['ino']and info.st_nlink==row['nlink'],'Snapshot identity changed')
   need(stat.S_IMODE(info.st_mode)==row['mode'],'Snapshot mode changed')
   if row['kind']=='file':
    need(stat.S_ISREG(info.st_mode)and info.st_nlink==1 and digest(file)==row['sha256']and info.st_size==row['size'],'Snapshot file changed')
   elif row['kind']=='symlink':
    need(file.is_symlink()and os.readlink(file)==row['target']and base in file.resolve().parents,'Snapshot link escaped')
   else:need(file.is_dir(),'Snapshot directory changed')
   if row['kind']!='symlink':need(row['mode']&0o222==0,'Snapshot writable')
 runtimeRows={row['path']:row for row in manifest['inventory']['runtime']}
 regular={};links={};nativeMembers=[]
 with tarfile.open(supplied['archive'],'r:gz')as archive:
  for member in archive.getmembers():
   name=member.name.rstrip('/')
   need(not member.name.startswith('/')and '..'not in PurePosixPath(name).parts and(name=='python'or name.startswith('python/')),'Unsafe pinned archive path')
   if member.isfile():
    data=archive.extractfile(member).read()
    regular[name]=hashlib.sha256(data).hexdigest()
    if data[:4].hex()in MAGIC:nativeMembers.append(name)
   elif member.issym():
    target=posixpath.normpath(posixpath.join(posixpath.dirname(name),member.linkname))
    need(target=='python'or target.startswith('python/'),'Unsafe pinned archive link')
    links[name]=member.linkname
   else:need(member.isdir(),'Unexpected pinned archive member type')
 need(len(regular)==1643 and len(nativeMembers)==10,'Pinned archive closure changed')
 need(set(regular)=={name for name,row in runtimeRows.items()if row['kind']=='file'},'Runtime file set differs from pinned archive')
 need(set(links)=={name for name,row in runtimeRows.items()if row['kind']=='symlink'},'Runtime link set differs from pinned archive')
 for name,sha in regular.items():need(runtimeRows[name]['sha256']==sha,'Runtime member differs from archive')
 for name,target in links.items():need(runtimeRows[name]['target']==target,'Runtime link differs from archive')
 need(sorted(nativeMembers)==sorted(row['file']for row in manifest['dependencies']),'Native audit omitted an archive member')
 for row in manifest['dependencies']:
  file=registration/'runtime'/row['file']
  load=subprocess.check_output(['/usr/bin/otool','-l',str(file)],text=True)
  blocks=re.split(r'Load command \d+\n',load)
  uses=[block for block in blocks if re.search(r'cmd LC_(?:LOAD_DYLIB|LOAD_WEAK_DYLIB|REEXPORT_DYLIB|LOAD_UPWARD_DYLIB|LAZY_LOAD_DYLIB)\b',block)]
  need(len(uses)==len(row['references']),'Native load omitted or ID counted as dependency')
  for ref in row['references']:
   need(set(ref)in[{'system'},{'private'}],'Bad dependency record')
   if 'system'in ref:need(ref['system'].startswith(('/usr/lib/','/System/Library/')),'Unknown system reference')
   else:need(ref['private']in regular,'Private reference outside runtime')

 prefix=registration/'runtime/python'
 startupCode='import json,sys,pathlib,hashlib,subprocess,ctypes;print(json.dumps(dict(prefix=sys.prefix,path=sys.path,isolated=sys.flags.isolated,noSite=sys.flags.no_site,dontWriteBytecode=sys.dont_write_bytecode,origins={m.__name__:m.__spec__.origin for m in [json,pathlib,hashlib,subprocess,ctypes]})))'
 startup=json.loads(subprocess.check_output([str(prefix/'bin/python3.13'),'-I','-S','-B','-c',startupCode],env={'PATH':'/usr/bin:/bin','LANG':'C','PYTHONDONTWRITEBYTECODE':'1'},text=True,timeout=15))
 expectedPaths=[str(prefix/'lib/python313.zip'),str(prefix/'lib/python3.13'),str(prefix/'lib/python3.13/lib-dynload')]
 need(startup['prefix']==str(prefix)and startup['path']==expectedPaths and startup['isolated']==1 and startup['noSite']==1 and startup['dontWriteBytecode']is True,'Private isolated startup path mismatch')
 need(all(value in ['frozen','built-in']or prefix in Path(value).parents for value in startup['origins'].values()),'Stdlib escaped snapshot')
 (o.evidence/'independent-startup-info.json').write_text(json.dumps(startup,indent=2)+'\n')
 for file,sha in manifest['systemBindings'].items():need(digest(file)==sha,'System/bootstrap binding changed')
 need(manifest['qualifiedHost']==read(case/'binding-proof.json')['qualifiedHost']and manifest['qualifiedHost']['buildVersion']=='24H32','OS binding mismatch')
 for file,sha in supplied['expectedState'].items():need(digest(file)==sha,'Original application state changed')
 original=read(case/'original-state.json')
 need(sorted(p.name for p in (Path(supplied['inputs']['state'])/'attempts').iterdir())==original['attempts']==['1793122875791456000-6699'],'Original application attempt changed')
 need(digest(Path(supplied['inputs']['state'])/'driver.lock')==original['lock']['sha256'],'Original lock changed')
 ids={};identities=[]
 for operation in ['engine','input-key','unchanged-build']:
  d=case/('real-'+operation);value=read(d/'result.json');terminal=read(d/'terminal.json')
  need(value['exit']['code']==0 and value['dataStreamsClosed']and value['protectedStateUnchanged'],'Real command failed')
  need(value['automaticReservationReleaseQualified']is False,'Staged evidence activated')
  need(value['binding']['manifestSha256']==digest(registration/'registration.json'),'Real command used other registration')
  ownership=value['ownership']
  need(ownership['ownershipKnown']and ownership['allRegisteredStopped']and ownership['channelClosed']and ownership['protocolFailure']is None,'Real ownership incomplete')
  need(len(terminal['calls'])==1 and terminal['frames']==6 and terminal['calls'][0]['controlComplete'],'Real control incomplete')
  journal=[json.loads(line)for line in(d/'supervisor-journal.jsonl').read_text().splitlines()]
  need([x['frame']['sequence']for x in journal]==list(range(6)),'Real journal order wrong')
  c=terminal['calls'][0];root=terminal['controllerIdentity']
  for identity in [root,c['guardianIdentity'],c['nativeIdentity']]:
   if identity is not None:identities.append(identity)
  for pid in [root['pid'],c['guardianPid'],c['nativePid']]:ids[pid]=True
  stop=read(d/'independent-stop.json')
  need(all(x is None for x in stop['identities'].values())and all(x is True for x in stop['groupsStopped'].values()),'Real group survived')
  if operation=='engine':need(value['output']==supplied['engine'],'Engine mismatch')
  elif operation=='input-key':need(value['output']['commandsExecuted']is False and value['output']['inputKey']==supplied['inputKey'],'Input key mismatch')
  else:need(value['output']['status']=='unchanged-project-build'and value['output']['inputKey']==supplied['inputKey']and value['output']['verification']=='not-repeated'and value['output']['activation']=='not-performed','Unchanged build not established')
 need(len(ids)==9,'Wrong registered process count')
 spec=importlib.util.spec_from_file_location('registration_review_live',o.root/'scripts/native_inspection_guard.py')
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 for pid in ids:need(m.process_identity(pid)is None and not m.group_live(pid),'Registered process/group alive now')
 for name in ['archive-race-and-bytecode.json','copy-corruption.json','hardlink-negative.json']:
  need(read(case/name)['primaryUnchanged'],'Primary snapshot changed')
 race=read(case/'archive-race-and-bytecode.json')
 need(race['exactVerifiedBytesUsed']and race['inputPathChanged']and race['addedBytecodeRefused'],'Race/bytecode control missing')
 need(read(case/'copy-corruption.json')['registrationPublished']is False,'Corrupted snapshot published')
 hard=read(case/'hardlink-negative.json');a=(Path(hard['secondary'])/'source/native_registered_controller.py').stat();b=Path(hard['alias']).stat()
 need(a.st_ino==b.st_ino and a.st_dev==b.st_dev and a.st_nlink==2,'Hardlink counterexample missing')
 for request,record,passed in zip(REQUESTS,o.guard_records,[False,False,False]):
  r=read(o.scheduler/'scheduler/requests'/(request+'.json'));g=read(record)
  need(r['state']=='finished'and r['leaseReleaseCompleted']is True,'Canonical reservation held')
  need(g['completed']is passed and g['exitCode']==(0 if passed else 1)and g['filesDeleted']==0,'Canonical outcome relabeled')
  need(g['containersAtStart']['known']and g['containersAtEnd']['known']and g['containersAtStart']['ids']==g['containersAtEnd']['ids'],'Container set changed')
 need(not(o.scheduler/'active-run').exists(),'Compatibility lease held')
 installed=Path('/Users/admin/Documents/Codex/storage-safeguards/engine/scripts/guarded-run.mjs');need(digest(installed)==GUARD,'Installed guard changed')
 print(json.dumps(dict(status='verified-failed-registration-evidence',qualificationAccepted=False,controlsPassed=14,controlsTimedOut=1,actualNativeTestCasesPassed=2,nativeOperationsEventuallyReturnedZero=3,registeredProcessIdsStopped=9,kernelIdentityInstancesCaptured=len(identities),runtimeRegularFilesMatchedToPinnedArchive=1643,runtimeSymlinksMatchedToPinnedArchive=len(links),nativeMachOMembersAudited=10,archiveSha256=ARCHIVE,sourceBindings=result['sourceBindings'],repairsUsed=2,failedAttemptsPreserved=3,unchangedBuildPassedTestDeadline=False,originalStateAndOneAttemptUnchanged=True,isolatedStartupPathsMatched=True,primaryRegistrationManifestSha256=digest(registration/'registration.json'),installedGuardUnchanged=True,canonicalRequestsReleased=REQUESTS,automaticReleaseActivated=False,parallelActivated=False,actualOwnerCrashRetried=False,goalComplete=False,reviewerSha256=digest(Path(__file__))),indent=2))
if __name__=='__main__':main()
