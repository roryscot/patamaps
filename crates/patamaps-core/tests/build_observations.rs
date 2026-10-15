use patamaps_contracts::*;
use patamaps_core::{
    CheckError, CheckedGraph, ConstraintEvaluationContext, ConstraintRegistry,
    ConstraintRegistryError, EvaluationOptions, admit,
};
use serde_json::json;

fn fixture() -> (GraphDocument, PolicyDocument) {
    let graph = json!({"schemaVersion":"0.1.0","documentType":"graph","id":"urn:test:build","namespace":"build-tests","revision":"1","entities":[
        {"id":"urn:test:requirement","kind":"build:requirement"},
        {"id":"urn:test:binary","kind":"cargo-target","attributes":{"name":"catalog-service","context":{"platform":"linux/amd64","features":[]},"ordinal":1}}
    ],"mappings":[{"id":"urn:test:binding","relation":"core:references","sources":["urn:test:requirement"],"targets":["urn:test:binary"],"cardinality":"one-to-one","lossiness":"lossless","provenance":{"status":"declared","assertedBy":"fixture-owner"}}],"authorities":[]});
    let policy = json!({"schemaVersion":"0.1.0","documentType":"policy","id":"urn:test:build-policy","graph":{"id":"urn:test:build","revision":"1"},"mappings":[{"mapping":"urn:test:binding","coverage":"total","determinism":"deterministic","reversibility":"irreversible"}],"constraints":[
        {"id":"urn:test:exists","kind":"core:requires-mapping","subjects":["urn:test:requirement"],"parameters":{"relation":"core:references","direction":"source"}},
        {"id":"urn:test:unique","kind":"core:unique-target","subjects":["urn:test:requirement"],"parameters":{"relation":"core:references","direction":"source"}},
        {"id":"urn:test:observations","kind":"build:observation-binding-v1","subjects":["urn:test:requirement"],"parameters":{"relation":"core:references","targetKind":"cargo-target","conditions":[{"path":["attributes","name"],"equals":"catalog-service"},{"path":["attributes","context","platform"],"equals":"linux/amd64"},{"path":["attributes","ordinal"],"equals":1.0}]}}
    ],"evidence":[]});
    (
        parse(&serde_json::to_vec(&graph).unwrap()).unwrap(),
        parse(&serde_json::to_vec(&policy).unwrap()).unwrap(),
    )
}
fn evaluate(graph: GraphDocument, policy: PolicyDocument) -> Result<(), CheckError> {
    let checked = CheckedGraph::check(
        graph,
        vec![parse(include_bytes!("../../../relation-packs/core.json")).unwrap()],
    )?;
    admit(
        &checked,
        &policy,
        EvaluationOptions {
            context: JsonObject::new(),
            evaluated_at: "2026-10-15T00:00:00Z".into(),
        },
    )
    .map(|_| ())
}
fn refused(g: GraphDocument, p: PolicyDocument, code: &str) {
    let e = evaluate(g, p).unwrap_err();
    assert!(e.0.iter().any(|i| i.code == code), "{code}: {e:?}");
}

#[test]
fn real_fields_and_canonical_numeric_equivalence_satisfy_existing_cardinality_rules() {
    let (mut g, p) = fixture();
    g.entities[1]
        .attributes
        .as_mut()
        .unwrap()
        .insert("ordinal".into(), json!(1));
    evaluate(g, p).unwrap();
}
#[test]
fn wrong_or_missing_fields_and_omitted_matching_candidates_refuse() {
    let (mut g, p) = fixture();
    g.entities[1]
        .attributes
        .as_mut()
        .unwrap()
        .insert("name".into(), json!("wrong"));
    refused(g, p, "BUILD_OBSERVATION_BINDING_MISMATCH");
    let (mut g, p) = fixture();
    g.entities[1].attributes.as_mut().unwrap().remove("context");
    refused(g, p, "BUILD_OBSERVATION_BINDING_MISMATCH");
    let (mut g, p) = fixture();
    let mut duplicate = g.entities[1].clone();
    duplicate.id = "urn:test:other-binary".into();
    g.entities.push(duplicate);
    refused(g, p, "BUILD_OBSERVATION_BINDING_MISMATCH");
}
#[test]
fn binding_all_ambiguous_matches_still_fails_the_existing_unique_target_constraint() {
    let (mut g, p) = fixture();
    let mut duplicate = g.entities[1].clone();
    duplicate.id = "urn:test:other-binary".into();
    g.entities.push(duplicate);
    g.mappings[0].targets.push("urn:test:other-binary".into());
    g.mappings[0].cardinality = serde_json::from_value(json!("one-to-many")).unwrap();
    refused(g, p, "NON_UNIQUE_MAPPING_TARGET");
}
#[test]
fn malformed_selectors_unknown_versions_and_protected_waivers_cannot_admit() {
    let (g, mut p) = fixture();
    p.constraints[2]
        .parameters
        .as_mut()
        .unwrap()
        .insert("unknown".into(), json!(true));
    refused(g, p, "INVALID_CONSTRAINT_PARAMETERS");
    let (g, mut p) = fixture();
    p.constraints[2].kind = "build:observation-binding-v2".into();
    refused(g, p, "UNKNOWN_CONSTRAINT_KIND");
    let (mut g, mut p) = fixture();
    g.entities[1]
        .attributes
        .as_mut()
        .unwrap()
        .insert("name".into(), json!("wrong"));
    p.waivers=Some(serde_json::from_value(json!([{"id":"urn:test:waiver","codes":["BUILD_OBSERVATION_BINDING_MISMATCH"],"subjects":["urn:test:requirement"],"reason":"attempted bypass","assertedBy":"fixture-owner","expiresAt":"2026-11-15T00:00:00Z"}])).unwrap());
    refused(g, p, "INVALID_WAIVER");
}
#[test]
fn callers_cannot_replace_the_default_replayable_evaluator() {
    let mut registry = ConstraintRegistry::new();
    let result = registry.register(
        "build:observation-binding-v1",
        ContentBinding {
            id: "urn:test:caller".into(),
            digest: format!("sha256:{}", "0".repeat(64)),
        },
        |_: &Constraint, _: &ConstraintEvaluationContext<'_>| Ok(vec![]),
    );
    assert_eq!(result, Err(ConstraintRegistryError::BuiltinKind));
}
#[test]
fn aggregate_work_exhaustion_refuses_instead_of_admitting_a_partial_check() {
    let (mut g, mut p) = fixture();
    for n in 0..250 {
        let mut e = g.entities[0].clone();
        e.id = format!("urn:test:unselected:{n}");
        e.kind = "unselected".into();
        g.entities.push(e);
    }
    let c = p.constraints[2].clone();
    p.constraints = (0..9000)
        .map(|n| {
            let mut copy = c.clone();
            copy.id = format!("urn:test:limit:{n}");
            copy
        })
        .collect();
    refused(g, p, "BUILD_OBSERVATION_RESOURCE_LIMIT");
}

#[test]
fn matching_query_returns_all_candidates_without_minting_admission() {
    let (mut g, p) = fixture();
    let mut duplicate = g.entities[1].clone();
    duplicate.id = "urn:test:other-binary".into();
    g.entities.push(duplicate);
    let checked = CheckedGraph::check(
        g.clone(),
        vec![parse(include_bytes!("../../../relation-packs/core.json")).unwrap()],
    )
    .unwrap();
    assert_eq!(
        patamaps_core::observation_matches(&checked, &p.constraints[2]).unwrap(),
        vec!["urn:test:binary", "urn:test:other-binary"]
    );
    refused(g, p, "BUILD_OBSERVATION_BINDING_MISMATCH");
}
#[test]
fn absent_fields_do_not_equal_explicit_null() {
    let (mut g, mut p) = fixture();
    p.constraints[2].parameters.as_mut().unwrap().insert(
        "conditions".into(),
        json!([{"path":["attributes","optional"],"equals":null}]),
    );
    refused(g.clone(), p.clone(), "BUILD_OBSERVATION_BINDING_MISMATCH");
    g.entities[1]
        .attributes
        .as_mut()
        .unwrap()
        .insert("optional".into(), serde_json::Value::Null);
    evaluate(g, p).unwrap();
}
