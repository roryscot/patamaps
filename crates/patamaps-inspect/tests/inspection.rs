use patamaps_contracts::*;
use patamaps_core::{CancellationToken, CheckError, CheckedGraph, WorkControl};
use patamaps_governance::GovernanceScope;
use patamaps_inspect::*;
use patamaps_projection::{CaptureInputs, CaptureRecord, capture, replay};
use serde::de::DeserializeOwned;
use serde_json::{Value, json};
use std::time::Duration;
fn typed<T: DeserializeOwned>(v: Value) -> T {
    parse(&canonical_bytes(&v).unwrap()).unwrap()
}
fn base() -> CaptureRecord {
    capture(CaptureInputs {
        projection_specs: vec![],
        graph:typed(json!({"schemaVersion":"0.1.0","documentType":"graph","id":"urn:graph:repair","namespace":"repair","entities":[{"id":"urn:command:greet","kind":"routing:command","label":"<img src=x onerror=alert(1)>"},{"id":"urn:handler:a","kind":"routing:handler"},{"id":"urn:handler:b","kind":"routing:handler"}],"mappings":[{"id":"urn:mapping:greet","relation":"routing:handled_by","sources":["urn:command:greet"],"targets":["urn:handler:missing"],"cardinality":"one-to-one","lossiness":"lossless","provenance":{"status":"declared","assertedBy":"proposer"}}],"authorities":[]})),
        packs:vec![parse(include_bytes!("../../../relation-packs/routing.json")).unwrap()],
        policy:typed(json!({"schemaVersion":"0.1.0","documentType":"policy","id":"urn:policy:repair","graph":{"id":"urn:graph:repair"},"mappings":[{"mapping":"urn:mapping:greet","coverage":"total","determinism":"deterministic","reversibility":"irreversible"}],"constraints":[],"evidence":[]})),
        context:Default::default(),evaluated_at:"2026-10-10T00:00:00Z".into(),
        projection_spec:Some(typed(json!({"schemaVersion":"0.1.0","documentType":"projection-spec","id":"urn:projection:repair","consumer":"urn:consumer:repair","select":{"ids":["urn:command:greet"]},"slots":[{"name":"handler","relation":"routing:handled_by","direction":"outgoing","cardinality":"exactly-one","targetKinds":["routing:handler"]}]}))),
    },vec![]).unwrap()
}
fn request() -> RepairRequest {
    let baseline = base();
    let expected_digest = canonical_digest(&baseline.inputs.graph.mappings[0]).unwrap();
    RepairRequest {
        schema_version: ProtocolVersion::Draft1,
        document_type: RepairType::Draft1,
        baseline,
        consumer: "urn:consumer:repair".into(),
        allowed_facts: vec![GovernanceScope {
            subject: "*".into(),
            fact: "*".into(),
        }],
        protected_facts: vec![],
        edits: vec![
            RepairEdit {
                id: "cheaper".into(),
                semantic_cost: SafeInteger::new(1).unwrap(),
                operation: RepairOperation::SelectTarget {
                    mapping_index: SafeInteger::new(0).unwrap(),
                    expected_digest: expected_digest.clone(),
                    target: "urn:handler:a".into(),
                },
            },
            RepairEdit {
                id: "dearer".into(),
                semantic_cost: SafeInteger::new(5).unwrap(),
                operation: RepairOperation::SelectTarget {
                    mapping_index: SafeInteger::new(0).unwrap(),
                    expected_digest,
                    target: "urn:handler:b".into(),
                },
            },
        ],
        bounds: RepairBounds {
            maximum_candidates: SafeInteger::new(100).unwrap(),
            maximum_edits: SafeInteger::new(2).unwrap(),
            maximum_derivation_depth: SafeInteger::new(128).unwrap(),
            maximum_elapsed_milliseconds: SafeInteger::new(60_000).unwrap(),
            maximum_work_units: SafeInteger::new(2_000_000).unwrap(),
        },
    }
}
fn blocked(report: &RepairReport, code: &str) {
    assert!(
        report.attempts.iter().any(|a| a["status"] == "blocked"
            && a["issues"]
                .as_array()
                .unwrap()
                .iter()
                .any(|i| i["code"] == code)),
        "{report:?}"
    );
}
fn code(e: CheckError, wanted: &str) {
    assert!(e.0.iter().any(|i| i.code == wanted), "{e:?}");
}
#[test]
fn finite_space_compiles_ranks_and_requires_approval_without_source_mutation() {
    let r = request();
    let bytes = canonical_bytes(&r.baseline).unwrap();
    let report = search_repairs(&r, CancellationToken::default()).unwrap();
    assert_eq!(report.status, "complete");
    assert_eq!(report.coverage["totalCombinations"], "3");
    assert_eq!(report.coverage["examined"], 3);
    assert_eq!(report.coverage["unexamined"], "0");
    assert_eq!(report.proposals.len(), 2);
    assert_eq!(report.minimality["status"], "within-finite-space");
    assert_eq!(report.minimality["global"], false);
    assert!(!report.applied);
    let best = report
        .attempts
        .iter()
        .find(|a| a["id"] == report.proposals[0])
        .unwrap();
    assert_eq!(best["rank"]["semanticCost"], 1);
    assert_eq!(best["authorization"], "approval-required");
    assert!(
        best["requirements"]
            .as_array()
            .unwrap()
            .iter()
            .any(|r| r["action"] == "rebind-implementation")
    );
    let candidate: CaptureRecord = typed(best["candidate"].clone());
    assert_eq!(replay(&candidate).unwrap().result()["status"], "viable");
    assert_eq!(candidate.sources.len(), 0);
    assert_eq!(canonical_bytes(&r.baseline).unwrap(), bytes);
    blocked(&report, "REPAIR_CONFLICTING_EDITS");
}
#[test]
fn protected_facts_and_exact_record_expectations_block_edits() {
    let mut r = request();
    r.protected_facts.push(GovernanceScope {
        subject: "urn:mapping:greet".into(),
        fact: "mapping.record".into(),
    });
    blocked(
        &search_repairs(&r, CancellationToken::default()).unwrap(),
        "REPAIR_PROTECTED_FACT",
    );
    r.protected_facts.clear();
    r.allowed_facts.clear();
    blocked(
        &search_repairs(&r, CancellationToken::default()).unwrap(),
        "REPAIR_SCOPE_DENIED",
    );
    r.allowed_facts.push(GovernanceScope {
        subject: "*".into(),
        fact: "*".into(),
    });
    if let RepairOperation::SelectTarget {
        expected_digest, ..
    } = &mut r.edits[0].operation
    {
        *expected_digest = "sha256:changed".into();
    }
    blocked(
        &search_repairs(&r, CancellationToken::default()).unwrap(),
        "REPAIR_STALE_MAPPING",
    );
}
#[test]
fn restore_and_supply_can_be_jointly_useful_but_never_replace_policy_or_invent_proofs() {
    let mut r = request();
    let mut restored = r.baseline.inputs.graph.mappings[0].clone();
    restored.targets = vec!["urn:handler:a".into()];
    let mut inputs = r.baseline.inputs.clone();
    inputs.graph.mappings.clear();
    inputs.policy.mappings.clear();
    r.baseline = capture(inputs, vec![]).unwrap();
    let declaration: Declaration = typed(
        json!({"mapping":restored.id,"coverage":"total","determinism":"deterministic","reversibility":"irreversible"}),
    );
    r.edits = vec![
        RepairEdit {
            id: "declare".into(),
            semantic_cost: SafeInteger::new(1).unwrap(),
            operation: RepairOperation::SupplyDeclaration {
                declaration: declaration.clone(),
            },
        },
        RepairEdit {
            id: "restore".into(),
            semantic_cost: SafeInteger::new(1).unwrap(),
            operation: RepairOperation::RestoreMapping {
                mapping: restored.clone(),
            },
        },
    ];
    let report = search_repairs(&r, CancellationToken::default()).unwrap();
    assert_eq!(report.status, "complete");
    assert_eq!(report.proposals.len(), 1);
    let viable = report
        .attempts
        .iter()
        .find(|a| a["viable"] == true)
        .unwrap();
    assert!(
        viable["requirements"]
            .as_array()
            .unwrap()
            .iter()
            .any(|r| r["action"] == "change-policy")
    );
    r = request();
    r.edits = vec![RepairEdit {
        id: "replace".into(),
        semantic_cost: SafeInteger::new(0).unwrap(),
        operation: RepairOperation::SupplyDeclaration { declaration },
    }];
    blocked(
        &search_repairs(&r, CancellationToken::default()).unwrap(),
        "REPAIR_DECLARATION_EXISTS",
    );
    restored.provenance.status = ProvenanceStatus::Inferred;
    r.baseline.inputs.graph.mappings.clear();
    r.baseline = capture(r.baseline.inputs.clone(), vec![]).unwrap();
    r.edits[0].operation = RepairOperation::RestoreMapping { mapping: restored };
    blocked(
        &search_repairs(&r, CancellationToken::default()).unwrap(),
        "REPAIR_PROOF_INVENTION",
    );
}
#[test]
fn exact_duplicate_removal_and_unchanged_keeper_are_enforced() {
    let mut r = request();
    let mut inputs = r.baseline.inputs.clone();
    inputs.graph.mappings[0].targets = vec!["urn:handler:a".into()];
    inputs.graph.mappings.push(inputs.graph.mappings[0].clone());
    r.baseline = capture(inputs, vec![]).unwrap();
    let digest = canonical_digest(&r.baseline.inputs.graph.mappings[0]).unwrap();
    r.edits = vec![RepairEdit {
        id: "remove".into(),
        semantic_cost: SafeInteger::new(0).unwrap(),
        operation: RepairOperation::RemoveDuplicate {
            mapping_index: SafeInteger::new(1).unwrap(),
            expected_digest: digest.clone(),
            keep_index: SafeInteger::new(0).unwrap(),
            keep_digest: digest.clone(),
        },
    }];
    let report = search_repairs(&r, CancellationToken::default()).unwrap();
    assert_eq!(report.proposals.len(), 1);
    assert_eq!(
        report.attempts[0]["candidate"]["inputs"]["graph"]["mappings"]
            .as_array()
            .unwrap()
            .len(),
        1
    );
    assert_eq!(report.attempts[0]["comparison"]["status"], "compared");
    let comparison = &report.attempts[0]["comparison"]["report"];
    assert_eq!(comparison["graphIdentityMode"], "occurrence-aware");
    let occurrence = &comparison["graphRecords"]["mapping"]["occurrences"][0];
    assert_eq!(
        occurrence["beforeDigests"],
        json!([digest.clone(), digest.clone()])
    );
    assert_eq!(occurrence["afterDigests"], json!([digest.clone()]));
    assert_eq!(comparison["declaredPathsBefore"]["status"], "unavailable");
    assert_eq!(comparison["declaredPathsAfter"]["status"], "available");
    assert_eq!(report.attempts[0]["authorization"], "approval-required");
    r.edits.push(RepairEdit {
        id: "change-keeper".into(),
        semantic_cost: SafeInteger::new(0).unwrap(),
        operation: RepairOperation::SelectTarget {
            mapping_index: SafeInteger::new(0).unwrap(),
            expected_digest: digest,
            target: "urn:handler:b".into(),
        },
    });
    blocked(
        &search_repairs(&r, CancellationToken::default()).unwrap(),
        "REPAIR_KEEPER_CHANGED",
    );
}
#[test]
fn partial_budgets_cancellation_and_overflow_never_claim_minimality() {
    let mut r = request();
    r.bounds.maximum_candidates = SafeInteger::new(1).unwrap();
    let report = search_repairs(&r, CancellationToken::default()).unwrap();
    assert_eq!(report.status, "incomplete");
    assert_eq!(report.coverage["examined"], 1);
    assert_eq!(report.coverage["unexamined"], "2");
    assert_eq!(report.minimality["status"], "not-established");
    r.bounds.maximum_candidates = SafeInteger::new(100).unwrap();
    r.bounds.maximum_edits = SafeInteger::new(1).unwrap();
    let report = search_repairs(&r, CancellationToken::default()).unwrap();
    assert_eq!(report.coverage["excludedByEditLimit"], "1");
    assert_eq!(report.status, "incomplete");
    let token = CancellationToken::default();
    token.cancel();
    let report = search_repairs(&r, token).unwrap();
    assert_eq!(report.coverage["examined"], 0);
    assert!(
        report.coverage["stopReasons"]
            .as_array()
            .unwrap()
            .contains(&json!("WORK_CANCELLED"))
    );
    r = request();
    r.bounds.maximum_work_units = SafeInteger::new(2).unwrap();
    let report = search_repairs(&r, CancellationToken::default()).unwrap();
    assert_eq!(report.coverage["examined"], 0);
    assert!(
        report.coverage["stopReasons"]
            .as_array()
            .unwrap()
            .contains(&json!("WORK_UNIT_LIMIT"))
    );
    r.bounds.maximum_work_units = SafeInteger::new(100_000).unwrap();
    r.bounds.maximum_elapsed_milliseconds = SafeInteger::new(0).unwrap();
    let report = search_repairs(&r, CancellationToken::default()).unwrap();
    assert_eq!(report.status, "incomplete");
    assert!(
        report.coverage["stopReasons"]
            .as_array()
            .unwrap()
            .contains(&json!("WORK_ELAPSED_LIMIT"))
    );
    r = request();
    for edit in &mut r.edits {
        edit.semantic_cost = SafeInteger::new(MAX_SAFE_INTEGER).unwrap();
    }
    blocked(
        &search_repairs(&r, CancellationToken::default()).unwrap(),
        "REPAIR_COST_OVERFLOW",
    );
}
#[test]
fn captured_explanation_preserves_rejection_ambiguity_missing_sources_and_safe_html() {
    let capture = base();
    let report = explain(
        &capture,
        None,
        InspectionSelection {
            kind: SelectionKind::Entity,
            id: "urn:command:greet".into(),
        },
        1,
        1,
    )
    .unwrap();
    assert_eq!(report.record()["admission"], "rejected");
    assert_eq!(report.record()["selection"]["state"], "known");
    assert_eq!(report.record()["navigation"]["status"], "truncated");
    assert_eq!(report.record()["generation"], Value::Null);
    assert_eq!(report.record()["approval"]["status"], "not-evaluated");
    let html = render_debugger(&report).unwrap();
    assert!(!html.contains("<img"));
    assert!(html.contains("&lt;img"));
    assert!(!html.contains("<script"));
    assert!(html.contains("default-src 'none'"));
    assert!(!html.contains("unsafe-inline"));
    assert!(html.contains("style-src 'sha256-"));
    assert!(html.contains("Skip to inspection"));
    assert!(html.contains("<summary>"));
    let missing = explain(
        &capture,
        None,
        InspectionSelection {
            kind: SelectionKind::Entity,
            id: "urn:missing".into(),
        },
        128,
        256,
    )
    .unwrap();
    assert_eq!(missing.record()["selection"]["state"], "missing");
    let mut inputs = capture.inputs.clone();
    inputs.graph.entities.push(inputs.graph.entities[0].clone());
    let ambiguous = capture_fn(inputs);
    let report = explain(
        &ambiguous,
        None,
        InspectionSelection {
            kind: SelectionKind::Entity,
            id: "urn:command:greet".into(),
        },
        128,
        256,
    )
    .unwrap();
    assert_eq!(report.record()["selection"]["state"], "ambiguous");
    assert_eq!(report.record()["impact"], Value::Null);
}
fn capture_fn(inputs: CaptureInputs) -> CaptureRecord {
    capture(inputs, vec![]).unwrap()
}
#[test]
fn bounded_focus_retains_late_selected_entities_and_ambiguous_mappings() {
    let capture = base();
    let before = canonical_bytes(&capture).unwrap();
    let selected = "urn:handler:b";
    let report = explain(
        &capture,
        None,
        InspectionSelection {
            kind: SelectionKind::Entity,
            id: selected.into(),
        },
        1,
        1,
    )
    .unwrap();
    assert_eq!(report.record()["selection"]["state"], "known");
    assert_eq!(report.record()["subjects"][0]["id"], selected);
    assert_eq!(
        report.record()["navigation"]["subjectIds"],
        json!([selected])
    );
    assert_eq!(report.record()["navigation"]["omittedSubjects"], 2);
    assert_eq!(report.record()["navigation"]["status"], "truncated");
    assert_eq!(canonical_bytes(&capture).unwrap(), before);

    let mut inputs = capture.inputs.clone();
    let mut late = inputs.graph.mappings[0].clone();
    late.id = "urn:mapping:z-selected".into();
    let mut conflicting = late.clone();
    conflicting.targets = vec!["urn:handler:b".into()];
    inputs.graph.mappings.extend([late, conflicting]);
    let capture = capture_fn(inputs);
    let before = canonical_bytes(&capture).unwrap();
    let report = explain(
        &capture,
        None,
        InspectionSelection {
            kind: SelectionKind::Mapping,
            id: "urn:mapping:z-selected".into(),
        },
        1,
        1,
    )
    .unwrap();
    assert_eq!(report.record()["selection"]["state"], "ambiguous");
    assert_eq!(report.record()["selection"]["occurrences"], 2);
    assert_eq!(
        report.record()["mappings"][0]["id"],
        "urn:mapping:z-selected"
    );
    assert_eq!(
        report.record()["mappings"][0]["records"]
            .as_array()
            .unwrap()
            .len(),
        2
    );
    assert_ne!(
        report.record()["mappings"][0]["records"][0],
        report.record()["mappings"][0]["records"][1]
    );
    assert_eq!(report.record()["mappings"][0]["activity"], "unavailable");
    assert_eq!(report.record()["navigation"]["omittedMappings"], 1);
    assert_eq!(canonical_bytes(&capture).unwrap(), before);

    let missing = explain(
        &capture,
        None,
        InspectionSelection {
            kind: SelectionKind::Mapping,
            id: "urn:mapping:missing".into(),
        },
        1,
        1,
    )
    .unwrap();
    assert_eq!(missing.record()["selection"]["state"], "missing");
    assert_eq!(missing.record()["selection"]["occurrences"], 0);
    assert!(
        missing.record()["mappings"]
            .as_array()
            .unwrap()
            .iter()
            .all(|m| m["id"] != "urn:mapping:missing")
    );
}
#[test]
fn hot_graph_work_and_recursive_result_data_cannot_bypass_controls() {
    let base = base();
    let token = CancellationToken::default();
    let control = WorkControl::new(token, Duration::from_secs(5), 1);
    code(
        CheckedGraph::check_controlled(
            base.inputs.graph.clone(),
            base.inputs.packs.clone(),
            &control,
        )
        .unwrap_err(),
        "WORK_UNIT_LIMIT",
    );
    let mut malformed = base.clone();
    let mut result = json!({});
    for _ in 0..100 {
        result = json!({"nested":result});
    }
    malformed.result = result;
    code(replay(&malformed).unwrap_err(), "CAPTURE_RESOURCE_LIMIT");
}
