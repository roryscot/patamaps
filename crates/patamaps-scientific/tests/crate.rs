use patamaps_contracts::*;
use patamaps_core::{CheckedGraph, DerivationStatus, derive};
use patamaps_projection::{CaptureInputs, CaptureRecord, SourceReceipt, capture};
use patamaps_scientific::*;
use serde::de::DeserializeOwned;
use serde_json::{Value, json};
const RAW: &[u8] = include_bytes!(
    "../../../fixtures/reference/examples/scientific-mapping/fixtures/mgi-subset.sssom.tsv"
);
fn decode<T: DeserializeOwned>(v: Value) -> T {
    parse(&canonical_bytes(&v).unwrap()).unwrap()
}
fn source() -> ImportOptions {
    decode(
        json!({"id":"urn:source:mgi", "namespace":"scientific-test", "sourceRevision":"e4fe727428661f0093f6ab9269f4fb80387e39fc"}),
    )
}
fn fixture() -> (CaptureRecord, CrateOptions) {
    let s = parse_tsv(RAW, None).unwrap();
    let mut graph = import_graph(&s, &source()).unwrap();
    for m in &mut graph.mappings {
        m.lossiness = Lossiness::Lossy;
    }
    let original: Vec<_> = graph.mappings.iter().map(|m| m.id.clone()).collect();
    let broad = graph
        .mappings
        .iter()
        .find(|m| m.relation == "scientific:broad-match")
        .unwrap()
        .id
        .clone();
    let context = json!({"executeScientificReversal":false});
    let proof = derive(
        &CheckedGraph::check(graph.clone(), vec![scientific_pack()]).unwrap(),
        &decode(
            json!({"schemaVersion":"0.1.0", "documentType":"composition-request", "law":"urn:metamap:scientific:law:reverse-broad", "premises":[broad], "context":context, "bounds":{"maxDepth":8, "maxDerivations":32}, "derivations":[], "assessments":[], "evidence":[]}),
        ),
    );
    assert_eq!(
        proof.status,
        DerivationStatus::Proposed,
        "{:?}",
        proof.issues
    );
    let derived = proof.mapping.unwrap();
    let derived_id = derived.id.clone();
    graph.mappings.push(derived);
    let classifications: Vec<_> = graph.mappings.iter().enumerate().map(|(i,m)| json!({"id":format!("urn:cost:{i}"), "select":{"ids":[m.id]}, "classification":"explicit-exploratory", "cost":if m.id == derived_id {0} else {match m.relation.as_str() {"scientific:exact-match"=>1, "scientific:close-match"=>4, "scientific:related-match"=>5, _=>2}}})).collect();
    let policy = decode(
        json!({"schemaVersion":"0.1.0", "documentType":"policy", "id":"urn:policy:exploratory", "graph":{"id":graph.id, "digest":canonical_digest(&graph).unwrap()}, "mappings":[{"select":{"ids":original}, "coverage":"partial", "determinism":"deterministic", "reversibility":"irreversible"}, {"mapping":derived_id, "coverage":"partial", "determinism":"deterministic", "reversibility":"irreversible", "applicability":{"when":{"key":"executeScientificReversal", "operator":"equals", "value":true}}}], "constraints":[], "evidence":[], "semantics":{"interpretation":"declared-law-application", "derivations":[proof.derivation.unwrap()], "derivationLimits":{"maxDepth":8,"maxDerivations":32}, "assessments":[], "uncertaintyRequirements":[], "riskBudgets":[{"id":"urn:budget:scientific", "consumer":"urn:consumer:scientific", "classifications":classifications, "maximumTotalCost":18,"maximumInferredMappings":0,"maximumLossyMappings":7,"requireCompleteClassification":true,"requireCompleteDependencies":true}]}}),
    );
    let slots = ["exact","close","broad","narrow","related"].iter().map(|n|json!({"name":n,"relation":format!("scientific:{n}-match"),"direction":"outgoing","cardinality":"many","allowLossy":true})).collect::<Vec<_>>();
    let spec = decode(
        json!({"schemaVersion":"0.1.0", "documentType":"projection-spec", "id":"urn:projection:scientific", "select":{"ids":graph.entities.iter().map(|e|e.id.clone()).collect::<Vec<_>>()}, "slots":slots, "semantics":{"consumer":"urn:consumer:scientific", "budget":"urn:budget:scientific"}}),
    );
    let c = capture(
        CaptureInputs {
            graph,
            packs: vec![scientific_pack()],
            policy,
            context: decode(context),
            evaluated_at: "2026-10-10T00:00:00.000Z".into(),
            projection_spec: Some(spec),
        },
        vec![SourceReceipt {
            id: "urn:source:mgi:tsv".into(),
            locator: "urn:patamaps:provided-source:tsv".into(),
            digest: byte_digest(RAW),
            byte_length: SafeInteger::new(RAW.len() as u64).unwrap(),
            content: Some(String::from_utf8(RAW.to_vec()).unwrap()),
        }],
    )
    .unwrap();
    let options = decode(
        json!({"name":"Licensed exploratory MGI subset", "description":"Seven source assertions of 1564; producer cross-species restriction remains visible", "datePublished":"2026-10-10", "consumer":"urn:consumer:scientific", "environment":"offline-exploration", "source":source(), "tsvReceipt":"urn:source:mgi:tsv", "externalSources":[{"id":"https://github.com/mapping-commons/mh_mapping_initiative/blob/e4fe727428661f0093f6ab9269f4fb80387e39fc/mappings/mp_hp_mgi_all.sssom.tsv", "name":"Full original 1564-record source", "description":"Pinned original producer bytes are external"}]}),
    );
    assert_eq!(c.result["status"], "viable", "{}", c.result);
    (c, options)
}
#[test]
fn crate_replays_exact_inventory_and_native_bindings_without_elevating_truth() {
    let (c, o) = fixture();
    assert_eq!(c.result["projection"]["semantics"]["risk"]["totalCost"], 18);
    let package = create_crate(&c, &o).unwrap();
    let round: ScientificCrate = parse(&canonical_bytes(&package).unwrap()).unwrap();
    verify_crate(&round).unwrap();
    assert!(round.files.contains_key("bindings-0.ts") && round.files.contains_key("bindings-1.rs"));
    assert_eq!(round.files["source/source-0.txt"].as_bytes(), RAW);
    assert!(
        round.metadata["@graph"][1]["description"]
            .as_str()
            .unwrap()
            .contains("not established")
    );
    assert_eq!(
        c.result["projection"]["semantics"]["usedMappings"]
            .as_array()
            .unwrap()
            .len(),
        7
    );
}
#[test]
fn complete_inventory_and_receipt_tampering_refuse() {
    let (c, o) = fixture();
    let package = create_crate(&c, &o).unwrap();
    for name in [
        "bindings-1.rs",
        "source/source-0.txt",
        "export.sssom.tsv",
        "artifact-manifest.json",
        "source-import.json",
    ] {
        let mut changed = package.record().clone();
        changed.files.get_mut(name).unwrap().push(' ');
        assert!(verify_crate(&changed).is_err(), "{name}");
    }
    let mut removed = package.record().clone();
    removed.files.remove("policy.json");
    assert!(verify_crate(&removed).is_err());
    let mut extra = package.record().clone();
    extra
        .files
        .insert("extra.txt".into(), "same inventory claim".into());
    assert!(verify_crate(&extra).is_err());
    let mut changed = package.record().clone();
    changed.metadata["@graph"][1]["name"] = json!("forged");
    assert!(verify_crate(&changed).is_err());
    let mut stale = c.clone();
    stale.sources[0].content.as_mut().unwrap().push(' ');
    assert!(create_crate(&stale, &o).is_err());
}
#[test]
fn newly_replayed_source_substitution_and_missing_payloads_refuse() {
    let (c, o) = fixture();
    let mut inputs = c.inputs.clone();
    inputs.graph.mappings[0]
        .attributes
        .as_mut()
        .unwrap()
        .insert("changed-source-assertion".into(), json!(true));
    inputs.policy.graph = GraphBinding {
        id: inputs.graph.id.clone(),
        revision: None,
        digest: Some(canonical_digest(&inputs.graph).unwrap()),
    };
    let substituted = capture(inputs, c.sources.clone()).unwrap();
    assert_eq!(substituted.result["status"], "viable");
    assert_eq!(
        create_crate(&substituted, &o).unwrap_err().code,
        "SCIENTIFIC_CRATE_SOURCE"
    );
    let mut missing = c.sources.clone();
    missing[0].content = None;
    let missing = capture(c.inputs, missing).unwrap();
    assert_eq!(
        create_crate(&missing, &o).unwrap_err().code,
        "SCIENTIFIC_CRATE_REPLAY"
    );
}
