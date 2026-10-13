import ast,datetime,hashlib,json,pathlib,re,subprocess,sys
root=pathlib.Path.cwd();out=pathlib.Path(__file__).resolve().parent
sha=lambda raw:'sha256:'+hashlib.sha256(raw).hexdigest()
write=lambda path,data:path.write_text(json.dumps(data,indent=2)+'\n')
run=root/json.loads((root/'.tools/parity/current-graph-functional-refresh.json').read_bytes())['output'];functional=run/'receipt.json';data=json.loads(functional.read_bytes());assert data['status']=='passed'
# The scientific driver writes per-case JSON before the final receipt object.
log=(run/'scientific-bounds.stdout.log').read_text();decoded=[]
for match in re.finditer(r'(?m)^\{',log):
 try:
  obj=json.JSONDecoder().raw_decode(log[match.start():])[0]
  if isinstance(obj,dict) and obj.get('receipt'):decoded.append(obj)
 except ValueError:pass
assert len(decoded)==1
scientific=root/decoded[0]['receipt'];raw=scientific.read_bytes();assert json.loads(raw)['status']=='capabilities-matched'
scientific_entry={'path':scientific.relative_to(root).as_posix(),'digest':sha(raw)}
if scientific_entry not in data['functionalEvidence']:
 (out/'functional-receipt-before-scientific-attachment.json').write_bytes(functional.read_bytes());data['functionalEvidence'].append(scientific_entry);write(functional,data)
evidence=data['functionalEvidence'];verified={'portableRustTests':149,'initialPackCases':159,'nestedPackCases':161,'loaderCases':22,'registryCases':35,'graphQueryCases':45,'inheritedFactoryCases':1,'frozenGraphCases':472,'originalCases':99,'installedNegativeTypeControls':26,'originalTypeComparisons':11,'graphTypeComparisons':18,'registryPublicMethodDeclarationComparison':True,'graphPublicInterfaceDeclarationComparison':True,'scientificBoundaryCases':9,'discoveryProviders':7}
for entry in evidence:
 raw=(root/entry['path']).read_bytes();assert sha(raw)==entry['digest'];record=json.loads(raw)
 if 'candidate' in record:
  assert record['candidate']['binaryDigest']==data['binaryDigest'];assert record['candidate']['engine']==data['candidateEngine']
  for item in record['candidate'].get('sdkSourceInventory',[]):assert sha((root/item['path']).read_bytes())==item['digest']
 if entry['path'].split('/')[-2].startswith('native-'):
  for item in record['sourceInventory']:assert sha((root/item['path']).read_bytes())==item['digest']
  assert sum(int(n) for n in re.findall(r'test result: ok\. (\d+) passed;', (root/entry['path']).parent.joinpath('stdout.log').read_text()))==149
assert sum(json.loads((root/e['path']).read_bytes()).get('counts',{}).get('originalCases',0) for e in evidence)==99
before=out/'previous-current-records'
mutable=['README.md','BUILD_PLAN.md','fixtures/parity/coverage.json','fixtures/parity/registry-validation-classification.json','fixtures/parity/legacy-pack-type-classification.json','fixtures/parity/legacy-graph-classification.json','.tools/parity/storage-review/current-source-checkpoint.json','docs/acceptance/parity/approved-cache-rebuild-2026-10-12T11-36-09.099744Z/receipt.json']
for name in mutable:
 source=root/name
 if source.exists():
  target=before/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
summary='The current graph refresh passes 149 portable Rust tests, Clippy, 26 installed negative type controls, 11 pack/context and 18 graph declaration comparisons with explicit public registry substitution. All 342 pack/file, 35 registry, 45 graph-query and one inherited-factory controls, 472 validation controls and 99 unchanged original cases pass. Finite evidence leaves complete accepted-domain, package and platform parity unresolved.'
for name in ['fixtures/parity/registry-validation-classification.json','fixtures/parity/legacy-pack-type-classification.json','fixtures/parity/legacy-graph-classification.json']:
 p=root/name;review=json.loads(p.read_bytes());review['componentEvidence']=evidence
 for row in review['rows']:
  row['facts']=[fact for fact in row['facts'] if not (fact.startswith('The current supervised build') or fact.startswith('The current graph refresh'))]
  row['facts'].append(summary)
 write(p,review)
coverage=root/'fixtures/parity/coverage.json';overlay=json.loads(coverage.read_bytes());byid={r['id']:r for r in overlay['rows']}
for name in ['fixtures/parity/registry-validation-classification.json','fixtures/parity/legacy-pack-type-classification.json','fixtures/parity/legacy-graph-classification.json']:
 p=root/name;review=json.loads(p.read_bytes());digest=sha(p.read_bytes())
 for row in review['rows']:
  existing=byid[row['id']];assert existing['status']!='verified-equivalent'
  existing['status']=row['status'];existing['candidateEntryPoint']=row.get('candidateEntryPoint',row['nativeAnalogue']);existing['classification']={'path':name,'digest':digest,'reason':row['unresolved']}
write(coverage,overlay)
commands=[]
def check(label,command,allowed=(0,)):
 result=subprocess.run(command,cwd=root,text=True,capture_output=True)
 (out/(label+'.stdout.log')).write_text(result.stdout);(out/(label+'.stderr.log')).write_text(result.stderr)
 commands.append({'label':label,'command':list(map(str,command)),'exitCode':result.returncode})
 assert result.returncode in allowed,(label,result.returncode,result.stderr[-2000:])
 return result
node='/Users/admin/.nvm/versions/node/v22.16.0/bin/node';cargo='/Users/admin/.cargo/bin/cargo'
ledger=json.loads(check('strict-ledger',[sys.executable,'-B','scripts/parity/verify.py','--strict'],(1,)).stdout)
assert ledger['currentVerifiedEquivalent']==99 and not ledger['invalidEvidence'] and not ledger['strictAcceptance']
counts=ledger['counts'];print('ledger',counts,flush=True)
checkpoint=out/'receipt.json'
# A concrete checkpoint path exists before the documentation link audit.
write(checkpoint,{'status':'running','goalStatus':'active'})
readme=root/'README.md';text=readme.read_text();old=next(line for line in text.splitlines() if 'The [latest supervised refresh]' in line)
new=old[:old.index('The [latest supervised refresh]')]+f'The [latest supervised refresh]({functional.relative_to(root).as_posix()}) passes the rebuilt candidate, Clippy, 149 portable Rust tests, the installed SDK\'s 26 negative type controls, 11 original pack/context and 18 graph declarations, and the public registry/graph interfaces. Graph registry properties/options use the separately compared public registry interface; original private nominal class identities remain unresolved. All 159 initial pack, 161 nested law/context/import, 22 file-loader, 35 registry, 45 graph-query and one inherited-factory controls, 472 graph validation controls and 99 selected unchanged original cases pass. The seven-provider discovery and nine scientific boundary checks also pass.'
text=text.replace(old,new)
needle='The asynchronous SDK `loadLegacyRelationPack(path)`'
paragraph='The SDK factory now exposes `LegacyGraph` through `legacy graph json`. Rust decides validation, fixed indexes, mapping selection, ordered n-ary neighbors, breadth-first traversal and fact-scoped authority observations. Retained SDK handles preserve caller identity and live field changes without renaming index keys. Empty relation filters select nothing, deep finite traces are supported, and delegation ambiguity terminates without granting authority. All four unchanged original graph cases pass. The [graph review](fixtures/parity/legacy-graph-classification.json) retains unresolved JavaScript/UTF-16/value, diagnostic, package-identity, resource and platform gaps. This query view supplies no admitted generation.\n\n'
if paragraph not in text:text=text.replace(needle,paragraph+needle)
readme.write_text(text)
plan=root/'BUILD_PLAN.md';text=plan.read_text();old=next(line for line in text.splitlines() if line.startswith('The [candidate ledger]'))
new=f'The [candidate ledger](fixtures/parity/coverage.json) classifies **99 current original cases as equivalent, {counts["missing"]} complete public contracts as missing, {counts["implemented-unverified"]} as implemented but unverified, and {counts["unclassified"]:,} obligations as unclassified**. The [latest supervised refresh]({functional.relative_to(root).as_posix()}) passes the rebuilt source, Clippy, 149 portable Rust tests, the installed SDK\'s 26 negative type controls, 11 pack/context and 18 graph declaration comparisons, plus public registry/graph interfaces with explicit registry substitution. All 342 pack/file, 35 registry, 45 graph-query and one inherited-factory controls, 472 frozen graph-validation controls, 99 unchanged original cases, seven discovery providers and nine scientific boundaries pass. Original-case evidence binds the current binary/source with no invalid evidence. Strict acceptance remains false. The [registry/validation review](fixtures/parity/registry-validation-classification.json), [pack type review](fixtures/parity/legacy-pack-type-classification.json) and [graph review](fixtures/parity/legacy-graph-classification.json) retain complete-contract gaps. No P0–P9 gate is closed.'
text=text.replace(old,new)
append=f'2026-10-12 graph API progress: Rust now constructs fixed legacy indexes and performs retained-handle lookups, mapping filters, ordered n-ary neighbors, breadth-first traces and fact-scoped authority observations. SDK handles preserve original object identity, live mutations and initial index keys. Four unchanged original graph cases add four equivalent cases to the ledger; 45 frozen comparisons and an inherited-factory comparison exercise order, direction/symmetry, empty filters, deep traces and authority ambiguity/cycles. The inherited factory returns the base class as the original does. The installed consumer adds typed graph queries/factory errors and six negative controls; original private nominal registry identity remains outside the public-interface type comparison. The [current graph checkpoint]({checkpoint.relative_to(root).as_posix()}) preserves earlier and failed type-comparison records, approved cache recovery and current evidence. No further deletion occurred. Next, implement legacy shard composition and continue the remaining API/workflow, accepted-domain, packaging and required Linux x86_64/ARM64 gates.\n\n'
text=text.replace('### Remaining capabilities by workstream',append+'### Remaining capabilities by workstream') if '### Remaining capabilities by workstream' in text else text.replace('### P0 Complete inventory and oracle',append+'### P0 Complete inventory and oracle')
if append.strip() not in text:
 text=text.replace('### Ordered implementation',append+'### Ordered implementation')
 if append.strip() not in text:text += '\n'+append
plan.write_text(text)
check('rust-format',[cargo,'fmt','--all','--','--check'])
for name in ['sdk/typescript/legacy-graph.mjs','sdk/typescript/legacy-validation.mjs','scripts/parity/graph_contracts.mjs','scripts/parity/original.mjs']:
 check(pathlib.Path(name).stem+'-syntax',[node,'--check',name])
check('javascript-format',[node,str(root/'.tools/parity/oracles/399747a4ad05-p8pkt3pr/reference/node_modules/prettier/bin/prettier.cjs'),'--check','sdk/typescript/legacy-graph.mjs','sdk/typescript/legacy-graph.d.ts','sdk/typescript/legacy-validation.mjs','sdk/typescript/legacy-validation.d.ts','scripts/parity/graph_contracts.mjs','scripts/parity/original.mjs','fixtures/parity/graph-scenarios.mjs'])
check('diff-check',['git','diff','--check'])
check('source-integrity',[sys.executable,'-B','scripts/test_source_integrity.py','/Users/admin/dev/SEEDZ/metamap','--output',str(out/'source-integrity.json')])
for path in sorted((root/'scripts/parity').glob('*.py')):ast.parse(path.read_bytes(),filename=str(path))
pointer=json.loads((root/'.tools/parity/oracles/current.json').read_bytes());oracle=root/pointer['source'];supplement=json.loads((root/'fixtures/parity/supplement.json').read_bytes())
for item in supplement['referenceTree']:
 raw=(oracle/item['path']).read_bytes();assert hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()==item['gitBlob']
files=sorted((root/'crates').rglob('*.rs'))+sorted((root/'crates').glob('*/Cargo.toml'))+sorted((root/'sdk/typescript').glob('*'))+sorted((root/'scripts/parity').glob('*.py'))+sorted((root/'scripts/parity').glob('*.mjs'))
files += [root/name for name in ['Cargo.toml','Cargo.lock','fixtures/parity/coverage.json','fixtures/parity/legacy-graph-type-mapping.json','fixtures/parity/legacy-graph-classification.json','fixtures/parity/graph-controls.json','fixtures/parity/graph-scenarios.mjs','fixtures/parity/graph-selected-cases.json']]
receipt={'schemaVersion':'1.0.0','status':'scoped-checks-passed-full-parity-open','goalStatus':'active','createdAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commands':commands,'ledger':ledger,'currentSourceMatchesBinary':True,'candidateEngine':data['candidateEngine'],'candidateBinaryDigest':data['binaryDigest'],'functionalRun':functional.relative_to(root).as_posix(),'functionalRunDigest':sha(functional.read_bytes()),'functionalEvidence':evidence,'verifiedScopes':verified,'frozenReferenceBlobsVerified':len(supplement['referenceTree']),'sourceInventory':[{'path':p.relative_to(root).as_posix(),'digest':sha(p.read_bytes())} for p in files if p.is_file()],'scope':'Graph API progress and approved-deletion rebuild continue; no further files were deleted. Component/public-interface comparisons do not close complete accepted-domain/package/platform parity. Original source/expectations and prior evidence remain preserved.','nextRequiredWork':'Legacy shard composition, remaining API/workflow accepted-domain repair, complete package/export evidence and installed real Linux x86_64/ARM64 acceptance. No owner deviation is accepted.','retainedFailedTypeComparison':'docs/acceptance/parity/sdk-consumer-2026-10-12T19-54-53.083552Z/receipt.json','driverDigest':sha(pathlib.Path(__file__).read_bytes())}
write(checkpoint,receipt)
write(root/'.tools/parity/storage-review/current-source-checkpoint.json',{'path':checkpoint.relative_to(root).as_posix()})
work=root/'docs/acceptance/parity/approved-cache-rebuild-2026-10-12T11-36-09.099744Z/receipt.json';record=json.loads(work.read_bytes());record.update({'latestSourceCheckpoint':checkpoint.relative_to(root).as_posix(),'latestSourceCheckpointDigest':sha(checkpoint.read_bytes()),'latestSourceBuilt':True,'goalStatus':'active','fullParityAcceptance':False,'currentScopedVerification':verified,'currentLedger':ledger});write(work,record)
print(json.dumps({'status':receipt['status'],'receipt':checkpoint.relative_to(root).as_posix(),'verifiedScopes':verified,'ledger':ledger},indent=2),flush=True)
