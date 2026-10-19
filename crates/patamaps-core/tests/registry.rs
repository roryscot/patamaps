use patamaps_contracts::{RelationPack, canonical_bytes, parse};
use patamaps_core::RelationRegistry;

#[test]
fn registry_queries_preserve_order_and_registration_is_atomic() {
    let mut registry = RelationRegistry::with_core().unwrap();
    let core = registry.all_packs()[0].clone();
    registry.register_pack(core.clone()).unwrap();
    assert_eq!(registry.all_packs().len(), 1);
    assert_eq!(
        registry.all().map(|r| r.id.as_str()).collect::<Vec<_>>(),
        core.relations
            .iter()
            .map(|r| r.id.as_str())
            .collect::<Vec<_>>()
    );
    assert!(registry.has_pack(&core.id, Some(&core.version)));
    assert!(registry.has_pack(&core.id, Some("")));
    assert!(!registry.has_pack(&core.id, Some("other")));
    assert!(registry.get("core:references").is_some());
    assert!(registry.get("missing:relation").is_none());
    assert!(registry.get_pack("urn:missing").is_none());
    assert!(registry.get_law("urn:missing").is_none());

    let scientific: RelationPack = parse(include_bytes!(
        "../package-inputs/relation-packs/scientific-skos.json"
    ))
    .unwrap();
    registry.register_pack(scientific.clone()).unwrap();
    assert_eq!(registry.executable_packs().count(), 1);
    let law = &scientific.laws.as_ref().unwrap()[0];
    let (owner, found) = registry.get_law(&law.id).unwrap();
    assert_eq!(owner.id, scientific.id);
    assert_eq!(found, law);
    let before = canonical_bytes(&registry.all_packs()).unwrap();
    let mut conflict = core.clone();
    conflict.version = "different".into();
    assert!(registry.register_pack(conflict).is_err());
    let mut duplicate = core;
    duplicate.id = "urn:duplicate:relation-owner".into();
    assert!(registry.register_pack(duplicate).is_err());
    let mut invalid_law = scientific;
    invalid_law.id = "urn:invalid:law-owner".into();
    invalid_law.relations[0].id = "new:relation".into();
    assert!(registry.register_pack(invalid_law).is_err());
    assert_eq!(canonical_bytes(&registry.all_packs()).unwrap(), before);
}
