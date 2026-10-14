use patamaps_contracts::*;
use patamaps_inspect::{InspectionSelection, SelectionKind, explain_source};
use patamaps_workspace::*;
use serde_json::json;
use std::fs;

fn main() {
    let root = std::env::current_dir().unwrap();
    let mut graph: GraphDocument = parse(&fs::read("graph.json").unwrap()).unwrap();
    let handler = graph
        .entities
        .iter_mut()
        .find(|e| e.kind == "routing:handler")
        .unwrap();
    handler.locators = Some(vec![
        parse(br#"{"uri":"rust:crate::service::greet"}"#).unwrap(),
    ]);
    fs::write("source-shard.json", canonical_bytes(&graph).unwrap()).unwrap();
    let mut policy: PolicyDocument = parse(&fs::read("policy.json").unwrap()).unwrap();
    policy.graph.id = "urn:workspace:installed-source".into();
    policy.graph.revision = Some("1".into());
    fs::write("source-policy.json", canonical_bytes(&policy).unwrap()).unwrap();
    let config: WorkspaceConfig = parse(&canonical_bytes(&json!({
        "schemaVersion":"0.1.0","documentType":"workspace-config","id":policy.graph.id,"namespace":"installed-source","revision":"1",
        "sources":[{"adapter":"portable-shard","id":"urn:source:installed","path":"source-shard.json"}],"packs":["routing.json"],
        "policy":"source-policy.json","projections":[{"path":"projection-spec.json","emissions":[{"path":"source-bindings.rs","language":"rust","bindingSlot":"handler"}]}],
        "context":{"environment":"production"},"evaluatedAt":"2026-10-10T12:00:00Z"
    })).unwrap()).unwrap();
    let baseline = generate(&root, &config, None).unwrap().baseline;
    let original = canonical_bytes(&baseline).unwrap();
    let mut inputs = baseline.captures[0].inputs.clone();
    let selected = inputs
        .graph
        .entities
        .iter_mut()
        .max_by(|a, b| a.id.cmp(&b.id))
        .unwrap();
    selected.label = Some("distinct installed candidate".into());
    let id = selected.id.clone();
    let record = capture_source_evaluation(&verify_baseline(&baseline).unwrap(), inputs).unwrap();
    let original_record = canonical_bytes(&record).unwrap();
    fs::rename("source-shard.json", "source-shard.retained.json").unwrap();
    let verified = verify_source_evaluation(&record).unwrap();
    let report = explain_source(
        &verified,
        None,
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
        report.record()["sources"]["inspection"]["relationship"],
        "candidate-differs"
    );
    assert_eq!(
        report.record()["sources"]["inspection"]["authorizationNow"],
        "not-evaluated"
    );
    assert_eq!(canonical_bytes(&baseline).unwrap(), original);
    assert_eq!(canonical_bytes(&record).unwrap(), original_record);
    println!(
        "{}",
        json!({"profile":SOURCE_EVALUATION_PROFILE,"offlineVerified":true,"distinctCandidate":true,"selectedRetained":true,"inputsUnchanged":true,"activation":"not-performed"})
    );
}
