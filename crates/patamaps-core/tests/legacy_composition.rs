use patamaps_core::{LegacyCompositionRequest, compose_legacy_documents};
use serde_json::{Value, json};

fn shard(id: &str, entities: Value) -> Value {
    json!({"schemaVersion":"2.0.0","id":id,"namespace":"input","entities":entities,"mappings":[],"authorities":[]})
}
fn invoke(documents: Vec<String>) -> Result<Value, patamaps_core::LegacyCompositionError> {
    let request: LegacyCompositionRequest=serde_json::from_value(json!({"documents":documents,"options":{"id":"urn:output","namespace":"output"},"locale":"en-US"})).unwrap();
    compose_legacy_documents(request)
}
#[test]
fn merge_retains_first_handles_in_insertion_order() {
    let a = shard(
        "urn:shard:a",
        json!([{"id":"urn:e:z","kind":"field"},{"id":"urn:e:a","kind":"field"}]),
    );
    let b = shard(
        "urn:shard:b",
        json!([{"id":"urn:e:a","kind":"field"},{"id":"urn:e:c","kind":"field"}]),
    );
    let result = invoke(vec![a.to_string(), b.to_string()]).unwrap();
    assert_eq!(
        result["entities"],
        json!([{"document":0,"item":0},{"document":0,"item":1},{"document":1,"item":1}])
    );
    assert_eq!(
        result["header"]["metadata"]["composedFrom"],
        json!(["urn:shard:a", "urn:shard:b"])
    );
}
#[test]
fn duplicate_shard_id_precedes_conflicting_entities() {
    let a = shard("urn:shard:a", json!([{"id":"urn:e:a","kind":"field"}]));
    let b = shard("urn:shard:a", json!([{"id":"urn:e:a","kind":"different"}]));
    let error = invoke(vec![a.to_string(), b.to_string()]).unwrap_err();
    assert_eq!(error.message, "Duplicate shard id urn:shard:a");
    assert_eq!(error.identifier.as_deref(), Some("urn:shard:a"));
}
#[test]
fn empty_shards_report_original_composition_error() {
    let error = invoke(vec![]).unwrap_err();
    assert_eq!(error.name, "MetamapCompositionError");
    assert_eq!(error.message, "At least one metamap shard is required");
    assert_eq!(error.identifier, None);
}
#[test]
fn pack_version_conflict_precedes_entity_conflict() {
    let mut a = shard("urn:shard:a", json!([{"id":"urn:e:a","kind":"field"}]));
    let mut b = shard("urn:shard:b", json!([{"id":"urn:e:a","kind":"other"}]));
    a["relationPacks"] = json!([{"id":"urn:pack:a","version":"1","digest":"old"}]);
    b["relationPacks"] = json!([{"id":"urn:pack:a","version":"2","digest":"new"}]);
    assert_eq!(
        invoke(vec![a.to_string(), b.to_string()])
            .unwrap_err()
            .message,
        "Relation pack urn:pack:a has incompatible versions 1 and 2"
    );
}
#[test]
fn stable_collation_ties_preserve_distinct_unicode_key_order() {
    let a = r#"{"schemaVersion":"2.0.0","id":"urn:shard:a","entities":[{"id":"urn:e:a","kind":"field","attributes":{"é":1,"e\u0301":2}}],"mappings":[],"authorities":[]}"#;
    let b = r#"{"schemaVersion":"2.0.0","id":"urn:shard:b","entities":[{"id":"urn:e:a","kind":"field","attributes":{"e\u0301":2,"é":1}}],"mappings":[],"authorities":[]}"#;
    assert_eq!(
        invoke(vec![a.into(), b.into()]).unwrap_err().message,
        "Conflicting entity definition for urn:e:a"
    );
}
#[test]
fn composition_defers_endpoint_resolution_to_graph_validation() {
    let mut a = shard("urn:shard:a", json!([]));
    a["mappings"] = json!([{"id":"urn:m:a","relation":"unknown","sources":["urn:e:missing"],"targets":["urn:e:also-missing"]}]);
    assert_eq!(
        invoke(vec![a.to_string()]).unwrap()["mappings"],
        json!([{"document":0,"item":0}])
    );
}
