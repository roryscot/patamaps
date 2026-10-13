import ast,datetime,hashlib,json,pathlib,re,shutil,subprocess,sys
root=pathlib.Path.cwd();out=pathlib.Path(__file__).resolve().parent
sha=lambda raw:'sha256:'+hashlib.sha256(raw).hexdigest()
def read(p):return json.loads(p.read_bytes())
def write(p,value):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,indent=2)+'\n')
functional=root/read(root/'.tools/parity/current-core-data-functional-refresh.json')['output']/'receipt.json';data=read(functional)
assert data['status']=='passed' and len(data['commands'])==40 and all(c['exitCode']==0 for c in data['commands'])
assert next(c for c in data['commands'] if c['label']=='original-correspondence')['attachedObligationsVerified']
evidence=data['functionalEvidence'];assert len(evidence)==38
verified={'portableRustTests':180,'originalCases':113,'installedNegativeTypeControls':57,'configTypeComparisons':19,'workspaceTypeComparisons':18,'workspaceAssemblyCases':59,'workspaceWorkflowObservations':28,'configParserCases':213,'configLoaderCases':12,'correspondenceTypeComparisons':16,'reportingTypeComparisons':9,'graphTypeComparisons':18,'originalTypeComparisons':11,'compositionTypeComparisons':3,'initialPackCases':159,'nestedPackCases':161,'loaderCases':22,'registryCases':35,'graphQueryCases':45,'compositionCases':36,'inheritedFactoryCases':1,'frozenGraphCases':472,'correspondenceCases':63,'referenceCases':253,'reportingCases':60,'uncheckedDigestCases':40,'utf16DigestCases':65,'discoveryProviders':7,'scientificBoundaryCases':9}
original_cases=0
for e in evidence:
 p=root/e['path'];raw=p.read_bytes();assert sha(raw)==e['digest'];record=json.loads(raw)
 assert record.get('status') in ['passed','matched','component-controls-passed','capabilities-matched'],(p,record.get('status'))
 if 'candidate' in record:
  assert record['candidate']['binaryDigest']==data['binaryDigest'] and record['candidate']['engine']==data['candidateEngine']
  for item in record['candidate'].get('sdkSourceInventory',[])+record['candidate'].get('sourceInventory',[]):
   path=pathlib.Path(item['path']);source=root/('sdk/typescript' if len(path.parts)==1 else '')/path
   assert sha(source.read_bytes())==item['digest']
 if p.parent.name.startswith('sdk-consumer-'):
  assert record['negativeTypeControls']==57 and record['allNegativeControlsRefused']
  assert record['workspaceTypeContractComparison']['mappedDeclarations']==18
  assert record['configDeclarationsCompared']==19 and record['configCorpus']['installedControls']==3
  assert record['correspondenceDeclarationsCompared']==16 and record['reportingDeclarationsCompared']==9
 if p.parent.name.startswith('native-'):
  for item in record['sourceInventory']:assert sha((root/item['path']).read_bytes())==item['digest']
  assert sum(int(n) for n in re.findall(r'test result: ok\. (\d+) passed;', (p.parent/'stdout.log').read_text()))==180
 original_cases+=record.get('counts',{}).get('originalCases',0)
assert original_cases==113
for prefix,count in [('config-controls-',225),('correspondence-controls-',63),('reference-controls-',253),('reporting-controls-',60),('digest-controls-',40),('digest-utf16-controls-',65)]:
 records=[read(root/e['path']) for e in evidence if pathlib.Path(e['path']).parent.name.startswith(prefix)]
 assert len(records)==1 and records[0]['counts']['cases']==records[0]['counts']['matched']==count
 if prefix=='config-controls-':
  record=records[0];p=root/next(e['path'] for e in evidence if pathlib.Path(e['path']).parent.name.startswith(prefix))
  assert record['driverDigest']==sha((root/'scripts/parity/config_contracts.mjs').read_bytes())==sha((p.parent/'driver.mjs').read_bytes())
  for item in record['loaderInputs']:assert sha((p.parent/item['path']).read_bytes())==item['digest']
workflow=[read(root/e['path']) for e in evidence if pathlib.Path(e['path']).parent.name.startswith('workspace-workflow-')]
assert len(workflow)==1 and workflow[0]['counts']=={'observations':28,'matched':28,'differences':0,'nativeCalls':385}
assembly=[read(root/e['path']) for e in evidence if pathlib.Path(e['path']).parent.name.startswith('workspace-controls-')]
assert len(assembly)==1 and assembly[0]['counts']=={'cases':59,'matched':59,'differences':0}

sys.path.insert(0,str(root/'scripts/parity'))
from identity import identities
binary=root/'target/debug/patamaps'
assert sha(binary.read_bytes())==data['binaryDigest']
engine=json.loads(subprocess.check_output([binary,'engine']))
assert engine==data['candidateEngine'] and all(engine[k]==v for k,v in identities(root).items())
verified.update({'migrationTypeComparisons':7,'mappedTypeComparisons':101,'cliProcessCases':104,'sourceMigrationCases':70})
cli=[read(root/e['path']) for e in evidence if pathlib.Path(e['path']).parent.name.startswith('cli-controls-')]
assert sorted(r['counts']['cases'] for r in cli)==[28,76] and all(r['counts']['matched']==r['counts']['cases'] and not r['differences'] for r in cli)
migration=[read(root/e['path']) for e in evidence if pathlib.Path(e['path']).parent.name.startswith('migration-controls-')]
assert len(migration)==1 and migration[0]['counts']['cases']==migration[0]['counts']['matched']==70 and not migration[0]['differences']
sdk=[read(root/e['path']) for e in evidence if pathlib.Path(e['path']).parent.name.startswith('sdk-consumer-')][0]
assert sdk['migrationTypeContractComparison']['mappedDeclarations']==7
verified['coreDataCases']=1
old_checkpoint=read(root/'.tools/parity/storage-review/current-source-checkpoint.json')['path']
for name in ['README.md','BUILD_PLAN.md','fixtures/parity/coverage.json','.tools/parity/storage-review/current-source-checkpoint.json','docs/acceptance/parity/approved-cache-rebuild-2026-10-12T11-36-09.099744Z/receipt.json']:
 p=out/'previous-current-records'/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,p)
commands_run=[]
def check(label,command,allowed=(0,)):
 result=subprocess.run(list(map(str,command)),cwd=root,text=True,capture_output=True)
 (out/(label+'.stdout.log')).write_text(result.stdout);(out/(label+'.stderr.log')).write_text(result.stderr)
 commands_run.append({'label':label,'command':list(map(str,command)),'exitCode':result.returncode})
 assert result.returncode in allowed,(label,result.returncode,result.stdout[-1000:],result.stderr[-1500:])
 return result
ledger=json.loads(check('strict-ledger',[sys.executable,'-B','scripts/parity/verify.py','--strict'],(1,)).stdout)
assert ledger['currentVerifiedEquivalent']==113 and not ledger['invalidEvidence'] and not ledger['strictAcceptance']
assert ledger['counts']=={'verified-equivalent':113,'missing':28,'implemented-unverified':118,'unclassified':1034}
checkpoint=out/'receipt.json';refresh=functional.relative_to(root).as_posix()
write(checkpoint,{'schemaVersion':'1.0.0','status':'checkpoint-verification-running','goalStatus':'active','functionalRun':refresh})
for name in ['README.md','BUILD_PLAN.md']:
 p=root/name;text=p.read_text();line=next(l for l in text.splitlines() if 'The [latest supervised refresh]' in l);line_new=line.replace('112','113').replace('1,035','1,034').replace(data['reusedEvidence'][0]['path'],refresh);text=text.replace(line,line_new)
 if name=='BUILD_PLAN.md':text=text.replace('### Observed gaps and audit targets',f"2026-10-12 core data verification: the unchanged original portable/runtime alignment callback passes through Rust, and the complete getter JSON value matches a separately frozen original runtime constant. The portable file additionally carries 12 relation descriptions that the original runtime omits; this distinction is preserved. No runtime implementation change was needed. The [current core-data checkpoint]({checkpoint.relative_to(root).as_posix()}) reuses the unchanged native/SDK/CLI checks and binds the current harness and ledger. Full parity and required platform checks remain open.\n\n### Observed gaps and audit targets",1)
 p.write_text(text)
node='/Users/admin/.nvm/versions/node/v22.16.0/bin/node';cargo='/Users/admin/.cargo/bin/cargo'
check('rust-format',[cargo,'fmt','--all','--','--check'])
js=['sdk/typescript/legacy-cli.mjs','sdk/typescript/cli.mjs','sdk/typescript/legacy-graph.mjs','sdk/typescript/legacy-validation.mjs','scripts/parity/migration_contracts.mjs','scripts/parity/original.mjs']
for name in js:check(pathlib.Path(name).stem+'-syntax',[node,'--check',name])
check('javascript-format',[node,str(root/'.tools/parity/oracles/399747a4ad05-p8pkt3pr/reference/node_modules/prettier/bin/prettier.cjs'),'--check',*js,'sdk/typescript/legacy-cli.d.ts','sdk/typescript/legacy-validation.d.ts'])
check('diff-check',['git','diff','--check'])
check('source-integrity',[sys.executable,'-B','scripts/test_source_integrity.py','/Users/admin/dev/SEEDZ/metamap','--output',str(out/'source-integrity.json')])
for p in sorted((root/'scripts/parity').glob('*.py')):ast.parse(p.read_bytes(),filename=str(p))
supplement=read(root/'fixtures/parity/supplement.json');oracle=root/read(root/'.tools/parity/oracles/current.json')['source']
for item in supplement['referenceTree']:
 raw=(oracle/item['path']).read_bytes();assert hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()==item['gitBlob']
assert not (root/'.tools/linux-vm/disk.raw').exists()
files=sorted((root/'crates').rglob('*.rs'))+sorted((root/'crates').glob('*/Cargo.toml'))+sorted((root/'sdk/typescript').glob('*'))+sorted(p for p in (root/'scripts/parity').glob('*') if p.is_file())+sorted(p for p in (root/'adapters/discovery').rglob('*') if p.is_file())+sorted(p for p in (root/'vendor/icu_collator').rglob('*') if p.is_file())
files += [root/name for name in ['Cargo.toml','Cargo.lock','NOTICE','README.md','BUILD_PLAN.md','crates/patamaps-core/src/legacy_cli_usage.txt']]+sorted((root/'fixtures/parity').glob('*'))+sorted((root/'fixtures/reference/schemas').glob('*.json'))
receipt={'schemaVersion':'1.0.0','status':'scoped-checks-passed-full-parity-open','goalStatus':'active','createdAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commands':commands_run,'ledger':ledger,'currentSourceMatchesBinary':True,'candidateEngine':engine,'candidateBinaryDigest':data['binaryDigest'],'functionalRun':refresh,'functionalRunDigest':sha(functional.read_bytes()),'functionalEvidence':evidence,'verifiedScopes':verified,'frozenReferenceBlobsVerified':len(supplement['referenceTree']),'sourceInventory':[{'path':p.relative_to(root).as_posix(),'digest':sha(p.read_bytes())} for p in sorted(set(files)) if p.is_file()],'previousPassedCheckpoint':old_checkpoint,'scope':'Core data alignment and complete original runtime constant value verified, with prior source-bound native/SDK/CLI/migration evidence reused. Full parity remains open; no owner deviation accepted. All prior records and failures retained. No additional deletion or VM recreation.','nextRequiredWork':'Complete the other 15 CLI workflows and original semantic/provenance/projection/generated helper/governance/inspection/adapter/example contracts, full accepted domains, installed distributions and fresh real Linux x86_64/ARM64 acceptance.','retainedRepairAndPriorRunReceipts':[read(root/'.tools/parity/current-cli-repair.json')['output']], 'driverDigest':sha(pathlib.Path(__file__).read_bytes())}
write(checkpoint,receipt);write(root/'.tools/parity/storage-review/current-source-checkpoint.json',{'path':checkpoint.relative_to(root).as_posix()})
p=root/'docs/acceptance/parity/approved-cache-rebuild-2026-10-12T11-36-09.099744Z/receipt.json';record=read(p);record.update({'latestSourceCheckpoint':checkpoint.relative_to(root).as_posix(),'latestSourceCheckpointDigest':sha(checkpoint.read_bytes()),'latestSourceBuilt':True,'goalStatus':'active','fullParityAcceptance':False,'currentScopedVerification':verified,'currentLedger':ledger});write(p,record)
print(json.dumps({'status':receipt['status'],'receipt':checkpoint.relative_to(root).as_posix(),'sourceFiles':len(receipt['sourceInventory']),'verifiedScopes':verified,'ledgerCounts':ledger['counts'],'invalidEvidence':ledger['invalidEvidence'],'strictAcceptance':ledger['strictAcceptance']},indent=2),flush=True)
