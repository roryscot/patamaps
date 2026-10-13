use patamaps_core::{LegacyGraphRequest, legacy_graph_request};
use serde_json::{Value, json};

fn registry() -> Value {
    json!({"definitions":[{"key":"test:r","value":{"id":"test:r","cyclePolicy":"allow"}}]})
}
fn document() -> Value {
    json!({"schemaVersion":"2.0.0","id":"urn:graph:test","namespace":"test",
        "entities":[{"id":"urn:e:a","kind":"field"},{"id":"urn:e:b","kind":"field"},{"id":"urn:e:c","kind":"field"}],
        "mappings":[{"id":"urn:m:z","relation":"test:r","sources":["urn:e:a"],"targets":["urn:e:c","urn:e:b"],"cardinality":"one-to-many","lossiness":"lossless","provenance":{"status":"declared","assertedBy":"test"}}],
        "authorities":[]})
}
fn invoke(value: Value) -> Result<Value, patamaps_core::LegacyGraphError> {
    legacy_graph_request(serde_json::from_value::<LegacyGraphRequest>(value).unwrap())
}
fn index(document: &Value) -> Value {
    let built =
        invoke(json!({"operation":"build","registry":registry(),"document":document})).unwrap();
    assert_eq!(built["validation"]["valid"], true);
    built["index"].clone()
}
fn query(operation: &str, document: &Value, index: &Value, id: &str, options: Value) -> Value {
    json!({"operation":operation,"registry":registry(),"index":index,"objects":{
        "entities":document["entities"],"mappings":document["mappings"],"authorities":document["authorities"]},"id":id,"options":options})
}

#[test]
fn traversal_order_follows_endpoints_and_empty_filter_selects_none() {
    let d = document();
    let i = index(&d);
    assert_eq!(
        invoke(query("trace", &d, &i, "urn:e:a", json!({}))).unwrap(),
        json!([
        {"entity":0,"depth":0},{"entity":2,"depth":1,"viaMapping":0,"predecessor":"urn:e:a"},
        {"entity":1,"depth":1,"viaMapping":0,"predecessor":"urn:e:a"}])
    );
    assert_eq!(
        invoke(query(
            "neighbors",
            &d,
            &i,
            "urn:e:a",
            json!({"relations":[]})
        ))
        .unwrap(),
        json!([])
    );
}

#[test]
fn lookup_keys_and_incidence_remain_fixed_when_retained_objects_mutate() {
    let mut d = document();
    let i = index(&d);
    d["entities"][0]["id"] = json!("urn:e:changed");
    d["mappings"][0]["sources"] = json!(["urn:e:c"]);
    assert_eq!(
        invoke(query("get-entity", &d, &i, "urn:e:a", json!({}))).unwrap(),
        json!(0)
    );
    assert_eq!(
        invoke(query("get-entity", &d, &i, "urn:e:changed", json!({}))).unwrap(),
        Value::Null
    );
    assert_eq!(
        invoke(query(
            "mappings-for",
            &d,
            &i,
            "urn:e:a",
            json!({"direction":"outgoing"})
        ))
        .unwrap(),
        json!([])
    );
}

#[test]
fn large_integer_depth_and_missing_start_follow_original_validation_order() {
    let mut d = document();
    let template = d["mappings"][0].clone();
    d["entities"] = json!(
        (0..71)
            .map(|n| json!({"id":format!("urn:e:{n}"),"kind":"field"}))
            .collect::<Vec<_>>()
    );
    d["mappings"] = json!(
        (0..70)
            .map(|n| {
                let mut m = template.clone();
                m["id"] = json!(format!("urn:m:{n}"));
                m["sources"] = json!([format!("urn:e:{n}")]);
                m["targets"] = json!([format!("urn:e:{}", n + 1)]);
                m
            })
            .collect::<Vec<_>>()
    );
    let i = index(&d);
    let result = invoke(query(
        "trace",
        &d,
        &i,
        "urn:e:0",
        json!({"direction":"outgoing","maxDepth":1e30}),
    ))
    .unwrap();
    assert_eq!(result.as_array().unwrap().len(), 71);
    assert_eq!(result[70]["depth"], 70);
    assert_eq!(
        invoke(query("trace", &d, &i, "absent", json!({"maxDepth":-1}))).unwrap(),
        json!([])
    );
    assert_eq!(
        invoke(query("trace", &d, &i, "urn:e:0", json!({"maxDepth":0.5})))
            .unwrap_err()
            .message,
        "maxDepth must be a non-negative integer"
    );
    for id in ["absent", "urn:e:0"] {
        let mut request = query("trace", &d, &i, id, json!({"maxDepth":null}));
        request["nonFiniteMaxDepth"] = json!(true);
        let result = invoke(request);
        if id == "absent" {
            assert_eq!(result.unwrap(), json!([]));
        } else {
            assert_eq!(
                result.unwrap_err().message,
                "maxDepth must be a non-negative integer"
            );
        }
    }
}

#[test]
fn mutated_delegation_cycle_is_ambiguous_and_supplies_no_effective_authority() {
    let mut d = document();
    let provenance = json!({"status":"declared","assertedBy":"test"});
    d["authorities"] = json!([
        {"id":"urn:auth:a","concept":"urn:e:a","source":"urn:e:b","facts":["type"],"mode":"canonical","provenance":provenance},
        {"id":"urn:auth:b","concept":"urn:e:a","source":"urn:e:c","facts":["type"],"mode":"delegated","delegatedFrom":"urn:auth:a","provenance":provenance}]);
    let i = index(&d);
    d["authorities"][1]["id"] = json!("urn:auth:a");
    let mut request = query("resolve-authority", &d, &i, "urn:e:a", json!({}));
    request["fact"] = json!("type");
    assert_eq!(
        invoke(request).unwrap(),
        json!({"status":"ambiguous","candidates":[0,1]})
    );
}

#[test]
fn invalid_retained_handles_refuse_instead_of_panicking() {
    let d = document();
    let mut i = index(&d);
    i["incident"][0]["handles"] = json!([9007199254740991u64]);
    assert_eq!(
        invoke(query("neighbors", &d, &i, "urn:e:a", json!({})))
            .unwrap_err()
            .message,
        "Legacy graph handle is outside its retained snapshot"
    );
}
