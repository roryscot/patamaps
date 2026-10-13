import ast,datetime,hashlib,json,pathlib,re,shutil,subprocess,sys
root=pathlib.Path.cwd();out=pathlib.Path(__file__).resolve().parent
sha=lambda raw:'sha256:'+hashlib.sha256(raw).hexdigest()
def read(p):return json.loads(p.read_bytes())
def write(p,value):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,indent=2)+'\n')
functional=root/read(root/'.tools/parity/current-evaluation-functional-refresh.json')['output']/'receipt.json';data=read(functional)
assert data['status']=='passed' and len(data['commands'])==43 and all(c['exitCode']==0 for c in data['commands'])
assert next(c for c in data['commands'] if c['label']=='original-correspondence')['attachedObligationsVerified']
evidence=data['functionalEvidence'];assert len(evidence)==41
verified={'portableRustTests':182,'originalCases':114,'installedNegativeTypeControls':64,'configTypeComparisons':19,'workspaceTypeComparisons':18,'workspaceAssemblyCases':59,'workspaceWorkflowObservations':28,'configParserCases':213,'configLoaderCases':12,'correspondenceTypeComparisons':16,'reportingTypeComparisons':9,'graphTypeComparisons':18,'originalTypeComparisons':11,'compositionTypeComparisons':3,'initialPackCases':159,'nestedPackCases':161,'loaderCases':22,'registryCases':35,'graphQueryCases':45,'compositionCases':36,'inheritedFactoryCases':1,'frozenGraphCases':472,'correspondenceCases':63,'referenceCases':253,'reportingCases':60,'uncheckedDigestCases':40,'utf16DigestCases':65,'discoveryProviders':7,'scientificBoundaryCases':9}
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
  assert record['negativeTypeControls']==64 and record['allNegativeControlsRefused']
  assert record['workspaceTypeContractComparison']['mappedDeclarations']==18
  assert record['configDeclarationsCompared']==19 and record['configCorpus']['installedControls']==3
  assert record['correspondenceDeclarationsCompared']==16 and record['reportingDeclarationsCompared']==9
 if p.parent.name.startswith('native-'):
  for item in record['sourceInventory']:assert sha((root/item['path']).read_bytes())==item['digest']
  assert sum(int(n) for n in re.findall(r'test result: ok\. (\d+) passed;', (p.parent/'stdout.log').read_text()))==182
 original_cases+=record.get('counts',{}).get('originalCases',0)
assert original_cases==114
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
verified.update({'migrationTypeComparisons':7,'mappedTypeComparisons':128,'cliProcessCases':104,'sourceMigrationCases':70})
cli=[read(root/e['path']) for e in evidence if pathlib.Path(e['path']).parent.name.startswith('cli-controls-')]
assert sorted(r['counts']['cases'] for r in cli)==[28,76] and all(r['counts']['matched']==r['counts']['cases'] and not r['differences'] for r in cli)
migration=[read(root/e['path']) for e in evidence if pathlib.Path(e['path']).parent.name.startswith('migration-controls-')]
assert len(migration)==1 and migration[0]['counts']['cases']==migration[0]['counts']['matched']==70 and not migration[0]['differences']
sdk=[read(root/e['path']) for e in evidence if pathlib.Path(e['path']).parent.name.startswith('sdk-consumer-')][0]
assert sdk['migrationTypeContractComparison']['mappedDeclarations']==7
verified['coreDataCases']=1
verified.update({'evaluationTypeComparisons':27,'evaluationCases':855,'evaluationExpandedCases':48})
assert sdk['evaluationTypeContractComparison']['mappedDeclarations']==27
observations=[read(root/e['path']) for e in evidence if pathlib.Path(e['path']).parent.name.startswith('evaluation-controls-')]
assert sorted(r['counts']['cases'] for r in observations)==[48,855] and all(r['counts']['matched']==r['counts']['cases'] and not r['differences'] for r in observations)
for e in evidence:
 p=root/e['path']
 if p.parent.name.startswith('evaluation-controls-'):
  r=read(p);assert r['driverDigest']==sha((root/'scripts/parity/evaluation_contracts.mjs').read_bytes())==sha((p.parent/'driver.mjs').read_bytes());assert sha((root/r['corpus']['path']).read_bytes())==r['corpus']['digest']
old_checkpoint=read(root/'.tools/parity/storage-review/current-source-checkpoint.json')['path']
for name in ['README.md','BUILD_PLAN.md','fixtures/parity/coverage.json','.tools/parity/storage-review/current-source-checkpoint.json','docs/acceptance/parity/approved-cache-rebuild-2026-10-12T11-36-09.099744Z/receipt.json']:
 p=out/'previous-current-records'/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,p)
mapping=read(root/'fixtures/parity/legacy-evaluation-type-mapping.json')
manifest=read(root/'fixtures/parity/manifest.json');originals={x['id']:x for x in manifest['obligations']};coverage_path=root/'fixtures/parity/coverage.json';coverage=read(coverage_path)
review={'schemaVersion':'1.0.0','referenceEngine':manifest['reference']['engine'],'scope':'Context/selector/impact decisions and original wire declarations. Finite observations and bidirectional types pass; complete contracts and original compiler/proof execution remain open. No owner deviation accepted.','componentEvidence':evidence,'rows':[]}
for item in mapping['rows']:
 original=originals[item['id']]
 review['rows'].append({'id':item['id'],'name':original['name'],'status':'implemented-unverified','nativeAnalogue':{'path':'crates/patamaps-core/src/legacy_evaluation.rs','symbol':'legacy_evaluation_request','scope':'Read-only context/selector/impact decisions; compiler/proof wire declarations alone do not establish execution parity.'},'candidateEntryPoint':{'path':'sdk/typescript/legacy-validation.mjs' if item.get('valueComparison') else item['candidateModule'],'symbol':item['candidateName']},'facts':['Rust reuses the admission expression evaluator and ordered key visitor with explicit Object.is numeric facts, and the shared selector matcher. The original impact algorithm retains direction defaults, active sets, proof invalidation, first causal paths and stable locale ordering. Caller context values/arrays and prototype bindings remain host-owned.','All 903 separately frozen original observation fixtures match; the unchanged original context callback executes through Rust. All 27 added original-source-generated declaration comparisons pass in both directions, with explicit public registry substitution. Compiler/proof wire models are compared as declarations only; no compiler execution is inferred from them.'],'unresolved':'Full v1/v2 compilation, constraint/custom callback/waiver/generation and proof semantics; complete module/package and private nominal compatibility; arbitrary accessors/proxies/custom array methods, short-circuit error effects, locales beyond the captured host and resource boundaries; fresh real Linux x86_64/ARM64 acceptance remain unverified. The finite corpus does not close a complete export contract.','acceptance':'Preserve every original expectation and input profile, complete compilation and remaining callbacks, extend independent accepted-domain/host/resource/installed-platform observations, and obtain owner disposition for any real compatibility deviation before full acceptance.'})
review_path=root/'fixtures/parity/legacy-evaluation-classification.json';assert not review_path.exists();write(review_path,review)
for row in coverage['rows']:
 if row['id'] in {x['id'] for x in mapping['rows']}:
  assert row['status']=='unclassified';row.update({'status':'implemented-unverified','candidateEvidence':[],'classification':{'path':review_path.relative_to(root).as_posix(),'digest':sha(review_path.read_bytes())}})
write(coverage_path,coverage)
commands_run=[]
def check(label,command,allowed=(0,)):
 result=subprocess.run(list(map(str,command)),cwd=root,text=True,capture_output=True)
 (out/(label+'.stdout.log')).write_text(result.stdout);(out/(label+'.stderr.log')).write_text(result.stderr)
 commands_run.append({'label':label,'command':list(map(str,command)),'exitCode':result.returncode})
 assert result.returncode in allowed,(label,result.returncode,result.stdout[-1000:],result.stderr[-1500:])
 return result
ledger=json.loads(check('strict-ledger',[sys.executable,'-B','scripts/parity/verify.py','--strict'],(1,)).stdout)
assert ledger['currentVerifiedEquivalent']==114 and not ledger['invalidEvidence'] and not ledger['strictAcceptance']
assert ledger['counts']=={'verified-equivalent':114,'missing':28,'implemented-unverified':145,'unclassified':1006}
checkpoint=out/'receipt.json';refresh=functional.relative_to(root).as_posix()
write(checkpoint,{'schemaVersion':'1.0.0','status':'checkpoint-verification-running','goalStatus':'active','functionalRun':refresh})
for name in ['README.md','BUILD_PLAN.md']:
 p=root/name;text=p.read_text();line=next(l for l in text.splitlines() if 'The [latest supervised refresh]' in l)
 line_new=line.replace('113 current original cases','114 current original cases').replace('118 as implemented','145 as implemented').replace('1,034 obligations','1,006 obligations').replace('180 portable Rust tests','182 portable Rust tests').replace('57 individually refused','64 individually refused').replace('101 mapped declarations','128 mapped declarations').replace('113 unchanged original callbacks','114 unchanged original callbacks')
 line_new=line_new.replace('113 selected unchanged original cases','114 selected unchanged original cases')
 line_new=re.sub(r'(?<=\]\()docs/acceptance/parity/core-data-functional-refresh-[^)]+/receipt.json',refresh,line_new)
 text=text.replace(line,line_new)
 if name=='README.md':text=text.replace('113 equivalent original cases','114 equivalent original cases').replace('118 implemented-unverified','145 implemented-unverified').replace('1,034 unclassified','1,006 unclassified').replace('180 portable native tests','182 portable native tests').replace('57 negative type controls','64 negative type controls').replace('101 bidirectional declarations','128 bidirectional declarations')
 if name=='BUILD_PLAN.md':text=text.replace('### Observed gaps and audit targets',f"2026-10-12 evaluation dependency repair: Rust now implements the original context helpers, selector matching and causal impact observations. All 903 frozen full-value/error/host observations, the unchanged original context callback and 27 added declaration comparisons pass. Context comparisons preserve NaN/negative zero; parsing retains array/prototype identity; impact retains proof invalidation, relation directions, first paths and stable locale ties. Full v1/v2 compilation, callback effects and required platform acceptance remain open. The [current evaluation checkpoint]({checkpoint.relative_to(root).as_posix()}) binds the rebuilt engine and refreshed controls.\n\n### Observed gaps and audit targets",1)
 p.write_text(text)
node='/Users/admin/.nvm/versions/node/v22.16.0/bin/node';cargo='/Users/admin/.cargo/bin/cargo'
check('rust-format',[cargo,'fmt','--all','--','--check'])
js=['sdk/typescript/legacy-evaluation.mjs','sdk/typescript/canonical.mjs','sdk/typescript/legacy-registry.mjs','scripts/parity/evaluation_contracts.mjs','sdk/typescript/legacy-cli.mjs','sdk/typescript/cli.mjs','sdk/typescript/legacy-graph.mjs','sdk/typescript/legacy-validation.mjs','scripts/parity/migration_contracts.mjs','scripts/parity/original.mjs']
for name in js:check(pathlib.Path(name).stem+'-syntax',[node,'--check',name])
check('javascript-format',[node,str(root/'.tools/parity/oracles/399747a4ad05-p8pkt3pr/reference/node_modules/prettier/bin/prettier.cjs'),'--check',*js,'sdk/typescript/legacy-evaluation.d.ts','sdk/typescript/legacy-cli.d.ts','sdk/typescript/legacy-validation.d.ts'])
check('diff-check',['git','diff','--check'])
check('source-integrity',[sys.executable,'-B','scripts/test_source_integrity.py','/Users/admin/dev/SEEDZ/metamap','--output',str(out/'source-integrity.json')])
for p in sorted((root/'scripts/parity').glob('*.py')):ast.parse(p.read_bytes(),filename=str(p))
supplement=read(root/'fixtures/parity/supplement.json');oracle=root/read(root/'.tools/parity/oracles/current.json')['source']
for item in supplement['referenceTree']:
 raw=(oracle/item['path']).read_bytes();assert hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()==item['gitBlob']
assert not (root/'.tools/linux-vm/disk.raw').exists()
files=sorted((root/'crates').rglob('*.rs'))+sorted((root/'crates').glob('*/Cargo.toml'))+sorted((root/'sdk/typescript').glob('*'))+sorted(p for p in (root/'scripts/parity').glob('*') if p.is_file())+sorted(p for p in (root/'adapters/discovery').rglob('*') if p.is_file())+sorted(p for p in (root/'vendor/icu_collator').rglob('*') if p.is_file())
files += [root/name for name in ['Cargo.toml','Cargo.lock','NOTICE','README.md','BUILD_PLAN.md','crates/patamaps-core/src/legacy_cli_usage.txt']]+sorted((root/'fixtures/parity').glob('*'))+sorted((root/'fixtures/reference/schemas').glob('*.json'))
receipt={'schemaVersion':'1.0.0','status':'scoped-checks-passed-full-parity-open','goalStatus':'active','createdAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commands':commands_run,'ledger':ledger,'currentSourceMatchesBinary':True,'candidateEngine':engine,'candidateBinaryDigest':data['binaryDigest'],'functionalRun':refresh,'functionalRunDigest':sha(functional.read_bytes()),'functionalEvidence':evidence,'verifiedScopes':verified,'frozenReferenceBlobsVerified':len(supplement['referenceTree']),'sourceInventory':[{'path':p.relative_to(root).as_posix(),'digest':sha(p.read_bytes())} for p in sorted(set(files)) if p.is_file()],'previousPassedCheckpoint':old_checkpoint,'scope':'Original context/selector/impact decisions and 27 declaration comparisons verified alongside the refreshed prior checks. Full parity remains open; no owner deviation accepted. All prior records and failures retained. No additional deletion or VM recreation.','nextRequiredWork':'Complete original v1/v2 compiler schema/constraint/custom callback/waiver/generation/activator contracts using the context/selector/impact foundation, then semantic/provenance/projection and remaining CLI/adapter/helper/governance/example contracts, full accepted domains and fresh real Linux x86_64/ARM64 acceptance.','retainedRepairAndPriorRunReceipts':[read(root/'.tools/parity/current-compilation-repair.json')['output']], 'driverDigest':sha(pathlib.Path(__file__).read_bytes())}
write(checkpoint,receipt);write(root/'.tools/parity/storage-review/current-source-checkpoint.json',{'path':checkpoint.relative_to(root).as_posix()})
p=root/'docs/acceptance/parity/approved-cache-rebuild-2026-10-12T11-36-09.099744Z/receipt.json';record=read(p);record.update({'latestSourceCheckpoint':checkpoint.relative_to(root).as_posix(),'latestSourceCheckpointDigest':sha(checkpoint.read_bytes()),'latestSourceBuilt':True,'goalStatus':'active','fullParityAcceptance':False,'currentScopedVerification':verified,'currentLedger':ledger});write(p,record)
print(json.dumps({'status':receipt['status'],'receipt':checkpoint.relative_to(root).as_posix(),'sourceFiles':len(receipt['sourceInventory']),'verifiedScopes':verified,'ledgerCounts':ledger['counts'],'invalidEvidence':ledger['invalidEvidence'],'strictAcceptance':ledger['strictAcceptance']},indent=2),flush=True)
