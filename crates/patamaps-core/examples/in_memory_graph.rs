//! An in-memory graph: no CLI, generated files, or application runtime.
use patamaps_core::{
    CheckedGraph, Direction,
    model::{
        Cardinality, CyclePolicy, Entity, GraphDocument, Lossiness, Mapping, Provenance,
        ProvenanceStatus, Relation, RelationPack,
    },
};

/// Creates draft records. They are not validated until CheckedGraph::check succeeds.
pub fn draft() -> (GraphDocument, Vec<RelationPack>) {
    let mut graph = GraphDocument::new("urn:example:graph", "example");
    graph
        .entities
        .push(Entity::new("urn:example:idea", "concept"));
    graph
        .entities
        .push(Entity::new("urn:example:implementation", "implementation"));
    graph.mappings.push(Mapping::new(
        "urn:example:mapping",
        "example:implemented_by",
        ["urn:example:idea"],
        ["urn:example:implementation"],
        Cardinality::OneToOne,
        Lossiness::Unknown,
        Provenance::new(ProvenanceStatus::Declared, "example-owner"),
    ));
    let mut pack = RelationPack::new("urn:example:relations", "1");
    pack.relations
        .push(Relation::new("example:implemented_by", CyclePolicy::Forbid));
    (graph, vec![pack])
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let (document, packs) = draft();
    let graph = CheckedGraph::check(document, packs)?;
    assert_eq!(graph.entity("urn:example:idea").unwrap().kind, "concept");
    assert_eq!(
        graph.mapping("urn:example:mapping").unwrap().targets,
        ["urn:example:implementation"]
    );
    let visits = graph.trace("urn:example:idea", Direction::Outgoing, 1, &[])?;
    assert!(
        visits
            .iter()
            .any(|v| v.entity_id == "urn:example:implementation")
    );
    println!(
        "checked {} entities and {} mapping",
        graph.document().entities.len(),
        graph.document().mappings.len()
    );
    Ok(())
}
