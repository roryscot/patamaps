#[path = "../examples/in_memory_graph.rs"]
mod example;

use patamaps_core::CheckedGraph;

#[test]
fn in_memory_records_support_checked_lookup_and_traversal() {
    let (document, packs) = example::draft();
    let graph = CheckedGraph::check(document, packs).unwrap();
    assert!(graph.entity("urn:example:idea").is_some());
    assert_eq!(graph.incident("urn:example:idea").count(), 1);
    assert!(
        graph
            .trace(
                "urn:example:idea",
                patamaps_core::Direction::Outgoing,
                1,
                &[]
            )
            .unwrap()
            .iter()
            .any(|v| v.entity_id == "urn:example:implementation")
    );
}

#[test]
fn draft_constructors_do_not_bypass_existing_graph_validation() {
    let (mut document, packs) = example::draft();
    document.entities.push(document.entities[0].clone());
    let error = CheckedGraph::check(document, packs).unwrap_err();
    assert!(error.0.iter().any(|i| i.code == "DUPLICATE_ID"));

    let (mut document, packs) = example::draft();
    document.mappings[0].targets = vec!["urn:example:missing".into()];
    let error = CheckedGraph::check(document, packs).unwrap_err();
    assert!(error.0.iter().any(|i| i.code == "UNRESOLVED_ENDPOINT"));
}
