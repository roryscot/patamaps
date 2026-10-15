from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess
ROOT=Path('/Volumes/dev_src_case_sensitive/patamaps-intel-20261014');REF=ROOT/'.tools/reference/metamap-399747a4ad05';REV='399747a4ad05a37cd8db1cedd53048fad2175be4'
def sha(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
rows={
'replay':(['C01','C08'],['crates/patamaps-projection/src/capture.rs','crates/patamaps-projection/tests/replay.rs'],['Exact source/dependency/toolchain/profile identities, immutable owned inputs, explicit time/context and complete result recomputation govern replay. Rehashing substituted output does not establish a verified replay.','Strict decoded JSON, closed typed envelopes, pack registration, duplicate spec refusal and built-in-only capture preserve portable boundaries. Native Rust source identities replace the historical Node executor; historical captures are not relabeled.']),
'semantic-replay':(['C04','C06','C07','C08'],['crates/patamaps-projection/src/capture.rs','crates/patamaps-projection/tests/replay.rs','crates/patamaps-projection/tests/risk.rs','crates/patamaps-projection/tests/path_tree.rs'],['Capture rechecks proof, dependency, uncertainty, budget, projection and tree outputs. Foreign executors, changed source bytes and self-consistently rehashed expected data refuse.','Native collection profile0.2 preserves known graph compilation independently of rejected consumer output. Historical single-spec0.1 keeps its original representation; consumers requiring per-expression known states use the collection profile, including for one specification.','Missing source content remains explicit and is never fetched or rediscovered by ordinary replay. Workspace/source evaluation performs its own separately checked lineage reconstruction.']),
'scientific-source-native':(['C04','C05','C06','C07','C17','C18'],['scripts/test_scientific.py','crates/patamaps-scientific/tests/crate.rs','examples/scientific-lookup/src/main.rs'],['The pinned source has seven assertions across five relations, with distinct duplicates and retained original provenance. Actual Rust lookup is compared with the unchanged TypeScript consumer through an explicit shape adapter.','Cost18, budget17 refusal, strict evidence refusal, irreversible reversal, stale proof, crate tampering and source byte preservation are native acceptance assertions. This verifies supported data/workflows, not scientific truth or current activation.']),
'scientific-crate':(['C08','C17'],['crates/patamaps-scientific/src/crate_export.rs','crates/patamaps-scientific/tests/crate.rs'],['Crate verification reconstructs its complete metadata, inventory, replay, export and Rust/TypeScript bytes. Extra/missing/tampered files, source assertion substitution, invalid date and conflicting JSON-LD identities refuse.','Included payload bytes must match their receipts; absent payloads remain explicit digest references and cannot enter closed governed artifacts. Partial mixed-payload alignment deserves additional adversarial checking; source review alone is not proof of every case.'])}
index=json.loads((ROOT/'docs/acceptance/capabilities/reference-scope-audit-2026-10-14.json').read_text())
reviewed=[]
for name,(caps,paths,findings) in rows.items():
    item=next(x for x in index['suites'] if x['suite']==name)
    raw=subprocess.check_output(['git','-C',REF,'show',REV+':'+item['sourcePath']])
    assert raw==(REF/item['sourcePath']).read_bytes() and sha(raw)==item['digest']
    reviewed.append({'suite':name,'sourcePath':item['sourcePath'],'sourceRevision':REV,'digest':sha(raw),'capabilities':caps,
        'substantiveGuaranteesReviewed':findings,'nativeEvidence':[{'path':p,'digest':sha((ROOT/p).read_bytes())} for p in paths],
        'review':'Complete reference assertion body and listed relevant native implementation/tests were read. This is not original-suite execution or final capability acceptance.'})
out=ROOT/'docs/acceptance/capabilities'/datetime.now(timezone.utc).strftime('substantive-replay-scientific-audit-%Y-%m-%dT%H-%M-%S.%fZ');out.mkdir()
(out/'driver.py').write_bytes(Path(__file__).read_bytes())
(out/'receipt.json').write_text(json.dumps({'status':'partial-substantive-audit','recordedAtUtc':datetime.now(timezone.utc).isoformat(),'referenceEngine':REV,
 'reviewedReferenceSources':reviewed,'originalCasesExecutedByThisReview':0,'ownerDispositions':[],'remaining':'Other suites, recorded dependency propagation, outstanding verification gaps and final capability acceptance remain open.','deleted':[]},indent=2)+'\n')
print(out/'receipt.json')
