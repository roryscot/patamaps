use patamaps_contracts::*;
use patamaps_projection::*;
use serde_json::json;

fn inputs() -> CaptureInputs {
    CaptureInputs {
        projection_specs: vec![],
        graph: parse(include_bytes!("../../../fixtures/routing/graph.json")).unwrap(),
        policy: parse(include_bytes!("../../../fixtures/routing/policy.json")).unwrap(),
        packs: vec![
            parse(include_bytes!("../../../relation-packs/core.json")).unwrap(),
            parse(include_bytes!("../../../relation-packs/routing.json")).unwrap(),
        ],
        context: JsonObject::new(),
        evaluated_at: "2026-10-10T12:00:00Z".into(),
        projection_spec: Some(
            parse(include_bytes!(
                "../../../fixtures/routing/projection-spec.json"
            ))
            .unwrap(),
        ),
    }
}

#[test]
fn success_and_structural_rejection_replay_offline() {
    let a = capture(inputs(), vec![]).unwrap();
    assert_eq!(replay(&a).unwrap().result()["status"], "viable");
    let wire = canonical_bytes(&a).unwrap();
    let restored: CaptureRecord = parse(&wire).unwrap();
    assert_eq!(
        canonical_bytes(replay(&restored).unwrap().result()).unwrap(),
        canonical_bytes(&a.result).unwrap()
    );
    let mut bad = inputs();
    bad.graph.mappings[0].targets = vec!["urn:unknown:endpoint".into()];
    let b = capture(bad, vec![]).unwrap();
    assert_eq!(replay(&b).unwrap().result()["status"], "rejected");
    let comparison = compare(&replay(&a).unwrap(), &replay(&b).unwrap()).unwrap();
    assert_eq!(comparison["statusChanged"], true);
    assert!(comparison["projectionChanged"].is_null());
    assert!(comparison["riskDelta"].is_null());
    assert_eq!(comparison["changes"][0]["kind"], "mapping");
}

#[test]
fn tampering_executor_substitution_and_forged_result_fail() {
    let a = capture(inputs(), vec![]).unwrap();
    let mut changed = a.clone();
    changed.inputs.graph.entities[0].label = Some("changed".into());
    assert!(replay(&changed).is_err());
    let mut changed = a.clone();
    changed.executor = "metamap:typescript:399747".into();
    assert!(replay(&changed).is_err());
    let mut changed = a;
    changed.result["status"] = json!("rejected");
    // Even an attacker who correctly re-addresses their modified evidence cannot
    // turn it into a verified replay of this executor's actual result.
    let mut value = serde_json::to_value(&changed).unwrap();
    value.as_object_mut().unwrap().remove("id");
    value.as_object_mut().unwrap().remove("digest");
    changed.digest = canonical_digest(&value).unwrap();
    changed.id = format!("urn:patamaps:capture:{}", &changed.digest[7..]);
    let error = replay(&changed).unwrap_err();
    assert!(error.0.iter().any(|i| i.code == "REPLAY_RESULT_MISMATCH"));
}

#[test]
fn a_receipt_does_not_claim_that_source_bytes_are_available() {
    let content = "independently captured UTF-8 source\n";
    let receipt = SourceReceipt {
        id: "urn:source:handler".into(),
        locator: "file:/must-not-be-opened".into(),
        digest: byte_digest(content.as_bytes()),
        byte_length: SafeInteger::new(content.len() as u64).unwrap(),
        content: None,
    };
    let a = capture(inputs(), vec![receipt.clone()]).unwrap();
    assert_eq!(
        replay(&a).unwrap().missing_sources(),
        std::slice::from_ref(&receipt.id)
    );
    let mut receipt = receipt;
    receipt.content = Some(content.into());
    let a = capture(inputs(), vec![receipt.clone()]).unwrap();
    assert!(replay(&a).unwrap().missing_sources().is_empty());
    receipt.content = Some("different bytes".into());
    assert!(capture(inputs(), vec![receipt]).is_err());
}

#[test]
fn changed_raw_sources_are_reported_without_inventing_an_extraction() {
    let receipt = |content: &str| SourceReceipt {
        id: "urn:source:handler".into(),
        locator: "file:/captured/handler".into(),
        digest: byte_digest(content.as_bytes()),
        byte_length: SafeInteger::new(content.len() as u64).unwrap(),
        content: Some(content.into()),
    };
    let before = capture(inputs(), vec![receipt("before")]).unwrap();
    let after = capture(inputs(), vec![receipt("after")]).unwrap();
    let comparison = compare(&replay(&before).unwrap(), &replay(&after).unwrap()).unwrap();
    assert_eq!(comparison["sourceDeltas"][0]["byteChange"], true);
    assert_eq!(
        comparison["sourceDeltas"][0]["graphExtractionRecomputed"],
        false
    );
    assert!(comparison["changes"].as_array().unwrap().is_empty());
}

#[test]
fn reordered_records_have_no_stable_identity_delta() {
    let a = inputs().graph;
    let mut b = a.clone();
    b.entities.reverse();
    b.mappings.reverse();
    assert!(patamaps_core::diff(&a, &b).unwrap().is_empty());
    assert_ne!(canonical_digest(&a).unwrap(), canonical_digest(&b).unwrap());
}

fn collection_inputs() -> CaptureInputs {
    let mut input = inputs();
    let a = input.projection_spec.take().unwrap();
    let mut b = a.clone();
    b.id = "urn:projection:second".into();
    b.slots[0].name = "secondHandler".into();
    input.projection_specs = vec![b, a];
    input
}

#[test]
fn collection_replay_preserves_individual_outputs_and_known_compilation_after_consumer_refusal() {
    let before = capture(collection_inputs(), vec![]).unwrap();
    assert_eq!(before.schema_version, CaptureVersion::Collection1);
    assert_eq!(before.result["status"], "viable");
    assert_eq!(before.result["projections"].as_array().unwrap().len(), 2);
    let wire = canonical_bytes(&before).unwrap();
    let restored: CaptureRecord = parse(&wire).unwrap();
    assert_eq!(
        canonical_bytes(replay(&restored).unwrap().result()).unwrap(),
        canonical_bytes(&before.result).unwrap()
    );
    let mut input = before.inputs.clone();
    let changed_id = input.projection_specs[1].id.clone();
    input.projection_specs[1].slots[0].target_kinds = Some(vec!["unavailable-kind".into()]);
    let after = capture(input, vec![]).unwrap();
    assert_eq!(after.result["status"], "rejected");
    assert_eq!(after.result["compilationStatus"], "viable");
    assert!(after.result["generation"].is_object());
    let report = compare(&replay(&before).unwrap(), &replay(&after).unwrap()).unwrap();
    assert_eq!(report["projectionSpecs"]["changed"], json!([changed_id]));
    assert_eq!(report["mappingStates"]["afterKnown"], true);
    assert_eq!(report["mappingStates"]["deactivated"], json!([]));
    let deltas = report["semantic"]["projections"].as_array().unwrap();
    assert_eq!(deltas.len(), 2);
    let delta = deltas
        .iter()
        .find(|row| row["specId"] == changed_id)
        .unwrap();
    assert_eq!(delta["beforeKnown"], true);
    assert_eq!(delta["afterKnown"], false);
    assert!(delta["usedMappingsChanged"].is_null());
    assert!(delta["dependenciesChanged"].is_null());
    assert!(delta["riskChanged"].is_null());
}

#[test]
fn collection_version_and_duplicate_specs_cannot_be_laundered_through_readdressing() {
    let mut input = collection_inputs();
    input
        .projection_specs
        .push(input.projection_specs[0].clone());
    assert!(
        capture(input, vec![])
            .unwrap_err()
            .0
            .iter()
            .any(|issue| issue.code == "CAPTURE_DUPLICATE_PROJECTION")
    );
    let mut record = capture(collection_inputs(), vec![]).unwrap();
    record.schema_version = CaptureVersion::Draft1;
    assert!(
        replay(&record)
            .unwrap_err()
            .0
            .iter()
            .any(|issue| issue.code == "CAPTURE_VERSION_MISMATCH")
    );
    let mut input = collection_inputs();
    input.projection_spec = Some(input.projection_specs[0].clone());
    assert!(capture(input, vec![]).is_err());
    let record = capture(inputs(), vec![]).unwrap();
    let mut wire = serde_json::to_value(&record).unwrap();
    wire["inputs"]["projectionSpecs"] = json!([]);
    assert!(parse::<CaptureRecord>(&canonical_bytes(&wire).unwrap()).is_err());
}

#[test]
fn a_lost_proof_is_reported_separately_from_unchanged_graph_records_and_unknown_projection_risk() {
    let mut graph: GraphDocument =
        parse(include_bytes!("../../../fixtures/laws/graph.json")).unwrap();
    let pack: RelationPack = parse(include_bytes!("../../../fixtures/laws/pack.json")).unwrap();
    let request: CompositionRequest =
        parse(include_bytes!("../../../fixtures/laws/request.json")).unwrap();
    let proposal = patamaps_core::derive(
        &patamaps_core::CheckedGraph::check(graph.clone(), vec![pack.clone()]).unwrap(),
        &request,
    );
    assert_eq!(proposal.status, patamaps_core::DerivationStatus::Proposed);
    graph.mappings.push(proposal.mapping.unwrap());
    let proof = proposal.derivation.unwrap();
    let mut policy: PolicyDocument =
        parse(include_bytes!("../../../fixtures/laws/policy.json")).unwrap();
    policy
        .semantics
        .as_mut()
        .unwrap()
        .derivations
        .push(proof.clone());
    let spec: ProjectionSpec = parse(include_bytes!(
        "../../../fixtures/laws/projection-spec.json"
    ))
    .unwrap();
    let input = CaptureInputs {
        graph,
        packs: vec![pack],
        policy,
        context: request.context,
        evaluated_at: "2026-10-10T12:00:00Z".into(),
        projection_spec: None,
        projection_specs: vec![spec],
    };
    let before = capture(input, vec![]).unwrap();
    assert_eq!(before.result["status"], "viable");
    let mut input = before.inputs.clone();
    input.policy.semantics.as_mut().unwrap().derivations.clear();
    let after = capture(input, vec![]).unwrap();
    assert_eq!(after.result["compilationStatus"], "rejected");
    let report = compare(&replay(&before).unwrap(), &replay(&after).unwrap()).unwrap();
    assert_eq!(report["changes"], json!([]));
    assert_eq!(
        report["semantic"]["derivations"]["removed"],
        json!([proof.id])
    );
    assert_eq!(report["mappingStates"]["beforeKnown"], true);
    assert_eq!(report["mappingStates"]["afterKnown"], false);
    assert!(report["mappingStates"]["deactivated"].is_null());
    assert!(report["semantic"]["projections"][0]["riskChanged"].is_null());
    assert!(
        report["inputChanges"]
            .as_array()
            .unwrap()
            .iter()
            .any(|row| row["input"] == "policy")
    );
}

#[test]
fn new_and_removed_specs_remain_unknown_instead_of_becoming_zero_deltas() {
    let before = capture(collection_inputs(), vec![]).unwrap();
    let mut input = before.inputs.clone();
    let removed = input.projection_specs.pop().unwrap();
    let mut added = removed.clone();
    added.id = "urn:projection:new".into();
    input.projection_specs.push(added.clone());
    let after = capture(input, vec![]).unwrap();
    let report = compare(&replay(&before).unwrap(), &replay(&after).unwrap()).unwrap();
    assert_eq!(report["projectionSpecs"]["removed"], json!([removed.id]));
    assert_eq!(report["projectionSpecs"]["added"], json!([added.id]));
    for id in [&removed.id, &added.id] {
        let delta = report["semantic"]["projections"]
            .as_array()
            .unwrap()
            .iter()
            .find(|row| row["specId"] == *id)
            .unwrap();
        assert!(delta["dependenciesChanged"].is_null());
        assert!(delta["riskChanged"].is_null());
    }
}
