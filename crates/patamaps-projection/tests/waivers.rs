use patamaps_contracts::*;
use patamaps_projection::*;

#[test]
fn a_compiler_waiver_cannot_opt_a_consumer_into_unknown_loss_and_replay_keeps_refusal() {
    let mut graph: GraphDocument =
        parse(include_bytes!("../../../fixtures/routing/graph.json")).unwrap();
    let mut policy: PolicyDocument =
        parse(include_bytes!("../../../fixtures/routing/policy.json")).unwrap();
    graph.mappings[0].lossiness = Lossiness::Unknown;
    policy.waivers = Some(vec![Waiver {
        id: "urn:waiver:temporary-loss".into(),
        codes: vec!["UNDECLARED_LOSSINESS".into()],
        subjects: vec![graph.mappings[0].id.clone()],
        reason: "Retain an explicitly unresolved migration mapping".into(),
        asserted_by: "team:architecture".into(),
        expires_at: "2026-10-11T12:00:00Z".into(),
    }]);
    let input = CaptureInputs {
        graph,
        policy,
        packs: vec![
            parse(include_bytes!("../../../relation-packs/core.json")).unwrap(),
            parse(include_bytes!("../../../relation-packs/routing.json")).unwrap(),
        ],
        context: JsonObject::new(),
        evaluated_at: "2026-10-10T12:00:00Z".into(),
        projection_spec: None,
        projection_specs: vec![
            parse(include_bytes!(
                "../../../fixtures/routing/projection-spec.json"
            ))
            .unwrap(),
        ],
    };
    let saved = capture(input.clone(), vec![]).unwrap();
    assert_eq!(saved.result["compilationStatus"], "viable");
    assert_eq!(saved.result["status"], "rejected");
    assert!(
        saved.result["issues"]
            .as_array()
            .unwrap()
            .iter()
            .any(|i| i["code"] == "LOSSY_PROJECTION_LINK")
    );
    assert_eq!(
        canonical_bytes(replay(&saved).unwrap().result()).unwrap(),
        canonical_bytes(&saved.result).unwrap()
    );
    assert_eq!(saved.inputs.graph.mappings[0].lossiness, Lossiness::Unknown);

    let mut expired = input;
    expired.evaluated_at = "2026-10-11T12:00:00Z".into();
    let refused = capture(expired, vec![]).unwrap();
    assert_eq!(refused.result["compilationStatus"], "rejected");
    assert_eq!(refused.result["status"], "rejected");
    assert!(refused.result["generation"].is_null());
    assert_eq!(
        canonical_bytes(replay(&refused).unwrap().result()).unwrap(),
        canonical_bytes(&refused.result).unwrap()
    );
}
