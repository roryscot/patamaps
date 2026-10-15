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
            projection_specs: vec![],
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

#[test]
fn partial_sources_remain_digest_references_and_cannot_enter_closed_governance() {
    let (c, mut o) = fixture();
    let mut receipts = c.sources.clone();
    receipts[0].content = None;
    let partial = capture(c.inputs.clone(), receipts).unwrap();
    o.raw_inputs = Some(Default::default());
    let package = create_crate(&partial, &o).unwrap();
    assert_eq!(package.external_raw_inputs(), 1);
    assert!(
        !package
            .record()
            .files
            .keys()
            .any(|p| p.starts_with("source/"))
    );
    let round: ScientificCrate = parse(&canonical_bytes(&package).unwrap()).unwrap();
    assert_eq!(verify_crate(&round).unwrap().external_raw_inputs(), 1);
    let id = format!("urn:patamaps:raw-input:{}", &partial.sources[0].digest[7..]);
    let entities = round.metadata["@graph"].as_array().unwrap();
    let reference = entities.iter().find(|entity| entity["@id"] == id).unwrap();
    assert_eq!(reference["sha256"], &partial.sources[0].digest[7..]);
    assert!(
        reference["description"]
            .as_str()
            .unwrap()
            .contains("reference only")
    );
    assert!(
        entities[1]["hasPart"]
            .as_array()
            .unwrap()
            .iter()
            .any(|p| p["@id"] == id)
    );
    let governed = patamaps_governance::GovernedCandidate {
        captures: vec![partial],
        emissions: vec![],
    };
    assert!(
        patamaps_governance::prepare_candidate_artifacts(&governed, &o.consumer, &o.environment)
            .is_err()
    );
    assert!(
        create_crate(&c, &o).is_err(),
        "Excluded bytes must not survive inside the exported capture"
    );
    let mut forged = round.clone();
    forged.metadata["@graph"]
        .as_array_mut()
        .unwrap()
        .iter_mut()
        .find(|entity| entity["@id"] == id)
        .unwrap()["sha256"] = json!("0".repeat(64));
    assert!(verify_crate(&forged).is_err());
    let mut extra = o;
    extra
        .raw_inputs
        .as_mut()
        .unwrap()
        .insert("urn:unknown:receipt".into(), "forged".into());
    assert!(create_crate(&governed.captures[0], &extra).is_err());
}

#[test]
fn included_inventory_is_exact_and_collection_crates_emit_all_native_bindings() {
    let (c, mut o) = fixture();
    o.raw_inputs = Some(std::collections::BTreeMap::from([(
        c.sources[0].id.clone(),
        c.sources[0].content.clone().unwrap(),
    )]));
    assert_eq!(
        verify_crate(create_crate(&c, &o).unwrap().record())
            .unwrap()
            .external_raw_inputs(),
        0
    );
    o.raw_inputs
        .as_mut()
        .unwrap()
        .values_mut()
        .next()
        .unwrap()
        .push(' ');
    assert!(create_crate(&c, &o).is_err());
    o.raw_inputs = None;
    let mut inputs = c.inputs;
    let spec = inputs.projection_spec.take().unwrap();
    let mut second = spec.clone();
    second.id = "urn:projection:scientific:second".into();
    inputs.projection_specs = vec![spec, second];
    let collection = capture(inputs, c.sources).unwrap();
    let package = create_crate(&collection, &o).unwrap();
    for file in [
        "bindings-0.ts",
        "bindings-1.rs",
        "bindings-2.ts",
        "bindings-3.rs",
        "projection-0-0.json",
        "projection-0-1.json",
    ] {
        assert!(package.record().files.contains_key(file), "{file}");
    }
    verify_crate(package.record()).unwrap();
}

fn mixed_source_fixture(
    include_tsv: bool,
    include_metadata: bool,
    changed_payload: Option<&str>,
) -> (CaptureRecord, CrateOptions) {
    let (c, mut options) = fixture();
    let document: SssomDocument =
        decode(c.inputs.graph.metadata.as_ref().unwrap()["sssom"]["rawDocument"].clone());
    let mut tsv = std::str::from_utf8(RAW)
        .unwrap()
        .split_inclusive('\n')
        .skip_while(|line| line.starts_with('#'))
        .collect::<String>();
    let mut metadata = document.metadata.clone();
    if changed_payload == Some("tsv") {
        let column = document
            .columns
            .iter()
            .position(|name| name == "subject_id")
            .unwrap();
        let original = &document.rows[0][column];
        assert!(tsv.contains(original));
        tsv = tsv.replacen(original, &format!("{original}-altered"), 1);
    }
    if changed_payload == Some("metadata") {
        metadata.insert(
            "mapping_set_title".into(),
            json!("Contradictory supplied metadata"),
        );
    }
    let metadata = String::from_utf8(canonical_bytes(&metadata).unwrap()).unwrap();
    let metadata_id = "urn:source:mgi:metadata";
    options.metadata_receipt = Some(metadata_id.into());
    let mut payloads = std::collections::BTreeMap::new();
    let mut receipts = Vec::new();
    for (id, bytes, included) in [
        (c.sources[0].id.as_str(), tsv, include_tsv),
        (metadata_id, metadata, include_metadata),
    ] {
        if included {
            payloads.insert(id.into(), bytes.clone());
        }
        receipts.push(SourceReceipt {
            id: id.into(),
            locator: format!("urn:provided:{id}"),
            digest: byte_digest(bytes.as_bytes()),
            byte_length: SafeInteger::new(bytes.len() as u64).unwrap(),
            content: included.then_some(bytes),
        });
    }
    options.raw_inputs = Some(payloads);
    let captured = capture(c.inputs, receipts).unwrap();
    assert_eq!(captured.result["status"], "viable");
    (captured, options)
}

#[test]
fn each_valid_partial_source_inventory_verifies_without_filling_missing_bytes() {
    for (tsv, metadata) in [(true, true), (true, false), (false, true), (false, false)] {
        let (capture, options) = mixed_source_fixture(tsv, metadata, None);
        let before = canonical_bytes(&capture).unwrap();
        let package = create_crate(&capture, &options).unwrap();
        let missing = 2 - usize::from(tsv) - usize::from(metadata);
        assert_eq!(package.external_raw_inputs(), missing);
        assert_eq!(
            verify_crate(package.record())
                .unwrap()
                .external_raw_inputs(),
            missing
        );
        assert_eq!(canonical_bytes(&capture).unwrap(), before);
        let embedded = package
            .record()
            .files
            .keys()
            .filter(|name| name.starts_with("source/"))
            .count();
        assert_eq!(embedded, usize::from(tsv) + usize::from(metadata));
    }
}

#[test]
fn supplied_tsv_or_metadata_contradictions_refuse_even_when_the_other_payload_is_missing() {
    for (tsv, metadata, changed) in [
        (true, false, "tsv"),
        (true, true, "tsv"),
        (false, true, "metadata"),
        (true, true, "metadata"),
    ] {
        let (capture, options) = mixed_source_fixture(tsv, metadata, Some(changed));
        assert_eq!(
            create_crate(&capture, &options).unwrap_err().code,
            "SCIENTIFIC_CRATE_SOURCE"
        );
    }
}

#[test]
fn an_absent_external_metadata_receipt_does_not_allow_embedded_metadata_mode() {
    let (capture, mut options) = fixture();
    let mut receipts = capture.sources.clone();
    receipts.push(SourceReceipt {
        id: "urn:source:mgi:metadata".into(),
        locator: "urn:provided:metadata".into(),
        digest: byte_digest(b"{}"),
        byte_length: SafeInteger::new(2).unwrap(),
        content: None,
    });
    options.metadata_receipt = Some("urn:source:mgi:metadata".into());
    options.raw_inputs = Some(std::collections::BTreeMap::from([(
        receipts[0].id.clone(),
        receipts[0].content.clone().unwrap(),
    )]));
    let captured = patamaps_projection::capture(capture.inputs, receipts).unwrap();
    assert_eq!(
        create_crate(&captured, &options).unwrap_err().code,
        "SSSOM_METADATA_MODE"
    );
}
