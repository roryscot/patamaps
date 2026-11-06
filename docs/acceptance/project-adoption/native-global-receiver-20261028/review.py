#!/usr/bin/env python3
"""Evidence review for the staged receiver; does not grant release authority."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,re,subprocess
GUARD_SHA='3bfb9aeb901e02419a156538ddf78b09b134844e4bea1efe73235d6d4d7ed6b0'
REQUESTS=['95fd43fc-aecf-4b39-a1be-476c58b4f7ec','9d1c9047-9845-4280-be5f-c848ddfb38a1']
def need(value,message):
 if not value:raise RuntimeError(message)
def read(path):return json.loads(path.read_text())
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def same(left,right):return all(left[k]==right[k] for k in ['pid','pgid','startSeconds','startMicroseconds'])
def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--root',type=Path,required=True)
 parser.add_argument('--evidence',type=Path,required=True)
 parser.add_argument('--first-guard-record',type=Path,required=True)
 parser.add_argument('--supplement-guard-record',type=Path,required=True)
 parser.add_argument('--scheduler-directory',type=Path,required=True)
 parser.add_argument('--installed-guard',type=Path,required=True)
 o=parser.parse_args()
 first=o.evidence/'attempt-0';supplement=o.evidence/'supplement-1'
 initial=read(first/'result.json');latest=read(supplement/'result.json')
 for base,result in [(first,initial),(supplement,latest)]:
  need(result['status']=='passed' and result['testExitCode']==0 and result['sourcesUnchanged'] and result['installedGuardUnchanged'],'Qualification failed')
  need(result['automaticReleaseActivated'] is False and result['parallelActivated'] is False,'Unexpected activation')
  for name,sha in result['sourceBindings'].items():
   need(digest(base/'source'/Path(name).name)==sha,'As-run source mismatch')
   if name!='scripts/test_native_inspection_receiver.mjs':
    need(digest(o.root/name)==sha,'Current production source changed')
 need((o.root/'scripts/test_native_inspection_receiver.mjs').read_bytes()==(supplement/'source/test_native_inspection_receiver.mjs').read_bytes(),'Latest test source mismatch')
 need((supplement/'source/test_native_inspection_receiver.mjs').read_bytes().startswith((first/'source/test_native_inspection_receiver.mjs').read_bytes()),'Prior test code changed')
 for base,count in [(first,32),(supplement,3)]:
  stdout=(base/'tests.stdout').read_text()
  need(re.search(r'^# pass '+str(count)+r'$',stdout,re.M),'Wrong passed count')
  need(re.search(r'^# fail 0$',stdout,re.M) and re.search(r'^# cancelled 0$',stdout,re.M),'Failed/cancelled control')
  need(not (base/'tests.stderr').read_text().strip(),'Unexpected stderr')
 need(re.search(r'^# skipped 0$',(first/'tests.stdout').read_text(),re.M),'Initial cases skipped')
 for name in ['valid-looking duplicate keys cannot silently become an accepted launch','individual record bound refuses before the aggregate channel limit','stream errors cannot become ordinary EOF completion']:
  need(re.search(r'^ok \d+ - '+re.escape(name)+r'$',(supplement/'tests.stdout').read_text(),re.M),'Missing supplement control')
 fixtures=list((first/'fixtures').iterdir());need(len(fixtures)==1,'Ambiguous initial fixture root');fixtures=fixtures[0]
 observed={}
 for name,count,known in [('real-normal',6,True),('real-controller-crash',4,True),('real-guardian-crash',5,True),('real-unsealed',3,False)]:
  case=fixtures/name;status=read(case/'status.json');assessment=read(case/'assessment.json')
  need(status['frames']==count and status['failure'] is None and status['channelClosed'],'Incomplete actual channel')
  need(assessment['ownershipKnown'] is known and assessment['allRegisteredStopped'] and assessment['channelClosed'],'Actual stop classification incorrect')
  need(assessment['sentinelUnchanged'] and assessment['automaticReservationReleaseQualified'] is False and assessment['sourceRuntimeRegistration']=='unqualified','Evidence confused with activation')
  rows=[json.loads(line) for line in (case/'journal.jsonl').read_text().splitlines()]
  need(len(rows)==count and [row['frame']['sequence'] for row in rows]==list(range(count)),'Journal order mismatch')
  need(rows[0]['frame']['event']=='guardian-launch-pending' and rows[1]['frame']['event']=='guardian-started','Missing pending-before-registration')
  call=status['calls'][0];root=status['controllerIdentity']
  need(call['guardianIdentity']['parentPid']==root['pid'],'Guardian ancestry mismatch')
  if known:
   live=read(case/'observed-live.json');lc=live['snapshot']['calls'][0]
   need(live['snapshot']['frames']==4 and not live['snapshot']['channelClosed'] and lc['registrationKnown'] and not lc['finished'],'Not a live registration observation')
   for identity in [root,lc['guardianIdentity'],lc['nativeIdentity']]:
    need(same(identity,live['probe']['identities'][str(identity['pid'])]),'Live kernel identity mismatch')
   need(lc['nativeIdentity']['parentPid']==lc['guardianPid'],'Native ancestry mismatch')
   need(call['controlComplete'] is (name=='real-normal'),'Crash relabeled complete')
  else:
   need(not call['registrationKnown'] and call['nativeIdentity'] is None,'Unknown native group declared owned')
   survivor=read(case/'unregistered.json')
   need(same(survivor,read(case/'survivor-before-cleanup.json')['identities'][str(survivor['pid'])]),'Unregistered survivor not observed alive')
   need(assessment['unregisteredSurvivorObserved'],'Survivor control absent')
  cleanup=read(case/'cleanup.json')
  need(all(value is None for value in cleanup['finalProbe']['identities'].values()) and all(value is True for value in cleanup['finalProbe']['groupsStopped'].values()),'Harness left workload')
  for identity in cleanup['identities']:
   observed[(identity['pid'],identity['startSeconds'],identity['startMicroseconds'])]=identity
 need(len(observed)==16,'Wrong observed process-instance count')
 spec=importlib.util.spec_from_file_location('receiver_review_live',o.root/'scripts/native_inspection_guard.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 for identity in observed.values():
  current=module.process_identity(identity['pid'])
  need(current is None or not same(identity,current),'Original process instance still alive')
 need(digest(o.installed_guard)==GUARD_SHA,'Installed guard changed')
 for request,record in zip(REQUESTS,[o.first_guard_record,o.supplement_guard_record]):
  value=read(o.scheduler_directory/'scheduler/requests'/(request+'.json'))
  need(value['state']=='finished' and value['leaseReleaseCompleted'] is True,'Canonical request not released')
  guard=read(record);need(guard['completed'] and guard['exitCode']==0 and guard['filesDeleted']==0,'Canonical run did not complete')
  need(guard['containersAtStart']['known'] and guard['containersAtEnd']['known'] and guard['containersAtStart']['ids']==guard['containersAtEnd']['ids'] and not guard['newSurvivingContainers'],'Container runtime changed during qualification')
 need(not (o.scheduler_directory/'active-run').exists(),'Canonical lease still held')
 print(json.dumps(dict(status='passed-staged-native-receiver-review',passedControls=35,initialControls=32,supplementalControls=3,realProcessCases=4,observedProcessInstancesStopped=16,oldTestSourcePreserved=True,productionRepairs=0,qualificationRepairs=1,installedGuardUnchanged=True,canonicalRequestsReleased=REQUESTS,unknownSurvivorStayedUnconfirmed=True,sourceBindings=latest['sourceBindings'],sourceRuntimeRegistration='unqualified',installedReleaseActivated=False,parallelActivated=False,actualOwnerCrashRetried=False,goalComplete=False,reviewerSha256=digest(Path(__file__))),indent=2))
if __name__=='__main__':main()
