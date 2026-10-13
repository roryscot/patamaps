import ast,datetime,hashlib,json,pathlib,re,shutil,subprocess,sys
root=pathlib.Path.cwd();out=pathlib.Path(__file__).resolve().parent
sha=lambda raw:'sha256:'+hashlib.sha256(raw).hexdigest()
def read(p):return json.loads(p.read_bytes())
def write(p,value):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,indent=2)+'\n')
functional=root/read(root/'.tools/parity/current-cli-functional-refresh.json')['output']/'receipt.json';data=read(functional)
assert data['status']=='passed' and len(data['commands'])==39 and all(c['exitCode']==0 for c in data['commands'])
assert next(c for c in data['commands'] if c['label']=='original-correspondence')['attachedObligationsVerified']
evidence=data['functionalEvidence'];assert len(evidence)==37
verified={'portableRustTests':180,'originalCases':112,'installedNegativeTypeControls':57,'configTypeComparisons':19,'workspaceTypeComparisons':18,'workspaceAssemblyCases':59,'workspaceWorkflowObservations':28,'configParserCases':213,'configLoaderCases':12,'correspondenceTypeComparisons':16,'reportingTypeComparisons':9,'graphTypeComparisons':18,'originalTypeComparisons':11,'compositionTypeComparisons':3,'initialPackCases':159,'nestedPackCases':161,'loaderCases':22,'registryCases':35,'graphQueryCases':45,'compositionCases':36,'inheritedFactoryCases':1,'frozenGraphCases':472,'correspondenceCases':63,'referenceCases':253,'reportingCases':60,'uncheckedDigestCases':40,'utf16DigestCases':65,'discoveryProviders':7,'scientificBoundaryCases':9}
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
assert original_cases==112
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
old_checkpoint=read(root/'.tools/parity/storage-review/current-source-checkpoint.json')['path']
review_names=['registry-validation-classification.json','legacy-pack-type-classification.json','legacy-graph-classification.json','legacy-composition-classification.json','legacy-reporting-classification.json','legacy-correspondence-classification.json','legacy-config-classification.json','legacy-workspace-classification.json']
mutable=['README.md','BUILD_PLAN.md','fixtures/parity/coverage.json','.tools/parity/storage-review/current-source-checkpoint.json','docs/acceptance/parity/approved-cache-rebuild-2026-10-12T11-36-09.099744Z/receipt.json']+['fixtures/parity/'+name for name in review_names]
for name in mutable:
 p=out/'previous-current-records'/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,p)
coverage=read(root/'fixtures/parity/coverage.json');by={r['id']:r for r in coverage['rows']}
for name in review_names:
 p=root/'fixtures/parity'/name;review=read(p);review['componentEvidence']=evidence
 for row in review['rows']:
  row['facts'].append('Current CLI-phase source evidence includes 180 portable Rust tests, 112 unchanged original callbacks and 101 declaration comparisons with explicit substitutions. Full exported contracts remain unverified.')
 write(p,review)
 for row in coverage['rows']:
  if row.get('classification',{}).get('path')==p.relative_to(root).as_posix():row['classification']['digest']=sha(p.read_bytes())
manifest=read(root/'fixtures/parity/manifest.json');mapping=read(root/'fixtures/parity/legacy-migration-type-mapping.json')['rows'];names={r['id']:r['candidateName'] for r in mapping}
commands={'validate','diff','trace','authority','generate','check','migrate-sources'}
obligations=[r for r in manifest['obligations'] if r['id'] in names or r['kind'] in ['cli-command','cli-option'] and r['name'].split(' ')[0] in commands];assert len(obligations)==20
review={'schemaVersion':'1.0.0','referenceEngine':'399747a4ad05a37cd8db1cedd53048fad2175be4','scope':'Rust source-catalog migration and seven original CLI workflows. Finite controls pass; complete public/CLI/package/platform contracts remain open. No owner deviation accepted.','componentEvidence':evidence,'rows':[]}
for item in obligations:
 entry={'path':'sdk/typescript/legacy-cli.mjs','symbol':names.get(item['id'],'runLegacyCli')}
 if item['kind'].startswith('cli-'):entry['launcher']={'path':'crates/patamaps-cli/src/main.rs','command':'patamaps legacy run --node <absolute-node> --entry <installed-cli-entry> -- <original-arguments>'}
 analogue={'path':'crates/patamaps-core/src/legacy_cli.rs','symbol':'legacy_cli_request'}
 review['rows'].append({'id':item['id'],'name':item['name'],'status':'implemented-unverified','nativeAnalogue':analogue,'candidateEntryPoint':entry,'facts':['Rust computes argument/usage/stream/exit and migration decisions; the installed SDK uses existing native validation, graph, registry, file and workspace operations. Catalog projection preserves member order, warning order, duplicate entity Map semantics, optional undefined fields and shared caller-visible provenance. The candidate imports no MetaMap runtime.','All 104 frozen original CLI processes match exit codes, stdout/stderr and complete file effects; all 70 frozen migration values/errors/member-order controls match. One unchanged original migration callback and seven additional bidirectional public declaration comparisons pass. Transport regressions cover nonfinite depth validation and migrated optional undefined graph fields.'], 'unresolved':'Remaining original CLI workflows, exhaustive option combinations and error/filesystem/concurrency/resource behavior, arbitrary JavaScript values/prototypes/accessors/coercions, nominal class/package compatibility and real Linux x86_64/ARM64 remain unverified. These finite observations do not establish full exported-contract parity.','acceptance':'Preserve original contracts and independently compare remaining original cases, documented options, installed packages and platform behavior. Expose disconfirming cases and real deviations for explicit disposition.'})
p=root/'fixtures/parity/legacy-cli-classification.json';assert not p.exists();write(p,review)
for row in review['rows']:
 target=by[row['id']];assert target['status']=='unclassified';target.update({'status':'implemented-unverified','candidateEvidence':[],'nativeAnalogue':row['nativeAnalogue'],'candidateEntryPoint':row['candidateEntryPoint'],'classification':{'path':p.relative_to(root).as_posix(),'digest':sha(p.read_bytes())}})
write(root/'fixtures/parity/coverage.json',coverage)
commands_run=[]
def check(label,command,allowed=(0,)):
 result=subprocess.run(list(map(str,command)),cwd=root,text=True,capture_output=True)
 (out/(label+'.stdout.log')).write_text(result.stdout);(out/(label+'.stderr.log')).write_text(result.stderr)
 commands_run.append({'label':label,'command':list(map(str,command)),'exitCode':result.returncode})
 assert result.returncode in allowed,(label,result.returncode,result.stdout[-1000:],result.stderr[-1500:])
 return result
ledger=json.loads(check('strict-ledger',[sys.executable,'-B','scripts/parity/verify.py','--strict'],(1,)).stdout)
assert ledger['currentVerifiedEquivalent']==112 and not ledger['invalidEvidence'] and not ledger['strictAcceptance']
assert ledger['counts']=={'verified-equivalent':112,'missing':28,'implemented-unverified':118,'unclassified':1035}
checkpoint=out/'receipt.json';refresh=functional.relative_to(root).as_posix()
readme=root/'README.md';text=readme.read_text();old=next(line for line in text.splitlines() if 'The [latest supervised refresh]' in line)
text=text.replace(old,old[:old.index('The [latest supervised refresh]')]+f'The [latest supervised refresh]({refresh}) passes Clippy, 180 portable Rust tests, 112 selected unchanged original cases, 57 individually refused installed negative type controls and 101 mapped declarations, plus public registry/graph/adapter interfaces with explicit registry and fluent-this substitutions. All 104 frozen CLI process comparisons and 70 source migration controls match. The 59 frozen workspace controls, 28 installed workflow observations and prior config/correspondence/reference/report/digest/pack/registry/graph/composition/validation controls pass; seven-provider discovery and nine scientific boundaries also pass. Full public/domain/package/platform parity remains unresolved.')
paragraph='The compatibility entry implements `validate`, `diff`, `trace`, `authority`, `generate`, `check` and `migrate-sources`. Run the installed entry with the Rust launcher: `patamaps legacy run --node /absolute/path/to/node --entry /absolute/path/to/installed/sdk/cli.mjs -- validate graph.json`. The SDK package also declares the `patamaps-compat` entry, which takes `--native /absolute/path/to/patamaps` before the original arguments. Rust decides arguments, diagnostics, graph results and output bytes; Node transports the SDK calls. Generation/checking additionally use the optional licensed discovery providers. The SDK exposes `isLegacySourceOfTruthDocument` and `adaptLegacySourcesOfTruth`. The [CLI/migration review](fixtures/parity/legacy-cli-classification.json) records remaining contracts, including the other 15 original commands.\n\n'
assert paragraph not in text;text=text.replace('The native compatibility workspace API',paragraph+'The native compatibility workspace API',1);readme.write_text(text)
plan=root/'BUILD_PLAN.md';text=plan.read_text();old=next(line for line in text.splitlines() if line.startswith('The [candidate ledger]'))
text=text.replace(old,f'The [candidate ledger](fixtures/parity/coverage.json) classifies **112 current original cases as equivalent, 28 complete public contracts as missing, 118 as implemented but unverified, and 1,035 obligations as unclassified**. The [latest supervised refresh]({refresh}) passes Clippy, 180 portable Rust tests, 57 individually refused installed negative type controls, 101 mapped declarations and public registry/graph/adapter interfaces with explicit substitutions. All 104 CLI process comparisons, 70 source migration controls, 59 workspace controls, 28 installed workflow observations and prior component controls pass, along with 112 unchanged original callbacks, seven discovery providers and nine scientific boundaries. Current original-case evidence has no invalid entries. Strict acceptance remains false. The [CLI/migration review](fixtures/parity/legacy-cli-classification.json) and existing reviews retain complete-contract gaps. No P0–P9 gate is closed.')
paragraph=f'2026-10-12 CLI/migration progress: Rust now supplies seven original CLI argument and output workflows, native source-catalog migration, direct mandatory JSON reads and direct writes, with an installed SDK entry launched by the native binary. All 104 frozen process comparisons preserve exact exit codes, streams and file effects, including failed-write warnings, valid graph tracing/authority/diffs and generation/check drift. All 70 migration controls and the unchanged original migration callback pass. Two disconfirming original cases drove transport fixes: nonfinite depth values reach native validation in the original order, and optional undefined graph fields reach native shape/semantic validation without mutating caller objects. Seven additional public declarations pass bidirectional comparison. The [current CLI checkpoint]({checkpoint.relative_to(root).as_posix()}) binds all current source and refreshed component evidence. The other 15 original CLI workflows, full accepted domains, examples, generated helper interfaces, governance/projection/replay/inspection contracts, package replacement and fresh real Linux x86_64/ARM64 checks remain open. No additional deletion or VM recreation occurred.\n\n'
text=text.replace('### Observed gaps and audit targets',paragraph+'### Observed gaps and audit targets',1);plan.write_text(text)
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
receipt={'schemaVersion':'1.0.0','status':'scoped-checks-passed-full-parity-open','goalStatus':'active','createdAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commands':commands_run,'ledger':ledger,'currentSourceMatchesBinary':True,'candidateEngine':engine,'candidateBinaryDigest':data['binaryDigest'],'functionalRun':refresh,'functionalRunDigest':sha(functional.read_bytes()),'functionalEvidence':evidence,'verifiedScopes':verified,'frozenReferenceBlobsVerified':len(supplement['referenceTree']),'sourceInventory':[{'path':p.relative_to(root).as_posix(),'digest':sha(p.read_bytes())} for p in sorted(set(files)) if p.is_file()],'previousPassedCheckpoint':old_checkpoint,'scope':'Seven compatibility CLI workflows and source-catalog migration with current source-bound scoped checks. Full parity remains open; no owner deviation accepted. All prior records and failures retained. No additional deletion or VM recreation.','nextRequiredWork':'Complete the other 15 CLI workflows and original semantic/provenance/projection/generated helper/governance/inspection/adapter/example contracts, full accepted domains, installed distributions and fresh real Linux x86_64/ARM64 acceptance.','retainedRepairAndPriorRunReceipts':[read(root/'.tools/parity/current-cli-repair.json')['output']], 'driverDigest':sha(pathlib.Path(__file__).read_bytes())}
write(checkpoint,receipt);write(root/'.tools/parity/storage-review/current-source-checkpoint.json',{'path':checkpoint.relative_to(root).as_posix()})
p=root/'docs/acceptance/parity/approved-cache-rebuild-2026-10-12T11-36-09.099744Z/receipt.json';record=read(p);record.update({'latestSourceCheckpoint':checkpoint.relative_to(root).as_posix(),'latestSourceCheckpointDigest':sha(checkpoint.read_bytes()),'latestSourceBuilt':True,'goalStatus':'active','fullParityAcceptance':False,'currentScopedVerification':verified,'currentLedger':ledger});write(p,record)
print(json.dumps({'status':receipt['status'],'receipt':checkpoint.relative_to(root).as_posix(),'sourceFiles':len(receipt['sourceInventory']),'verifiedScopes':verified,'ledgerCounts':ledger['counts'],'invalidEvidence':ledger['invalidEvidence'],'strictAcceptance':ledger['strictAcceptance']},indent=2),flush=True)
