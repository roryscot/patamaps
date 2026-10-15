from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, subprocess

root = Path('/Volumes/dev_src_case_sensitive/patamaps-intel-20261014')
ref = root / '.tools/reference/metamap-399747a4ad05'
revision = '399747a4ad05a37cd8db1cedd53048fad2175be4'
def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()
def bound(path):
    return {'path': path, 'digest': digest((root / path).read_bytes())}

rows = {
 'projection': (['C07'], ['crates/patamaps-projection/src/lib.rs','crates/patamaps-projection/tests/projection.rs','scripts/test_native.py'], [
   'Admitted immutable graph, exact packs/context/time and bound specification produce an addressed projection; private Rust states prevent forged/stale mutable generations.',
   'Slot cardinality, active links, target kinds and loss policy govern output. Escaped metadata remains data; generated Rust/TypeScript consumers execute across a real module move.',
   'Native SemanticId naming replaces incidental generated type-alias naming. This review is not a claim to execute the original JavaScript test suite.']),
 'semantic-projection': (['C04','C06','C07','C08'], ['crates/patamaps-core/src/risk.rs','crates/patamaps-projection/src/lib.rs','crates/patamaps-projection/src/path_tree.rs','crates/patamaps-projection/tests/risk.rs','crates/patamaps-projection/tests/path_tree.rs'], [
   'Complete unique used-mapping/proof closure preserves typed uncertainty, exact consumer/spec/generation bindings and explicit unevaluated risk.',
   'Shared premises are charged once; missing/overlapping classifications, overflow, consumer budget substitution and disabled complete-accounting refuse.',
   'Persisted reports convey data; native checked states require recomputation. New TypeScript tree emission is undergoing separate installed acceptance.']),
 'semantic-counterfactual': (['C08','C09'], ['crates/patamaps-projection/src/compare.rs','crates/patamaps-projection/tests/replay.rs','crates/patamaps-projection/tests/risk.rs','crates/patamaps-core/src/impact.rs','crates/patamaps-inspect/src/explanation.rs'], [
   'Comparison accepts verified replays, records policy/proof/spec/source changes separately, preserves known compilation after a consumer refusal, and leaves unavailable projection/risk deltas null.',
   'Known gap: current native impact follows authored graph directions only. The reference also traces a removed premise through its recorded derivation ID to the inferred mapping. Native proof-dependency path reporting remains required; existing loss-of-proof deltas do not close it.']),
 'adapter-registry': (['C15','C16'], ['sdk/typescript/legacy-workspace.mjs','adapters/discovery/index.mjs','crates/patamaps-workspace/src/process_tests.rs'], [
   'Optional discovery supplies seven licensed providers. Custom adapter callbacks preserve configuration/context; native dispatch owns registry and workspace decisions.',
   'Native process responses bind source/request/code inputs and fail on unknown provider, diagnostic error, malformed response, timeout, exit and pipe limits.']),
 'adapters': (['C16'], ['adapters/discovery/provenance.json','adapters/discovery/process.mjs','scripts/test_adapter_bridge.py'], [
   'Pinned Prisma/Zod/JSON fact parser code is retained exactly apart from source-map comments; native candidate runtime does not import MetaMap.',
   'Original bodies cover typed/nullability/cardinality facts, stable locators, Zod derivation chains and privacy-preserving JSON references. Current seven-provider fixture coverage is narrower than whole-framework coverage.']),
 'correspondence': (['C02','C15'], ['crates/patamaps-core/src/legacy_correspondence.rs','crates/patamaps-core/tests/legacy_correspondence.rs','sdk/typescript/legacy-correspondence.mjs'], [
   'Native correspondence materialization emits structure/field/concept/authority references with fact scopes and retains unwaived FIELD_DRIFT as error.',
   'The frozen 63-case original-value corpus and 253 reference controls are existing independent native regression inputs; this source review does not turn compatibility output into admission.']),
 'metamap-shard': (['C02','C15','C16'], ['adapters/discovery/adapters/metamap-shard.js','adapters/discovery/schemas/metamap-graph.schema.json','scripts/test_adapter_bridge.py','crates/patamaps-workspace/tests/workspace.rs'], [
   'External shard values and configured relation semantics survive discovery; unchanged shape schema is relocated locally.',
   'Composed graph admission remains in Rust. Native portable shards use their explicit draft envelope, while the optional provider reads original MetaMap data without relabeling it.']),
 'nextjs-app-router': (['C03','C16'], ['adapters/discovery/adapters/nextjs-app-router.js','adapters/discovery/provenance.json','scripts/test_adapter_bridge.py','crates/patamaps-core/tests/topology.rs'], [
   'Pinned provider retains pages/containers/providers/loaders/boundaries/hydration/parameters/handlers, exclusion attribution and stale-exclusion diagnostics.',
   'Original assertion bodies include fetch/static-params/metadata/query and shared context-provider distinctions. Exact provider reuse is verified; the installed small fixture is not full Next.js application acceptance.']),
}
index = json.loads((root / 'docs/acceptance/capabilities/reference-scope-audit-2026-10-14.json').read_text())
reviewed = []
for name, (caps, native, findings) in rows.items():
    item = next(x for x in index['suites'] if x['suite'] == name)
    raw = subprocess.check_output(['git','-C',ref,'show',revision+':'+item['sourcePath']])
    assert raw == (ref / item['sourcePath']).read_bytes()
    assert digest(raw) == item['digest']
    reviewed.append({'suite':name,'sourcePath':item['sourcePath'],'sourceRevision':revision,'digest':digest(raw),
        'capabilities':caps,'substantiveGuaranteesReviewed':findings,
        'nativeEvidence':[bound(x) for x in native],
        'review':'Complete reference assertion bodies and the relevant native implementation/test portions were read. Original suite execution and final workflow acceptance are not claimed.'})
provenance = json.loads((root / 'adapters/discovery/provenance.json').read_text())
reuse=[]
for name in ['prisma','typescript-zod','json-collections','nextjs-app-router','metamap-shard']:
    item=next(x for x in provenance['files'] if x['path']=='adapters/'+name+'.js')
    original=(ref/item['compiledOrigin']).read_bytes()
    assert digest(original)==item['compiledOriginDigest']
    source=subprocess.check_output(['git','-C',ref,'show',revision+':'+item['sourceOrigin']])
    assert digest(source)==item['sourceOriginDigest']
    lines=original.splitlines(keepends=True)
    assert lines[-1].startswith(b'//# sourceMappingURL=')
    expected=b''.join(lines[:-1])
    if name=='metamap-shard':
        assert expected.count(b'../../schemas/metamap-graph.schema.json')==1
        expected=expected.replace(b'../../schemas/metamap-graph.schema.json',b'../schemas/metamap-graph.schema.json')
    actual=(root/'adapters/discovery'/item['path']).read_bytes()
    assert actual==expected and digest(actual)==item['digest']
    reuse.append({'path':'adapters/discovery/'+item['path'],'digest':digest(actual),'sourceOrigin':item['sourceOrigin'],
        'sourceOriginDigest':digest(source),'transformation':item['transformation'],'exactDeclaredTransformation':True})
report={'status':'partial-substantive-audit','recordedAtUtc':datetime.now(timezone.utc).isoformat(),
 'referenceEngine':revision,'reviewedReferenceSources':reviewed,'providerReuse':reuse,
 'nextRequiredRepair':{'capability':'C09','requirement':'Bounded before/after recorded derivation dependency paths, including removed premises, without implying current admission, activation or unique causality.',
   'referenceAssertion':'semantic-counterfactual.test.ts: explains a removed premise through the captured proof without inventing deactivations',
   'nativeObservation':'compare.rs exposes declaredPathsBefore/After from core::impact, which reads checked graph mappings and declared relation directions, not policy derivation dependencies.',
   'status':'not-implemented'},
 'originalCasesExecutedByThisReview':0,'ownerDispositions':[],'remainingAudit':'Other pinned suites and final capability acceptance remain open.','deleted':[]}
stamp=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S.%fZ')
out=root/'docs/acceptance/capabilities'/('substantive-projection-discovery-audit-'+stamp)
out.mkdir()
(out/'driver.py').write_bytes(Path(__file__).read_bytes())
(out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'receipt':str(out/'receipt.json'),'reviewedSuites':len(reviewed),'providerTransformationsVerified':len(reuse),'knownGap':'C09 recorded derivation impact paths'}))
