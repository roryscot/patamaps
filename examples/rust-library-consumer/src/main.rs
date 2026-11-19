use patamaps_core::{
    CheckedGraph, Direction,
    model::{
        Cardinality, CyclePolicy, Entity, GraphDocument, Lossiness, Mapping, Provenance,
        ProvenanceStatus, Relation, RelationPack,
    },
};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut draft = GraphDocument::new("urn:consumer:graph", "consumer");
    draft
        .entities
        .push(Entity::new("urn:consumer:idea", "concept"));
    draft
        .entities
        .push(Entity::new("urn:consumer:handler", "implementation"));
    draft.mappings.push(Mapping::new(
        "urn:consumer:binding",
        "consumer:implemented_by",
        ["urn:consumer:idea"],
        ["urn:consumer:handler"],
        Cardinality::OneToOne,
        Lossiness::Unknown,
        Provenance::new(ProvenanceStatus::Declared, "consumer-owner"),
    ));
    let mut relations = RelationPack::new("urn:consumer:relations", "1");
    relations.relations.push(Relation::new(
        "consumer:implemented_by",
        CyclePolicy::Forbid,
    ));
    let graph = CheckedGraph::check(draft, vec![relations])?;

    let updated = graph.try_edit(|draft| {
        draft
            .entities
            .push(Entity::new("urn:consumer:second-idea", "concept"));
    })?;
    assert!(graph.entity("urn:consumer:second-idea").is_none());
    assert!(updated.entity("urn:consumer:second-idea").is_some());
    assert!(
        updated
            .trace("urn:consumer:idea", Direction::Outgoing, 1, &[])?
            .iter()
            .any(|visit| visit.entity_id == "urn:consumer:handler")
    );
    println!("independent Rust consumer checked and edited its graph");
    Ok(())
}
