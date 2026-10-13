use patamaps_contracts::{RelationPack, byte_digest, canonical_digest};
use patamaps_core::{ParsedLegacyRelationPack, RelationRegistry, import_legacy_relation_pack};
use serde_json::{Value, json};

fn core() -> Value {
    serde_json::from_slice(include_bytes!("../src/legacy_core.json")).unwrap()
}

fn executable(core: &Value) -> Value {
    json!({
        "schemaVersion":"2.0.0", "id":"urn:pack:legacy-test", "version":"1",
        "imports":[{
            "id":core["id"], "version":core["version"],
            "digest":import_legacy_relation_pack(core.clone()).unwrap().original_digest()
        }],
        "relations":[],
        "laws":[{
            "id":"urn:law:legacy-test", "operation":"chain",
            "operands":["core:contains","core:contains"], "resultRelation":"core:contains",
            "handling":{"lossiness":"conservative","uncertainty":"conservative","authority":"none"}
        }]
    })
}

#[test]
fn portable_schema_refusals_preserve_original_type_and_unknown_property_messages() {
    let base = json!({
        "schemaVersion":"1.0.0", "id":"urn:pack:control", "version":"1",
        "relations":[{"id":"test:edge","cyclePolicy":"allow"}]
    });
    let mut wrong_type = base.clone();
    wrong_type["version"] = Value::Null;
    let mut extra = base.clone();
    extra["unknownA"] = json!(true);
    extra["unknownB"] = json!(false);
    for (input, diagnostic) in [
        (json!([]), "$ must be object"),
        (wrong_type, "/version must be string"),
        (
            extra,
            "$ must NOT have additional properties; $ must NOT have additional properties",
        ),
    ] {
        let error =
            ParsedLegacyRelationPack::parse(serde_json::to_vec(&input).unwrap()).unwrap_err();
        assert_eq!(error.code, "LEGACY_PACK_SCHEMA");
        assert_eq!(
            error.message,
            format!("Relation pack does not match the portable schema: {diagnostic}")
        );
    }
}

#[test]
fn portable_array_refusals_preserve_ajv_duplicate_pair_selection_and_type_filtering() {
    // Expected pair order follows the frozen AJV 8.20.0 uniqueItems source:
    // string items use reverse indexed lookup; enum-only items use reverse pairs.
    let mut pack = json!({
        "schemaVersion":"1.0.0", "id":"urn:pack:control", "version":"1",
        "relations":[{"id":"test:edge","cyclePolicy":"allow"}]
    });
    for (field, values, diagnostic) in [
        (
            "sourceKinds",
            json!(["a", "b", "a", "b", "a"]),
            "/relations/0/sourceKinds must NOT have duplicate items (items ## 4 and 2 are identical)",
        ),
        (
            "cardinalities",
            json!([
                "one-to-one",
                "many-to-one",
                "one-to-one",
                "many-to-one",
                "one-to-one"
            ]),
            "/relations/0/cardinalities must NOT have duplicate items (items ## 2 and 4 are identical)",
        ),
        (
            "sourceKinds",
            json!([null, null]),
            "/relations/0/sourceKinds/0 must be string; /relations/0/sourceKinds/1 must be string",
        ),
    ] {
        pack["relations"][0][field] = values;
        let error =
            ParsedLegacyRelationPack::parse(serde_json::to_vec(&pack).unwrap()).unwrap_err();
        assert_eq!(error.code, "LEGACY_PACK_SCHEMA");
        assert_eq!(
            error.message,
            format!("Relation pack does not match the portable schema: {diagnostic}")
        );
        pack["relations"][0].as_object_mut().unwrap().remove(field);
    }
}

#[test]
fn original_pack_text_retains_legacy_duplicates_and_exact_source_binding() {
    let raw = br#"{"schemaVersion":"2.0.0","schemaVersion":"1.0.0","id":"urn:discarded","\u0069d":"urn:kept","version":"1","relations":[]}"#;
    let parsed = ParsedLegacyRelationPack::parse(raw.to_vec()).unwrap();
    let expected =
        b"{\"id\":\"urn:kept\",\"relations\":[],\"schemaVersion\":\"1.0.0\",\"version\":\"1\"}\n";
    assert_eq!(parsed.original_digest(), byte_digest(expected));
    assert_eq!(parsed.document_json().as_bytes(), raw);
    let imported = parsed.import_native_view().unwrap();
    assert_eq!(imported.source_bytes().unwrap(), raw);
    assert_eq!(imported.original_document()["id"], "urn:kept");
    let source = imported.report().source.as_ref().unwrap();
    assert_eq!(source.byte_digest, byte_digest(raw));
    assert_eq!(source.byte_length, raw.len());
    assert_eq!(source.duplicate_property_policy, "last-property-wins");
    assert!(!source.utf8_replacement_occurred);
    assert!(!imported.report().admitted);
}

#[test]
fn valid_legacy_utf16_pack_remains_readable_and_addressable_without_lossy_native_admission() {
    let raw = br#"{"schemaVersion":"1.0.0","id":"urn:pack:utf16","version":"\ud800","relations":[{"id":"test:edge","cyclePolicy":"allow","sourceKinds":["\udfff","\ue000\ue800"]}]}"#;
    let parsed = ParsedLegacyRelationPack::parse(raw.to_vec()).unwrap();
    let expected = "{\"id\":\"urn:pack:utf16\",\"relations\":[{\"cyclePolicy\":\"allow\",\"id\":\"test:edge\",\"sourceKinds\":[\"\\udfff\",\"\u{e000}\u{e800}\"]}],\"schemaVersion\":\"1.0.0\",\"version\":\"\\ud800\"}\n";
    assert_eq!(parsed.original_digest(), byte_digest(expected.as_bytes()));
    assert_eq!(parsed.document_json().as_bytes(), raw);
    let error = parsed.import_native_view().unwrap_err();
    assert_eq!(error.code, "LEGACY_NATIVE_UTF16");
    assert_eq!(
        error.original_document_digest.as_deref(),
        Some(parsed.original_digest())
    );
    assert_eq!(error.source_record.unwrap().byte_digest, byte_digest(raw));
    assert_eq!(
        error
            .issues
            .iter()
            .map(|issue| issue.path.as_str())
            .collect::<Vec<_>>(),
        ["/relations/0/sourceKinds/0", "/version"]
    );
}

#[test]
fn executable_file_text_rejects_decoded_duplicates_before_unicode_and_retains_scalar_sources() {
    let duplicate =
        br#"{"schemaVersion":"1.0.0","description":"\ud800","\u0073chemaVersion":"2.0.0"}"#;
    assert_eq!(
        ParsedLegacyRelationPack::parse(duplicate.to_vec())
            .unwrap_err()
            .code,
        "DUPLICATE_JSON_KEY"
    );
    let invalid = br#"{"schemaVersion":"2.0.0","id":"urn:pack:test","version":"1","relations":[],"laws":[],"description":"\ud800"}"#;
    assert_eq!(
        ParsedLegacyRelationPack::parse(invalid.to_vec())
            .unwrap_err()
            .code,
        "INVALID_JSON_UNICODE"
    );
    let raw = br#"{"version":"1","schemaVersion":"2.0.0","relations":[],"laws":[],"id":"urn:pack:test","description":"\ud800\udc00\ue000"}"#;
    let parsed = ParsedLegacyRelationPack::parse(raw.to_vec()).unwrap();
    let imported = parsed.import_native_view().unwrap();
    assert_eq!(
        parsed.original_digest(),
        canonical_digest(imported.original_document()).unwrap()
    );
    assert_eq!(
        imported.original_document()["description"],
        "\u{10000}\u{e000}"
    );
    assert_eq!(
        imported
            .report()
            .source
            .as_ref()
            .unwrap()
            .duplicate_property_policy,
        "reject-decoded-duplicates"
    );
    assert_eq!(imported.source_bytes().unwrap(), raw);
}

#[test]
fn legacy_empty_kind_lists_preserve_data_and_original_digest_without_admission() {
    let document = json!({
        "version":"1", "schemaVersion":"1.0.0", "id":"urn:pack:empty-kinds",
        "relations":[{"id":"test:edge", "cyclePolicy":"allow", "sourceKinds":[], "targetKinds":[], "cardinalities":[]}]
    });
    let imported = import_legacy_relation_pack(document.clone()).unwrap();
    // Independently specified original compact stable JSON, including its LF.
    let bytes = b"{\"id\":\"urn:pack:empty-kinds\",\"relations\":[{\"cardinalities\":[],\"cyclePolicy\":\"allow\",\"id\":\"test:edge\",\"sourceKinds\":[],\"targetKinds\":[]}],\"schemaVersion\":\"1.0.0\",\"version\":\"1\"}\n";
    assert_eq!(imported.original_digest(), byte_digest(bytes));
    assert_eq!(imported.original_document(), &document);
    assert_eq!(imported.report().discarded_paths.len(), 0);
    assert_eq!(imported.report().changes.len(), 2);
    assert_eq!(
        imported
            .report()
            .pending_checks
            .iter()
            .filter(|check| check.code == "NATIVE_EMPTY_LIST_INCOMPATIBILITY")
            .map(|check| check.path.as_str())
            .collect::<Vec<_>>(),
        [
            "/relations/0/sourceKinds",
            "/relations/0/targetKinds",
            "/relations/0/cardinalities"
        ]
    );
    assert!(!imported.report().admitted);
    assert!(!imported.report().registry_validated);
    assert_ne!(
        imported.original_digest(),
        imported.report().native_view_digest
    );
    let mut restored = serde_json::to_value(imported.native_view()).unwrap();
    restored.as_object_mut().unwrap().remove("documentType");
    restored["schemaVersion"] = "1.0.0".into();
    assert_eq!(restored, document);

    let registry = RelationRegistry::from_legacy_packs([document]).unwrap();
    assert!(
        registry
            .get("test:edge")
            .unwrap()
            .source_kinds
            .as_ref()
            .unwrap()
            .is_empty()
    );
    // A valid legacy shape is not automatically a valid modern checked pack.
    assert!(RelationRegistry::new([imported.native_view().clone()]).is_err());
}

#[test]
fn executable_imports_bind_original_addresses_and_registration_order() {
    let core = core();
    let pack = executable(&core);
    let imported = import_legacy_relation_pack(pack.clone()).unwrap();
    assert_eq!(imported.original_digest(), canonical_digest(&pack).unwrap());
    let registry = RelationRegistry::from_legacy_packs([core.clone(), pack.clone()]).unwrap();
    let (owner, law) = registry.get_law("urn:law:legacy-test").unwrap();
    assert_eq!(owner.id, "urn:pack:legacy-test");
    assert_eq!(law.operands, ["core:contains", "core:contains"]);
    assert_eq!(
        registry.imported_packs().unwrap()[0].original_document(),
        &core
    );
    assert_eq!(registry.all_packs().len(), 2);

    let error = RelationRegistry::from_legacy_packs([pack.clone(), core.clone()]).unwrap_err();
    assert!(
        error
            .0
            .iter()
            .any(|issue| issue.code == "MISSING_EXACT_PACK_IMPORT")
    );
    let mut changed = core.clone();
    changed["description"] = "changed imported data".into();
    let error = RelationRegistry::from_legacy_packs([changed, pack.clone()]).unwrap_err();
    assert!(
        error
            .0
            .iter()
            .any(|issue| issue.code == "PACK_IMPORT_BINDING_MISMATCH")
    );
    let mut wrong_profile = pack;
    wrong_profile["imports"][0]["digest"] = import_legacy_relation_pack(core.clone())
        .unwrap()
        .report()
        .native_view_digest
        .clone()
        .into();
    let error = RelationRegistry::from_legacy_packs([core, wrong_profile]).unwrap_err();
    assert!(
        error
            .0
            .iter()
            .any(|issue| issue.code == "PACK_IMPORT_BINDING_MISMATCH")
    );
}

#[test]
fn schema_dispatch_rejects_unreported_fields_and_invalid_version_specific_shapes() {
    let base = executable(&core());
    let mut unknown = base.clone();
    unknown["newMandatoryFeature"] = true.into();
    let error = import_legacy_relation_pack(unknown).unwrap_err();
    assert_eq!(error.code, "LEGACY_PACK_SCHEMA");
    assert!(
        error
            .issues
            .iter()
            .any(|issue| issue.message.contains("newMandatoryFeature"))
    );
    let mut empty = base.clone();
    empty["relations"] = json!([{"id":"test:edge", "cyclePolicy":"allow", "sourceKinds":[]}]);
    assert!(import_legacy_relation_pack(empty).is_err());
    let mut arity = base.clone();
    arity["laws"][0]["operands"] = json!(["core:contains"]);
    assert!(import_legacy_relation_pack(arity).is_err());
    let mut reverse = base.clone();
    reverse["laws"][0]["operation"] = "reverse".into();
    reverse["laws"][0]["operands"] = json!(["core:contains"]);
    reverse["laws"][0]["conditions"] = json!({"middleKinds":["concept"]});
    assert!(import_legacy_relation_pack(reverse).is_err());
    let mut null = base;
    null["description"] = Value::Null;
    let error = import_legacy_relation_pack(null).unwrap_err();
    assert!(
        error
            .issues
            .iter()
            .any(|issue| issue.path == "/description")
    );
    let mut version = core();
    version["schemaVersion"] = "3.0.0".into();
    assert!(import_legacy_relation_pack(version).is_err());
}

#[test]
fn imported_registry_rejects_collisions_and_modern_mutation_without_changing_snapshot() {
    let original = core();
    let mut duplicate = original.clone();
    duplicate["id"] = "urn:pack:duplicate".into();
    let error = RelationRegistry::from_legacy_packs([original.clone(), duplicate]).unwrap_err();
    assert!(
        error
            .0
            .iter()
            .any(|issue| issue.code == "DUPLICATE_RELATION")
    );
    let mut registry = RelationRegistry::from_legacy_packs([original.clone(), original]).unwrap();
    assert_eq!(registry.all_packs().len(), 1);
    let before = canonical_digest(&registry.all_packs()).unwrap();
    let native: RelationPack = registry.all_packs()[0].clone();
    let error = registry.register_pack(native).unwrap_err();
    assert_eq!(error.0[0].code, "LEGACY_REGISTRY_SNAPSHOT");
    assert_eq!(before, canonical_digest(&registry.all_packs()).unwrap());
    let empty = RelationRegistry::from_legacy_packs([]).unwrap();
    assert!(empty.imported_packs().unwrap().is_empty());
    assert!(empty.get("core:contains").is_none());
}

#[test]
fn portable_shape_is_separate_from_executable_scope_validation() {
    let mut pack = executable(&core());
    pack["laws"][0]["resultRelation"] = "missing:relation".into();
    assert!(import_legacy_relation_pack(pack.clone()).is_ok());
    let error = RelationRegistry::from_legacy_packs([core(), pack]).unwrap_err();
    assert!(
        error
            .0
            .iter()
            .any(|issue| issue.code == "LAW_RELATION_OUTSIDE_PACK")
    );
}

#[test]
fn preserved_uri_format_and_javascript_whitespace_are_not_replaced_by_other_standards() {
    for schema in [
        "",
        "#fragment",
        "../relative",
        "relative\"quoted",
        "'quoted'",
    ] {
        let pack = json!({"$schema":schema,"schemaVersion":"1.0.0","id":"urn:legacy:x\u{0085}","version":"1","relations":[]});
        assert!(import_legacy_relation_pack(pack).is_ok(), "{schema:?}");
    }
    for schema in ["has space", "[broken", "urn:😀", "urn:a%xx"] {
        let pack = json!({"$schema":schema,"schemaVersion":"1.0.0","id":"urn:legacy:x","version":"1","relations":[]});
        assert!(import_legacy_relation_pack(pack).is_err(), "{schema:?}");
    }
    for suffix in ["\n", "\r", "\t", "\u{00a0}", "\u{feff}"] {
        let pack = json!({"schemaVersion":"1.0.0","id":format!("urn:legacy:x{suffix}"),"version":"1","relations":[]});
        assert!(import_legacy_relation_pack(pack).is_err(), "{suffix:?}");
    }
}
