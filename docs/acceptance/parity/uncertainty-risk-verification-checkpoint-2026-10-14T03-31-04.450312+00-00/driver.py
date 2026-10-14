import ast,hashlib,json,os,re,subprocess,sys
from pathlib import Path
root=Path.cwd();out=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'scripts/parity'))
from storage_guard import ensure_guarded
from identity import identities
ensure_guarded()
sha=lambda raw:'sha256:'+hashlib.sha256(raw).hexdigest(); rows=[]
env={**os.environ,'SDKROOT':'/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk','CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0'}
checks=[('rust-format',['/Users/admin/.cargo/bin/cargo','fmt','--all','--','--check']),('diff-whitespace',['git','diff','--check']),('sdk-format',['/Users/admin/.nvm/versions/node/v24.21.0/bin/node','.tools/parity/oracles/399747a4ad05-p8pkt3pr/reference/node_modules/prettier/bin/prettier.cjs','--check','sdk/typescript/canonical.mjs','sdk/typescript/legacy-viability.mjs','sdk/typescript/package.json','scripts/parity/viability_signed_zero.mjs','scripts/parity/legacy_validation.mjs','scripts/parity/viability_numeric.mjs','sdk/typescript/native-input.mjs','sdk/typescript/native-input-worker.mjs','sdk/typescript/legacy-validation.mjs','sdk/typescript/sssom.mjs','sdk/typescript/legacy-graph.mjs','sdk/typescript/legacy-viability.d.ts','sdk/typescript/legacy-validation.d.ts','scripts/parity/constraint_callbacks.mjs','scripts/parity/memory_activation.mjs','scripts/parity/original.mjs','sdk/typescript/legacy-semantic.mjs','sdk/typescript/legacy-semantic.d.ts','scripts/parity/semantic_validation.mjs','sdk/typescript/legacy-uncertainty-risk.mjs','sdk/typescript/legacy-uncertainty-risk.d.ts','scripts/parity/uncertainty_risk.mjs','README.md','BUILD_PLAN.md']),('strict-ledger',['/opt/homebrew/bin/python3','-B','scripts/parity/verify.py','--strict'])]
for label,command in checks:
 with (out/(label+'.stdout.log')).open('x') as stdout,(out/(label+'.stderr.log')).open('x') as stderr:
  result=subprocess.run(command,cwd=root,env=env,stdout=stdout,stderr=stderr)
 rows.append({'label':label,'command':command,'exitCode':result.returncode});print(label+' '+str(result.returncode),flush=True)
 assert result.returncode==(1 if label=='strict-ledger' else 0)
ledger=json.loads((out/'strict-ledger.stdout.log').read_text());assert ledger['inventory']['obligations']==1293 and not ledger['invalidEvidence'] and ledger['currentVerifiedEquivalent']==125 and not ledger['strictAcceptance']
for p in (root/'scripts/parity').glob('*.py'):ast.parse(p.read_text(),filename=str(p))
supplement=json.loads((root/'fixtures/parity/supplement.json').read_text());oracle=root/json.loads((root/'.tools/parity/oracles/current.json').read_text())['source']
for item in supplement['referenceTree']:
 raw=(oracle/item['path']).read_bytes();assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==item['gitBlob'],item['path']
assert len(supplement['referenceTree'])==610
assert sha((root/'fixtures/parity/viability-controls.json').read_bytes())=='sha256:df246fe562839235f187e2f61e21a329d01c3e4f2c20d90c03d37c8191a464fc'
assert sha((root/'fixtures/parity/viability-signed-zero-controls.json').read_bytes())=='sha256:56f166b4418990175a91f512c5bc22ab90eaf6393932d9aa51bc2f80c3d88244'
assert sha((root/'fixtures/parity/viability-numeric-controls.json').read_bytes())=='sha256:eca5ec36bac010643489dc929f834b086b909e6772371bc3e091006556680361'
assert sha((root/'fixtures/parity/constraint-callback-controls.json').read_bytes())=='sha256:b2b0b824ecadc544de6bb5d6748f874707879112ce47435c8d537e5f46c232f7'
assert sha((root/'fixtures/parity/constraint-callback-host-controls.json').read_bytes())=='sha256:e2c88a14c7970b7fce272479b5a8b6c0e8a9c99708053849e6b06da4cfa20197'
assert sha((root/'fixtures/parity/memory-activation-controls.json').read_bytes())=='sha256:a075af3abaa522533bd43d5b9ce9335215a1c6ed77c7e7518b8176ed8a403e2c'
assert sha((root/'fixtures/parity/memory-activation-receiver-controls.json').read_bytes())=='sha256:7b21f42ffd669bf346aa80f0144fdf53f5601a22fad998b7fd218411cd926ccc'
assert sha((root/'fixtures/parity/semantic-validation-controls.json').read_bytes())=='sha256:f8b33a4c6666d454220bddd015b488846ffd8b4347c860d4bfa8b6dfe7e452ee'
assert sha((root/'fixtures/parity/uncertainty-risk-controls.json').read_bytes())=='sha256:8475785f4a8b75c5d209e76bb264951dfa02d866e3338fbf06aca3feecdbdc10'
assert sha((root/'fixtures/parity/uncertainty-risk-assessment-controls.json').read_bytes())=='sha256:2f17db893503b01aed39a9d8b8ea802b1498217b7eb53f6b5dfa0626a271ed55'
binary=root/'target/debug/patamaps';engine=json.loads(subprocess.check_output([binary,'engine']));assert all(engine[k]==v for k,v in identities(root).items())
(out/'checks.json').write_text(json.dumps({'schemaVersion':'1.0.0','checks':rows,'strictLedger':ledger,'frozenReferenceBlobsVerified':610,'pythonSyntax':'passed','currentSourceMatchesBinary':True,'candidateEngine':engine,'candidateBinaryDigest':sha(binary.read_bytes())},indent=2)+'\n');print(str(out/'checks.json'),flush=True)
