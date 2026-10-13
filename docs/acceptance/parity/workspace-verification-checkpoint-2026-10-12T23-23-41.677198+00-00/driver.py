import ast,datetime,hashlib,json,pathlib,re,shutil,subprocess,sys
root=pathlib.Path.cwd();out=pathlib.Path(__file__).resolve().parent
sha=lambda raw:'sha256:'+hashlib.sha256(raw).hexdigest()
def read(p):return json.loads(p.read_bytes())
def write(p,value):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,indent=2)+'\n')
functional=root/read(root/'.tools/parity/current-workspace-functional-refresh.json')['output']/'receipt.json';data=read(functional)
assert data['status']=='passed' and len(data['commands'])==35 and all(c['exitCode']==0 for c in data['commands'])
assert next(c for c in data['commands'] if c['label']=='original-correspondence')['attachedObligationsVerified']
evidence=data['functionalEvidence'];assert len(evidence)==33
verified={'portableRustTests':176,'originalCases':111,'installedNegativeTypeControls':53,'configTypeComparisons':19,'workspaceTypeComparisons':18,'workspaceAssemblyCases':59,'workspaceWorkflowObservations':28,'configParserCases':213,'configLoaderCases':12,'correspondenceTypeComparisons':16,'reportingTypeComparisons':9,'graphTypeComparisons':18,'originalTypeComparisons':11,'compositionTypeComparisons':3,'initialPackCases':159,'nestedPackCases':161,'loaderCases':22,'registryCases':35,'graphQueryCases':45,'compositionCases':36,'inheritedFactoryCases':1,'frozenGraphCases':472,'correspondenceCases':63,'referenceCases':253,'reportingCases':60,'uncheckedDigestCases':40,'utf16DigestCases':65,'discoveryProviders':7,'scientificBoundaryCases':9}
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
  assert record['negativeTypeControls']==53 and record['allNegativeControlsRefused']
  assert record['workspaceTypeContractComparison']['mappedDeclarations']==18
  assert record['configDeclarationsCompared']==19 and record['configCorpus']['installedControls']==3
  assert record['correspondenceDeclarationsCompared']==16 and record['reportingDeclarationsCompared']==9
 if p.parent.name.startswith('native-'):
  for item in record['sourceInventory']:assert sha((root/item['path']).read_bytes())==item['digest']
  assert sum(int(n) for n in re.findall(r'test result: ok\. (\d+) passed;', (p.parent/'stdout.log').read_text()))==176
 original_cases+=record.get('counts',{}).get('originalCases',0)
assert original_cases==111
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
old_checkpoint=read(root/'.tools/parity/storage-review/current-source-checkpoint.json')['path']
review_names=['registry-validation-classification.json','legacy-pack-type-classification.json','legacy-graph-classification.json','legacy-composition-classification.json','legacy-reporting-classification.json','legacy-correspondence-classification.json','legacy-config-classification.json']
mutable=['README.md','BUILD_PLAN.md','fixtures/parity/coverage.json','.tools/parity/storage-review/current-source-checkpoint.json','docs/acceptance/parity/approved-cache-rebuild-2026-10-12T11-36-09.099744Z/receipt.json']+['fixtures/parity/'+name for name in review_names]
for name in mutable:
 p=out/'previous-current-records'/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,p)
for name in review_names:
 p=root/'fixtures/parity'/name;review=read(p);review['componentEvidence']=evidence
 # Keep old scoped facts and explicitly date the current source evidence.
 for row in review['rows']:
  row['currentVerification']='Current source refresh passes 176 portable Rust tests, Clippy, 111 unchanged original cases, 53 independently refused installed negative type controls, 94 mapped declaration comparisons and public registry/graph/adapter interfaces with explicit registry and fluent-this substitutions. Workspace has 59 frozen assembly controls and 28 complete installed pipeline observations. Complete CLI/package/platform and arbitrary JavaScript/resource/filesystem contracts remain unverified.'
 write(p,review)
mapping=read(root/'fixtures/parity/legacy-workspace-type-mapping.json')
review={'schemaVersion':'1.0.0','referenceEngine':'399747a4ad05a37cd8db1cedd53048fad2175be4','scope':'Rust legacy workspace observations and ordered adapter registry, with licensed provider callbacks and native file transport. Full exported contracts remain unverified; no deviation accepted.','componentEvidence':evidence,'rows':[]}
for item in mapping['rows']:
 review['rows'].append({'id':item['id'],'name':item['referenceName'],'status':'implemented-unverified','nativeAnalogue':{'path':'crates/patamaps-core/src/legacy_workspace.rs','symbol':'legacy_workspace_request'},'candidateEntryPoint':{'path':'sdk/typescript/legacy-workspace.mjs','symbol':item['candidateName']},'facts':['Rust reuses composition, correspondence, validation, digests and reporting for workspace assembly/snapshots/checks/cache/output decisions and adapter registry ordering/refusals. The SDK preserves caller objects and adapter callback receiver/configuration/context identities. Native filesystem transport retains UTF-16 path resolution and Node UTF-8 write replacement. Seven licensed providers are supplied by an optional package without a MetaMap runtime.','All 59 frozen pure workspace controls and 28 original-installed workflow observations match complete results and exact output/cache bytes. The original workspace callback and all three adapter-registry callbacks pass unchanged. Eighteen mapped public declaration comparisons, installed custom registry/assembly and 53 individually refused negative controls pass. Public registry substitution includes the original fluent-this return, whose private nominal class identity is outside the comparison.','The current 35-command refresh passes Clippy, 176 portable Rust tests, 111 unchanged original callbacks and all prior finite controls. All 610 pinned original source blobs are verified.'],'unresolved':'Full exported accepted-domain equivalence remains unverified: arbitrary JavaScript values/prototypes/accessors/coercion/hooks/nonfinite values, exact private nominal class identity, supplemental error.report/stacks, native resource bounds and owner dispositions, exhaustive filesystem/path/error/concurrency behavior, package replacement, remaining CLI/adapters/examples and real Linux x86_64/ARM64. These finite observations supply scoped evidence only.','acceptance':'Execute remaining original workspace/CLI/examples through installed Rust consumers, preserve values/errors/types/filesystem effects and callback semantics, classify disconfirming inputs, disposition real deviations explicitly and verify required platforms.'})
write(root/'fixtures/parity/legacy-workspace-classification.json',review)
coverage=read(root/'fixtures/parity/coverage.json')
for name in review_names+['legacy-workspace-classification.json']:
 p=root/'fixtures/parity'/name;review=read(p)
 for item in review['rows']:
  row=next(row for row in coverage['rows'] if row['id']==item['id']);row['status']=item['status'];row['nativeAnalogue']=item['nativeAnalogue'];row['candidateEntryPoint']=item.get('candidateEntryPoint',item['nativeAnalogue']);row['classification']={'path':p.relative_to(root).as_posix(),'digest':sha(p.read_bytes())}
write(root/'fixtures/parity/coverage.json',coverage)
commands=[]
def check(label,command,allowed=(0,)):
 result=subprocess.run(command,cwd=root,text=True,capture_output=True)
 (out/(label+'.stdout.log')).write_text(result.stdout);(out/(label+'.stderr.log')).write_text(result.stderr)
 commands.append({'label':label,'command':list(map(str,command)),'exitCode':result.returncode})
 assert result.returncode in allowed,(label,result.returncode,result.stdout[-1000:],result.stderr[-1500:])
 return result
node='/Users/admin/.nvm/versions/node/v22.16.0/bin/node';cargo='/Users/admin/.cargo/bin/cargo'
ledger=json.loads(check('strict-ledger',[sys.executable,'-B','scripts/parity/verify.py','--strict'],(1,)).stdout)
assert ledger['currentVerifiedEquivalent']==111 and not ledger['invalidEvidence'] and not ledger['strictAcceptance']
assert ledger['counts']=={'verified-equivalent':111,'missing':28,'implemented-unverified':98,'unclassified':1056}
checkpoint=out/'receipt.json';write(checkpoint,{'status':'running','goalStatus':'active'})
refresh= functional.relative_to(root).as_posix()
readme=root/'README.md';text=readme.read_text();old=next(line for line in text.splitlines() if 'The [latest supervised refresh]' in line)
new=old[:old.index('The [latest supervised refresh]')]+f'The [latest supervised refresh]({refresh}) passes Clippy, 176 portable Rust tests, 111 selected unchanged original cases, 53 individually refused installed negative type controls and 94 mapped declarations, plus public registry/graph/adapter interfaces with explicit registry and fluent-this substitutions. All 59 frozen workspace assembly and 28 complete installed workflow observations match, including generation, cache reuse, drift, callbacks and exact output bytes. All prior 225 config, 63 correspondence, 253 reference, 60 diff/report, 105 digest/UTF-16, 342 pack/file, 35 registry, 45 graph-query, 36 composition, one inherited-factory and 472 validation controls pass; seven-provider discovery and nine scientific boundaries also pass. Full public/domain/package/platform parity remains unresolved.'
text=text.replace(old,new)
paragraph='The native compatibility workspace API now exposes discovery, assembly, snapshots, baseline checks, output writes and adapter registries. Rust computes graph/cache/diff/report decisions and performs file transport; the optional `patamaps-discovery-draft` package supplies the seven licensed built-in adapters. Consumer adapters retain callback receiver and configuration/context identity. Checking preserves the baseline; writing the four configured outputs is explicit. Pass `{useCache: false, writeCache: false}` for discovery without cache writes. The [workspace review](fixtures/parity/legacy-workspace-classification.json) retains full-contract gaps. This workflow observes legacy graphs and does not activate a native generation.\n\n'
assert paragraph not in text;text=text.replace('The SDK exposes `parseLegacyMetamapConfig`',paragraph+'The SDK exposes `parseLegacyMetamapConfig`',1);readme.write_text(text)
plan=root/'BUILD_PLAN.md';text=plan.read_text();old=next(line for line in text.splitlines() if line.startswith('The [candidate ledger]'))
new=f'The [candidate ledger](fixtures/parity/coverage.json) classifies **111 current original cases as equivalent, 28 complete public contracts as missing, 98 as implemented but unverified, and 1,056 obligations as unclassified**. The [latest supervised refresh]({refresh}) passes Clippy, 176 portable Rust tests, 53 individually refused installed negative type controls, 94 mapped declarations and public registry/graph/adapter interfaces with explicit substitutions. All 59 frozen workspace controls, 28 installed workflow observations and prior component controls pass, along with 111 unchanged original callbacks, seven discovery providers and nine scientific boundaries. Current original-case evidence has no invalid entries. Strict acceptance remains false. The [workspace review](fixtures/parity/legacy-workspace-classification.json) and existing component reviews retain complete-contract gaps. No P0–P9 gate is closed.'
text=text.replace(old,new)
paragraph=f'2026-10-12 workspace progress: Rust now computes the original workspace assembly, adapter registry, cache keys/hits/entries, snapshot, baseline diff and output content, reusing existing engines. Native file transport preserves observed JSON/UTF-8/UTF-16 behavior. The SDK retains callback and caller object identities and connects the optional licensed seven-provider package. All 59 frozen assembly controls, 28 complete installed workflow observations, five additional Rust regressions and four unchanged original workspace/adapter-registry callbacks pass. Eighteen additional public declarations receive bidirectional comparisons with explicit public registry and fluent-this substitution. The [current workspace checkpoint]({checkpoint.relative_to(root).as_posix()}) binds the source and full refresh; earlier checkpoints remain historical. Complete arbitrary JavaScript/error/resource/filesystem, CLI/package and real Linux x86_64/ARM64 parity remain open. No files were deleted and the VM disk was not recreated during this workspace phase. Continue with CLI/adapter/example integration and complete accepted-domain/obligation/platform classification.\n\n'
text=text.replace('### Observed gaps and audit targets',paragraph+'### Observed gaps and audit targets',1);plan.write_text(text)
check('rust-format',[cargo,'fmt','--all','--','--check'])
js=['sdk/typescript/legacy-workspace.mjs','sdk/typescript/legacy-validation.mjs','adapters/discovery/index.mjs','scripts/parity/workspace_contracts.mjs','scripts/parity/original.mjs']
for name in js:check(pathlib.Path(name).stem+'-syntax',[node,'--check',name])
check('javascript-format',[node,str(root/'.tools/parity/oracles/399747a4ad05-p8pkt3pr/reference/node_modules/prettier/bin/prettier.cjs'),'--check',*js,'sdk/typescript/legacy-workspace.d.ts','sdk/typescript/legacy-validation.d.ts'])
check('diff-check',['git','diff','--check'])
check('source-integrity',[sys.executable,'-B','scripts/test_source_integrity.py','/Users/admin/dev/SEEDZ/metamap','--output',str(out/'source-integrity.json')])
for p in sorted((root/'scripts/parity').glob('*.py')):ast.parse(p.read_bytes(),filename=str(p))
supplement=read(root/'fixtures/parity/supplement.json');oracle=root/read(root/'.tools/parity/oracles/current.json')['source']
for item in supplement['referenceTree']:
 raw=(oracle/item['path']).read_bytes();assert hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()==item['gitBlob']
assert not (root/'.tools/linux-vm/disk.raw').exists()
files=sorted((root/'crates').rglob('*.rs'))+sorted((root/'crates').glob('*/Cargo.toml'))+sorted((root/'sdk/typescript').glob('*'))+sorted(p for p in (root/'scripts/parity').glob('*') if p.is_file())+sorted(p for p in (root/'adapters/discovery').rglob('*') if p.is_file())+sorted(p for p in (root/'vendor/icu_collator').rglob('*') if p.is_file())
files += [root/name for name in ['Cargo.toml','Cargo.lock','NOTICE','README.md','BUILD_PLAN.md']]+sorted((root/'fixtures/parity').glob('*'))+sorted((root/'fixtures/reference/schemas').glob('*.json'))
receipt={'schemaVersion':'1.0.0','status':'scoped-checks-passed-full-parity-open','goalStatus':'active','createdAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commands':commands,'ledger':ledger,'currentSourceMatchesBinary':True,'candidateEngine':data['candidateEngine'],'candidateBinaryDigest':data['binaryDigest'],'functionalRun':refresh,'functionalRunDigest':sha(functional.read_bytes()),'functionalEvidence':evidence,'verifiedScopes':verified,'frozenReferenceBlobsVerified':len(supplement['referenceTree']),'sourceInventory':[{'path':p.relative_to(root).as_posix(),'digest':sha(p.read_bytes())} for p in sorted(set(files)) if p.is_file()],'previousPassedCheckpoint':old_checkpoint,'scope':'Legacy workspace/cache/snapshot/check/output/registry and original public declarations implemented with scoped controls verified. Full parity remains open; no owner deviation accepted. All prior records and failure observations retained. No additional deletion or VM recreation.','nextRequiredWork':'Complete workspace/CLI/adapter/examples integration, remaining semantics and all obligations, package identity and installed real Linux x86_64/ARM64 evidence.','retainedRepairAndPriorRunReceipts':['docs/acceptance/parity/config-controls-2026-10-12T22-45-18.800Z/receipt.json','docs/acceptance/parity/config-controls-2026-10-12T22-53-30.478Z/receipt.json','docs/acceptance/parity/config-repair-2026-10-12T22-41-40.737186+00-00/focused-2026-10-12T22-47-09.336017+00-00/receipt.json'],'driverDigest':sha(pathlib.Path(__file__).read_bytes())}
write(checkpoint,receipt);write(root/'.tools/parity/storage-review/current-source-checkpoint.json',{'path':checkpoint.relative_to(root).as_posix()})
p=root/'docs/acceptance/parity/approved-cache-rebuild-2026-10-12T11-36-09.099744Z/receipt.json';record=read(p);record.update({'latestSourceCheckpoint':checkpoint.relative_to(root).as_posix(),'latestSourceCheckpointDigest':sha(checkpoint.read_bytes()),'latestSourceBuilt':True,'goalStatus':'active','fullParityAcceptance':False,'currentScopedVerification':verified,'currentLedger':ledger});write(p,record)
print(json.dumps({'status':receipt['status'],'receipt':checkpoint.relative_to(root).as_posix(),'verifiedScopes':verified,'ledger':ledger},indent=2),flush=True)
