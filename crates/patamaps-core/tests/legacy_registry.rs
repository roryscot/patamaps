use patamaps_core::{LegacyRegistryRequest, legacy_registry_request};
use serde_json::{Value, json};

fn invoke(state: Value, action: Value) -> Result<Value, patamaps_core::LegacyRegistryError> {
    let request: LegacyRegistryRequest =
        serde_json::from_value(json!({"state":state,"action":action})).unwrap();
    legacy_registry_request(request)
}
fn portable(id: &str, relations: Value) -> Value {
    json!({"schemaVersion":"1.0.0","id":id,"version":"1","relations":relations})
}
fn state(key: &str, value: &Value, definitions: Value) -> Value {
    json!({"packs":[{"key":key,"json":value.to_string()}],"definitions":definitions,"laws":[]})
}

#[test]
fn failed_registration_never_supplies_commit_handles() {
    let original = portable("urn:old", json!([{"id":"test:old","cyclePolicy":"allow"}]));
    let incoming = portable(
        "urn:new",
        json!([{"id":"test:new","cyclePolicy":"allow"},{"id":"test:old","cyclePolicy":"allow"}]),
    );
    let current = state("urn:old", &original, json!(["test:old"]));
    let error = invoke(
        current.clone(),
        json!({"operation":"register","json":incoming.to_string()}),
    )
    .unwrap_err();
    assert_eq!(error.message, "Relation test:old is already registered");
    assert_eq!(
        invoke(current, json!({"operation":"get","id":"test:new"})).unwrap(),
        Value::Null
    );
}

#[test]
fn lookup_retains_keys_and_reads_current_versions_and_schema_tags() {
    let mut mutated = portable("urn:changed", json!([]));
    mutated["version"] = json!("2");
    let current = state("urn:original", &mutated, json!(["test:original"]));
    assert_eq!(
        invoke(
            current.clone(),
            json!({"operation":"get-pack","id":"urn:original"})
        )
        .unwrap(),
        json!(0)
    );
    assert_eq!(
        invoke(
            current.clone(),
            json!({"operation":"get-pack","id":"urn:changed"})
        )
        .unwrap(),
        Value::Null
    );
    assert_eq!(
        invoke(
            current.clone(),
            json!({"operation":"has-pack","id":"urn:original","version":"1"})
        )
        .unwrap(),
        json!(false)
    );
    assert_eq!(
        invoke(
            current.clone(),
            json!({"operation":"has-pack","id":"urn:original","version":""})
        )
        .unwrap(),
        json!(true)
    );
    assert_eq!(
        invoke(
            current.clone(),
            json!({"operation":"get","id":"test:original"})
        )
        .unwrap(),
        json!(0)
    );
    mutated["schemaVersion"] = json!("2.0.0");
    assert_eq!(
        invoke(
            state("urn:original", &mutated, json!([])),
            json!({"operation":"executable-packs"})
        )
        .unwrap(),
        json!([0])
    );
}

#[test]
fn conflict_uses_stringify_order_and_version_precedence() {
    let existing = r#"{"schemaVersion":"1.0.0","id":"urn:pack","version":"1","relations":[]}"#;
    let reordered = r#"{"id":"urn:pack","schemaVersion":"1.0.0","version":"1","relations":[]}"#;
    let current = json!({"packs":[{"key":"urn:pack","json":existing}]});
    assert_eq!(
        invoke(
            current.clone(),
            json!({"operation":"register","json":existing})
        )
        .unwrap(),
        json!({"inserted":false})
    );
    assert_eq!(
        invoke(
            current.clone(),
            json!({"operation":"register","json":reordered})
        )
        .unwrap_err()
        .message,
        "Relation pack urn:pack@1 conflicts with its registered definition"
    );
    assert_eq!(
        invoke(
            current,
            json!({"operation":"register","json":reordered.replace("\"1\"","\"2\"")})
        )
        .unwrap_err()
        .message,
        "Relation pack urn:pack is already registered at version 1"
    );
}

#[test]
fn malformed_wire_law_is_refused_without_panicking_or_admitting() {
    let malformed = json!({"schemaVersion":"2.0.0","id":"urn:pack","version":"1","relations":[{"id":"test:r","cyclePolicy":"allow"}],"laws":[{"id":"urn:law","operation":"chain","operands":[],"resultRelation":"test:r"}]});
    let current = json!({"packs":[{"key":"urn:pack","json":malformed.to_string()}],"laws":[{"id":"urn:law","pack":"urn:pack","index":0}]});
    assert_eq!(
        invoke(current, json!({"operation":"get-law","id":"urn:law"}))
            .unwrap_err()
            .code,
        "LEGACY_REGISTRY_INPUT"
    );
}

#[test]
fn scalar_identity_is_restored_even_with_non_scalar_metadata() {
    let raw = r#"{"schemaVersion":"1.0.0","id":"urn:pack:\ue000","version":"1","description":"\ud800","relations":[{"id":"test:\ue000","cyclePolicy":"allow"}]}"#;
    let result = invoke(json!({}), json!({"operation":"register","json":raw})).unwrap();
    assert_eq!(result["packId"], json!("urn:pack:\u{e000}"));
    assert_eq!(result["relationIds"], json!(["test:\u{e000}"]));
}

#[test]
fn non_scalar_kinds_cannot_collide_with_scalar_private_use_names() {
    let raw = r#"{"schemaVersion":"1.0.0","id":"urn:pack:p","version":"1","relations":[{"id":"test:r","cyclePolicy":"allow","sourceKinds":["\ud800"]}]}"#;
    let parsed = patamaps_core::ParsedLegacyRelationPack::parse(raw.as_bytes().to_vec()).unwrap();
    let executable = json!({"schemaVersion":"2.0.0","id":"urn:pack:x","version":"1","imports":[{"id":"urn:pack:p","version":"1","digest":parsed.original_digest()}],"relations":[{"id":"test:q","cyclePolicy":"allow","targetKinds":["\u{e000}\u{e001}"]}],"laws":[{"id":"urn:law:r","operation":"reverse","operands":["test:r"],"resultRelation":"test:q","handling":{"authority":"none","lossiness":"conservative","uncertainty":"conservative"}}]});
    let current = json!({"packs":[{"key":"urn:pack:p","json":raw}],"definitions":["test:r"]});
    assert_eq!(
        invoke(
            current,
            json!({"operation":"register","json":executable.to_string()})
        )
        .unwrap_err()
        .message,
        "Law urn:law:r has incompatible reverse endpoint kinds"
    );
}
