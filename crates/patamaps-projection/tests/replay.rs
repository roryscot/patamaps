use patamaps_contracts::*;
use patamaps_projection::*;
use serde_json::json;

fn inputs() -> CaptureInputs {
    CaptureInputs {
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
