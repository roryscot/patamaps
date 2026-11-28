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
        "../package-data/relation-packs/scientific-skos.json"
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

#[test]
fn constructor_validates_complete_import_set_in_either_order() {
    use patamaps_contracts::{PackContentBinding, canonical_digest};

    let base = RelationRegistry::with_core().unwrap().all_packs()[0].clone();
    let mut importer = RelationPack::new("urn:test:importer", "1");
    importer.imports = Some(vec![PackContentBinding {
        id: base.id.clone(),
        version: base.version.clone(),
        digest: canonical_digest(&base).unwrap(),
    }]);
    importer.laws = Some(vec![]);

    for ordered in [
        vec![base.clone(), importer.clone()],
        vec![importer.clone(), base.clone()],
    ] {
        let registry = RelationRegistry::new(ordered.clone()).unwrap();
        assert_eq!(registry.all_packs(), ordered);
        assert!(registry.get("core:contains").is_some());
    }
    let deduplicated =
        RelationRegistry::new([importer.clone(), base.clone(), base.clone()]).unwrap();
    assert_eq!(deduplicated.all_packs().len(), 2);
    let missing = RelationRegistry::new([importer.clone()]).unwrap_err();
    assert!(
        missing
            .issues()
            .iter()
            .any(|issue| issue.code == "MISSING_EXACT_PACK_IMPORT")
    );
    let mut drifted = importer.clone();
    drifted.imports.as_mut().unwrap()[0].digest = format!("sha256:{}", "0".repeat(64));
    let drift = RelationRegistry::new([drifted, base.clone()]).unwrap_err();
    assert!(
        drift
            .issues()
            .iter()
            .any(|issue| issue.code == "PACK_IMPORT_BINDING_MISMATCH")
    );
    let mut conflict = base.clone();
    conflict.version = "different".into();
    let conflict = RelationRegistry::new([base.clone(), conflict]).unwrap_err();
    assert!(
        conflict
            .issues()
            .iter()
            .any(|issue| issue.code == "RELATION_PACK_CONFLICT")
    );

    let mut incremental = RelationRegistry::new([]).unwrap();
    assert!(incremental.register_pack(importer.clone()).is_err());
    assert!(incremental.all_packs().is_empty());
    incremental.register_pack(base).unwrap();
    incremental.register_pack(importer).unwrap();
    assert_eq!(incremental.all_packs().len(), 2);
}

#[test]
fn constructor_rejects_too_many_distinct_packs() {
    let packs = (0..65).map(|n| RelationPack::new(format!("urn:test:pack:{n}"), "1"));
    let error = RelationRegistry::new(packs).unwrap_err();
    assert!(
        error
            .issues()
            .iter()
            .any(|issue| issue.code == "GRAPH_RESOURCE_LIMIT")
    );
}
