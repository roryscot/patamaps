use patamaps_contracts::*;
use patamaps_core::*;
use patamaps_projection::*;

fn input() -> (
    GraphDocument,
    PolicyDocument,
    ProjectionSpec,
    Vec<RelationPack>,
) {
    (
        parse(include_bytes!("../../../fixtures/routing/graph.json")).unwrap(),
        parse(include_bytes!("../../../fixtures/routing/policy.json")).unwrap(),
        parse(include_bytes!(
            "../../../fixtures/routing/projection-spec.json"
        ))
        .unwrap(),
        vec![
            parse(include_bytes!("../../../relation-packs/core.json")).unwrap(),
            parse(include_bytes!("../../../relation-packs/routing.json")).unwrap(),
        ],
    )
}
fn opts() -> EvaluationOptions {
    EvaluationOptions {
        context: JsonObject::new(),
        evaluated_at: "2026-10-10T12:00:00Z".into(),
    }
}

#[test]
fn cardinality_kind_loss_and_native_locator_failures_are_visible() {
    let (mut d, p, s, packs) = input();
    let graph = CheckedGraph::check(d.clone(), packs.clone()).unwrap();
    let a = admit(&graph, &p, opts()).unwrap();
    let projection = project(&a, &s).unwrap();
    assert_eq!(projection.record().entries.len(), 1);
    assert!(emit_rust(&projection, Some("handler")).is_err());
    d.mappings[0].lossiness = Lossiness::Lossy;
    let graph = CheckedGraph::check(d.clone(), packs.clone()).unwrap();
    let a = admit(&graph, &p, opts()).unwrap();
    assert!(project(&a, &s).is_err());
    d.mappings[0].lossiness = Lossiness::Lossless;
    let mut second = d.mappings[0].clone();
    second.id = "urn:mapping:second".into();
    let mut target = d.entities[1].clone();
    target.id = "urn:handler:second".into();
    target.locators = None;
    second.targets = vec![target.id.clone()];
    d.entities.push(target);
    d.mappings.push(second);
    let graph = CheckedGraph::check(d, packs).unwrap();
    let mut p = p;
    p.constraints.clear();
    let mut declaration = p.mappings[0].clone();
    declaration.mapping = Some("urn:mapping:second".into());
    p.mappings.push(declaration);
    let a = admit(&graph, &p, opts()).unwrap();
    assert!(project(&a, &s).is_err());
}

#[test]
fn strings_and_prototype_like_metadata_remain_data() {
    let (mut d, p, s, packs) = input();
    d.entities[1].attributes = Some(
        parse(br#"{"__proto__":{"admin":true},"payload":"\";throw new Error('injection');//"}"#)
            .unwrap(),
    );
    let graph = CheckedGraph::check(d, packs).unwrap();
    let a = admit(&graph, &p, opts()).unwrap();
    let projection = project(&a, &s).unwrap();
    let ts = emit_typescript(&projection, "bindings", None).unwrap();
    assert!(ts.contains("JSON.parse("));
    assert!(emit_typescript(&projection, "default", None).is_err());
    assert!(emit_typescript(&projection, "JSON", None).is_err());
    assert!(emit_typescript(&projection, "handler0", Some("handler")).is_err());
}

#[test]
fn repeated_target_metadata_is_bounded_before_cloning_unlimited_output() {
    let (mut d, mut p, mut s, packs) = input();
    // A small authored graph can request a very large duplicated static view.
    d.entities[1].attributes =
        Some([("data".into(), serde_json::json!("x".repeat(1_000_000)))].into());
    s.slots.clear();
    for i in 0..32 {
        s.slots.push(SlotSpec {
            name: format!("handler{i}"),
            relation: "routing:handled_by".into(),
            direction: SlotDirection::Outgoing,
            cardinality: SlotCardinality::ExactlyOne,
            target_kinds: None,
            allow_lossy: None,
        });
    }
    p.constraints.clear();
    let g = CheckedGraph::check(d, packs).unwrap();
    let admitted = admit(&g, &p, opts()).unwrap();
    assert!(
        project(&admitted, &s)
            .unwrap_err()
            .0
            .iter()
            .any(|i| i.code == "PROJECTION_BYTE_LIMIT")
    );
}
