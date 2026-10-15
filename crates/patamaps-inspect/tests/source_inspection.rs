use base64::{Engine, engine::general_purpose::STANDARD};
use ed25519_dalek::{Signer, SigningKey};
use patamaps_contracts::*;
use patamaps_governance::*;
use patamaps_inspect::{InspectionSelection, SelectionKind, explain_source, render_debugger};
use patamaps_workspace::*;
use serde_json::{Value, json};
use std::fs;

#[path = "../../patamaps-workspace/tests/support/source_fixture.rs"]
mod source_fixture;
use source_fixture::fixture;

#[test]
fn focused_source_report_and_escaped_html_use_verified_offline_context() {
    let f = fixture();
    let baseline = generate(&f.root, &f.config, None).unwrap().baseline;
    let initial = capture_source_evaluation(
        &verify_baseline(&baseline).unwrap(),
        baseline.captures[0].inputs.clone(),
    )
    .unwrap();
    let mut inputs = baseline.captures[0].inputs.clone();
    let selected = inputs
        .graph
        .entities
        .iter_mut()
        .max_by(|a, b| a.id.cmp(&b.id))
        .unwrap();
    selected.label = Some("<script>source-label</script>".into());
    let id = selected.id.clone();
    let changed = capture_source_evaluation(&verify_baseline(&baseline).unwrap(), inputs).unwrap();
    let original_bytes = (
        canonical_bytes(&initial).unwrap(),
        canonical_bytes(&changed).unwrap(),
    );
    fs::rename(f.root.join("one.json"), f.root.join("one.retained.json")).unwrap();
    let before = verify_source_evaluation(&initial).unwrap();
    let after = verify_source_evaluation(&changed).unwrap();
    let report = explain_source(
        &after,
        Some(&before),
        InspectionSelection {
            kind: SelectionKind::Entity,
            id: id.clone(),
        },
        1,
        1,
    )
    .unwrap();
    assert_eq!(report.record()["subjects"][0]["id"], id);
    assert_eq!(
        report.record()["navigation"]["omittedSubjects"],
        baseline.captures[0].inputs.graph.entities.len() - 1
    );
    let source = &report.record()["sources"]["inspection"];
    assert_eq!(source["relationship"], "candidate-differs");
    assert_eq!(source["sourceRediscovery"], "not-performed");
    assert_eq!(source["authorizationNow"], "not-evaluated");
    assert_eq!(
        report.record()["sources"]["comparison"]["status"],
        "compared"
    );
    let member = source["sources"][0]["records"]
        .as_array()
        .unwrap()
        .iter()
        .find(|r| r["kind"] == "entity" && r["id"] == id)
        .unwrap();
    assert_eq!(member["sourceOccurrences"], 1);
    assert_eq!(member["candidateOccurrences"], 1);
    let html = render_debugger(&report).unwrap();
    assert!(html.contains("&lt;script&gt;source-label&lt;/script&gt;"));
    assert!(!html.contains("<script>source-label</script>"));
    assert!(html.contains("verified-recorded-shards-to-candidate-inputs"));
    assert!(html.contains("style-src 'sha256-"));
    assert!(!html.contains("unsafe-inline"));
    assert_eq!(canonical_bytes(&initial).unwrap(), original_bytes.0);
    assert_eq!(canonical_bytes(&changed).unwrap(), original_bytes.1);
}

#[test]
fn source_only_change_invalidates_the_actual_artifact_manifest() {
    let f = fixture();
    let first = generate(&f.root, &f.config, None).unwrap().baseline;
    let mut inputs = first.captures[0].inputs.clone();
    for spec in &mut inputs.projection_specs {
        spec.consumer = Some("urn:consumer:source-test".into());
    }
    if let Some(spec) = &mut inputs.projection_spec {
        spec.consumer = Some("urn:consumer:source-test".into());
    }
    let initial =
        capture_source_evaluation(&verify_baseline(&first).unwrap(), inputs.clone()).unwrap();
    let old = fs::read(f.root.join("one.json")).unwrap();
    fs::write(f.root.join("one.before.json"), &old).unwrap();
    let mut shard: GraphDocument = parse(&old).unwrap();
    shard.revision = Some("source-revision-2".into());
    fs::write(f.root.join("one.json"), canonical_bytes(&shard).unwrap()).unwrap();
    let second = generate(&f.root, &f.config, None).unwrap().baseline;
    let changed = capture_source_evaluation(&verify_baseline(&second).unwrap(), inputs).unwrap();
    assert_eq!(
        canonical_bytes(&initial.candidate.inputs).unwrap(),
        canonical_bytes(&changed.candidate.inputs).unwrap()
    );
    let prepare = |record: &SourceEvaluationRecord| {
        prepare_candidate_artifacts(
            &GovernedCandidate {
                captures: vec![record.candidate.clone()],
                emissions: vec![],
            },
            "urn:consumer:source-test",
            "production",
        )
        .unwrap()
    };
    let before = prepare(&initial);
    let after = prepare(&changed);
    assert_ne!(before.manifest().digest, after.manifest().digest);
    assert_ne!(before.files(), after.files());
    // Public fixture trust and a synthetic test-only signer. Production APIs
    // still receive only externally signed approval bytes.
    let signer = SigningKey::from_bytes(&[73; 32]);
    let mut public_key = vec![
        0x30, 0x2a, 0x30, 0x05, 0x06, 0x03, 0x2b, 0x65, 0x70, 0x03, 0x21, 0x00,
    ];
    public_key.extend(signer.verifying_key().as_bytes());
    let trust:TrustedConsumer = parse(&canonical_bytes(&json!({
        "schemaVersion":"0.1.0","documentType":"trusted-consumer","mode":"governed",
        "id":"urn:trust:source-test","revision":"1","consumer":"urn:consumer:source-test","environment":"production",
        "principals":[{"id":"fixture-owner","role":"owner","revoked":false}],
        "keys":[{"id":"fixture-key","principal":"fixture-owner","algorithm":"Ed25519","publicKey":STANDARD.encode(public_key),"validFrom":"2026-10-10T00:00:00.000Z","validUntil":"2026-10-11T00:00:00.000Z","revoked":false}],
        "grants":[{"id":"fixture-grant","principal":"fixture-owner","actions":["activate","bootstrap","rollback","rebind-implementation","change-graph","change-authority","change-policy","relax-policy","raise-budget","add-waiver","change-law","change-source","change-context","change-projection"],"scopes":[{"subject":"*","fact":"*"}],"validFrom":"2026-10-10T00:00:00.000Z","validUntil":"2026-10-11T00:00:00.000Z","revoked":false}]
    })).unwrap()).unwrap();
    let propose = |record: &SourceEvaluationRecord| {
        create_proposal(
            &GovernedCandidate {
                captures: vec![record.candidate.clone()],
                emissions: vec![],
            },
            ProposalOptions {
                consumer: "urn:consumer:source-test",
                environment: "production",
                proposer: "fixture-agent",
                intent: DeploymentIntent::Deploy,
                trust: &trust,
                baseline: None,
            },
        )
        .unwrap()
    };
    let old_proposal = propose(&initial);
    let new_proposal = propose(&changed);
    verify_artifact_bytes(&old_proposal, before.files()).unwrap();
    verify_artifact_bytes(&new_proposal, after.files()).unwrap();
    assert!(verify_artifact_bytes(&new_proposal, before.files()).is_err());
    let grants = vec!["fixture-grant".into()];
    let payload = create_approval_payload(
        &old_proposal,
        ApprovalOptions {
            principal: "fixture-owner",
            key: "fixture-key",
            grants: &grants,
            issued_at: "2026-10-10T11:59:00.000Z",
            expires_at: "2026-10-10T13:00:00.000Z",
        },
    )
    .unwrap();
    let signature = signer.sign(&approval_signing_bytes(&payload).unwrap());
    let approval = attach_signature(payload, &STANDARD.encode(signature.to_bytes())).unwrap();
    let context = || VerificationContext {
        trust: &trust,
        baseline: None,
        now: "2026-10-10T12:00:00.000Z",
    };
    verify_approval(&old_proposal, &approval, context()).unwrap();
    let refused = verify_approval(&new_proposal, &approval, context()).unwrap_err();
    assert!(
        refused
            .0
            .iter()
            .any(|issue| issue.code == "GOVERNANCE_APPROVAL_CONTENT_MISMATCH")
    );
}

#[test]
fn ambiguous_source_focus_retains_records_and_compares_recorded_occurrences() {
    let f = fixture();
    let baseline = generate(&f.root, &f.config, None).unwrap().baseline;
    let initial = capture_source_evaluation(
        &verify_baseline(&baseline).unwrap(),
        baseline.captures[0].inputs.clone(),
    )
    .unwrap();
    let mut inputs = initial.candidate.inputs.clone();
    let mut duplicate = inputs
        .graph
        .mappings
        .iter()
        .max_by(|a, b| a.id.cmp(&b.id))
        .unwrap()
        .clone();
    let id = duplicate.id.clone();
    duplicate.provenance.asserted_by = "duplicate occurrence".into();
    inputs.graph.mappings.push(duplicate);
    let changed = capture_source_evaluation(&verify_baseline(&baseline).unwrap(), inputs).unwrap();
    let before = verify_source_evaluation(&initial).unwrap();
    let after = verify_source_evaluation(&changed).unwrap();
    let report = explain_source(
        &after,
        Some(&before),
        InspectionSelection {
            kind: SelectionKind::Mapping,
            id,
        },
        1,
        1,
    )
    .unwrap();
    assert_eq!(report.record()["selection"]["state"], "ambiguous");
    assert_eq!(
        report.record()["mappings"][0]["records"]
            .as_array()
            .unwrap()
            .len(),
        2
    );
    assert_eq!(
        report.record()["sources"]["inspection"]["graphChanges"],
        Value::Null
    );
    assert_eq!(
        report.record()["sources"]["comparison"]["report"]["candidateComparison"]["status"],
        "compared"
    );
    let candidate = &report.record()["sources"]["comparison"]["report"]["candidate"];
    assert_eq!(candidate["graphIdentityMode"], "occurrence-aware");
    let occurrence = &candidate["graphRecords"]["mapping"]["occurrences"][0];
    assert_eq!(occurrence["beforeDigests"].as_array().unwrap().len(), 1);
    assert_eq!(occurrence["afterDigests"].as_array().unwrap().len(), 2);
    assert_eq!(candidate["admittedPathsAfter"]["status"], "unavailable");
    assert_eq!(candidate["riskDelta"], Value::Null);
    assert_eq!(report.record()["approval"]["active"], "not-evaluated");
}
