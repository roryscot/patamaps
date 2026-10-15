from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/parity'))
from identity import identities
sha=lambda p:'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
inputs=json.loads((ROOT/'.tools/intel-bootstrap/final-acceptance-inputs-956f1a8.json').read_bytes())
out=ROOT/'docs/acceptance/capabilities/package-reproducibility-956f1a8'
package_path=out/'receipt.json';package=json.loads(package_path.read_bytes())
assert package['status']=='passed'
assert package['allSourceMembersAndCurrentBytesVerified'] and package['nativeBinaryBytesVerified'] and package['existingOutputsPreserved']
engines=identities(ROOT);assert engines==inputs['engines']
rows={}
records={}
for name,relative in inputs['receipts'].items():
 path=ROOT/relative;record=json.loads(path.read_bytes());records[name]=record
 expected={'linux':'actual-two-architecture-acceptance-passed-retained','scientificProbe':'controls-passed'}.get(name,'passed')
 assert record['status']==expected,(name,record['status'])
 rows[name]={'path':relative,'digest':sha(path),'status':record['status']}
compiler=records['compiler'];assert len(compiler['commands'])==10 and all(c['exitCode']==0 for c in compiler['commands'])
for item in compiler['sourceInventory']:assert sha(ROOT/item['path'])==item['digest']
assert {k:compiler['engines'][k] for k in engines}==engines
for name in ['installed','release','integrations']:
 assert {k:records[name]['engines'][k] for k in engines}==engines
assert records['scientificProbe']['partialPayloadAlignmentBypassObserved'] is False
assert records['diagnostics']['requireComplete'] is True
for key in ['duplicateComparisonAvailable','consumerOriginsAvailable','policyOriginsAvailable','explicitDiagnosticAvailable']:assert records['diagnostics'][key] is True
linux=records['linux'];assert linux['sourceRevision']==inputs['implementationRevision']
assert {v['architecture'] for v in linux['architectures']}=={'aarch64','x86_64'}
for architecture in linux['architectures']:
 assert sha(ROOT/architecture['receipt'])==architecture['receiptDigest']
 r=json.loads((ROOT/architecture['receipt']).read_bytes())
 assert r['status']=='passed' and r['sourceRevision']==inputs['implementationRevision'] and r['sourceUnchanged'] is True
 assert len(r['commands'])==6 and all(c['exitCode']==0 for c in r['commands'])
 for source in r['sourceInventory']:assert sha(ROOT/source['path'])==source['digest']
 for file,key in [('artifactZip','artifactZipDigest'),('archive','archiveDigest')]:assert sha(ROOT/architecture[file])==architecture[key]
 assert {k:r['engines'][k] for k in engines}==engines
readonly_roots=['crates','scripts','sdk','adapters','vendor','fixtures','schemas','relation-packs','Cargo.toml','Cargo.lock','rust-toolchain.toml']
assert not subprocess.check_output(['git','diff','--name-only','HEAD','--',*readonly_roots],cwd=ROOT,text=True).strip()
review=ROOT/'docs/acceptance/capabilities/substantive-final-suite-review-2026-10-15T03-27-41.269475Z/receipt.json'
review_record=json.loads(review.read_bytes());assert review_record['distinctOriginalSuiteBodiesReviewed']==53 and review_record['originalCasesExecutedByThisReview']==0 and not review_record['ownerDispositions']
renderer=ROOT/inputs['rendererContinuity'];assert json.loads(renderer.read_bytes())['status']=='passed'
original=ROOT/'scripts/capabilities/package_reproducibility.py';adapted=ROOT/'.tools/intel-bootstrap/package-reproducibility-956f1a8.py'
old='output = ROOT / "docs/acceptance/capabilities" / datetime.now(timezone.utc).strftime("package-reproducibility-%Y-%m-%dT%H-%M-%S.%fZ")'
new='output = ROOT / "docs/acceptance/capabilities" / "package-reproducibility-956f1a8"'
assert adapted.read_text()==original.read_text().replace(old,new)
(out/'driver-adaptation.json').write_text(json.dumps({'originalDriver':'scripts/capabilities/package_reproducibility.py','originalDriverDigest':sha(original),'retainedDriverDigest':sha(out/'driver.py'),'onlyChange':'Stable acceptance output directory; every original archive, member/current-byte, metadata and overwrite-refusal assertion unchanged.'},indent=2)+'\n')
report={
 'status':'all-scoped-native-capabilities-implemented-and-verified',
 'recordedAtUtc':datetime.now(timezone.utc).isoformat(),
 'implementationRevision':inputs['implementationRevision'],
 'engines':engines,
 'referenceEngine':'399747a4ad05a37cd8db1cedd53048fad2175be4',
 'capabilities':[{'id':key,'status':'implemented-and-workflow-verified','evidence':value} for key,value in sorted(inputs['capabilities'].items())],
 'verifiedReceipts':{**rows,'package':{'path':package_path.relative_to(ROOT).as_posix(),'digest':sha(package_path),'status':package['status']}},
 'compilerInputsStillMatch':len(compiler['sourceInventory']),
 'linuxSourceInputsStillMatch':{v['architecture']:v['sourceInventoryEntriesMatched'] for v in linux['architectures']},
 'sourceReview':{'path':review.relative_to(ROOT).as_posix(),'digest':sha(review),'originalSuitesSourceReviewed':53,'originalCasesExecutedBySourceReview':0,'scope':'Source discovery only; native, independent and platform execution evidence is recorded separately.'},
 'manualBrowserObservation':{'path':inputs['manualObservation'],'digest':sha(ROOT/inputs['manualObservation']),'rendererContinuity':inputs['rendererContinuity'],'rendererContinuityDigest':sha(renderer),'automatedBrowserExecution':'not-run'},
 'documentationChangesAfterInstallation':inputs['documentChangesAfterInstallation'],
 'finalSourceAndNativeArchives':package['archives'],
 'ownerDispositions':[],
 'boundaries':{'registryPublication':'not-requested-or-performed','productionTrustBootstrapActivation':'not-requested-or-performed','exactJavaScriptObservableParity':'not-claimed; native capability and required integration criteria apply','deterministicIndependentBinaryRebuilds':'not-established','performanceAdvantage':'not-measured-or-claimed','scientificTruth':'not-established'},
 'limitations':'Finite controls and supported integration profiles establish the recorded workflow outcomes, not a proof over every possible input. Optional discovery fixtures do not establish whole-framework dependency closure. Literal legacy signed JavaScript memory transport is not a demonstrated required integration; the native governed memory workflow is verified.',
 'deleted':[],
}
assert len(report['capabilities'])==19
(out/'capability-acceptance.json').write_text(json.dumps(report,indent=2)+'\n')
(out/'finalizer.py').write_bytes(Path(__file__).read_bytes())
pointer=ROOT/'.tools/capabilities/current.json';backup=pointer.with_name('current.before-final-acceptance-20261015.json');backup.open('xb').write(pointer.read_bytes());p=json.loads(pointer.read_bytes())
p.update(status='all-scoped-native-capabilities-implemented-and-verified',capabilityAcceptance=(out/'capability-acceptance.json').relative_to(ROOT).as_posix(),capabilityAcceptanceDigest=sha(out/'capability-acceptance.json'),workingSource='Implementation956f1a8 verified across all19 scoped native capabilities; compiler, installed/optimized consumers, independent controls, real two-architecture Linux and final archive gate pass. Documentation differences from the installed archive remain explicit.')
pointer.write_text(json.dumps(p,indent=2)+'\n')
print(json.dumps({'status':report['status'],'capabilities':19,'acceptance':str(out/'capability-acceptance.json')}))
