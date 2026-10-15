from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess
ROOT=Path('/Volumes/dev_src_case_sensitive/patamaps-intel-20261014')
REF=ROOT/'.tools/reference/metamap-399747a4ad05';REV='399747a4ad05a37cd8db1cedd53048fad2175be4'
def sha(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
rows={
'activation':(['C11','C12'],['crates/patamaps-activator/tests/memory.rs','crates/patamaps-activator/src/linux_tests.rs'],['A rejected candidate cannot replace accepted state. Native memory and Linux persistence expose separate explicit profiles.']),
'governed-activation':(['C10','C11'],['crates/patamaps-activator/src/memory.rs','crates/patamaps-activator/tests/memory.rs','crates/patamaps-activator/tests/transport.rs'],['Owner-selected host context supplies fresh trust/time; exact signed files, predecessor, environment and current grants determine transition and retry.','Tampered files/proposal/signature/inventory, host failure/panic, revocation, expiry and self-approval retain accepted state. Historical verification grants no current authority.','Rust borrowing/private constructors preserve state ownership; no literal JavaScript object-identity or deep-freeze equivalence is claimed.']),
'protected-activation':(['C10','C12'],['crates/patamaps-activator/src/transaction.rs','crates/patamaps-activator/src/linux_tests.rs','crates/patamaps-activator/tests/transport.rs'],['Strict ingress and fixed protected runtime reject caller trust/time, non-Linux hosts, unsafe files/links/ownership and extra artifacts.','Actual Linux tests cover distinct proposer/consumer UID, native lock, fresh authorization, concurrent stale bases, five SIGKILL phases, native module move and fresh-approved rollback.','Verification gap: the precommit swap branch asserts rejection but skips readback of the prior active state. Add an independent pointer/state preservation assertion and run it on Linux. No production defect has yet been demonstrated.']),
'governance-native':(['C07','C10'],['scripts/test_native.py','scripts/capabilities/consumers/typed_tree.rs','crates/patamaps-activator/src/linux_tests.rs'],['The reference wrapper requires actual reviewed-byte native execution, external owner approval, refusal of agent self-approval and output substitution, plus path hydration.','Existing native checks and the new checked-tree consumer provide the constituent flows. The exact original nine-file/seven-label fixture and public subpath names are not the native completion criterion.']),
'lifecycle-native':(['C02','C04','C05','C06','C07','C10','C11','C12'],['scripts/test_lifecycle_pure.py','scripts/test_native.py','crates/patamaps-activator/tests/transport.rs','crates/patamaps-activator/src/linux_tests.rs'],['The reference wrapper binds two owned shards, checked proof, unique ordinal cost, real consumer move, stale approval/output/evidence/binding refusals, accepted-state preservation and fresh rollback.','Native portable and Linux fixtures implement these stages with independently authored data; their costs and output counts need not copy incidental fixture values. New native typed consumer separately checks exact cost five and rejected capture replay.']),
'explanation-native':(['C09','C13','C18'],['scripts/capabilities/source_reporting.py','scripts/capabilities/workspace.py','crates/patamaps-inspect/src/explanation.rs'],['The reference wrapper requires one source-preserving report through API and strict CLI, explicit unknown causality/current authority, and no application.','Native report/CLI and static escaped HTML checks exist. Interactive browser execution remains explicitly unverified; this review does not close that boundary.']),
'repair-native':(['C07','C14'],['scripts/test_lifecycle_pure.py','crates/patamaps-activator/src/linux_tests.rs','crates/patamaps-inspect/src/repair.rs'],['The original wrapper executes actual repaired provider/native-path output and read-only CLI without application or implied authorization.','Native checks already verify finite repair proposals and preserved accepted state; direct execution of the selected returned repair capture as a generated native consumer still needs an explicit acceptance check.'])}
index=json.loads((ROOT/'docs/acceptance/capabilities/reference-scope-audit-2026-10-14.json').read_text())
reviewed=[]
for name,(caps,paths,findings) in rows.items():
    item=next(x for x in index['suites'] if x['suite']==name)
    raw=subprocess.check_output(['git','-C',REF,'show',REV+':'+item['sourcePath']])
    assert raw==(REF/item['sourcePath']).read_bytes() and sha(raw)==item['digest']
    reviewed.append({'suite':name,'sourceRevision':REV,'sourcePath':item['sourcePath'],'digest':sha(raw),'capabilities':caps,
        'substantiveGuaranteesReviewed':findings,'nativeEvidence':[{'path':p,'digest':sha((ROOT/p).read_bytes())} for p in paths],
        'review':'Complete reference assertion body and relevant listed native implementation/assertion portions read. Constituent checks are distinguished from complete workflow acceptance; original-suite execution is not claimed.'})
stamp=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S.%fZ')
out=ROOT/'docs/acceptance/capabilities'/('substantive-activation-consumer-audit-'+stamp);out.mkdir()
(out/'driver.py').write_bytes(Path(__file__).read_bytes())
report={'status':'partial-substantive-audit','recordedAtUtc':datetime.now(timezone.utc).isoformat(),'referenceEngine':REV,
 'reviewedReferenceSources':reviewed,'originalCasesExecutedByThisReview':0,'ownerDispositions':[],
 'remaining':'Other pinned suites, the recorded C09 dependency-path repair, C12 swap-preservation assertion, returned repair-capture native execution and browser acceptance remain open.','deleted':[]}
(out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'receipt':str(out/'receipt.json'),'reviewedSuites':len(reviewed),'fullAcceptanceClaimed':False}))
