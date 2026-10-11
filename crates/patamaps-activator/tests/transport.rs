use patamaps_activator::{ActivationRequest, ActivePointer, ProtectedHost};
use patamaps_contracts::{canonical_bytes, parse};
use serde_json::json;

#[path = "support/lifecycle.rs"]
mod lifecycle;

#[test]
fn transport_never_accepts_host_options_or_ambiguous_json() {
    assert!(parse::<ActivationRequest>(br#"{"schemaVersion":"0.1.0","documentType":"activation-request","prepared":{},"approval":{},"now":"2026-01-01"}"#).is_err());
    assert!(
        parse::<ActivePointer>(br#"{"schemaVersion":"0.1.0","schemaVersion":"0.1.0"}"#).is_err()
    );
    let bytes=canonical_bytes(&json!({"schemaVersion":"0.1.0","documentType":"active-pointer","consumer":"urn:consumer:test","environment":"test","manifest":{"id":"urn:manifest:one","digest":"sha256:bad"},"trustPath":"/tmp/self-appointed"})).unwrap();
    assert!(parse::<ActivePointer>(&bytes).is_err());
}

#[test]
fn unsupported_host_refuses_without_touching_a_path() {
    if !cfg!(target_os = "linux") {
        let error = ProtectedHost::new("/does-not-exist/trust.json").unwrap_err();
        assert_eq!(error.code(), "ACTIVATION_UNSUPPORTED_HOST");
    }
}

#[test]
fn complete_lifecycle_pure_stages_check_proof_unknown_policy_and_unique_budget() {
    use patamaps_contracts::{SafeInteger, UncertaintyStatus};
    use patamaps_governance::{
        ArtifactEmission, EmissionLanguage, GovernedCandidate, prepare_candidate_artifacts,
    };
    use patamaps_projection::{capture, replay};
    let admitted = lifecycle::consumer_capture("1", "service");
    assert_eq!(admitted.result["status"], "viable", "{}", admitted.result);
    let verified = replay(&admitted).unwrap();
    assert_eq!(verified.result()["status"], "viable");
    let risk = &admitted.result["projection"]["semantics"]["risk"];
    assert_eq!(risk["totalCost"], 3);
    assert_eq!(risk["classifications"].as_array().unwrap().len(), 3);
    assert_eq!(risk["inferredMappings"].as_array().unwrap().len(), 1);
    let proof = &admitted
        .inputs
        .policy
        .semantics
        .as_ref()
        .unwrap()
        .derivations[0];
    assert_eq!(proof.result.id, "urn:mapping:greet");
    assert_eq!(proof.dependencies.len(), 2);
    assert!(
        proof
            .uncertainty
            .iter()
            .all(|d| d.status == UncertaintyStatus::Unknown)
    );
    assert_eq!(admitted.inputs.graph.authorities.len(), 2);
    let candidate = GovernedCandidate {
        captures: vec![admitted.clone()],
        emissions: vec![ArtifactEmission {
            projection: "urn:projection:linux".into(),
            language: EmissionLanguage::Rust,
            binding_slot: Some("handler".into()),
        }],
    };
    let artifacts = prepare_candidate_artifacts(&candidate, "urn:consumer:linux", "test").unwrap();
    assert!(artifacts.files()["bindings-0.rs"].contains("crate::service::greet"));
    assert_eq!(admitted.sources.len(), 3);
    if let Some(directory) = std::env::var_os("PATAMAPS_TEST_LIFECYCLE_OUTPUT") {
        let directory = std::path::PathBuf::from(directory);
        std::fs::create_dir(&directory).unwrap();
        std::fs::write(
            directory.join("capture.json"),
            canonical_bytes(&admitted).unwrap(),
        )
        .unwrap();
        for (name, content) in artifacts.files() {
            std::fs::write(directory.join(name), content).unwrap();
        }
    }
    for (kind, code) in [
        ("cost", "CONSUMER_RISK_BUDGET_EXCEEDED"),
        ("unknown", "UNCERTAINTY_STATE_NOT_ALLOWED"),
    ] {
        let mut inputs = admitted.inputs.clone();
        let semantics = inputs.policy.semantics.as_mut().unwrap();
        if kind == "cost" {
            semantics.risk_budgets[0].maximum_total_cost = SafeInteger::new(2).unwrap();
        } else {
            semantics.uncertainty_requirements[0].allowed_states =
                vec![UncertaintyStatus::Supported];
        }
        let refused = capture(inputs, admitted.sources.clone()).unwrap();
        assert_eq!(refused.result["status"], "rejected");
        assert!(
            refused.result["issues"]
                .as_array()
                .unwrap()
                .iter()
                .any(|i| i["code"] == code),
            "{}",
            refused.result
        );
        let mut unprepared = candidate.clone();
        unprepared.captures[0] = refused;
        assert!(prepare_candidate_artifacts(&unprepared, "urn:consumer:linux", "test").is_err());
    }
}
