use crate::*;
use patamaps_contracts::{
    JsonLimits, JsonObject, MAX_SAFE_INTEGER, STRICT_JSON_LIMITS, canonical_bytes,
    parse_with_limits,
};
use serde::Deserialize;
use serde_json::{Number, Value, json};
use std::{
    collections::{BTreeMap, BTreeSet},
    sync::OnceLock,
};
const XSD: &str = "http://www.w3.org/2001/XMLSchema#";
#[derive(Debug, Deserialize)]
pub(crate) struct Slot {
    pub range: String,
    pub multivalued: bool,
    pub propagated: bool,
}
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct Slots {
    pub mapping: BTreeMap<String, Slot>,
    pub mapping_set: BTreeMap<String, Slot>,
}
pub(crate) fn slots() -> &'static Slots {
    static SLOTS: OnceLock<Slots> = OnceLock::new();
    SLOTS.get_or_init(|| {
        serde_json::from_slice(include_bytes!(
            "../../../fixtures/reference/schemas/sssom-1.0.0-slots.json"
        ))
        .expect("pinned slot index")
    })
}
fn validator() -> &'static jsonschema::Validator {
    static MODEL: OnceLock<jsonschema::Validator> = OnceLock::new();
    MODEL.get_or_init(|| {
        let upstream: Value = serde_json::from_slice(include_bytes!("../../../fixtures/reference/schemas/sssom-1.0.0.schema.json")).expect("pinned schema");
        jsonschema::options().with_draft(jsonschema::Draft::Draft201909).should_validate_formats(true)
            .build(&json!({"$schema":"https://json-schema.org/draft/2019-09/schema","$defs":upstream["$defs"],"$ref":"#/$defs/MappingSet"})).expect("pinned offline MappingSet schema")
    })
}
pub(crate) fn has(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::String(v) => !v.is_empty(),
        Value::Array(v) => !v.is_empty(),
        _ => true,
    }
}
pub(crate) fn ncname(value: &str) -> bool {
    fn start(c: char) -> bool {
        c == '_'
            || c.is_ascii_alphabetic()
            || matches!(c as u32, 0xC0..=0xD6|0xD8..=0xF6|0xF8..=0x2FF|0x370..=0x37D|0x37F..=0x1FFF|0x200C..=0x200D|0x2070..=0x218F|0x2C00..=0x2FEF|0x3001..=0xD7FF|0xF900..=0xFDCF|0xFDF0..=0xFFFD|0x10000..=0xEFFFF)
    }
    let mut chars = value.chars();
    chars.next().is_some_and(start)
        && chars.all(|c| {
            start(c)
                || c.is_ascii_digit()
                || matches!(c, '.' | '-' | '\u{b7}')
                || matches!(c as u32, 0x300..=0x36F|0x203F..=0x2040)
        })
}
pub(crate) fn iri(value: &str) -> Result<()> {
    if !patamaps_core::valid_identifier(value)
        || value.chars().any(|c| c <= '\u{20}' || c == '\u{7f}')
        || fluent_uri::Iri::parse(value).is_err()
    {
        return refuse(
            "SSSOM_IDENTIFIER",
            "Expected an absolute IRI without whitespace/control characters",
        );
    }
    Ok(())
}
pub fn expand_curie(value: &str, prefixes: &BTreeMap<String, String>) -> Result<String> {
    let Some((prefix, local)) = value.split_once(':') else {
        return refuse("SSSOM_CURIE", "Expected a CURIE");
    };
    if !ncname(prefix)
        || local.is_empty()
        || local.starts_with("//")
        || value.chars().any(|c| c <= '\u{20}' || c == '\u{7f}')
    {
        return refuse("SSSOM_CURIE", "Malformed CURIE or unsupported full IRI");
    }
    let Some(base) = prefixes.get(prefix) else {
        return refuse("SSSOM_UNDECLARED_PREFIX", "Undeclared CURIE prefix");
    };
    let result = format!("{base}{local}");
    iri(&result)?;
    Ok(result)
}
pub fn builtin_prefixes() -> BTreeMap<String, String> {
    [
        ("owl", "http://www.w3.org/2002/07/owl#"),
        ("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
        ("rdfs", "http://www.w3.org/2000/01/rdf-schema#"),
        ("semapv", "https://w3id.org/semapv/vocab/"),
        ("skos", "http://www.w3.org/2004/02/skos/core#"),
        ("sssom", "https://w3id.org/sssom/"),
        ("xsd", XSD),
        ("linkml", "https://w3id.org/linkml/"),
    ]
    .into_iter()
    .map(|(k, v)| (k.into(), v.into()))
    .collect()
}
fn prefixes(metadata: &JsonObject) -> Result<BTreeMap<String, String>> {
    let mut prefixes = builtin_prefixes();
    if let Some(declared) = metadata.get("curie_map") {
        let Value::Object(declared) = declared else {
            return refuse("SSSOM_PREFIX_MAP", "curie_map must be a mapping");
        };
        for (name, value) in declared {
            let Some(value) = value.as_str() else {
                return refuse("SSSOM_PREFIX_MAP", "Prefix values must be IRI strings");
            };
            if !ncname(name) {
                return refuse("SSSOM_PREFIX_MAP", "Invalid prefix NCName");
            }
            iri(value)?;
            if prefixes.get(name).is_some_and(|current| current != value) {
                return refuse(
                    "SSSOM_PREFIX_COLLISION",
                    "Built-in prefixes cannot be redefined",
                );
            }
            prefixes.insert(name.clone(), value.into());
        }
    }
    Ok(prefixes)
}
fn extensions(
    metadata: &JsonObject,
    prefixes: &BTreeMap<String, String>,
) -> Result<Vec<Extension>> {
    let Some(definitions) = metadata.get("extension_definitions") else {
        return Ok(Vec::new());
    };
    let Some(definitions) = definitions.as_array() else {
        return refuse("SSSOM_EXTENSION", "Extension definitions must be an array");
    };
    let mut names = BTreeSet::new();
    let mut properties = BTreeSet::new();
    let mut result = Vec::new();
    for value in definitions {
        let Some(value) = value.as_object() else {
            return refuse("SSSOM_EXTENSION", "Malformed extension definition");
        };
        let Some(name) = value.get("slot_name").and_then(Value::as_str) else {
            return refuse("SSSOM_EXTENSION", "Missing extension name");
        };
        if !ncname(name)
            || !names.insert(name)
            || slots().mapping.contains_key(name)
            || slots().mapping_set.contains_key(name)
            || value
                .keys()
                .any(|k| !["slot_name", "property", "type_hint"].contains(&k.as_str()))
        {
            return refuse("SSSOM_EXTENSION", "Invalid or duplicate extension slot");
        }
        let field = |name: &str| -> Result<Option<&str>> {
            value
                .get(name)
                .map(|v| {
                    v.as_str().ok_or_else(|| {
                        Error::new(
                            "SSSOM_EXTENSION",
                            "Extension definitions require CURIE strings",
                        )
                    })
                })
                .transpose()
        };
        let property = field("property")?
            .map(|v| expand_curie(v, prefixes))
            .transpose()?
            .unwrap_or_else(|| format!("http://sssom.invalid/{name}"));
        let type_ = field("type_hint")?
            .map(|v| expand_curie(v, prefixes))
            .transpose()?
            .unwrap_or_else(|| format!("{XSD}string"));
        if !properties.insert(property.clone()) {
            return refuse("SSSOM_EXTENSION", "Duplicate extension property");
        }
        result.push(Extension {
            name: name.into(),
            property,
            type_,
        });
    }
    Ok(result)
}
fn decimal(text: &str) -> Option<f64> {
    let mut rest = text.strip_prefix(['+', '-']).unwrap_or(text);
    if rest.is_empty() {
        return None;
    }
    if let Some((mantissa, exp)) = rest.split_once(['e', 'E']) {
        rest = mantissa;
        let exp = exp.strip_prefix(['+', '-']).unwrap_or(exp);
        if exp.is_empty() || !exp.bytes().all(|c| c.is_ascii_digit()) {
            return None;
        }
    }
    let mut dots = 0;
    let mut digits = 0;
    for c in rest.bytes() {
        if c == b'.' {
            dots += 1;
        } else if c.is_ascii_digit() {
            digits += 1;
        } else {
            return None;
        }
    }
    if dots > 1 || digits == 0 {
        return None;
    }
    text.parse::<f64>().ok().filter(|v| v.is_finite())
}
fn extension_value(
    value: &Value,
    type_: &str,
    prefixes: &BTreeMap<String, String>,
) -> Result<Value> {
    if value.is_null() || value.is_object() || value.is_array() {
        return refuse("SSSOM_EXTENSION_VALUE", "Extension values must be scalar");
    }
    if type_ == format!("{XSD}string") && !value.is_string() {
        return refuse(
            "SSSOM_EXTENSION_VALUE",
            "String extension requires a string",
        );
    }
    if [format!("{XSD}integer"), format!("{XSD}double")].contains(&type_.into()) {
        let number = value
            .as_f64()
            .or_else(|| value.as_str().and_then(decimal))
            .ok_or_else(|| {
                Error::new(
                    "SSSOM_EXTENSION_VALUE",
                    "Invalid finite numeric lexical form",
                )
            })?;
        if type_.ends_with("integer")
            && (number.fract() != 0.0 || number.abs() > MAX_SAFE_INTEGER as f64)
        {
            return refuse("SSSOM_EXTENSION_VALUE", "Unsafe extension integer");
        }
        return Ok(Value::Number(
            Number::from_f64(number).expect("finite checked number"),
        ));
    }
    if type_ == format!("{XSD}boolean") {
        return match value {
            Value::Bool(v) => Ok(Value::Bool(*v)),
            Value::String(v) if v == "true" || v == "false" => Ok(Value::Bool(v == "true")),
            _ => refuse(
                "SSSOM_EXTENSION_VALUE",
                "Boolean extension requires true or false",
            ),
        };
    }
    if [
        format!("{XSD}date"),
        format!("{XSD}datetime"),
        format!("{XSD}dateTime"),
    ]
    .contains(&type_.into())
    {
        let schema = json!({"type":"string","format":if type_.ends_with("date") { "date" } else { "date-time" }});
        if !jsonschema::options()
            .should_validate_formats(true)
            .build(&schema)
            .expect("fixed format schema")
            .is_valid(value)
        {
            return refuse("SSSOM_EXTENSION_VALUE", "Invalid extension date/time");
        }
    } else if type_ == "https://w3id.org/linkml/Uriorcurie" {
        expand_curie(
            value
                .as_str()
                .ok_or_else(|| Error::new("SSSOM_EXTENSION_VALUE", "Expected CURIE"))?,
            prefixes,
        )?;
    }
    Ok(value.clone())
}
pub(crate) fn interpret(document: &SssomDocument) -> Result<Interpretation> {
    if document.metadata.contains_key("mappings") {
        return refuse("SSSOM_METADATA", "Metadata must not contain mappings");
    }
    let prefixes = prefixes(&document.metadata)?;
    let extensions = extensions(&document.metadata, &prefixes)?;
    let extension_map: BTreeMap<_, _> = extensions
        .iter()
        .map(|e| (e.name.as_str(), e.type_.as_str()))
        .collect();
    let mut metadata = document.metadata.clone();
    for (name, value) in &mut metadata {
        if let Some(slot) = slots().mapping_set.get(name) {
            if slot.multivalued && name != "curie_map" && has(value) && !value.is_array() {
                *value = Value::Array(vec![value.clone()]);
            }
            if slot.range == "EntityReference" && has(value) {
                for id in members(value) {
                    expand_curie(
                        id.as_str().ok_or_else(|| {
                            Error::new(
                                "SSSOM_IDENTIFIER",
                                "Metadata reference must be CURIE string",
                            )
                        })?,
                        &prefixes,
                    )?;
                }
            }
        } else {
            let Some(type_) = extension_map.get(name.as_str()) else {
                return refuse("SSSOM_UNDEFINED_EXTENSION", "Undefined metadata extension");
            };
            *value = extension_value(value, type_, &prefixes)?;
        }
    }
    for name in &document.columns {
        if !slots().mapping.contains_key(name) && !extension_map.contains_key(name.as_str()) {
            return refuse("SSSOM_UNDEFINED_EXTENSION", "Undefined TSV column");
        }
    }
    for name in [
        "subject_id",
        "predicate_id",
        "object_id",
        "mapping_justification",
    ] {
        if !document.columns.iter().any(|v| v == name) {
            return refuse("SSSOM_REQUIRED_FIELD", "Missing required column");
        }
    }
    let mut records = Vec::new();
    for row in &document.rows {
        if row.len() != document.columns.len() {
            return refuse("SSSOM_TSV_WIDTH", "Record width differs from header");
        }
        let raw: BTreeMap<_, _> = document
            .columns
            .iter()
            .cloned()
            .zip(row.iter().cloned())
            .collect();
        let mut fields = BTreeMap::new();
        let mut origins = BTreeMap::new();
        for (name, value) in &raw {
            if !value.is_empty() {
                let value = if let Some(type_) = extension_map.get(name.as_str()) {
                    extension_value(&Value::String(value.clone()), type_, &prefixes)?
                } else {
                    let slot = &slots().mapping[name];
                    if slot.range == "double" {
                        Value::Number(
                            Number::from_f64(decimal(value).ok_or_else(|| {
                                Error::new("SSSOM_NUMERIC_VALUE", "Invalid numeric cell")
                            })?)
                            .expect("finite number"),
                        )
                    } else if slot.multivalued {
                        Value::Array(value.split('|').map(|v| Value::String(v.into())).collect())
                    } else {
                        Value::String(value.clone())
                    }
                };
                if value
                    .as_array()
                    .is_some_and(|a| a.iter().any(|v| v.as_str() == Some("")))
                {
                    return refuse("SSSOM_MULTIVALUE", "Empty multi-value member");
                }
                fields.insert(name.clone(), value);
                origins.insert(name.clone(), FieldOrigin::Record);
            }
        }
        records.push(SssomRecord {
            raw,
            fields,
            origins,
            expanded: BTreeMap::new(),
        });
    }
    let mut propagation = Vec::new();
    for name in crate::propagatable_slots() {
        let Some(value) = metadata.get(name).filter(|v| has(v)) else {
            continue;
        };
        let value = value.clone();
        let blocked = records.iter().any(|r| r.fields.get(name).is_some_and(has));
        propagation.push(Propagation {
            slot: name.clone(),
            status: if blocked {
                PropagationStatus::BlockedByRecordValue
            } else {
                PropagationStatus::Propagated
            },
            value: value.clone(),
        });
        if !blocked {
            for record in &mut records {
                record.fields.insert(name.clone(), value.clone());
                record.origins.insert(name.clone(), FieldOrigin::Set);
            }
            metadata.remove(name);
        }
    }
    for record in &mut records {
        if ["subject_type", "object_type"]
            .iter()
            .any(|k| record.fields.get(*k).and_then(Value::as_str) == Some("rdfs literal"))
        {
            return refuse(
                "SSSOM_UNSUPPORTED_LITERAL",
                "Literal records are outside the entity TSV profile",
            );
        }
        if record.fields.contains_key("predicate_modifier") {
            return refuse(
                "SSSOM_UNSUPPORTED_NEGATION",
                "Negated records are outside the entity TSV profile",
            );
        }
        for name in [
            "subject_id",
            "predicate_id",
            "object_id",
            "mapping_justification",
        ] {
            if record
                .fields
                .get(name)
                .and_then(Value::as_str)
                .is_none_or(str::is_empty)
            {
                return refuse("SSSOM_REQUIRED_FIELD", "Missing required record value");
            }
        }
        for (name, value) in &record.fields {
            if !slots()
                .mapping
                .get(name)
                .is_some_and(|s| s.range == "EntityReference")
            {
                continue;
            }
            let expanded = members(value)
                .iter()
                .map(|v| {
                    let result = expand_curie(
                        v.as_str().ok_or_else(|| {
                            Error::new("SSSOM_IDENTIFIER", "Expected CURIE string")
                        })?,
                        &prefixes,
                    )?;
                    if result == "https://w3id.org/sssom/NoTermFound" {
                        return refuse(
                            "SSSOM_UNSUPPORTED_UNMAPPED",
                            "NoTermFound is outside the entity TSV profile",
                        );
                    }
                    Ok(Value::String(result))
                })
                .collect::<Result<Vec<_>>>()?;
            record.expanded.insert(
                name.clone(),
                if value.is_array() {
                    Value::Array(expanded)
                } else {
                    expanded.into_iter().next().expect("one scalar")
                },
            );
        }
    }
    let standard_metadata: JsonObject = metadata
        .iter()
        .filter(|(k, _)| slots().mapping_set.contains_key(*k))
        .map(|(k, v)| (k.clone(), v.clone()))
        .collect();
    let mappings: Vec<JsonObject> = records
        .iter()
        .map(|r| {
            r.fields
                .iter()
                .filter(|(k, _)| slots().mapping.contains_key(*k))
                .map(|(k, v)| (k.clone(), v.clone()))
                .collect()
        })
        .collect();
    let mut model = serde_json::to_value(standard_metadata)
        .map_err(|e| Error::new("SSSOM_MODEL", e.to_string()))?;
    model["mappings"] = json!(mappings);
    if let Err(error) = validator().validate(&model) {
        return Err(Error::new("SSSOM_MODEL", error.to_string()));
    }
    for name in ["mapping_set_id", "license"] {
        iri(metadata
            .get(name)
            .and_then(Value::as_str)
            .ok_or_else(|| Error::new("SSSOM_REQUIRED_FIELD", "Missing required set IRI"))?)?;
    }
    Ok(Interpretation {
        metadata,
        prefixes,
        extensions,
        propagation,
        records,
    })
}
fn members(value: &Value) -> Vec<&Value> {
    match value {
        Value::Array(v) => v.iter().collect(),
        _ => vec![value],
    }
}

pub fn check_document(document: &SssomDocument) -> Result<CheckedSssom> {
    check_document_with_limits(document, STRICT_JSON_LIMITS)
}
pub fn check_document_compatible(document: &SssomDocument) -> Result<CheckedSssom> {
    check_document_with_limits(document, SSSOM_COMPATIBILITY_LIMITS)
}
pub(crate) fn check_document_with_limits(
    document: &SssomDocument,
    limits: JsonLimits,
) -> Result<CheckedSssom> {
    if document.rows.len() > 50_000
        || !(1..=256).contains(&document.columns.len())
        || document.columns.iter().any(|c| c.is_empty())
        || document.columns.iter().collect::<BTreeSet<_>>().len() != document.columns.len()
    {
        return refuse(
            "SSSOM_DOCUMENT",
            "Invalid document row/header bounds or duplicate column",
        );
    }
    patamaps_core::check_metadata_bounds_with_limits(
        [(&document.metadata, 2)],
        "sssom",
        "SSSOM_METADATA_LIMIT",
        limits,
    )?;
    let bytes = canonical_bytes(document)?;
    if bytes.len() > limits.max_bytes {
        return Err(Error::new(
            "SSSOM_SIZE_LIMIT",
            format!("Encoded source exceeds {} bytes", limits.max_bytes),
        ));
    }
    let document: SssomDocument = parse_with_limits(&bytes, limits)?;
    let interpretation = interpret(&document)?;
    Ok(CheckedSssom {
        document,
        interpretation,
        limits,
    })
}
pub fn parse_tsv(input: &[u8], external: Option<&[u8]>) -> Result<CheckedSssom> {
    parse_tsv_with_limits(input, external, STRICT_JSON_LIMITS)
}
pub fn parse_tsv_compatible(input: &[u8], external: Option<&[u8]>) -> Result<CheckedSssom> {
    parse_tsv_with_limits(input, external, SSSOM_COMPATIBILITY_LIMITS)
}
pub(crate) fn parse_tsv_with_limits(
    input: &[u8],
    external: Option<&[u8]>,
    limits: JsonLimits,
) -> Result<CheckedSssom> {
    check_document_with_limits(&syntax::decode(input, external, limits)?, limits)
}
