use crate::*;
use patamaps_contracts::*;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ImportOptions {
    pub id: String,
    pub namespace: String,
    pub source_revision: String,
    #[serde(
        default,
        deserialize_with = "patamaps_contracts::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub record_id_column: Option<String>,
    #[serde(
        default,
        deserialize_with = "patamaps_contracts::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub provenance: Option<JsonObject>,
}
pub fn scientific_pack() -> RelationPack {
    parse(include_bytes!(
        "../package-inputs/relation-packs/scientific-skos.json"
    ))
    .expect("pinned draft SKOS pack")
}
pub fn predicate_relation(iri: &str) -> Option<&'static str> {
    match iri.strip_prefix("http://www.w3.org/2004/02/skos/core#")? {
        "exactMatch" => Some("scientific:exact-match"),
        "closeMatch" => Some("scientific:close-match"),
        "broadMatch" => Some("scientific:broad-match"),
        "narrowMatch" => Some("scientific:narrow-match"),
        "relatedMatch" => Some("scientific:related-match"),
        _ => None,
    }
}
#[derive(Default)]
struct EntityData {
    identifiers: BTreeSet<String>,
    labels: BTreeSet<String>,
    types: BTreeSet<String>,
}

/// Emits source observations with unknown loss and no authenticated ownership.
pub fn import_graph(checked: &CheckedSssom, options: &ImportOptions) -> Result<GraphDocument> {
    let local_source_name = options.id.starts_with(|c: char| c.is_ascii_alphabetic())
        && options
            .id
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || b"._-".contains(&c));
    if !(patamaps_core::valid_identifier(&options.id) || local_source_name)
        || options.id.len() > 4096
        || options.source_revision.is_empty()
        || options.source_revision.len() > 4096
        || options.namespace.is_empty()
        || !options
            .namespace
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || b"._-".contains(&c))
        || !options
            .namespace
            .starts_with(|c: char| c.is_ascii_alphabetic())
    {
        return refuse(
            "SSSOM_SOURCE_CONFIG",
            "Invalid source identity, revision or namespace",
        );
    }
    patamaps_core::check_metadata_bounds(
        options.provenance.iter().map(|v| (v, 1)),
        &options.id,
        "SSSOM_SOURCE_CONFIG",
    )?;
    if let Some(column) = &options.record_id_column
        && !checked.document.columns.contains(column)
    {
        return refuse(
            "SSSOM_RECORD_ID",
            "Selected explicit record ID column absent",
        );
    }
    let interpreted = &checked.interpretation;
    let mut entities: BTreeMap<String, EntityData> = BTreeMap::new();
    let mut mappings = Vec::new();
    let mut occurrences = BTreeMap::new();
    let mut explicit_ids = BTreeSet::new();
    let set_context: JsonObject = interpreted
        .metadata
        .iter()
        .filter(|(name, _)| {
            !interpret::slots()
                .mapping_set
                .get(*name)
                .is_some_and(|s| s.propagated)
        })
        .map(|(k, v)| (k.clone(), v.clone()))
        .collect();
    let provenance = Provenance {
        status: ProvenanceStatus::Observed,
        asserted_by: options.id.clone(),
        observed_at: None,
        source_revision: Some(options.source_revision.clone()),
        confidence: None,
    };
    for record in &interpreted.records {
        for side in ["subject", "object"] {
            let id = record.expanded[&format!("{side}_id")]
                .as_str()
                .expect("checked reference");
            let data = entities.entry(id.into()).or_default();
            data.identifiers.insert(
                record.fields[&format!("{side}_id")]
                    .as_str()
                    .expect("checked identifier")
                    .into(),
            );
            if let Some(label) = record
                .fields
                .get(&format!("{side}_label"))
                .and_then(Value::as_str)
            {
                data.labels.insert(label.into());
            }
            if let Some(type_) = record
                .fields
                .get(&format!("{side}_type"))
                .and_then(Value::as_str)
            {
                data.types.insert(type_.into());
            }
        }
        let predicate = record.expanded["predicate_id"]
            .as_str()
            .expect("checked predicate");
        let recognized = predicate_relation(predicate);
        let relation = if let Some(relation) = recognized {
            relation.into()
        } else {
            format!(
                "sssom:uninterpreted-{}",
                &canonical_digest(&predicate)?[7..]
            )
        };
        let mut fields = record.fields.clone();
        fields.extend(record.expanded.clone());
        let source_record_id = options.record_id_column.as_ref().map(|c| &record.raw[c]);
        let identity = if let Some(source_record_id) = source_record_id {
            if source_record_id.is_empty() || !explicit_ids.insert(source_record_id) {
                return refuse(
                    "SSSOM_RECORD_ID",
                    "Explicit source IDs must be present and unique",
                );
            }
            canonical_digest(
                &json!({"source":options.id,"mappingSet":interpreted.metadata["mapping_set_id"],"sourceRecordId":source_record_id}),
            )?
        } else {
            let content = canonical_digest(
                &json!({"source":options.id,"context":set_context,"fields":fields}),
            )?;
            let occurrence = occurrences.entry(content.clone()).or_insert(0u64);
            let identity = canonical_digest(&json!({"content":content,"occurrence":*occurrence}))?;
            *occurrence += 1;
            identity
        };
        mappings.push(Mapping { id: format!("urn:metamap:sssom:assertion:{}", &identity[7..]), relation, sources: vec![record.expanded["subject_id"].as_str().unwrap().into()], targets: vec![record.expanded["object_id"].as_str().unwrap().into()], cardinality: Cardinality::OneToOne, lossiness: Lossiness::Unknown, provenance: provenance.clone(), transform: None, invariants: None,
            attributes: Some(BTreeMap::from([("sssom".into(),json!({"raw":record.raw,"fields":record.fields,"origins":record.origins,"expanded":record.expanded,"predicateInterpretation":if recognized.is_some() { "explicit-skos-lookup" } else { "uninterpreted" },"sourceRecordId":source_record_id,"uncertaintyInterpretation":"source-confidence-is-not-a-typed-assessment"}))])) });
    }
    let entities = entities.into_iter().map(|(id,data)| Entity { id: id.clone(), kind: "scientific:entity".into(), label: data.labels.iter().next().cloned(), schema: None,
        locators: Some(vec![Locator { uri: id, media_type: None, revision: None, digest: None }]),
        attributes: Some(BTreeMap::from([("sssom".into(),json!({"originalIdentifiers":data.identifiers,"labels":data.labels,"types":data.types}))])), provenance: Some(provenance.clone()) }).collect();
    let pack = scientific_pack();
    let graph = GraphDocument {
        schema: None,
        schema_version: ProtocolVersion::Draft1,
        document_type: GraphType::Graph,
        id: format!(
            "urn:metamap:sssom:source:{}",
            &canonical_digest(
                &json!({"namespace":options.namespace,"source":options.id,"mappingSet":interpreted.metadata["mapping_set_id"]})
            )?[7..]
        ),
        namespace: options.namespace.clone(),
        label: interpreted
            .metadata
            .get("mapping_set_title")
            .and_then(Value::as_str)
            .map(String::from)
            .or_else(|| Some("Scientific mapping source".into())),
        revision: Some(options.source_revision.clone()),
        relation_packs: Some(vec![PackReference {
            id: pack.id.clone(),
            version: pack.version.clone(),
            uri: None,
            digest: Some(canonical_digest(&pack)?),
        }]),
        entities,
        mappings,
        authorities: Vec::new(),
        extensions: None,
        metadata: Some(BTreeMap::from([(
            "sssom".into(),
            json!({"profile":"sssom-1.0-entity-tsv","formatVersion":"1.0.0","rawDocument":checked.document,"effectiveMetadata":interpreted.metadata,"propagation":interpreted.propagation,"prefixes":interpreted.prefixes,"extensions":interpreted.extensions,"assertionIdentity":if options.record_id_column.is_some() { "scoped-explicit-source-record-id" } else { "effective-content-occurrence-with-set-only-context" },"sourceRevision":options.source_revision,"rawSourceBytesEmbedded":false,"observedRecordCount":checked.document.rows.len(),"setCompleteness":"not-established-by-TSV","declaredProvenance":options.provenance,"scientificTruth":"not-established","authority":"source-declared-only"}),
        )])),
    };
    // This is source-shaped data, not a CheckedGraph. Unknown predicates remain
    // uninterpreted and will refuse use unless a consumer registers semantics.
    let limits = if checked.limits.max_bytes == MAX_INPUT_BYTES {
        STRICT_JSON_LIMITS
    } else {
        SSSOM_TRANSPORT_LIMITS
    };
    parse_with_limits::<GraphDocument>(&canonical_bytes(&graph)?, limits)?;
    Ok(graph)
}
