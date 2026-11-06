from pathlib import Path
import json,hashlib,ast
R=Path('/Volumes/dev_src_case_sensitive/projects/patamaps')
D=R/'.tools/owner-status-investigation-20261030/prepared-guarded-diagnostic'
P=R/'.tools/owner-auth-endpoint-20261029/services-one-extension-proposal-20261030'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
F=json.loads((D/'frozen.json').read_text())
for p,h in F['bindings'].items():assert sha(p)==h,p
ir=json.loads((D/'independent-review.json').read_text())
assert sha(D/'probe.stdout.private')==ir['rawProbeStdoutSha256']
n=next(n for n in ast.parse((R/'scripts/bench_axum_retained.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='validate_ownership')
scope={'ROOT':R};exec(compile(ast.Module(body=[n],type_ignores=[]),'<saved-original-validator>','exec'),scope)
proof=json.loads((D/'probe.stdout.private').read_text())
try:scope['validate_ownership'](proof,'functional',R)
except AssertionError as e:reason=str(e)
else:raise AssertionError('Expected saved stale-heartbeat refusal')
assert reason=='MEASUREMENT_HEARTBEAT_OR_CANCELLATION'
v=json.loads((D/'proof-review.json').read_text())
assert v['validatorRefusal']==reason and v['ownershipProofValidatorAccepted'] is False
for key in ['heartbeatStale','ownerAlive','ownerIdentityVerified','ownerIsAncestor','cancellationRequested','otherActiveReservations','runningContainers']:assert v[key]==proof[key]
pf=json.loads((P/'frozen.json').read_text())
for p,h in pf['inputs'].items():assert 'sha256:'+sha(p)==h,p
review=json.loads((P/'preparation-review.json').read_text())
assert review['frozenManifestSha256']==sha(P/'frozen.json')
assert not any((P/n).exists() for n in ['supervisor.json','receipt.json','APPROVAL.json'])
out=dict(status='saved-proof-and-proposed-bindings-verified',originalValidatorRefusal=reason,originalProbeNotReexecuted=True,allDiagnosticBindingsMatched=True,all421ProposedInputsMatched=True,proposalFrozenManifestSha256=sha(P/'frozen.json'),applicationExecutionAbsent=True,reviewerSha256=sha(__file__))
with (D/'proof-review-check.json').open('x')as f:json.dump(out,f,indent=2);f.write('\n')
print(json.dumps(out))
