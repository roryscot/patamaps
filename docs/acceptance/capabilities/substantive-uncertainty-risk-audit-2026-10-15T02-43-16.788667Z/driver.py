from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess
ROOT=Path('/Volumes/dev_src_case_sensitive/patamaps-intel-20261014');REF=ROOT/'.tools/reference/metamap-399747a4ad05';REV='399747a4ad05a37cd8db1cedd53048fad2175be4'
def sha(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
rows={
'uncertainty':(['C04','C05'],['crates/patamaps-core/src/uncertainty.rs','crates/patamaps-core/tests/uncertainty.rs','scripts/reference/semantic.py'],['All six dimensions propagate independently through a qualitative meet; contradiction/unknown and incompatible named models cannot be erased by direct result support or scalar confidence.','Full assessment/evidence values, explicit subject revisions, dimensional scope, attribution and dependencies bind proofs. Shared evidence does not manufacture stronger support or transfer ownership.','Every contributing assessment must meet the consumer evidence/exemption policy; stale/unknown selectors, missing evidence, invalid revisions and unreasoned not-applicable states refuse.']),
'risk':(['C06'],['crates/patamaps-core/src/risk.rs','crates/patamaps-projection/tests/risk.rs','scripts/reference/semantic.py'],['Complete unique mapping/premise closure is charged once, including shared branching proofs and explicit zero-cost derived edges; unused or inactive mappings are excluded.','Missing/overlapping/stale classifications, invalid/overflowing safe-integer cost, wrong consumer budgets and attempts to disable complete accounting refuse. Total, inferred and lossy caps are enforced at equality boundaries.','Unevaluated cost remains null. Private admitted/projected states and verified capture recomputation prevent a rehashed report from creating checked accounting.'])}
index=json.loads((ROOT/'docs/acceptance/capabilities/reference-scope-audit-2026-10-14.json').read_text())
reviewed=[]
for name,(caps,paths,findings) in rows.items():
    item=next(x for x in index['suites'] if x['suite']==name);raw=subprocess.check_output(['git','-C',REF,'show',REV+':'+item['sourcePath']])
    assert raw==(REF/item['sourcePath']).read_bytes() and sha(raw)==item['digest']
    reviewed.append({'suite':name,'sourcePath':item['sourcePath'],'sourceRevision':REV,'digest':sha(raw),'capabilities':caps,
        'substantiveGuaranteesReviewed':findings,'nativeEvidence':[{'path':p,'digest':sha((ROOT/p).read_bytes())} for p in paths],
        'review':'Complete original assertion body and the relevant listed native implementations/tests were read. No original-suite execution or full capability acceptance is claimed.'})
out=ROOT/'docs/acceptance/capabilities'/datetime.now(timezone.utc).strftime('substantive-uncertainty-risk-audit-%Y-%m-%dT%H-%M-%S.%fZ');out.mkdir()
(out/'driver.py').write_bytes(Path(__file__).read_bytes())
(out/'receipt.json').write_text(json.dumps({'status':'partial-substantive-audit','recordedAtUtc':datetime.now(timezone.utc).isoformat(),'referenceEngine':REV,
 'reviewedReferenceSources':reviewed,'originalCasesExecutedByThisReview':0,'ownerDispositions':[],'remaining':'Other pinned suites, complete workflow/platform acceptance and already-recorded gaps remain open.','deleted':[]},indent=2)+'\n')
print(out/'receipt.json')
