// The example entry point is used when run directly, not when imported here.
#[allow(dead_code)]
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

#[test]
fn edited_graph_is_checked_and_failed_edits_leave_original_unchanged() {
    let (document, packs) = example::draft();
    let original = CheckedGraph::check(document, packs).unwrap();
    let before = original.digest().to_owned();

    let updated = original
        .try_edit(|draft| {
            draft.entities.push(patamaps_core::model::Entity::new(
                "urn:example:extra",
                "concept",
            ));
        })
        .unwrap();
    assert!(updated.entity("urn:example:extra").is_some());
    assert!(original.entity("urn:example:extra").is_none());
    assert_ne!(updated.digest(), before);

    let error = original
        .try_edit(|draft| {
            draft.entities.push(draft.entities[0].clone());
        })
        .unwrap_err();
    assert!(error.0.iter().any(|issue| issue.code == "DUPLICATE_ID"));
    assert_eq!(original.digest(), before);
    assert_eq!(original.document().entities.len(), 2);
}

#[test]
fn native_registry_remains_available_without_legacy_compatibility() {
    let registry = patamaps_core::RelationRegistry::with_core().unwrap();
    assert!(registry.get("core:contains").is_some());
}

#[test]
fn relation_lookup_returns_document_order_and_reflects_checked_edits() {
    let (mut document, packs) = example::draft();
    document.entities.push(patamaps_core::model::Entity::new(
        "urn:example:other-implementation",
        "implementation",
    ));
    let mut second = document.mappings[0].clone();
    second.id = "urn:example:second-mapping".into();
    second.targets = vec!["urn:example:other-implementation".into()];
    document.mappings.push(second);

    let original = CheckedGraph::check(document, packs).unwrap();
    let ids = |graph: &CheckedGraph| {
        graph
            .mappings_for_relation("example:implemented_by")
            .map(|mapping| mapping.id.clone())
            .collect::<Vec<_>>()
    };
    assert_eq!(
        ids(&original),
        ["urn:example:mapping", "urn:example:second-mapping"]
    );
    assert_eq!(original.mappings_for_relation("example:missing").count(), 0);

    let updated = original
        .try_edit(|draft| {
            draft.mappings.remove(0);
        })
        .unwrap();
    assert_eq!(ids(&updated), ["urn:example:second-mapping"]);
    assert_eq!(ids(&original).len(), 2);
}
