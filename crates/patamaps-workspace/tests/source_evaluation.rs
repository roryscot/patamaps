use patamaps_contracts::*;
use patamaps_projection::{capture, replay};
use patamaps_workspace::*;
use serde_json::{Value, json};
use std::fs;
#[path = "support/source_fixture.rs"]
mod source_fixture;
use source_fixture::fixture;
fn record(base: &WorkspaceBaseline) -> SourceEvaluationRecord {
    capture_source_evaluation(
        &verify_baseline(base).unwrap(),
        base.captures[0].inputs.clone(),
    )
    .unwrap()
}
fn rehash(value: &mut SourceEvaluationRecord) {
    let mut data = serde_json::to_value(&*value).unwrap();
    let fields = data.as_object_mut().unwrap();
    fields.remove("id");
    fields.remove("digest");
    value.digest = canonical_digest(&data).unwrap();
    value.id = format!("urn:patamaps:source-evaluation:{}", &value.digest[7..]);
}
#[test]
fn exact_membership_and_distinct_candidate_survive_missing_live_sources() {
    let f = fixture();
    let baseline = generate(&f.root, &f.config, None).unwrap().baseline;
    let before = canonical_bytes(&baseline).unwrap();
    let initial = record(&baseline);
    let checked = verify_source_evaluation(&initial).unwrap();
    let report = checked.inspect().unwrap();
    assert_eq!(report.record()["relationship"], "identical");
    assert_eq!(report.record()["sources"][0]["sourceId"], "urn:source:one");
    assert!(
        report.record()["sources"][1]["records"]
            .as_array()
            .unwrap()
            .is_empty()
    );
    assert_eq!(report.record()["authorizationNow"], "not-evaluated");
    let selected = baseline.captures[0].inputs.graph.entities[0].id.clone();
    let membership = report.record()["sources"][0]["records"]
        .as_array()
        .unwrap()
        .iter()
        .find(|r| r["kind"] == "entity" && r["id"] == selected)
        .unwrap();
    assert_eq!(membership["sourceOccurrences"], 1);
    assert_eq!(membership["candidateOccurrences"], 1);
    let mut inputs = baseline.captures[0].inputs.clone();
    inputs.graph.label = Some("candidate metadata only".into());
    let changed = capture_source_evaluation(&verify_baseline(&baseline).unwrap(), inputs).unwrap();
    fs::rename(f.root.join("one.json"), f.root.join("one.retained.json")).unwrap();
    let checked = verify_source_evaluation(&changed).unwrap();
    let report = checked.inspect().unwrap();
    assert_eq!(report.record()["relationship"], "candidate-differs");
    assert_eq!(report.record()["graphMetadataChanged"], true);
    assert_eq!(report.record()["graphChanges"].as_array().unwrap().len(), 1);
    assert_eq!(report.record()["graphChanges"][0]["kind"], "document");
    assert_eq!(report.record()["sourceRediscovery"], "not-performed");
    assert_eq!(canonical_bytes(&baseline).unwrap(), before);
}
#[test]
fn rejected_candidate_retains_source_membership_and_unknown_projection_state() {
    let f = fixture();
    let baseline = generate(&f.root, &f.config, None).unwrap().baseline;
    let initial = record(&baseline);
    let mut inputs = baseline.captures[0].inputs.clone();
    let removed = inputs.graph.mappings.remove(0);
    let changed = capture_source_evaluation(&verify_baseline(&baseline).unwrap(), inputs).unwrap();
    let a = verify_source_evaluation(&initial).unwrap();
    let b = verify_source_evaluation(&changed).unwrap();
    let report = b.inspect().unwrap();
    assert_eq!(report.record()["candidateAdmission"], "rejected");
    let missing = report.record()["sources"][0]["records"]
        .as_array()
        .unwrap()
        .iter()
        .find(|r| r["kind"] == "mapping" && r["id"] == removed.id)
        .unwrap();
    assert_eq!(missing["candidateOccurrences"], 0);
    assert_eq!(missing["candidateState"], "missing");
    let comparison = compare_source_evaluations(&a, &b).unwrap();
    assert!(
        comparison.record()["sourceChanges"]
            .as_array()
            .unwrap()
            .is_empty()
    );
    assert_eq!(comparison.record()["candidate"]["riskDelta"], Value::Null);
    assert_eq!(
        comparison.record()["candidate"]["mappingStates"]["afterKnown"],
        false
    );
}
#[test]
fn ambiguous_candidates_keep_every_occurrence_without_fabricating_deltas() {
    let f = fixture();
    let baseline = generate(&f.root, &f.config, None).unwrap().baseline;
    let initial = record(&baseline);
    let mut inputs = baseline.captures[0].inputs.clone();
    let mut duplicate = inputs.graph.mappings[0].clone();
    duplicate.provenance.asserted_by = "second occurrence".into();
    let id = duplicate.id.clone();
    inputs.graph.mappings.push(duplicate);
    let changed = capture_source_evaluation(&verify_baseline(&baseline).unwrap(), inputs).unwrap();
    let checked = verify_source_evaluation(&changed).unwrap();
    let report = checked.inspect().unwrap();
    assert_eq!(report.record()["candidateAdmission"], "rejected");
    assert_eq!(report.record()["graphChanges"], Value::Null);
    assert_eq!(report.record()["graphComparison"]["status"], "unavailable");
    let membership = report.record()["sources"][0]["records"]
        .as_array()
        .unwrap()
        .iter()
        .find(|r| r["kind"] == "mapping" && r["id"] == id)
        .unwrap();
    assert_eq!(membership["sourceOccurrences"], 1);
    assert_eq!(membership["candidateOccurrences"], 2);
    assert_eq!(membership["candidateState"], "ambiguous");
    let comparison =
        compare_source_evaluations(&verify_source_evaluation(&initial).unwrap(), &checked).unwrap();
    assert_eq!(
        comparison.record()["candidateComparison"]["status"],
        "compared"
    );
    let candidate = &comparison.record()["candidate"];
    assert_eq!(candidate["graphIdentityMode"], "occurrence-aware");
    let occurrence = &candidate["graphRecords"]["mapping"]["occurrences"][0];
    assert_eq!(occurrence["beforeDigests"].as_array().unwrap().len(), 1);
    assert_eq!(occurrence["afterDigests"].as_array().unwrap().len(), 2);
    assert_eq!(candidate["admittedPathsAfter"]["status"], "unavailable");
    assert_eq!(candidate["riskDelta"], Value::Null);
    assert_eq!(candidate["mappingStates"]["afterKnown"], false);
    assert!(
        comparison.record()["sourceChanges"]
            .as_array()
            .unwrap()
            .is_empty()
    );
}
#[test]
fn source_only_revision_changes_bind_a_new_candidate_even_with_identical_graph_inputs() {
    let f = fixture();
    let first = generate(&f.root, &f.config, None).unwrap().baseline;
    let a = record(&first);
    let old = fs::read(f.root.join("one.json")).unwrap();
    fs::write(f.root.join("one.before.json"), &old).unwrap();
    let mut shard: GraphDocument = parse(&old).unwrap();
    shard.revision = Some("source-revision-2".into());
    fs::write(f.root.join("one.json"), canonical_bytes(&shard).unwrap()).unwrap();
    let second = generate(&f.root, &f.config, None).unwrap().baseline;
    let b = capture_source_evaluation(
        &verify_baseline(&second).unwrap(),
        first.captures[0].inputs.clone(),
    )
    .unwrap();
    assert_eq!(
        canonical_bytes(&a.candidate.inputs).unwrap(),
        canonical_bytes(&b.candidate.inputs).unwrap()
    );
    assert_ne!(
        a.candidate.digest, b.candidate.digest,
        "Existing approvals must not authorize a changed source baseline"
    );
    let comparison = compare_source_evaluations(
        &verify_source_evaluation(&a).unwrap(),
        &verify_source_evaluation(&b).unwrap(),
    )
    .unwrap();
    assert_eq!(
        comparison.record()["sourceChanges"]
            .as_array()
            .unwrap()
            .len(),
        1
    );
    assert_eq!(
        comparison.record()["sourceChanges"][0]["sourceId"],
        "urn:source:one"
    );
    assert_eq!(comparison.record()["sourceGraphChanged"], true);
    assert!(
        comparison.record()["candidate"]["changes"]
            .as_array()
            .unwrap()
            .is_empty()
    );
}
#[test]
fn rehashed_envelope_and_individually_valid_candidate_substitutions_refuse() {
    let f = fixture();
    let baseline = generate(&f.root, &f.config, None).unwrap().baseline;
    let original = record(&baseline);
    let mut changed = original.clone();
    changed
        .candidate
        .sources
        .retain(|s| s.id != "urn:patamaps:source-evaluation:baseline-binding");
    changed.candidate = capture(
        changed.candidate.inputs.clone(),
        changed.candidate.sources.clone(),
    )
    .unwrap();
    rehash(&mut changed);
    replay(&changed.candidate).unwrap();
    assert!(
        verify_source_evaluation(&changed)
            .unwrap_err()
            .to_string()
            .contains("SOURCE_CANDIDATE_BINDING")
    );
    let mut changed = original.clone();
    changed.candidate.inputs.graph.id = "urn:unrelated:graph".into();
    changed.candidate = capture(
        changed.candidate.inputs.clone(),
        changed.candidate.sources.clone(),
    )
    .unwrap();
    rehash(&mut changed);
    assert!(
        verify_source_evaluation(&changed)
            .unwrap_err()
            .to_string()
            .contains("SOURCE_CANDIDATE_BINDING")
    );
    let mut changed = original.clone();
    changed.workspace.discovery[0].source_id = "urn:forged:source".into();
    let mut value = serde_json::to_value(&changed.workspace).unwrap();
    value.as_object_mut().unwrap().remove("digest");
    changed.workspace.digest = canonical_digest(&value).unwrap();
    rehash(&mut changed);
    assert!(
        verify_source_evaluation(&changed)
            .unwrap_err()
            .to_string()
            .contains("WORKSPACE_SOURCE_INVENTORY")
    );
    let mut changed = original.clone();
    changed.profile = "unsupported".into();
    rehash(&mut changed);
    assert!(
        verify_source_evaluation(&changed)
            .unwrap_err()
            .to_string()
            .contains("SOURCE_EVALUATION_PROFILE")
    );
    let mut value = serde_json::to_value(&original).unwrap();
    value["authorize"] = json!(true);
    assert!(parse::<SourceEvaluationRecord>(&canonical_bytes(&value).unwrap()).is_err());
    let raw = String::from_utf8(canonical_bytes(&original).unwrap()).unwrap();
    assert!(
        parse::<SourceEvaluationRecord>(
            format!("{{\"schemaVersion\":\"0.1.0\",{}", &raw[1..]).as_bytes()
        )
        .is_err()
    );
}
