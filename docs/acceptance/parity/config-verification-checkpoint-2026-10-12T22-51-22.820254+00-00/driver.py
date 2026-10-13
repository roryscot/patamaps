import ast,datetime,hashlib,json,pathlib,re,shutil,subprocess,sys
root=pathlib.Path.cwd();out=pathlib.Path(__file__).resolve().parent
sha=lambda raw:'sha256:'+hashlib.sha256(raw).hexdigest()
def read(p):return json.loads(p.read_bytes())
def write(p,value):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,indent=2)+'\n')
functional=root/read(root/'.tools/parity/current-config-functional-refresh.json')['output']/'receipt.json';data=read(functional)
assert data['status']=='passed' and len(data['commands'])==31 and all(c['exitCode']==0 for c in data['commands'])
assert next(c for c in data['commands'] if c['label']=='original-correspondence')['attachmentExitCode']==0
evidence_repair=root/read(root/'.tools/parity/current-config-evidence-repair.json')['output']/'receipt.json';repair=read(evidence_repair);assert repair['status']=='passed' and repair['exitCode']==0 and repair['repairedVerifierDigest']==sha((root/'scripts/parity/verify.py').read_bytes())
evidence=data['functionalEvidence'];assert len(evidence)==29
verified={'portableRustTests':171,'originalCases':107,'installedNegativeTypeControls':48,'configTypeComparisons':19,'configParserCases':213,'configLoaderCases':12,'correspondenceTypeComparisons':16,'reportingTypeComparisons':9,'graphTypeComparisons':18,'originalTypeComparisons':11,'compositionTypeComparisons':3,'initialPackCases':159,'nestedPackCases':161,'loaderCases':22,'registryCases':35,'graphQueryCases':45,'compositionCases':36,'inheritedFactoryCases':1,'frozenGraphCases':472,'correspondenceCases':63,'referenceCases':253,'reportingCases':60,'uncheckedDigestCases':40,'utf16DigestCases':65,'discoveryProviders':7,'scientificBoundaryCases':9}
original_cases=0
for e in evidence:
 p=root/e['path'];raw=p.read_bytes();assert sha(raw)==e['digest'];record=json.loads(raw)
 assert record.get('status') in ['passed','matched','component-controls-passed','capabilities-matched'],(p,record.get('status'))
 if 'candidate' in record:
  assert record['candidate']['binaryDigest']==data['binaryDigest'] and record['candidate']['engine']==data['candidateEngine']
  for item in record['candidate'].get('sdkSourceInventory',[]):
   path=pathlib.Path(item['path']);source=root/('sdk/typescript' if len(path.parts)==1 else '')/path
   assert sha(source.read_bytes())==item['digest']
 if p.parent.name.startswith('sdk-consumer-'):
  assert record['negativeTypeControls']==48 and record['allNegativeControlsRefused']
  assert record['configDeclarationsCompared']==19 and record['configCorpus']['installedControls']==3
  assert record['correspondenceDeclarationsCompared']==16 and record['reportingDeclarationsCompared']==9
 if p.parent.name.startswith('native-'):
  for item in record['sourceInventory']:assert sha((root/item['path']).read_bytes())==item['digest']
  assert sum(int(n) for n in re.findall(r'test result: ok\. (\d+) passed;', (p.parent/'stdout.log').read_text()))==171
 original_cases+=record.get('counts',{}).get('originalCases',0)
assert original_cases==107
for prefix,count in [('config-controls-',225),('correspondence-controls-',63),('reference-controls-',253),('reporting-controls-',60),('digest-controls-',40),('digest-utf16-controls-',65)]:
 records=[read(root/e['path']) for e in evidence if pathlib.Path(e['path']).parent.name.startswith(prefix)]
 assert len(records)==1 and records[0]['counts']['cases']==records[0]['counts']['matched']==count
 if prefix=='config-controls-':
  record=records[0];p=root/next(e['path'] for e in evidence if pathlib.Path(e['path']).parent.name.startswith(prefix))
  assert record['driverDigest']==sha((root/'scripts/parity/config_contracts.mjs').read_bytes())==sha((p.parent/'driver.mjs').read_bytes())
  for item in record['loaderInputs']:assert sha((p.parent/item['path']).read_bytes())==item['digest']
old_checkpoint=read(root/'.tools/parity/storage-review/current-source-checkpoint.json')['path']
review_names=['registry-validation-classification.json','legacy-pack-type-classification.json','legacy-graph-classification.json','legacy-composition-classification.json','legacy-reporting-classification.json','legacy-correspondence-classification.json']
mutable=['README.md','BUILD_PLAN.md','fixtures/parity/coverage.json','.tools/parity/storage-review/current-source-checkpoint.json','docs/acceptance/parity/approved-cache-rebuild-2026-10-12T11-36-09.099744Z/receipt.json']+['fixtures/parity/'+name for name in review_names]
for name in mutable:
 p=out/'previous-current-records'/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,p)
for name in review_names:
 p=root/'fixtures/parity'/name;review=read(p);review['componentEvidence']=evidence
 # Keep old scoped facts and explicitly date the current source evidence.
 for row in review['rows']:
  row['currentVerification']='Current source refresh passes 171 portable Rust tests, Clippy, 107 unchanged original cases, 48 independently refused installed negative type controls, 76 mapped declaration comparisons plus public registry/graph interfaces and all prior finite component controls. Config parsing/loading now has scoped evidence; complete workspace/CLI/package/platform and arbitrary JavaScript/resource contracts remain unverified.'
 write(p,review)
mapping=read(root/'fixtures/parity/legacy-config-type-mapping.json')
review={'schemaVersion':'1.0.0','referenceEngine':'399747a4ad05a37cd8db1cedd53048fad2175be4','scope':'Rust workspace config parsing/loading, built-in and custom source/config/output/policy declarations. Complete exported contract remains unverified; no deviation accepted.','componentEvidence':evidence,'rows':[]}
for item in mapping['rows']:
 review['rows'].append({'id':item['id'],'name':item['referenceName'],'status':'implemented-unverified','nativeAnalogue':{'path':'crates/patamaps-scientific/src/legacy_config.rs','symbol':'parse_legacy_metamap_config / load_legacy_metamap_config_bytes'},'candidateEntryPoint':{'path':'sdk/typescript/legacy-validation.mjs','symbol':item['candidateName']},'facts':['Preserved config schema is compiled by the existing Rust validator and ordered AJV diagnostic adapter. Rust checks source IDs, SSSOM config and correspondence IDs/references in original order. SDK parser returns the caller object unchanged; asynchronous loading preserves key order, JSON.parse last-value behavior, UTF-8 replacement and UTF-16 repository roots.','All 213 frozen parser observations and 12 retained loader observations match complete results, messages, error names/codes and IO metadata; both native config regressions and all three original config callbacks pass unchanged. Nineteen strict installed declaration comparisons and three installed config samples/async paths/semantic refusal checks pass.','All 31 full-refresh commands pass, including 171 portable Rust tests, Clippy, 107 unchanged original cases and every one of 48 installed negative type controls. All original 610 Git blobs remain verified.'],'unresolved':'Full exported accepted-domain equivalence remains unverified: arbitrary JavaScript values/prototypes/accessors/coercions/nonfinite/hook behavior, supplemental error.report and stacks, exact resource-bound owner disposition, exhaustive filesystem/path edge behavior, published package identity, complete workspace/CLI/adapter/example integration and real Linux x86_64/ARM64. Finite controls and type assignability are scoped evidence only.','acceptance':'Execute complete original config/workspace/CLI/example workflows through installed Rust consumers; preserve accepted values/errors/types/filesystem effects, classify disconfirming inputs and verify required platforms.'})
config_review=root/'fixtures/parity/legacy-config-classification.json';write(config_review,review)
coverage=root/'fixtures/parity/coverage.json';overlay=read(coverage);byid={r['id']:r for r in overlay['rows']}
for name in review_names+['legacy-config-classification.json']:
 p=root/'fixtures/parity'/name;review=read(p)
 for row in review['rows']:
  current=byid[row['id']];assert current['status']!='verified-equivalent'
  current['status']=row['status'];current['candidateEntryPoint']=row.get('candidateEntryPoint',row['nativeAnalogue']);current['classification']={'path':p.relative_to(root).as_posix(),'digest':sha(p.read_bytes()),'reason':row['unresolved']}
write(coverage,overlay)
commands=[]
def check(label,command,allowed=(0,)):
 result=subprocess.run(command,cwd=root,text=True,capture_output=True)
 (out/(label+'.stdout.log')).write_text(result.stdout);(out/(label+'.stderr.log')).write_text(result.stderr)
 commands.append({'label':label,'command':list(map(str,command)),'exitCode':result.returncode})
 assert result.returncode in allowed,(label,result.returncode,result.stdout[-1000:],result.stderr[-1500:])
 return result
node='/Users/admin/.nvm/versions/node/v22.16.0/bin/node';cargo='/Users/admin/.cargo/bin/cargo'
ledger=json.loads(check('strict-ledger',[sys.executable,'-B','scripts/parity/verify.py','--strict'],(1,)).stdout)
assert ledger['currentVerifiedEquivalent']==107 and not ledger['invalidEvidence'] and not ledger['strictAcceptance']
assert ledger['counts']=={'verified-equivalent':107,'missing':28,'implemented-unverified':80,'unclassified':1078}
checkpoint=out/'receipt.json';write(checkpoint,{'status':'running','goalStatus':'active'})
refresh= functional.relative_to(root).as_posix()
readme=root/'README.md';text=readme.read_text();old=next(line for line in text.splitlines() if 'The [latest supervised refresh]' in line)
new=old[:old.index('The [latest supervised refresh]')]+f'The [latest supervised refresh]({refresh}) passes the rebuilt candidate, Clippy, 171 portable Rust tests, 48 individually refused installed negative type controls and 76 mapped declarations (including 19 config declarations), plus public registry/graph interfaces with explicit registry substitution. All 225 config parser/loader comparisons, 63 correspondence, 253 reference, 60 diff/report, 105 digest/UTF-16, 342 pack/file, 35 registry, 45 graph-query, 36 composition and one inherited-factory controls, 472 validation controls and 107 selected unchanged original cases pass. Seven-provider discovery and nine scientific boundary checks also pass. Complete original private nominal identity, accepted-domain, package and platform contracts remain unresolved.'
text=text.replace(old,new)
paragraph='The SDK exposes `parseLegacyMetamapConfig` and asynchronous `loadLegacyMetamapConfig` through the Rust config parser/loader. The preserved schema, exact ordered schema errors, source/correspondence uniqueness and source references, SSSOM validation and resolved paths match the scoped original observations. Parsed caller identity, UTF-16 strings, duplicate-key last values and UTF-8 file replacement are retained. The [config review](fixtures/parity/legacy-config-classification.json) records remaining JavaScript, filesystem, workspace/CLI, resource, package and platform gaps. Config parsing supplies no admitted generation.\n\n'
assert paragraph not in text;text=text.replace('The SDK exposes `materializeLegacyCorrespondences`',paragraph+'The SDK exposes `materializeLegacyCorrespondences`',1);readme.write_text(text)
plan=root/'BUILD_PLAN.md';text=plan.read_text();old=next(line for line in text.splitlines() if line.startswith('The [candidate ledger]'))
new=f'The [candidate ledger](fixtures/parity/coverage.json) classifies **107 current original cases as equivalent, 28 complete public contracts as missing, 80 as implemented but unverified, and 1,078 obligations as unclassified**. The [latest supervised refresh]({refresh}) passes the rebuilt source, Clippy, 171 portable Rust tests, 48 individually refused installed negative type controls, 76 mapped declarations and public registry/graph interfaces with explicit registry substitution. All 225 config parser/loader, 63 correspondence, 253 reference, 60 diff/report, 105 digest/UTF-16, 342 pack/file, 35 registry, 45 graph-query, 36 composition and one inherited-factory controls, 472 validation controls, 107 unchanged original cases, seven discovery providers and nine scientific boundaries pass. Current original-case evidence has no invalid entries. Strict acceptance remains false. The [config review](fixtures/parity/legacy-config-classification.json) and existing component reviews retain complete-contract gaps. No P0–P9 gate is closed.'
text=text.replace(old,new)
paragraph=f'2026-10-12 configuration progress: Rust now implements the original config parse/load workflow, sharing the existing portable-schema diagnostic adapter and SSSOM parser. All 213 frozen parser controls, 12 retained loader comparisons, two native regressions and three unchanged original config callbacks pass. The installed consumer compares 19 additional declarations and checks config identity, async resolved paths and semantic errors. The [current config checkpoint]({checkpoint.relative_to(root).as_posix()}) binds the source and full refresh. The earlier correspondence checkpoint above is historical. Complete arbitrary JavaScript/error/resource/filesystem, workspace/CLI/package and real Linux x86_64/ARM64 parity remain open. No further files were deleted and the VM disk was not recreated. Continue with workspace orchestration and complete accepted-domain/obligation/platform classification.\n\n'
text=text.replace('### Observed gaps and audit targets',paragraph+'### Observed gaps and audit targets',1);plan.write_text(text)
check('rust-format',[cargo,'fmt','--all','--','--check'])
js=['sdk/typescript/legacy-config.mjs','sdk/typescript/legacy-validation.mjs','scripts/parity/config_contracts.mjs','scripts/parity/original.mjs']
for name in js:check(pathlib.Path(name).stem+'-syntax',[node,'--check',name])
check('javascript-format',[node,str(root/'.tools/parity/oracles/399747a4ad05-p8pkt3pr/reference/node_modules/prettier/bin/prettier.cjs'),'--check',*js,'sdk/typescript/legacy-config.d.ts','sdk/typescript/legacy-validation.d.ts'])
check('diff-check',['git','diff','--check'])
check('source-integrity',[sys.executable,'-B','scripts/test_source_integrity.py','/Users/admin/dev/SEEDZ/metamap','--output',str(out/'source-integrity.json')])
for p in sorted((root/'scripts/parity').glob('*.py')):ast.parse(p.read_bytes(),filename=str(p))
supplement=read(root/'fixtures/parity/supplement.json');oracle=root/read(root/'.tools/parity/oracles/current.json')['source']
for item in supplement['referenceTree']:
 raw=(oracle/item['path']).read_bytes();assert hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()==item['gitBlob']
assert not (root/'.tools/linux-vm/disk.raw').exists()
files=sorted((root/'crates').rglob('*.rs'))+sorted((root/'crates').glob('*/Cargo.toml'))+sorted((root/'sdk/typescript').glob('*'))+sorted((root/'scripts/parity').glob('*.py'))+sorted((root/'scripts/parity').glob('*.mjs'))+sorted(p for p in (root/'vendor/icu_collator').rglob('*') if p.is_file())
files += [root/name for name in ['Cargo.toml','Cargo.lock','NOTICE','README.md','BUILD_PLAN.md']]+sorted((root/'fixtures/parity').glob('*'))+sorted((root/'fixtures/reference/schemas').glob('*.json'))
receipt={'schemaVersion':'1.0.0','status':'scoped-checks-passed-full-parity-open','goalStatus':'active','createdAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commands':commands,'ledger':ledger,'currentSourceMatchesBinary':True,'candidateEngine':data['candidateEngine'],'candidateBinaryDigest':data['binaryDigest'],'functionalRun':refresh,'functionalRunDigest':sha(functional.read_bytes()),'functionalEvidence':evidence,'evidenceRepair':{'path':evidence_repair.relative_to(root).as_posix(),'digest':sha(evidence_repair.read_bytes())},'verifiedScopes':verified,'frozenReferenceBlobsVerified':len(supplement['referenceTree']),'sourceInventory':[{'path':p.relative_to(root).as_posix(),'digest':sha(p.read_bytes())} for p in sorted(set(files)) if p.is_file()],'previousPassedCheckpoint':old_checkpoint,'scope':'Config parse/load and original declarations implemented and scoped controls verified. Full parity remains open; no owner deviation accepted. All prior records and failure observations retained. No additional deletion or VM recreation.','nextRequiredWork':'Complete workspace/CLI/adapter/examples integration, remaining semantics and all obligations, package identity and installed real Linux x86_64/ARM64 evidence.','retainedRepairAndPriorRunReceipts':['docs/acceptance/parity/config-controls-2026-10-12T22-45-18.800Z/receipt.json','docs/acceptance/parity/config-controls-2026-10-12T22-48-30.478Z/receipt.json','docs/acceptance/parity/config-repair-2026-10-12T22-41-40.737186+00-00/focused-2026-10-12T22-47-09.336017+00-00/receipt.json'],'driverDigest':sha(pathlib.Path(__file__).read_bytes())}
write(checkpoint,receipt);write(root/'.tools/parity/storage-review/current-source-checkpoint.json',{'path':checkpoint.relative_to(root).as_posix()})
p=root/'docs/acceptance/parity/approved-cache-rebuild-2026-10-12T11-36-09.099744Z/receipt.json';record=read(p);record.update({'latestSourceCheckpoint':checkpoint.relative_to(root).as_posix(),'latestSourceCheckpointDigest':sha(checkpoint.read_bytes()),'latestSourceBuilt':True,'goalStatus':'active','fullParityAcceptance':False,'currentScopedVerification':verified,'currentLedger':ledger});write(p,record)
print(json.dumps({'status':receipt['status'],'receipt':checkpoint.relative_to(root).as_posix(),'verifiedScopes':verified,'ledger':ledger},indent=2),flush=True)
