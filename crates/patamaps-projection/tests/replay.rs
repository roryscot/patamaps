use patamaps_contracts::*;
use patamaps_projection::*;
use serde_json::json;

fn inputs() -> CaptureInputs {
    CaptureInputs {
        projection_specs: vec![],
        graph: parse(include_bytes!(
            "../package-inputs/fixtures/routing/graph.json"
        ))
        .unwrap(),
        policy: parse(include_bytes!(
            "../package-inputs/fixtures/routing/policy.json"
        ))
        .unwrap(),
        packs: vec![
            parse(include_bytes!("../package-inputs/relation-packs/core.json")).unwrap(),
            parse(include_bytes!(
                "../package-inputs/relation-packs/routing.json"
            ))
            .unwrap(),
        ],
        context: JsonObject::new(),
        evaluated_at: "2026-10-10T12:00:00Z".into(),
        projection_spec: Some(
            parse(include_bytes!(
                "../package-inputs/fixtures/routing/projection-spec.json"
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

#[test]
fn explicit_diagnostics_work_without_changes_and_preserve_both_captures() {
    let a = capture(inputs(), vec![]).unwrap();
    let bytes = canonical_bytes(&a).unwrap();
    let subject = a.inputs.graph.entities[0].id.clone();
    let verified = replay(&a).unwrap();
    let report =
        compare_with_origins(&verified, &verified, std::slice::from_ref(&subject)).unwrap();
    assert_eq!(report["changes"], json!([]));
    assert_eq!(report["diagnosticOrigins"]["subjects"], json!([subject]));
    assert_eq!(report["diagnosticOrigins"]["complete"], true);
    assert_eq!(report["admittedPathsAfter"]["status"], "available");
    assert!(
        report["declaredPathsAfter"]["report"]["visits"]
            .as_array()
            .unwrap()
            .iter()
            .any(|v| v["origin"] == subject)
    );
    assert_eq!(canonical_bytes(&a).unwrap(), bytes);
    assert!(compare_with_origins(&verified, &verified, &vec![subject; 257]).is_err());
    assert!(compare_with_origins(&verified, &verified, &[String::new()]).is_err());
    let report =
        compare_with_origins(&verified, &verified, &["urn:missing:subject".into()]).unwrap();
    assert_eq!(report["admittedPathsAfter"]["report"]["complete"], false);
    assert_eq!(
        report["admittedPathsAfter"]["report"]["unavailableOrigins"],
        json!(["urn:missing:subject"])
    );
}

#[test]
fn duplicate_graph_rejections_retain_occurrences_instead_of_losing_the_comparison() {
    let before = capture(inputs(), vec![]).unwrap();
    let mut input = before.inputs.clone();
    let entity = input.graph.entities[0].clone();
    input.graph.entities.push(entity.clone());
    let after = capture(input, vec![]).unwrap();
    assert_eq!(after.result["status"], "rejected");
    let report = compare(&replay(&before).unwrap(), &replay(&after).unwrap()).unwrap();
    assert_eq!(report["graphIdentityMode"], "occurrence-aware");
    let row = &report["graphRecords"]["entity"]["occurrences"][0];
    assert_eq!(row["id"], entity.id);
    assert_eq!(row["beforeDigests"].as_array().unwrap().len(), 1);
    assert_eq!(row["afterDigests"].as_array().unwrap().len(), 2);
    assert_eq!(report["changes"][0]["afterDigest"], serde_json::Value::Null);
    assert_eq!(report["declaredPathsAfter"]["status"], "unavailable");
    assert_eq!(report["admittedPathsAfter"]["status"], "unavailable");
    assert!(
        report["issueDelta"]["introduced"]
            .as_array()
            .unwrap()
            .iter()
            .any(|r| r["issue"]["code"] == "DUPLICATE_ID")
    );
}

#[test]
fn document_metadata_does_not_manufacture_a_dependency_origin() {
    let before = capture(inputs(), vec![]).unwrap();
    let mut input = before.inputs.clone();
    input.graph.metadata =
        Some(serde_json::from_value(json!({"review":"administrative note"})).unwrap());
    let after = capture(input, vec![]).unwrap();
    let report = compare(&replay(&before).unwrap(), &replay(&after).unwrap()).unwrap();
    assert_eq!(report["changes"][0]["kind"], "document");
    assert_eq!(report["diagnosticOrigins"]["subjects"], json!([]));
    assert_eq!(report["declaredPathsAfter"]["report"]["visits"], json!([]));
    assert_eq!(report["issueDelta"]["introduced"], json!([]));
}

#[test]
fn declared_paths_and_recomputed_admitted_paths_distinguish_inactive_mappings() {
    let mut input = inputs();
    let mapping = input.policy.mappings[4].mapping.clone().unwrap();
    input.policy.mappings[4].applicability = Some(Applicability {
        when: Some(
            parse(br#"{"key":"environment","operator":"equals","value":"production"}"#).unwrap(),
        ),
        unless: None,
    });
    input
        .context
        .insert("environment".into(), json!("development"));
    for pack in &mut input.packs {
        for relation in &mut pack.relations {
            relation.impact_direction = Some(ImpactDirection::SourceToTarget);
        }
    }
    let subject = input
        .graph
        .mappings
        .iter()
        .find(|m| m.id == mapping)
        .unwrap()
        .sources[0]
        .clone();
    let captured = capture(input, vec![]).unwrap();
    assert_eq!(captured.result["status"], "viable");
    let verified = replay(&captured).unwrap();
    let report = compare_with_origins(&verified, &verified, &[subject]).unwrap();
    let uses = |name: &str| {
        report[name]["report"]["visits"]
            .as_array()
            .unwrap()
            .iter()
            .any(|v| {
                v["path"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .any(|s| s["mapping"] == mapping)
            })
    };
    assert!(uses("declaredPathsAfter"));
    assert!(!uses("admittedPathsAfter"));
    let report =
        compare_with_origins(&verified, &verified, std::slice::from_ref(&mapping)).unwrap();
    assert_eq!(
        report["admittedPathsAfter"]["report"]["unavailableOrigins"],
        json!([mapping])
    );
}

#[test]
fn policy_evidence_and_evaluation_context_seed_potential_subjects_without_graph_edits() {
    let before = capture(inputs(), vec![]).unwrap();
    let mut input = before.inputs.clone();
    let subject = input.graph.entities[0].id.clone();
    input.policy.evidence.push(parse(&serde_json::to_vec(&json!({"id":"urn:test:evidence","subjects":[subject],"kind":"observation","result":"supports","producer":"urn:test:producer"})).unwrap()).unwrap());
    let after = capture(input, vec![]).unwrap();
    let report = compare(&replay(&before).unwrap(), &replay(&after).unwrap()).unwrap();
    assert_eq!(report["changes"], json!([]));
    assert!(
        report["diagnosticOrigins"]["subjects"]
            .as_array()
            .unwrap()
            .contains(&json!(subject))
    );
    let mut input = before.inputs.clone();
    input
        .context
        .insert("environment".into(), json!("development"));
    let after = capture(input, vec![]).unwrap();
    let report = compare(&replay(&before).unwrap(), &replay(&after).unwrap()).unwrap();
    for mapping in &before.inputs.graph.mappings {
        assert!(
            report["diagnosticOrigins"]["subjects"]
                .as_array()
                .unwrap()
                .contains(&json!(mapping.id))
        );
    }
}

#[test]
fn legacy_rejection_retains_aggregate_findings_without_inventing_a_failure_stage() {
    let before = capture(inputs(), vec![]).unwrap();
    let mut input = before.inputs.clone();
    input.projection_spec.as_mut().unwrap().slots[0].target_kinds =
        Some(vec!["unavailable-kind".into()]);
    let after = capture(input, vec![]).unwrap();
    assert_eq!(after.result["status"], "rejected");
    let report = compare(&replay(&before).unwrap(), &replay(&after).unwrap()).unwrap();
    assert!(
        !report["issueDelta"]["introduced"]
            .as_array()
            .unwrap()
            .is_empty()
    );
    let compilation = report["issueStages"]
        .as_array()
        .unwrap()
        .iter()
        .find(|s| s["stage"] == "compilation")
        .unwrap();
    assert_eq!(compilation["delta"]["afterKnown"], false);
    assert!(compilation["delta"]["resolved"].is_null());
    // A fresh admission recomputation can establish these paths even though
    // the historical single-profile result did not record its failure stage.
    assert_eq!(report["admittedPathsAfter"]["status"], "available");
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
    assert!(
        !report["diagnosticOrigins"]["subjects"]
            .as_array()
            .unwrap()
            .is_empty()
    );
    let stage = report["issueStages"]
        .as_array()
        .unwrap()
        .iter()
        .find(|row| row["stage"] == "projection" && row["specId"] == changed_id)
        .unwrap();
    assert_eq!(stage["delta"]["beforeKnown"], true);
    assert_eq!(stage["delta"]["afterKnown"], true);
    assert!(!stage["delta"]["introduced"].as_array().unwrap().is_empty());
    let reverse = compare(&replay(&after).unwrap(), &replay(&before).unwrap()).unwrap();
    let stage = reverse["issueStages"]
        .as_array()
        .unwrap()
        .iter()
        .find(|row| row["stage"] == "projection" && row["specId"] == changed_id)
        .unwrap();
    assert!(!stage["delta"]["resolved"].as_array().unwrap().is_empty());
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

fn semantic_comparison_fixture() -> CaptureRecord {
    let mut graph: GraphDocument =
        parse(include_bytes!("../package-inputs/fixtures/laws/graph.json")).unwrap();
    let pack: RelationPack =
        parse(include_bytes!("../package-inputs/fixtures/laws/pack.json")).unwrap();
    let request: CompositionRequest = parse(include_bytes!(
        "../package-inputs/fixtures/laws/request.json"
    ))
    .unwrap();
    let proposal = patamaps_core::derive(
        &patamaps_core::CheckedGraph::check(graph.clone(), vec![pack.clone()]).unwrap(),
        &request,
    );
    assert_eq!(proposal.status, patamaps_core::DerivationStatus::Proposed);
    graph.mappings.push(proposal.mapping.unwrap());
    let proof = proposal.derivation.unwrap();
    let mut policy: PolicyDocument = parse(include_bytes!(
        "../package-inputs/fixtures/laws/policy.json"
    ))
    .unwrap();
    policy
        .semantics
        .as_mut()
        .unwrap()
        .derivations
        .push(proof.clone());
    let spec: ProjectionSpec = parse(include_bytes!(
        "../package-inputs/fixtures/laws/projection-spec.json"
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
    capture(input, vec![]).unwrap()
}

#[test]
fn a_lost_proof_is_reported_separately_from_unchanged_graph_records_and_unknown_projection_risk() {
    let before = semantic_comparison_fixture();
    let proof = before.inputs.policy.semantics.as_ref().unwrap().derivations[0].clone();
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
    let compilation = report["issueStages"]
        .as_array()
        .unwrap()
        .iter()
        .find(|s| s["stage"] == "compilation")
        .unwrap();
    assert!(
        !compilation["delta"]["introduced"]
            .as_array()
            .unwrap()
            .is_empty()
    );
    let projection = report["issueStages"]
        .as_array()
        .unwrap()
        .iter()
        .find(|s| s["stage"] == "projection")
        .unwrap();
    assert_eq!(projection["delta"]["afterKnown"], false);
    assert!(projection["delta"]["resolved"].is_null());
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

#[test]
fn removed_premise_traces_through_recorded_proof_even_when_the_candidate_is_rejected() {
    let before = semantic_comparison_fixture();
    let proof = &before.inputs.policy.semantics.as_ref().unwrap().derivations[0];
    let premise = &proof.premises[1].mapping;
    let mut inputs = before.inputs.clone();
    inputs.graph.mappings.retain(|m| &m.id != premise);
    inputs.policy.graph = GraphBinding {
        id: inputs.graph.id.clone(),
        revision: None,
        digest: Some(canonical_digest(&inputs.graph).unwrap()),
    };
    let after = capture(inputs, vec![]).unwrap();
    assert_eq!(after.result["compilationStatus"], "rejected");
    let saved = (
        canonical_bytes(&before).unwrap(),
        canonical_bytes(&after).unwrap(),
    );
    let report = compare(&replay(&before).unwrap(), &replay(&after).unwrap()).unwrap();
    let paths = &report["recordedProofPathsAfter"]["report"];
    assert_eq!(paths["complete"], true);
    assert!(paths["paths"].as_array().unwrap().contains(&json!({"origin":premise,"subjectId":proof.result.id,"path":[premise,proof.id,proof.result.id]})));
    assert_eq!(report["mappingStates"]["afterKnown"], false);
    assert!(report["mappingStates"]["deactivated"].is_null());
    assert!(report["semantic"]["projections"][0]["riskChanged"].is_null());
    assert_eq!(
        (
            canonical_bytes(&before).unwrap(),
            canonical_bytes(&after).unwrap()
        ),
        saved
    );
    assert_eq!(
        report,
        compare(&replay(&before).unwrap(), &replay(&after).unwrap()).unwrap()
    );
}

#[test]
fn duplicate_cyclic_recorded_proofs_terminate_without_validity_or_completeness_claims() {
    let before = semantic_comparison_fixture();
    let mut inputs = before.inputs.clone();
    let mut cyclic = inputs.policy.semantics.as_ref().unwrap().derivations[0].clone();
    cyclic.premises[0].mapping = cyclic.result.id.clone();
    inputs
        .policy
        .semantics
        .as_mut()
        .unwrap()
        .derivations
        .push(cyclic);
    let after = capture(inputs, vec![]).unwrap();
    assert_eq!(after.result["compilationStatus"], "rejected");
    let report = compare(&replay(&before).unwrap(), &replay(&after).unwrap()).unwrap();
    let impact = &report["recordedProofPathsAfter"]["report"];
    assert_eq!(impact["complete"], false);
    assert_eq!(impact["ambiguousDerivations"].as_array().unwrap().len(), 1);
    assert!(impact["paths"].as_array().unwrap().len() < 10);
}

#[test]
fn comparison_retains_recorded_evidence_changes_without_manufacturing_support_validity() {
    let mut input = inputs();
    input.policy.evidence.push(parse(&canonical_bytes(&json!({"id":"urn:evidence:recorded-support","subjects":["urn:command:greet"],"kind":"recorded-only","result":"supports","producer":"unverified-producer"})).unwrap()).unwrap());
    let before = capture(input.clone(), vec![]).unwrap();
    input.policy.evidence.clear();
    let after = capture(input, vec![]).unwrap();
    let report = compare(&replay(&before).unwrap(), &replay(&after).unwrap()).unwrap();
    assert_eq!(
        report["policyRecords"]["evidence"]["removed"],
        json!(["urn:evidence:recorded-support"])
    );
    assert_eq!(
        report["evidenceSupport"]["recordedSupportLost"],
        json!(["urn:command:greet"])
    );
    let reverse = compare(&replay(&after).unwrap(), &replay(&before).unwrap()).unwrap();
    assert_eq!(
        reverse["evidenceSupport"]["recordedSupportGained"],
        json!(["urn:command:greet"])
    );
}

#[test]
fn proof_trace_bounds_are_explicit_for_many_origins_and_expanding_recorded_paths() {
    let before = semantic_comparison_fixture();
    let mut inputs = before.inputs.clone();
    let template = inputs.graph.entities[0].clone();
    for index in 0..257 {
        let mut entity = template.clone();
        entity.id = format!("urn:added:{index}");
        inputs.graph.entities.push(entity);
    }
    let after = capture(inputs, vec![]).unwrap();
    let report = compare(&replay(&before).unwrap(), &replay(&after).unwrap()).unwrap();
    assert_eq!(report["recordedProofPathsAfter"]["status"], "unavailable");
    assert_eq!(report["recordedProofPathsAfter"]["complete"], false);

    let template = before.inputs.policy.semantics.as_ref().unwrap().derivations[0].clone();
    let mut inputs = before.inputs.clone();
    let proofs = &mut inputs.policy.semantics.as_mut().unwrap().derivations;
    proofs.clear();
    for index in 0..70 {
        let mut proof = template.clone();
        proof.id = format!("urn:recorded:{index:03}");
        proof.result.id = format!("urn:recorded-mapping:{index:03}");
        proof.premises.truncate(1);
        proof.premises[0].mapping = if index == 0 {
            template.premises[0].mapping.clone()
        } else {
            format!("urn:recorded-mapping:{:03}", index - 1)
        };
        proofs.push(proof);
    }
    let after = capture(inputs.clone(), vec![]).unwrap();
    let report = compare(&replay(&before).unwrap(), &replay(&after).unwrap()).unwrap();
    assert_eq!(
        report["recordedProofPathsAfter"]["report"]["complete"],
        false
    );
    assert!(
        report["recordedProofPathsAfter"]["report"]["limits"]
            .as_array()
            .unwrap()
            .contains(&json!("recorded-path-depth-limit"))
    );

    let proofs = &mut inputs.policy.semantics.as_mut().unwrap().derivations;
    for index in 0..proofs.len() {
        proofs[index].id.push_str(&"x".repeat(1000));
        proofs[index].result.id.push_str(&"x".repeat(1000));
        if index > 0 {
            proofs[index].premises[0].mapping = proofs[index - 1].result.id.clone();
        }
    }
    let after = capture(inputs, vec![]).unwrap();
    let report = compare(&replay(&before).unwrap(), &replay(&after).unwrap()).unwrap();
    let paths = &report["recordedProofPathsAfter"];
    assert_eq!(paths["report"]["complete"], false);
    assert!(
        paths["report"]["limits"]
            .as_array()
            .unwrap()
            .contains(&json!("recorded-path-output-limit"))
    );
    assert!(canonical_bytes(paths).unwrap().len() < MAX_INPUT_BYTES);
}

#[test]
fn selectors_and_changed_semantic_limits_have_conservative_mapping_origins() {
    let before = capture(inputs(), vec![]).unwrap();
    let mut input = before.inputs.clone();
    let id = input.policy.mappings[4].mapping.take().unwrap();
    input.policy.mappings[4].select = Some(MappingSelector {
        ids: Some(vec![id]),
        ..Default::default()
    });
    let after = capture(input, vec![]).unwrap();
    assert_eq!(after.result["status"], "viable");
    let report = compare(&replay(&before).unwrap(), &replay(&after).unwrap()).unwrap();
    assert_eq!(report["changes"], json!([]));
    for mapping in &before.inputs.graph.mappings {
        assert!(
            report["diagnosticOrigins"]["subjects"]
                .as_array()
                .unwrap()
                .contains(&json!(mapping.id))
        );
    }
    let before = semantic_comparison_fixture();
    let mut input = before.inputs.clone();
    let bounds = &mut input.policy.semantics.as_mut().unwrap().derivation_limits;
    bounds.max_derivations = SafeInteger::new(bounds.max_derivations.get() + 1).unwrap();
    let after = capture(input, vec![]).unwrap();
    let report = compare(&replay(&before).unwrap(), &replay(&after).unwrap()).unwrap();
    assert_eq!(report["changes"], json!([]));
    for mapping in &before.inputs.graph.mappings {
        assert!(
            report["diagnosticOrigins"]["subjects"]
                .as_array()
                .unwrap()
                .contains(&json!(mapping.id))
        );
    }
}
