use patamaps_contracts::*;
use patamaps_core::*;
use patamaps_projection::*;
use serde_json::json;
use std::collections::BTreeMap;
fn inputs() -> (GraphDocument, PolicyDocument, ProjectionSpec) {
    let g=parse(&canonical_bytes(&json!({"schemaVersion":"0.1.0","documentType":"graph","id":"urn:paths:graph","namespace":"paths","revision":"1","entities":[{"id":"urn:route:root","kind":"route","attributes":{"path":"/"}},{"id":"urn:route:user","kind":"route","attributes":{"path":"/users/:id"},"provenance":{"status":"declared","assertedBy":"route-owner","sourceRevision":"1"}},{"id":"urn:route:files","kind":"route","attributes":{"path":"/files/*rest?"}}],"mappings":[],"authorities":[]})).unwrap()).unwrap();
    let p=parse(&canonical_bytes(&json!({"schemaVersion":"0.1.0","documentType":"policy","id":"urn:paths:policy","graph":{"id":"urn:paths:graph","revision":"1"},"mappings":[],"constraints":[],"evidence":[]})).unwrap()).unwrap();
    let s=parse(&canonical_bytes(&json!({"schemaVersion":"0.1.0","documentType":"projection-spec","id":"urn:paths:spec","select":{"kinds":["route"]},"slots":[],"pathTree":{}})).unwrap()).unwrap();
    (g, p, s)
}
fn compile(g: GraphDocument, p: &PolicyDocument, s: &ProjectionSpec) -> CheckedProjection {
    let g = CheckedGraph::check(g, vec![]).unwrap();
    let generation = admit(
        &g,
        p,
        EvaluationOptions {
            context: JsonObject::new(),
            evaluated_at: "2026-10-10T12:00:00Z".into(),
        },
    )
    .unwrap();
    project(&generation, s).unwrap()
}
fn code(e: CheckError, code: &str) {
    assert!(
        e.0.iter().any(|i| i.code == code),
        "wanted {code}; found {:?}",
        e.0
    );
}
#[test]
fn paths_are_authored_and_provenance_stays_in_the_captured_graph_contract() {
    let (g, p, s) = inputs();
    let projection = compile(g.clone(), &p, &s);
    assert!(g.entities[1].provenance.is_some());
    assert!(
        projection
            .record()
            .entries
            .iter()
            .all(|e| e.subject.provenance.is_none())
    );
    let tree = compile_path_tree(&projection, &s).unwrap();
    assert_eq!(tree.record().params, ["*rest?", ":id"]);
    assert_eq!(tree.record().tree.path, "/");
    assert_eq!(
        tree.record().tree.occupant.as_ref().unwrap().id,
        "urn:route:root"
    );
    assert_eq!(
        tree.record().tree.children["users"].children[":id"]
            .occupant
            .as_ref()
            .unwrap()
            .id,
        "urn:route:user"
    );
    assert_eq!(tree.record().projection.digest, projection.record().digest);
}
#[test]
fn hydration_changes_only_paths_keeps_template_keys_occupants_and_requires_parameters() {
    let (g, p, s) = inputs();
    let tree = compile_path_tree(&compile(g, &p, &s), &s).unwrap();
    let before = canonical_bytes(tree.record()).unwrap();
    let hydrated = hydrate(&tree, BTreeMap::from([("id".into(), "ada".into())])).unwrap();
    let user = &hydrated.tree.children["users"].children[":id"];
    assert_eq!(user.path, "/users/ada");
    assert_eq!(
        canonical_bytes(&user.occupant).unwrap(),
        canonical_bytes(&tree.record().tree.children["users"].children[":id"].occupant).unwrap()
    );
    assert_eq!(
        hydrated.tree.children["files"].children["*rest?"].path,
        "/files"
    );
    assert_eq!(before, canonical_bytes(tree.record()).unwrap());
    code(
        hydrate(&tree, BTreeMap::new()).unwrap_err(),
        "MISSING_PATH_PARAMETER",
    );
    for value in ["", "a/b", "a?b", "a#b", "a\u{feff}b"] {
        code(
            hydrate(&tree, BTreeMap::from([("id".into(), value.into())])).unwrap_err(),
            "UNSAFE_PATH_PARAMETER",
        );
    }
    let hydrated = hydrate(
        &tree,
        BTreeMap::from([("id".into(), "ada".into()), ("rest".into(), "a/b".into())]),
    )
    .unwrap();
    assert_eq!(
        hydrated.tree.children["files"].children["*rest?"].path,
        "/files/a/b"
    );
}
#[test]
fn path_collisions_missing_attributes_reserved_keys_and_stale_specs_refuse() {
    let (g, p, s) = inputs();
    let projection = compile(g.clone(), &p, &s);
    let mut changed = s.clone();
    changed.path_tree.as_mut().unwrap().attribute = Some("other".into());
    code(
        compile_path_tree(&projection, &changed).unwrap_err(),
        "PATH_TREE_SPEC_DIGEST_MISMATCH",
    );
    for (path, expected) in [
        ("/", "PATH_TREE_COLLISION"),
        ("/_", "PATH_TREE_RESERVED_SEGMENT"),
        ("/users/", "PATH_TREE_INVALID_PATH"),
        ("users/:id", "PATH_TREE_INVALID_PATH"),
    ] {
        let mut g = g.clone();
        g.entities[1]
            .attributes
            .as_mut()
            .unwrap()
            .insert("path".into(), path.into());
        code(
            compile_path_tree(&compile(g, &p, &s), &s).unwrap_err(),
            expected,
        );
    }
    let mut g = g;
    g.entities[1].attributes = None;
    code(
        compile_path_tree(&compile(g, &p, &s), &s).unwrap_err(),
        "PATH_TREE_PATH_MISSING",
    );
    let mut s = s;
    s.path_tree = None;
    let (g, p, _) = inputs();
    code(
        compile_path_tree(&compile(g, &p, &s), &s).unwrap_err(),
        "PATH_TREE_SPEC_MISSING",
    );
}
#[test]
fn substituted_parameter_text_is_literal_and_not_reinterpreted_as_another_token() {
    let (mut g, p, s) = inputs();
    g.entities.truncate(2);
    g.entities[1]
        .attributes
        .as_mut()
        .unwrap()
        .insert("path".into(), "/users/:id/:next".into());
    let tree = compile_path_tree(&compile(g, &p, &s), &s).unwrap();
    let hydrated = hydrate(
        &tree,
        BTreeMap::from([
            ("id".into(), ":next".into()),
            ("next".into(), "literal".into()),
        ]),
    )
    .unwrap();
    assert_eq!(
        hydrated.tree.children["users"].children[":id"].children[":next"].path,
        "/users/:next/literal"
    );
    let (mut g, p, s) = inputs();
    g.entities.truncate(2);
    g.entities[1]
        .attributes
        .as_mut()
        .unwrap()
        .insert("path".into(), "/users/:longname/:id".into());
    let tree = compile_path_tree(&compile(g, &p, &s), &s).unwrap();
    let hydrated = hydrate(
        &tree,
        BTreeMap::from([
            ("longname".into(), ":id".into()),
            ("id".into(), "literal".into()),
        ]),
    )
    .unwrap();
    assert_eq!(
        hydrated.tree.children["users"].children[":longname"].children[":id"].path,
        "/users/:id/literal"
    );
}
#[test]
fn alternate_delimiters_and_prototype_like_child_keys_are_plain_data() {
    let (mut g, p, mut s) = inputs();
    g.entities.truncate(1);
    g.entities[0]
        .attributes
        .as_mut()
        .unwrap()
        .insert("path".into(), "--__proto__--:id".into());
    s.path_tree.as_mut().unwrap().delimiter = Some(PathDelimiter::Hyphen);
    let tree = compile_path_tree(&compile(g, &p, &s), &s).unwrap();
    let hydrated = hydrate(&tree, BTreeMap::from([("id".into(), "value".into())])).unwrap();
    assert_eq!(
        hydrated.tree.children["__proto__"].children[":id"].path,
        "--__proto__--value"
    );
    code(
        hydrate(&tree, BTreeMap::from([("id".into(), "a--b".into())])).unwrap_err(),
        "UNSAFE_PATH_PARAMETER",
    );
}
#[test]
fn excessive_path_depth_refuses_before_recursive_tree_construction() {
    let (mut g, p, s) = inputs();
    g.entities.truncate(1);
    g.entities[0].attributes.as_mut().unwrap().insert(
        "path".into(),
        format!("/{}", vec!["x"; 49].join("/")).into(),
    );
    code(
        compile_path_tree(&compile(g, &p, &s), &s).unwrap_err(),
        "PATH_TREE_RESOURCE_LIMIT",
    );
}
#[test]
fn semantic_tree_capture_success_and_refusal_replay_through_the_same_evaluator() {
    let (g, p, s) = inputs();
    let input = CaptureInputs {
        graph: g.clone(),
        packs: vec![],
        policy: p.clone(),
        context: JsonObject::new(),
        evaluated_at: "2026-10-10T12:00:00Z".into(),
        projection_spec: Some(s.clone()),
    };
    let successful = capture(input.clone(), vec![]).unwrap();
    assert_eq!(successful.result["status"], "viable");
    assert!(successful.result["pathTree"].is_object());
    replay(&successful).unwrap();
    let mut broken = input;
    broken.graph.entities[1].attributes = None;
    let rejected = capture(broken, vec![]).unwrap();
    assert_eq!(rejected.result["status"], "rejected");
    replay(&rejected).unwrap();
    let report = compare(&replay(&successful).unwrap(), &replay(&rejected).unwrap()).unwrap();
    assert!(report["pathTreeChanged"].is_null());
}
