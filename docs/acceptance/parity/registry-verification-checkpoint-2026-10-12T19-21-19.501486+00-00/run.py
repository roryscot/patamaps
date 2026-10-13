from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,subprocess,sys,ast,os,re
ROOT=Path('/Users/admin/dev/patamaps/patamaps');OUT=Path(__file__).resolve().parent
sha=lambda p:'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
functional=ROOT/json.loads((ROOT/'.tools/parity/current-registry-functional-refresh.json').read_text())['output']
record=json.loads((functional/'receipt.json').read_text());assert len(record['commands'])==17 and all(c['exitCode']==0 for c in record['commands'])
node='/Users/admin/.nvm/versions/node/v22.16.0/bin/node'
commands=[('rust-format',['/Users/admin/.cargo/bin/cargo','fmt','--all','--','--check'])]
commands += [(Path(p).stem+'-syntax',[node,'--check',p]) for p in ['sdk/typescript/legacy-registry.mjs','sdk/typescript/legacy-validation.mjs','scripts/parity/registry_contracts.mjs','scripts/parity/original.mjs']]
commands += [('javascript-format',[node,str(ROOT/'.tools/parity/oracles/399747a4ad05-p8pkt3pr/reference/node_modules/prettier/bin/prettier.cjs'),'--check','sdk/typescript/legacy-registry.mjs','sdk/typescript/legacy-validation.mjs','sdk/typescript/legacy-validation.d.ts','scripts/parity/registry_contracts.mjs','scripts/parity/original.mjs','fixtures/parity/registry-scenarios.mjs']),('diff-check',['git','diff','--check']),('source-integrity',[sys.executable,'-B','scripts/test_source_integrity.py','/Users/admin/dev/SEEDZ/metamap','--output',str(OUT/'source-integrity.json')]),('strict-ledger',[sys.executable,'-B','scripts/parity/verify.py','--strict'])]
receipt={'schemaVersion':'1.0.0','status':'running','goalStatus':'active','commands':[]}
(OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
for name,command in commands:
 result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
 for label,data in [('stdout',result.stdout),('stderr',result.stderr)]: (OUT/(name+'.'+label+'.log')).write_text(data)
 receipt['commands'].append({'name':name,'command':command,'exitCode':result.returncode,'logs':{label:{'path':str((OUT/(name+'.'+label+'.log')).relative_to(ROOT)),'digest':sha(OUT/(name+'.'+label+'.log'))} for label in ['stdout','stderr']}})
 print(name,result.returncode,flush=True)
 if name=='strict-ledger':
  ledger=json.loads(result.stdout);assert result.returncode==1 and ledger['currentVerifiedEquivalent']==95 and not ledger['invalidEvidence'] and not ledger['strictAcceptance'];receipt['ledger']=ledger
 else: assert result.returncode==0,result.stderr
for p in ['scripts/parity/sdk_consumer.py','scripts/parity/verify.py','scripts/parity/native.py']:ast.parse((ROOT/p).read_text())
supplement=json.loads((ROOT/'fixtures/parity/supplement.json').read_text());oracle=ROOT/json.loads((ROOT/'.tools/parity/oracles/current.json').read_text())['source']
for item in supplement['referenceTree']:
 raw=(oracle/item['path']).read_bytes();assert hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()==item['gitBlob']
corpus=json.loads((ROOT/'fixtures/parity/registry-controls.json').read_text());assert len(corpus['cases'])==35 and corpus['scenarioDigest']==sha(ROOT/'fixtures/parity/registry-scenarios.mjs') and corpus['referenceEngine']==supplement['referenceEngine']
sys.path.insert(0,str(ROOT/'scripts/parity'));from identity import identities
engine=json.loads(subprocess.check_output([str(ROOT/'target/debug/patamaps'),'engine']));assert all(engine[k]==v for k,v in identities(ROOT).items())
scopes={'portableRustTests':144,'initialPackCases':159,'nestedPackCases':161,'loaderCases':22,'registryCases':35,'frozenGraphCases':472,'originalCases':95,'installedNegativeTypeControls':20,'originalTypeComparisons':11,'registryPublicMethodDeclarationComparison':True,'scientificBoundaryCases':9,'discoveryProviders':7}
evidence=json.loads((OUT/'functional-evidence.json').read_text())['receipts']
for item in evidence:assert sha(ROOT/item['path'])==item['digest']
record.update({'status':'component-checks-passed','binaryDigest':sha(ROOT/'target/debug/patamaps'),'candidateEngine':engine,'ledger':ledger,'evidenceAttachmentRepair':{'verifiedBy':str((OUT/'strict-ledger.stdout.log').relative_to(ROOT)),'verifierDigest':sha(ROOT/'scripts/parity/verify.py'),'scope':'Native core-data loading happens once before callbacks and is explicitly verified as initialization. All selected case operations remain attributed to original callback names; prior attachment failure is retained.'},'functionalEvidence':evidence})
(functional/'receipt.json').write_text(json.dumps(record,indent=2)+'\n')
receipt.update({'status':'scoped-verification-passed-full-parity-incomplete','createdAt':datetime.now(timezone.utc).isoformat(),'currentSourceMatchesBinary':True,'candidateEngine':engine,'candidateBinaryDigest':sha(ROOT/'target/debug/patamaps'),'frozenReferenceBlobsVerified':len(supplement['referenceTree']),'runnerAstChecks':'passed','functionalRun':str((functional/'receipt.json').relative_to(ROOT)),'functionalRunDigest':sha(functional/'receipt.json'),'functionalEvidence':evidence,'verifiedScopes':scopes,'scope':'Current portable/installed/component and original-case checks. Full public contracts, JavaScript/value/diagnostic/resource/platform coverage, broad SDK/workflow implementation and fresh Linux acceptance remain required. No P0–P9 gate closes.','sourceInventory':[{'path':str(p.relative_to(ROOT)),'digest':sha(p)} for p in [*sorted((ROOT/'crates').rglob('*.rs')),*sorted((ROOT/'crates').glob('*/Cargo.toml')),ROOT/'Cargo.toml',ROOT/'Cargo.lock',*sorted((ROOT/'sdk/typescript').glob('*')),*[ROOT/p for p in ['scripts/parity/original.mjs','scripts/parity/registry_contracts.mjs','scripts/parity/verify.py','scripts/parity/sdk_consumer.py','fixtures/parity/registry-controls.json','fixtures/parity/registry-scenarios.mjs','fixtures/parity/registry-selected-cases.json']]] if p.is_file()],'driverDigest':sha(OUT/'run.py')})
(OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
pointer={'path':str((OUT/'receipt.json').relative_to(ROOT))}
(ROOT/'.tools/parity/storage-review/current-source-checkpoint.json').write_text(json.dumps(pointer,indent=2)+'\n')
(ROOT/'.tools/parity/current-verification-run.json').write_text(json.dumps({'output':str(OUT.relative_to(ROOT))},indent=2)+'\n')
workpath=ROOT/'docs/acceptance/parity/approved-cache-rebuild-2026-10-12T11-36-09.099744Z/receipt.json';work=json.loads(workpath.read_text());work.update({'status':receipt['status'],'latestSourceCheckpoint':pointer['path'],'latestSourceCheckpointDigest':sha(OUT/'receipt.json'),'latestSourceBuilt':True,'currentScopedVerification':scopes,'currentLedger':ledger});workpath.write_text(json.dumps(work,indent=2)+'\n')
print(json.dumps({'status':receipt['status'],'receipt':pointer['path'],'verifiedScopes':scopes,'ledger':ledger},indent=2))
