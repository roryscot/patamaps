//! Source configuration is a portable observation contract, never authority.
use crate::{Error, Result, SSSOM_TRANSPORT_LIMITS, interpret, refuse};
use jsonschema::error::ValidationErrorKind;
use patamaps_contracts::{JsonObject, parse_value_with_limits};
use serde::{Deserialize, Serialize, de};
use serde_json::Value;
use std::{fmt, sync::OnceLock};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SssomSourceConfig {
    pub id: String,
    pub adapter: String,
    pub path: String,
    pub format_version: String,
    pub source_revision: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub metadata_path: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub record_id_column: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub provenance: Option<JsonObject>,
}

// JSON object order affects the reference's all-errors diagnostics. Keep it
// separately from serde_json's sorted value map; values are already checked.
struct OrderedKeys(Vec<String>);
impl<'de> Deserialize<'de> for OrderedKeys {
    fn deserialize<D: de::Deserializer<'de>>(
        deserializer: D,
    ) -> std::result::Result<Self, D::Error> {
        struct Visitor;
        impl<'de> de::Visitor<'de> for Visitor {
            type Value = OrderedKeys;
            fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
                f.write_str("an object whose keys retain source order")
            }
            fn visit_map<A: de::MapAccess<'de>>(
                self,
                mut map: A,
            ) -> std::result::Result<Self::Value, A::Error> {
                let mut keys = Vec::new();
                while let Some(key) = map.next_key()? {
                    keys.push(key);
                    map.next_value::<de::IgnoredAny>()?;
                }
                Ok(OrderedKeys(keys))
            }
        }
        deserializer.deserialize_map(Visitor)
    }
}
fn ordered_keys(bytes: &[u8]) -> Result<Vec<String>> {
    let mut parser = serde_json::Deserializer::from_slice(bytes);
    parser.disable_recursion_limit();
    OrderedKeys::deserialize(&mut parser)
        .map(|keys| keys.0)
        .map_err(|error| Error::new("SSSOM_SOURCE_CONFIG", error.to_string()))
}
const PROPERTIES: [&str; 8] = [
    "id",
    "adapter",
    "path",
    "metadataPath",
    "formatVersion",
    "sourceRevision",
    "recordIdColumn",
    "provenance",
];
const REQUIRED: [&str; 5] = ["id", "adapter", "path", "formatVersion", "sourceRevision"];
fn validator() -> &'static jsonschema::Validator {
    static SOURCE: OnceLock<jsonschema::Validator> = OnceLock::new();
    SOURCE.get_or_init(|| {
        let schema: Value = serde_json::from_slice(include_bytes!(
            "../../../fixtures/reference/schemas/metamap-sssom-source.schema.json"
        ))
        .expect("pinned source schema");
        assert_eq!(schema["required"], serde_json::json!(REQUIRED));
        assert_eq!(
            schema["properties"].as_object().unwrap().len(),
            PROPERTIES.len()
        );
        assert!(
            PROPERTIES
                .iter()
                .all(|name| schema["properties"].get(name).is_some())
        );
        jsonschema::options()
            .with_draft(jsonschema::Draft::Draft202012)
            .build(&schema)
            .expect("pinned source schema compiles")
    })
}

/// Parse the pinned open provenance/closed configuration schema. Filesystem
/// selection and local-input enforcement belong to discovery, not this parser.
pub fn parse_sssom_source_config(bytes: &[u8]) -> Result<SssomSourceConfig> {
    let value = parse_value_with_limits(bytes, SSSOM_TRANSPORT_LIMITS)?;
    let keys = if value.is_object() {
        ordered_keys(bytes)?
    } else {
        Vec::new()
    };
    let mut messages = Vec::new();
    for error in validator().iter_errors(&value) {
        let pointer = error.instance_path().to_string();
        let path = if pointer.is_empty() { "$" } else { &pointer };
        let property = pointer.strip_prefix('/').unwrap_or("");
        let order = PROPERTIES
            .iter()
            .position(|name| *name == property)
            .unwrap_or(0);
        let message = match error.kind() {
            ValidationErrorKind::Required { property } => {
                let property = property.as_str().expect("string property");
                messages.push((
                    0,
                    REQUIRED.iter().position(|name| *name == property).unwrap(),
                    format!("$ must have required property '{property}'"),
                ));
                continue;
            }
            ValidationErrorKind::AdditionalProperties { unexpected } => {
                for property in unexpected {
                    messages.push((
                        1,
                        keys.iter().position(|name| name == property).unwrap(),
                        "$ must NOT have additional properties".into(),
                    ));
                }
                continue;
            }
            ValidationErrorKind::Constant { .. } => "must be equal to constant".into(),
            ValidationErrorKind::Type { .. } => format!(
                "must be {}",
                if pointer.is_empty() || property == "provenance" {
                    "object"
                } else {
                    "string"
                }
            ),
            ValidationErrorKind::MinLength { limit } => {
                format!("must NOT have fewer than {limit} characters")
            }
            ValidationErrorKind::MaxLength { limit } => {
                format!("must NOT have more than {limit} characters")
            }
            _ => error.to_string(),
        };
        messages.push((2, order, format!("{path} {message}")));
    }
    if !messages.is_empty() {
        messages.sort_by_key(|(group, order, _)| (*group, *order));
        return refuse(
            "SSSOM_SOURCE_CONFIG",
            &messages
                .into_iter()
                .map(|(_, _, message)| message)
                .collect::<Vec<_>>()
                .join("; "),
        );
    }
    serde_json::from_value(value)
        .map_err(|error| Error::new("SSSOM_SOURCE_CONFIG", error.to_string()))
}

/// Pinned slot source order is observable in the public TypeScript constant.
pub fn propagatable_slots() -> &'static [String] {
    static ORDER: OnceLock<Vec<String>> = OnceLock::new();
    ORDER.get_or_init(|| {
        #[derive(Deserialize)]
        struct SlotOrder {
            #[serde(rename = "mappingSet")]
            mapping_set: OrderedKeys,
        }
        let order: SlotOrder = serde_json::from_slice(include_bytes!(
            "../../../fixtures/reference/schemas/sssom-1.0.0-slots.json"
        ))
        .expect("pinned slot index");
        order
            .mapping_set
            .0
            .into_iter()
            .filter(|name| interpret::slots().mapping_set[name].propagated)
            .collect()
    })
}
