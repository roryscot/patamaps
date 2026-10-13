import ast,datetime,hashlib,json,pathlib,re,subprocess,sys
root=pathlib.Path.cwd();out=pathlib.Path(__file__).resolve().parent
sha=lambda raw:'sha256:'+hashlib.sha256(raw).hexdigest()
write=lambda path,data:path.write_text(json.dumps(data,indent=2)+'\n')
run=root/json.loads((root/'.tools/parity/current-digest-functional-refresh.json').read_bytes())['output'];functional=run/'receipt.json';data=json.loads(functional.read_bytes());assert data['status']=='passed'
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
sys.path.insert(0,str(root/'scripts/parity'))
from identity import identities
assert all(data['candidateEngine'][key]==value for key,value in identities(root).items())
upstream=json.loads((root/'vendor/icu_collator/PATAMAPS-UPSTREAM.json').read_bytes())
patched=[item['path'] for item in upstream['files'] if sha((root/'vendor/icu_collator'/item['path']).read_bytes())!=item['digest']]
assert patched==['src/comparison.rs','src/elements.rs'] and len(upstream['files'])==29
assert len([p for p in (root/'vendor/icu_collator').rglob('*') if p.is_file()])==31
evidence=data['functionalEvidence'];verified={'portableRustTests':161,'initialPackCases':159,'nestedPackCases':161,'loaderCases':22,'registryCases':35,'graphQueryCases':45,'inheritedFactoryCases':1,'frozenGraphCases':472,'originalCases':101,'installedNegativeTypeControls':29,'originalTypeComparisons':11,'graphTypeComparisons':18,'compositionTypeComparisons':3,'compositionCases':36,'uncheckedDigestCases':40,'utf16DigestCases':65,'vendoredCollatorFiles':31,'registryPublicMethodDeclarationComparison':True,'graphPublicInterfaceDeclarationComparison':True,'scientificBoundaryCases':9,'discoveryProviders':7}
for entry in evidence:
 raw=(root/entry['path']).read_bytes();assert sha(raw)==entry['digest'];record=json.loads(raw)
 if 'candidate' in record:
  assert record['candidate']['binaryDigest']==data['binaryDigest'];assert record['candidate']['engine']==data['candidateEngine']
  for item in record['candidate'].get('sdkSourceInventory',[]):
   sdk_path=pathlib.Path(item['path']);source=root/('sdk/typescript' if len(sdk_path.parts)==1 else '')/sdk_path
   assert sha(source.read_bytes())==item['digest']
 if entry['path'].split('/')[-2].startswith('native-'):
  for item in record['sourceInventory']:assert sha((root/item['path']).read_bytes())==item['digest']
  assert sum(int(n) for n in re.findall(r'test result: ok\. (\d+) passed;', (root/entry['path']).parent.joinpath('stdout.log').read_text()))==161
assert sum(json.loads((root/e['path']).read_bytes()).get('counts',{}).get('originalCases',0) for e in evidence)==101
for prefix,count in [('digest-controls-',40),('digest-utf16-controls-',65)]:
 matches=[json.loads((root/e['path']).read_bytes()) for e in evidence if pathlib.Path(e['path']).parent.name.startswith(prefix)]
 assert len(matches)==1 and matches[0]['counts']['cases']==matches[0]['counts']['matched']==count
before=out/'previous-current-records'
mutable=['README.md','BUILD_PLAN.md','fixtures/parity/coverage.json','fixtures/parity/registry-validation-classification.json','fixtures/parity/legacy-pack-type-classification.json','fixtures/parity/legacy-graph-classification.json','fixtures/parity/legacy-composition-classification.json','NOTICE','.tools/parity/storage-review/current-source-checkpoint.json','docs/acceptance/parity/approved-cache-rebuild-2026-10-12T11-36-09.099744Z/receipt.json']
for name in mutable:
 source=root/name
 if source.exists():
  target=before/name;target.parent.mkdir(parents=True,exist_ok=True)
  if not target.exists():target.write_bytes(source.read_bytes())
summary='The current digest refresh passes 161 portable Rust tests, Clippy, 29 installed negative type controls, 11 pack/context, 18 graph and three composition declaration comparisons with explicit public registry substitution. All 105 digest/UTF-16, 342 pack/file, 35 registry, 45 graph-query, 36 composition and one inherited-factory controls, 472 validation controls and 101 unchanged original cases pass. Finite evidence leaves complete accepted-domain, package and platform parity unresolved.'
for name in ['fixtures/parity/registry-validation-classification.json','fixtures/parity/legacy-pack-type-classification.json','fixtures/parity/legacy-graph-classification.json','fixtures/parity/legacy-composition-classification.json']:
 p=root/name;review=json.loads(p.read_bytes());review['componentEvidence']=evidence
 for row in review['rows']:
  row['facts']=[fact for fact in row['facts'] if not (fact.startswith('The current supervised build') or fact.startswith('The current digest refresh') or fact.startswith('The current graph refresh') or fact.startswith('The current composition refresh'))]
  row['facts'].append(summary)
 if name == 'fixtures/parity/registry-validation-classification.json':
  for row in review['rows']:
   if row['name']=='relationPackDigest':
    row['candidateEntryPoint']={'path':'sdk/typescript/legacy-validation.mjs','symbol':'digestLegacyRelationPack','native':'crates/patamaps-contracts/src/legacy_json.rs'}
    row['facts'].append('Rust now computes unchecked legacy stable JSON over retained source order and original UTF-16 units; the SDK supplies its observed locale. All 40 frozen digest and 65 UTF-16 controls match, including all 2,048 unpaired units, numeric enumeration, locale-equal key ties, duplicate positions and finite numeric formatting. Executable definitions keep JCS, and null dispatch reproduces TypeError. The vendored ICU4X patch is bound into compiled source identity. Complete arbitrary-JavaScript, exhaustive locale/data-version, package and platform parity remains open.')
    row['unresolved']='Complete arbitrary JavaScript/value/prototype/accessor serialization, exhaustive host locale/collation-data/version equivalence, resource-bound disposition, published package identity and required platform behavior remain unverified. The 105 finite digest controls do not close the complete export contract.'
 write(p,review)
coverage=root/'fixtures/parity/coverage.json';overlay=json.loads(coverage.read_bytes());byid={r['id']:r for r in overlay['rows']}
for name in ['fixtures/parity/registry-validation-classification.json','fixtures/parity/legacy-pack-type-classification.json','fixtures/parity/legacy-graph-classification.json','fixtures/parity/legacy-composition-classification.json']:
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
assert ledger['currentVerifiedEquivalent']==101 and not ledger['invalidEvidence'] and not ledger['strictAcceptance']
counts=ledger['counts'];print('ledger',counts,flush=True)
checkpoint=out/'receipt.json'
# A concrete checkpoint path exists before the documentation link audit.
write(checkpoint,{'status':'running','goalStatus':'active'})
readme=root/'README.md';text=readme.read_text();old=next(line for line in text.splitlines() if 'The [latest supervised refresh]' in line)
new=old[:old.index('The [latest supervised refresh]')]+f'The [latest supervised refresh]({functional.relative_to(root).as_posix()}) passes the rebuilt candidate, Clippy, 161 portable Rust tests, the installed SDK\'s 29 negative type controls, 11 original pack/context 18 graph and three composition declarations, and the public registry/graph interfaces. Graph registry properties/options use the separately compared public registry interface; original private nominal class identities remain unresolved. All 105 unchecked digest/UTF-16, 159 initial pack, 161 nested law/context/import, 22 file-loader, 35 registry, 45 graph-query, 36 composition and one inherited-factory controls, 472 graph validation controls and 101 selected unchanged original cases pass. The seven-provider discovery and nine scientific boundary checks also pass.'
text=text.replace(old,new)
needle='The asynchronous SDK `loadLegacyRelationPack(path)`'
paragraph='The SDK factory now exposes `LegacyGraph` through `legacy graph json`. Rust decides validation, fixed indexes, mapping selection, ordered n-ary neighbors, breadth-first traversal and fact-scoped authority observations. Retained SDK handles preserve caller identity and live field changes without renaming index keys. Empty relation filters select nothing, deep finite traces are supported, and delegation ambiguity terminates without granting authority. All four unchanged original graph cases pass. The [graph review](fixtures/parity/legacy-graph-classification.json) retains unresolved JavaScript/UTF-16/value, diagnostic, package-identity, resource and platform gaps. This query view supplies no admitted generation.\n\n'
if not any(line.startswith('The SDK factory now exposes `LegacyGraph`') for line in text.splitlines()):text=text.replace(needle,paragraph+needle)
composition_paragraph='The SDK factory exposes `composeLegacyDocuments` through `legacy compose json`. Rust decides original shard prerequisites, merge order, stable-value equivalence and conflicts. The result retains first caller objects and defers graph validation, including cross-shard references, to `LegacyGraph`. Native collation is supplied by [ICU4X 2.2.1](https://docs.rs/icu_collator/2.2.1/icu_collator/struct.Collator.html); the original runtime locale is explicit input, and complete collation-data/version equivalence remains open. The [composition review](fixtures/parity/legacy-composition-classification.json) records the remaining value, diagnostic, package and platform gaps.\n\n'
if composition_paragraph not in text:text=text.replace(needle,composition_paragraph+needle)
digest_paragraph='Unchecked legacy digest inputs now use the shared ordered JSON parser and [native UTF-16 collation patch](vendor/icu_collator/PATAMAPS-PATCH.md). JSON property order, numeric-index enumeration, locale-equal Unicode key ties, duplicate positions, finite numeric formatting and original UTF-16 units match the frozen controls. The SDK supplies its observed host locale; executable 2.0 keeps JCS. The patched complete patched dependency source is bound into the compiler identity. Full arbitrary-JavaScript and collation-data/version, package and platform equivalence remain open.\n\n'
if digest_paragraph not in text:text=text.replace(needle,digest_paragraph+needle)
readme.write_text(text)
plan=root/'BUILD_PLAN.md';text=plan.read_text();old=next(line for line in text.splitlines() if line.startswith('The [candidate ledger]'))
new=f'The [candidate ledger](fixtures/parity/coverage.json) classifies **101 current original cases as equivalent, {counts["missing"]} complete public contracts as missing, {counts["implemented-unverified"]} as implemented but unverified, and {counts["unclassified"]:,} obligations as unclassified**. The [latest supervised refresh]({functional.relative_to(root).as_posix()}) passes the rebuilt source, Clippy, 161 portable Rust tests, the installed SDK\'s 29 negative type controls, 11 pack/context, 18 graph and three composition declaration comparisons, plus public registry/graph interfaces with explicit registry substitution. All 105 digest/UTF-16, 342 pack/file, 35 registry, 45 graph-query, 36 composition and one inherited-factory controls, 472 frozen graph-validation controls, 101 unchanged original cases, seven discovery providers and nine scientific boundaries pass. Original-case evidence binds the current binary/source with no invalid evidence. Strict acceptance remains false. The [registry/validation review](fixtures/parity/registry-validation-classification.json), [pack type review](fixtures/parity/legacy-pack-type-classification.json) [graph review](fixtures/parity/legacy-graph-classification.json) and [composition review](fixtures/parity/legacy-composition-classification.json) retain complete-contract gaps. No P0–P9 gate is closed.'
text=text.replace(old,new)
append=f'2026-10-12 unchecked digest progress: Rust reuses the ordered JSON foundation for legacy stable JSON, retaining last-wins positions, numeric property enumeration, locale-equal key ties, finite number formatting and original UTF-16 strings. The SDK explicitly supplies its observed locale; executable 2.0 keeps JCS. A two-file ICU4X patch retains unpaired units as tagged input and original implicit collation weights without invalid Rust characters or new unsafe code. All 40 frozen original digest controls, 65 additional UTF-16 contexts including every unpaired unit, six native regressions and installed digest/refusal checks pass. The current refresh passes 161 portable Rust tests, Clippy and all 101 unchanged original cases. The [current digest checkpoint]({checkpoint.relative_to(root).as_posix()}) binds every vendored file, preserves failed 14/40 and 38/40 comparisons, compilation/source-fingerprint and installed fixture repairs, and confirms the rebuilt source. Full arbitrary JavaScript/value/locale/data-version, package and real Linux x86_64/ARM64 parity remain open; publishing Rust crates requires preserving the patched dependency. No additional deletion, registry publication, production activation or owner deviation occurred. Continue with remaining API/workflow and accepted-domain implementation, classification, packaging and real platform checks.\n\n'
text=text.replace(append,'')
text=text.replace('### Observed gaps and audit targets',append+'### Observed gaps and audit targets')
text=text.rstrip()+'\n'
plan.write_text(text)
check('rust-format',[cargo,'fmt','--all','--','--check'])
for name in ['sdk/typescript/legacy-graph.mjs','sdk/typescript/legacy-validation.mjs','sdk/typescript/legacy-composition.mjs','scripts/parity/composition_contracts.mjs','scripts/parity/graph_contracts.mjs','scripts/parity/original.mjs','scripts/parity/digest_contracts.mjs']:
 check(pathlib.Path(name).stem+'-syntax',[node,'--check',name])
check('javascript-format',[node,str(root/'.tools/parity/oracles/399747a4ad05-p8pkt3pr/reference/node_modules/prettier/bin/prettier.cjs'),'--check','sdk/typescript/legacy-graph.mjs','sdk/typescript/legacy-graph.d.ts','sdk/typescript/legacy-composition.mjs','sdk/typescript/legacy-composition.d.ts','sdk/typescript/legacy-validation.mjs','sdk/typescript/legacy-validation.d.ts','scripts/parity/graph_contracts.mjs','scripts/parity/original.mjs','fixtures/parity/graph-scenarios.mjs','scripts/parity/composition_contracts.mjs','fixtures/parity/composition-scenarios.mjs','scripts/parity/digest_contracts.mjs'])
check('diff-check',['git','diff','--check'])
check('source-integrity',[sys.executable,'-B','scripts/test_source_integrity.py','/Users/admin/dev/SEEDZ/metamap','--output',str(out/'source-integrity.json')])
for path in sorted((root/'scripts/parity').glob('*.py')):ast.parse(path.read_bytes(),filename=str(path))
pointer=json.loads((root/'.tools/parity/oracles/current.json').read_bytes());oracle=root/pointer['source'];supplement=json.loads((root/'fixtures/parity/supplement.json').read_bytes())
for item in supplement['referenceTree']:
 raw=(oracle/item['path']).read_bytes();assert hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()==item['gitBlob']
files=sorted((root/'crates').rglob('*.rs'))+sorted((root/'crates').glob('*/Cargo.toml'))+sorted((root/'sdk/typescript').glob('*'))+sorted((root/'scripts/parity').glob('*.py'))+sorted((root/'scripts/parity').glob('*.mjs'))
files += sorted(p for p in (root/'vendor/icu_collator').rglob('*') if p.is_file())
files += [root/name for name in ['Cargo.toml','Cargo.lock','fixtures/parity/coverage.json','fixtures/parity/legacy-graph-type-mapping.json','fixtures/parity/legacy-graph-classification.json','fixtures/parity/graph-controls.json','fixtures/parity/graph-scenarios.mjs','fixtures/parity/graph-selected-cases.json','fixtures/parity/legacy-composition-classification.json','fixtures/parity/composition-controls.json','fixtures/parity/composition-scenarios.mjs','fixtures/parity/composition-selected-cases.json','NOTICE','fixtures/parity/digest-controls.json','fixtures/parity/digest-utf16-controls.json']]
receipt={'schemaVersion':'1.0.0','status':'scoped-checks-passed-full-parity-open','goalStatus':'active','createdAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commands':commands,'ledger':ledger,'currentSourceMatchesBinary':True,'candidateEngine':data['candidateEngine'],'candidateBinaryDigest':data['binaryDigest'],'functionalRun':functional.relative_to(root).as_posix(),'functionalRunDigest':sha(functional.read_bytes()),'functionalEvidence':evidence,'verifiedScopes':verified,'frozenReferenceBlobsVerified':len(supplement['referenceTree']),'sourceInventory':[{'path':p.relative_to(root).as_posix(),'digest':sha(p.read_bytes())} for p in files if p.is_file()],'scope':'Unchecked digest progress and approved-deletion rebuild continue; no further files were deleted. Component/public-interface comparisons do not close complete accepted-domain/package/platform parity. Original source/expectations and prior evidence remain preserved.','nextRequiredWork':'Remaining API/workflow accepted-domain repair and complete obligation classification, complete package/export evidence and installed real Linux x86_64/ARM64 acceptance. No owner deviation is accepted.','retainedFocusedFailures':['docs/acceptance/parity/digest-controls-2026-10-12T20-43-48.338Z/receipt.json','docs/acceptance/parity/digest-controls-2026-10-12T20-48-00.960Z/receipt.json','docs/acceptance/parity/digest-repair-2026-10-12T20-43-56.914555+00-00/focused-receipt.json','docs/acceptance/parity/digest-repair-2026-10-12T20-43-56.914555+00-00/native-surrogate-repair/focused-receipt.json','docs/acceptance/parity/digest-functional-refresh-2026-10-12T20-59-53.294259+00-00/receipt.json','docs/acceptance/parity/digest-functional-refresh-2026-10-12T21-03-33.869797+00-00/receipt.json'],'buildRepairRecords':['/Users/admin/Documents/Codex/.storage-control/heavy-builds/runs/285457ab-ed2b-492a-99e8-e7eead85c00e/run.json','/Users/admin/Documents/Codex/.storage-control/heavy-builds/runs/b3a09d81-8cca-4bac-a208-b007129fdc82/run.json','/Users/admin/Documents/Codex/.storage-control/heavy-builds/runs/046edcfb-da1c-480b-8423-e20e40d19991/run.json','/Users/admin/Documents/Codex/.storage-control/heavy-builds/runs/6e3c5fb6-351b-4314-a76d-5446d6a8bbf0/run.json','/Users/admin/Documents/Codex/.storage-control/heavy-builds/runs/36bb5542-90f6-4f14-ab59-ec111c20a00d/run.json'],'driverDigest':sha(pathlib.Path(__file__).read_bytes())}
write(checkpoint,receipt)
write(root/'.tools/parity/storage-review/current-source-checkpoint.json',{'path':checkpoint.relative_to(root).as_posix()})
work=root/'docs/acceptance/parity/approved-cache-rebuild-2026-10-12T11-36-09.099744Z/receipt.json';record=json.loads(work.read_bytes());record.update({'latestSourceCheckpoint':checkpoint.relative_to(root).as_posix(),'latestSourceCheckpointDigest':sha(checkpoint.read_bytes()),'latestSourceBuilt':True,'goalStatus':'active','fullParityAcceptance':False,'currentScopedVerification':verified,'currentLedger':ledger});write(work,record)
print(json.dumps({'status':receipt['status'],'receipt':checkpoint.relative_to(root).as_posix(),'verifiedScopes':verified,'ledger':ledger},indent=2),flush=True)
