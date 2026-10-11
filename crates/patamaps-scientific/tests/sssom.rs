use patamaps_contracts::{Lossiness, canonical_bytes};
use patamaps_scientific::*;
use std::collections::BTreeSet;
const FIXTURE: &[u8] = include_bytes!(
    "../../../fixtures/reference/examples/scientific-mapping/fixtures/mgi-subset.sssom.tsv"
);
fn options() -> ImportOptions {
    ImportOptions {
        id: "urn:source:mgi".into(),
        namespace: "scientific-test".into(),
        source_revision: "e4fe727428661f0093f6ab9269f4fb80387e39fc".into(),
        record_id_column: None,
        provenance: None,
    }
}
fn error(bytes: &[u8], expected: &str) {
    assert_eq!(parse_tsv(bytes, None).unwrap_err().code, expected);
}

#[test]
fn licensed_source_keeps_seven_assertions_unknown_loss_and_full_metadata() {
    let source = parse_tsv(FIXTURE, None).unwrap();
    assert_eq!(source.document().rows.len(), 7);
    let graph = import_graph(&source, &options()).unwrap();
    assert_eq!(graph.mappings.len(), 7);
    assert!(
        graph
            .mappings
            .iter()
            .all(|m| m.lossiness == Lossiness::Unknown)
    );
    assert!(graph.authorities.is_empty());
    assert!(
        source
            .interpretation()
            .records
            .iter()
            .all(|r| r.fields.contains_key("confidence"))
    );
    assert_eq!(
        graph
            .mappings
            .iter()
            .map(|m| &m.id)
            .collect::<BTreeSet<_>>()
            .len(),
        7
    );
    let narrow: Vec<_> = graph
        .mappings
        .iter()
        .filter(|m| m.sources[0].ends_with("MP_0000433"))
        .collect();
    assert_eq!(narrow.len(), 2);
    assert_eq!(narrow[0].targets, narrow[1].targets);
    assert_ne!(narrow[0].id, narrow[1].id);
    let mut doc = source.document().clone();
    doc.rows.reverse();
    let reversed = import_graph(&check_document(&doc).unwrap(), &options()).unwrap();
    assert_eq!(
        graph
            .mappings
            .iter()
            .map(|m| &m.id)
            .collect::<BTreeSet<_>>(),
        reversed
            .mappings
            .iter()
            .map(|m| &m.id)
            .collect::<BTreeSet<_>>()
    );
    let packed = scientific_pack();
    assert_eq!(packed.laws.unwrap().len(), 7);
    assert!(
        packed
            .relations
            .iter()
            .find(|r| r.id == "scientific:close-match")
            .unwrap()
            .transitive
            == Some(false)
    );
}

#[test]
fn default_and_explicit_condensed_exports_preserve_effective_fields() {
    let original = parse_tsv(FIXTURE, None).unwrap();
    // A separate explicit control gives every row the same date, an eligible
    // propagatable slot in the pinned model. Author attribution never condenses.
    let mut document = original.document().clone();
    let date = document
        .columns
        .iter()
        .position(|c| c == "mapping_date")
        .unwrap();
    for row in &mut document.rows {
        row[date] = "2022-08-02".into();
    }
    let source = check_document(&document).unwrap();
    for condense in [false, true] {
        let exported = export_tsv(&source, condense).unwrap();
        let after = parse_tsv(exported.text.as_bytes(), None).unwrap();
        assert_eq!(
            canonical_bytes(
                &source
                    .interpretation()
                    .records
                    .iter()
                    .map(|r| &r.fields)
                    .collect::<Vec<_>>()
            )
            .unwrap(),
            canonical_bytes(
                &after
                    .interpretation()
                    .records
                    .iter()
                    .map(|r| &r.fields)
                    .collect::<Vec<_>>()
            )
            .unwrap()
        );
        assert!(exported.loss.semantic_fields_preserved);
        assert!(!exported.loss.byte_identity_preserved);
        assert!(exported.loss.dropped_fields.is_empty());
        if condense {
            assert!(
                exported
                    .loss
                    .condensed_slots
                    .contains(&"mapping_date".into())
            );
            assert!(!exported.loss.condensed_slots.contains(&"author_id".into()));
        }
    }
}

#[test]
fn strict_yaml_duplicates_aliases_tags_directives_and_wire_bounds_refuse() {
    let text = std::str::from_utf8(FIXTURE).unwrap();
    error(
        format!("#license: https://invalid.example/\n{text}").as_bytes(),
        "SSSOM_METADATA_YAML",
    );
    error(
        format!("#%YAML 1.2\n{text}").as_bytes(),
        "SSSOM_FORBIDDEN_YAML",
    );
    error(
        text.replace(
            "#mapping_set_title:",
            "#mapping_set_title: &anchor\n#unused:",
        )
        .as_bytes(),
        "SSSOM_FORBIDDEN_YAML",
    );
    error(
        text.replace("#mapping_set_title:", "#mapping_set_title: !!str")
            .as_bytes(),
        "SSSOM_FORBIDDEN_YAML",
    );
    error(format!("\u{feff}{text}").as_bytes(), "SSSOM_BOM");
    error(&[0xff], "SSSOM_UTF8");
    let mut doc = parse_tsv(FIXTURE, None).unwrap().document().clone();
    doc.columns.push(doc.columns[0].clone());
    assert_eq!(check_document(&doc).unwrap_err().code, "SSSOM_DOCUMENT");
    let nested = format!("#x: {}null{}\nsubject_id\n", "[".repeat(80), "]".repeat(80));
    assert_eq!(
        parse_tsv(nested.as_bytes(), None).unwrap_err().code,
        "SSSOM_METADATA_LIMIT"
    );
}

#[test]
fn unknown_prefix_builtin_collision_unsupported_assertions_and_lexical_numbers_refuse() {
    let text = std::str::from_utf8(FIXTURE).unwrap();
    error(
        text.replace("MP:0003622", "Missing:0003622").as_bytes(),
        "SSSOM_UNDECLARED_PREFIX",
    );
    error(
        text.replace(
            "http://www.w3.org/2004/02/skos/core#",
            "https://wrong.example/",
        )
        .as_bytes(),
        "SSSOM_PREFIX_COLLISION",
    );
    error(
        text.replace("MP:0003622", "sssom:NoTermFound").as_bytes(),
        "SSSOM_UNSUPPORTED_UNMAPPED",
    );
    let source = parse_tsv(FIXTURE, None).unwrap();
    for (column, value, expected) in [
        ("subject_type", "rdfs literal", "SSSOM_UNSUPPORTED_LITERAL"),
        ("predicate_modifier", "Not", "SSSOM_UNSUPPORTED_NEGATION"),
        ("undefined_slot", "opaque", "SSSOM_UNDEFINED_EXTENSION"),
    ] {
        let mut doc = source.document().clone();
        doc.columns.push(column.into());
        for row in &mut doc.rows {
            row.push(value.into());
        }
        assert_eq!(check_document(&doc).unwrap_err().code, expected);
    }
    let mut doc = source.document().clone();
    let index = doc.columns.iter().position(|c| c == "confidence").unwrap();
    for value in ["NaN", "Infinity", "0x1", " 0.7", "1e1000", ".", "1e"] {
        doc.rows[0][index] = value.into();
        assert_eq!(
            check_document(&doc).unwrap_err().code,
            "SSSOM_NUMERIC_VALUE"
        );
    }
}

#[test]
fn quoting_scalar_extensions_explicit_identity_and_unknown_predicate_are_preserved() {
    let source = parse_tsv(FIXTURE, None).unwrap();
    let mut doc = source.document().clone();
    let index = doc.columns.iter().position(|c| c == "comment").unwrap();
    doc.rows[0][index] = "embedded\ttab\nline\r\n\"quote\"".into();
    let checked = check_document(&doc).unwrap();
    let exported = export_tsv(&checked, false).unwrap();
    assert_eq!(
        parse_tsv(exported.text.as_bytes(), None)
            .unwrap()
            .document()
            .rows[0][index],
        doc.rows[0][index]
    );
    doc.metadata.insert(
        "extension_definitions".into(),
        serde_json::json!([{"slot_name":"record_key","type_hint":"xsd:integer"}]),
    );
    doc.columns.push("record_key".into());
    for (i, row) in doc.rows.iter_mut().enumerate() {
        row.push(i.to_string());
    }
    let checked = check_document(&doc).unwrap();
    let mut options = options();
    options.record_id_column = Some("record_key".into());
    let graph = import_graph(&checked, &options).unwrap();
    doc.rows[0][index] = "changed content".into();
    assert_eq!(
        graph.mappings[0].id,
        import_graph(&check_document(&doc).unwrap(), &options)
            .unwrap()
            .mappings[0]
            .id
    );
    *doc.rows[1].last_mut().unwrap() = "0".into();
    assert_eq!(
        import_graph(&check_document(&doc).unwrap(), &options)
            .unwrap_err()
            .code,
        "SSSOM_RECORD_ID"
    );
    let mut doc = source.document().clone();
    let pred = doc
        .columns
        .iter()
        .position(|c| c == "predicate_id")
        .unwrap();
    doc.rows[0][pred] = "skos:unregistered".into();
    let graph = import_graph(&check_document(&doc).unwrap(), &self::options()).unwrap();
    assert!(
        graph.mappings[0]
            .relation
            .starts_with("sssom:uninterpreted-")
    );
    assert!(predicate_relation("http://www.w3.org/2002/07/owl#sameAs").is_none());
}
