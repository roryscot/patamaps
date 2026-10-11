use patamaps_contracts::*;
use patamaps_core::{CheckError, CheckedGraph, EvaluationOptions, admit};
use serde_json::json;

fn fixture() -> (GraphDocument, PolicyDocument) {
    (
        parse(include_bytes!("../../../fixtures/topology/graph.json")).unwrap(),
        parse(include_bytes!("../../../fixtures/topology/policy.json")).unwrap(),
    )
}
fn evaluate(graph: GraphDocument, policy: PolicyDocument) -> Result<(), CheckError> {
    let packs = [
        include_bytes!("../../../relation-packs/core.json").as_slice(),
        include_bytes!("../../../relation-packs/routing.json").as_slice(),
        include_bytes!("../../../relation-packs/application-topology.json").as_slice(),
    ]
    .into_iter()
    .map(|p| parse(p).unwrap())
    .collect();
    let checked = CheckedGraph::check(graph, packs)?;
    admit(
        &checked,
        &policy,
        EvaluationOptions {
            context: JsonObject::new(),
            evaluated_at: "2026-09-08T00:00:00.000Z".into(),
        },
    )
    .map(|_| ())
}
fn refuse(graph: GraphDocument, policy: PolicyDocument, code: &str) {
    let e = evaluate(graph, policy).unwrap_err();
    assert!(e.0.iter().any(|i| i.code == code), "{code}: {e:?}");
}
fn remove(graph: &mut GraphDocument, name: &str) {
    graph
        .mappings
        .retain(|m| m.id != format!("urn:test:mapping:{name}"));
}
fn mapping(graph: &mut GraphDocument, name: &str, relation: &str, source: &str, target: &str) {
    let mut m = graph.mappings[0].clone();
    m.id = format!("urn:test:mapping:{name}");
    m.relation = relation.into();
    m.sources = vec![source.into()];
    m.targets = vec![target.into()];
    graph.mappings.push(m);
}
#[test]
fn original_application_fixture_satisfies_totality_reachability_hydration_and_context() {
    let (g, p) = fixture();
    evaluate(g, p).unwrap();
}
#[test]
fn removing_semantic_binding_provider_hydration_or_containment_refuses() {
    for (name, code) in [
        ("route-page", "TOPOLOGY_REQUIRED_RELATION_MISSING"),
        ("container-context", "TOPOLOGY_CONTEXT_PROVIDER_MISSING"),
        ("hydration-page", "TOPOLOGY_REQUIRED_RELATION_MISSING"),
        ("segment-page", "TOPOLOGY_ENTITY_UNREACHABLE"),
    ] {
        let (mut g, p) = fixture();
        remove(&mut g, name);
        refuse(g, p, code);
    }
}
#[test]
fn closest_provider_shadows_ancestor_but_two_providers_at_one_depth_refuse() {
    let (mut g, p) = fixture();
    let mut parent = g.entities[2].clone();
    parent.id = "urn:test:container:parent".into();
    g.entities.push(parent);
    mapping(
        &mut g,
        "parent-contained",
        "topology:contains",
        "urn:test:segment:root",
        "urn:test:container:parent",
    );
    mapping(
        &mut g,
        "parent-wrap",
        "topology:wraps",
        "urn:test:container:parent",
        "urn:test:container:root",
    );
    mapping(
        &mut g,
        "parent-provider",
        "topology:provides_context",
        "urn:test:container:parent",
        "urn:test:context:web",
    );
    evaluate(g.clone(), p.clone()).unwrap();
    remove(&mut g, "container-context");
    evaluate(g.clone(), p.clone()).unwrap();
    mapping(
        &mut g,
        "current-provider",
        "topology:provides_context",
        "urn:test:container:root",
        "urn:test:context:web",
    );
    let mut provider = g.entities[2].clone();
    provider.id = "urn:test:provider:second".into();
    provider.kind = "topology:context-provider".into();
    g.entities.push(provider);
    mapping(
        &mut g,
        "host-second",
        "topology:hosts_provider",
        "urn:test:container:root",
        "urn:test:provider:second",
    );
    mapping(
        &mut g,
        "provide-second",
        "topology:provides_context",
        "urn:test:provider:second",
        "urn:test:context:web",
    );
    refuse(g, p, "TOPOLOGY_CONTEXT_PROVIDER_AMBIGUOUS");
}
#[test]
fn exclusions_require_exact_relation_permission_visible_owner_reason_and_no_binding() {
    let (mut g, p) = fixture();
    remove(&mut g, "route-page");
    let a = g.entities[3].attributes.as_mut().unwrap();
    a.insert("topologyDisposition".into(), json!("excluded"));
    a.insert(
        "exclusionReason".into(),
        json!("Reviewed semantic exception"),
    );
    a.insert("exclusionOwner".into(), json!("team:test"));
    refuse(g.clone(), p.clone(), "TOPOLOGY_EXCLUSION_NOT_ALLOWED");
    g.entities[3].attributes.as_mut().unwrap().insert(
        "exclusionRelations".into(),
        json!(["topology:implemented_by"]),
    );
    evaluate(g.clone(), p.clone()).unwrap();
    g.entities[3]
        .attributes
        .as_mut()
        .unwrap()
        .remove("exclusionOwner");
    refuse(g, p, "INVALID_TOPOLOGY_EXCLUSION");
    let (mut g, p) = fixture();
    g.entities[3].attributes = Some(serde_json::from_value(json!({"runtime":"client","topologyDisposition":"excluded","exclusionReason":"Reviewed","exclusionOwner":"team:test","exclusionRelations":["topology:implemented_by"]})).unwrap());
    refuse(g, p, "EXCLUDED_TOPOLOGY_SUBJECT_MAPPED");
}
#[test]
fn empty_selection_parameter_types_counterpart_kinds_and_unique_cardinality_refuse() {
    let (g, p) = fixture();
    for index in 0..p.constraints.len() {
        let mut changed = p.clone();
        changed.constraints[index]
            .parameters
            .as_mut()
            .unwrap()
            .insert("unknownParameter".into(), json!(true));
        refuse(g.clone(), changed, "INVALID_CONSTRAINT_PARAMETERS");
        let mut changed = p.clone();
        changed.constraints[index]
            .parameters
            .as_mut()
            .unwrap()
            .insert("subjectKinds".into(), json!(["unknown:kind"]));
        refuse(g.clone(), changed, "EMPTY_TOPOLOGY_SELECTION");
    }
    let mut changed = p.clone();
    changed.constraints[0]
        .parameters
        .as_mut()
        .unwrap()
        .insert("counterpartKinds".into(), json!(["routing:schema"]));
    refuse(g.clone(), changed, "TOPOLOGY_COUNTERPART_KIND_MISMATCH");
    let mut g = g;
    let mut route = g.entities[4].clone();
    route.id = "urn:test:route:other".into();
    route.attributes = None;
    g.entities.push(route);
    mapping(
        &mut g,
        "other-route-page",
        "topology:implemented_by",
        "urn:test:route:other",
        "urn:test:page:home",
    );
    refuse(g, p, "TOPOLOGY_RELATION_AMBIGUOUS");
}
#[test]
fn aggregate_topology_work_exhaustion_cannot_become_an_admitted_generation() {
    let (mut g, mut p) = fixture();
    for n in 0..250 {
        let mut e = g.entities[0].clone();
        e.id = format!("urn:unselected:{n}");
        e.kind = "other:unselected".into();
        g.entities.push(e);
    }
    let base = p.constraints[0].clone();
    p.constraints = (0..9_000)
        .map(|n| {
            let mut c = base.clone();
            c.id = format!("urn:constraint:{n}");
            c
        })
        .collect();
    refuse(g, p, "TOPOLOGY_RESOURCE_LIMIT");
}
