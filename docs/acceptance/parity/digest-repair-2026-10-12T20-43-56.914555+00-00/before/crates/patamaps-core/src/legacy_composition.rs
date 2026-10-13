//! Legacy shard composition selects retained source handles. It performs no
//! graph validation, admission, ownership evaluation or authorization.
use icu_collator::{Collator, CollatorBorrowed, CollatorPreferences};
use patamaps_contracts::{COMPATIBILITY_JSON_LIMITS, SafeInteger, parse_value_with_limits};
use serde::{
    Deserialize, Serialize,
    de::{MapAccess, SeqAccess, Visitor},
};
use serde_json::{Value, json};
use std::{
    cmp::Ordering,
    collections::{HashMap, HashSet},
    fmt,
};

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct LegacyCompositionRequest {
    /// JSON strings preserve host member order without changing the modern
    /// serde_json map profile. The SDK keeps the original source objects.
    documents: Vec<String>,
    options: Value,
    #[serde(default = "default_locale")]
    locale: String,
}
fn default_locale() -> String {
    "en-US".into()
}

#[derive(Debug, thiserror::Error, Serialize)]
#[error("{message}")]
pub struct LegacyCompositionError {
    pub code: String,
    pub name: String,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub identifier: Option<String>,
}
fn failure(
    name: &str,
    message: impl Into<String>,
    identifier: Option<&str>,
) -> LegacyCompositionError {
    LegacyCompositionError {
        code: "LEGACY_COMPOSITION_INPUT".into(),
        name: name.into(),
        message: message.into(),
        identifier: identifier.map(str::to_owned),
    }
}
fn conflict(message: impl Into<String>, id: Option<&str>) -> LegacyCompositionError {
    failure("MetamapCompositionError", message, id)
}

/// The native compatibility parser first checks grammar, duplicates, Unicode,
/// values and bounds. This visitor only retains member order for the original
/// stable-sort equivalence, including locale-equal but distinct Unicode keys.
#[derive(Debug)]
enum OrderedJson {
    Null,
    Bool(bool),
    Number(f64),
    String(String),
    Array(Vec<Self>),
    Object(Vec<(String, Self)>),
}
impl<'de> Deserialize<'de> for OrderedJson {
    fn deserialize<D: serde::Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        struct OrderedVisitor;
        impl<'de> Visitor<'de> for OrderedVisitor {
            type Value = OrderedJson;
            fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
                f.write_str("ordered JSON data")
            }
            fn visit_unit<E>(self) -> Result<Self::Value, E> {
                Ok(OrderedJson::Null)
            }
            fn visit_bool<E>(self, v: bool) -> Result<Self::Value, E> {
                Ok(OrderedJson::Bool(v))
            }
            fn visit_i64<E>(self, v: i64) -> Result<Self::Value, E> {
                Ok(OrderedJson::Number(v as f64))
            }
            fn visit_u64<E>(self, v: u64) -> Result<Self::Value, E> {
                Ok(OrderedJson::Number(v as f64))
            }
            fn visit_f64<E>(self, v: f64) -> Result<Self::Value, E> {
                Ok(OrderedJson::Number(v))
            }
            fn visit_str<E: serde::de::Error>(self, v: &str) -> Result<Self::Value, E> {
                Ok(OrderedJson::String(v.into()))
            }
            fn visit_string<E>(self, v: String) -> Result<Self::Value, E> {
                Ok(OrderedJson::String(v))
            }
            fn visit_seq<A: SeqAccess<'de>>(self, mut seq: A) -> Result<Self::Value, A::Error> {
                let mut values = Vec::new();
                while let Some(value) = seq.next_element()? {
                    values.push(value);
                }
                Ok(OrderedJson::Array(values))
            }
            fn visit_map<A: MapAccess<'de>>(self, mut map: A) -> Result<Self::Value, A::Error> {
                let mut values = Vec::new();
                while let Some(value) = map.next_entry()? {
                    values.push(value);
                }
                Ok(OrderedJson::Object(values))
            }
        }
        deserializer.deserialize_any(OrderedVisitor)
    }
}
impl OrderedJson {
    fn get(&self, key: &str) -> Option<&Self> {
        if let Self::Object(items) = self {
            items.iter().find(|(k, _)| k == key).map(|(_, v)| v)
        } else {
            None
        }
    }
    fn string(&self) -> Option<&str> {
        if let Self::String(text) = self {
            Some(text)
        } else {
            None
        }
    }
    fn array(&self) -> Option<&[Self]> {
        if let Self::Array(items) = self {
            Some(items)
        } else {
            None
        }
    }
    fn js_text(&self) -> String {
        match self {
            Self::Null => "null".into(),
            Self::Bool(v) => v.to_string(),
            Self::String(v) => v.clone(),
            Self::Object(_) => "[object Object]".into(),
            Self::Number(v) => String::from_utf8(
                patamaps_contracts::canonical_bytes(&json!(v)).expect("finite source number"),
            )
            .expect("canonical UTF-8"),
            Self::Array(items) => items
                .iter()
                .map(|v| {
                    if matches!(v, Self::Null) {
                        String::new()
                    } else {
                        v.js_text()
                    }
                })
                .collect::<Vec<_>>()
                .join(","),
        }
    }
}
fn property_text(value: &OrderedJson, key: &str) -> String {
    value
        .get(key)
        .map(OrderedJson::js_text)
        .unwrap_or_else(|| "undefined".into())
}
fn identifier(value: &OrderedJson) -> Result<&str, LegacyCompositionError> {
    value
        .get("id")
        .and_then(OrderedJson::string)
        .ok_or_else(|| {
            failure(
                "TypeError",
                "Legacy composition requires string identifiers",
                None,
            )
        })
}
fn integer_key(key: &str) -> Option<u32> {
    let value = key.parse::<u32>().ok()?;
    (value < u32::MAX && value.to_string() == key).then_some(value)
}
fn key_order(left: &str, right: &str, collator: &CollatorBorrowed<'_>) -> Ordering {
    // Object.fromEntries/JSON.stringify enumerate integer-index keys first.
    match (integer_key(left), integer_key(right)) {
        (Some(a), Some(b)) => a.cmp(&b),
        (Some(_), None) => Ordering::Less,
        (None, Some(_)) => Ordering::Greater,
        (None, None) => collator.compare(left, right),
    }
}
fn equivalent(left: &OrderedJson, right: &OrderedJson, collator: &CollatorBorrowed<'_>) -> bool {
    match (left, right) {
        (OrderedJson::Null, OrderedJson::Null) => true,
        (OrderedJson::Bool(a), OrderedJson::Bool(b)) => a == b,
        (OrderedJson::Number(a), OrderedJson::Number(b)) => a == b,
        (OrderedJson::String(a), OrderedJson::String(b)) => a == b,
        (OrderedJson::Array(a), OrderedJson::Array(b)) => {
            a.len() == b.len() && a.iter().zip(b).all(|(a, b)| equivalent(a, b, collator))
        }
        (OrderedJson::Object(a), OrderedJson::Object(b)) => {
            if a.len() != b.len() {
                return false;
            }
            let mut a = a.iter().collect::<Vec<_>>();
            let mut b = b.iter().collect::<Vec<_>>();
            // Stable sorting is intentional: collation equality preserves the
            // input position of different keys, as Array.sort does.
            a.sort_by(|a, b| key_order(&a.0, &b.0, collator));
            b.sort_by(|a, b| key_order(&a.0, &b.0, collator));
            a.iter()
                .zip(b)
                .all(|(a, b)| a.0 == b.0 && equivalent(&a.1, &b.1, collator))
        }
        _ => false,
    }
}
fn list<'a>(
    document: &'a OrderedJson,
    field: &str,
) -> Result<&'a [OrderedJson], LegacyCompositionError> {
    document
        .get(field)
        .and_then(OrderedJson::array)
        .ok_or_else(|| {
            failure(
                "TypeError",
                "select is not a function or its return value is not iterable",
                None,
            )
        })
}
fn selected(
    documents: &[OrderedJson],
    field: &str,
    kind: &str,
    collator: &CollatorBorrowed<'_>,
) -> Result<Vec<Value>, LegacyCompositionError> {
    let mut keys = HashMap::new();
    let mut items = Vec::new();
    let mut handles = Vec::new();
    for (di, document) in documents.iter().enumerate() {
        let values = if field == "relationPacks"
            && document
                .get(field)
                .is_none_or(|v| matches!(v, OrderedJson::Null))
        {
            &[][..]
        } else {
            list(document, field)?
        };
        for (ii, item) in values.iter().enumerate() {
            let id = identifier(item)?;
            if let Some(&slot) = keys.get(id) {
                let existing: &OrderedJson = items[slot];
                if field == "relationPacks"
                    && !equivalent(
                        existing.get("version").unwrap_or(&OrderedJson::Null),
                        item.get("version").unwrap_or(&OrderedJson::Null),
                        collator,
                    )
                {
                    return Err(conflict(
                        format!(
                            "Relation pack {id} has incompatible versions {} and {}",
                            property_text(existing, "version"),
                            property_text(item, "version")
                        ),
                        Some(id),
                    ));
                }
                if !equivalent(existing, item, collator) {
                    return Err(conflict(
                        if field == "relationPacks" {
                            format!(
                                "Relation pack {id}@{} has conflicting references",
                                property_text(item, "version")
                            )
                        } else {
                            format!("Conflicting {kind} definition for {id}")
                        },
                        Some(id),
                    ));
                }
            } else {
                keys.insert(id, items.len());
                items.push(item);
                handles.push(json!({"document":SafeInteger::new(di as u64).expect("bounded index"),"item":SafeInteger::new(ii as u64).expect("bounded index")}));
            }
        }
    }
    Ok(handles)
}

pub fn compose_legacy_documents(
    request: LegacyCompositionRequest,
) -> Result<Value, LegacyCompositionError> {
    if request.documents.is_empty() {
        return Err(conflict("At least one metamap shard is required", None));
    }
    let mut documents = Vec::new();
    for raw in &request.documents {
        parse_value_with_limits(raw.as_bytes(), COMPATIBILITY_JSON_LIMITS)
            .map_err(|e| failure("Error", e.to_string(), None))?;
        let mut de = serde_json::Deserializer::from_str(raw);
        de.disable_recursion_limit();
        let ordered =
            OrderedJson::deserialize(&mut de).map_err(|e| failure("Error", e.to_string(), None))?;
        documents.push(ordered);
    }
    let mut ids = HashSet::new();
    for document in &documents {
        if document.get("schemaVersion").and_then(OrderedJson::string) != Some("2.0.0") {
            return Err(conflict(
                format!(
                    "Cannot compose {}: unsupported schema {}",
                    property_text(document, "id"),
                    property_text(document, "schemaVersion")
                ),
                document.get("id").and_then(OrderedJson::string),
            ));
        }
        let id = identifier(document)?;
        if !ids.insert(id) {
            return Err(conflict(format!("Duplicate shard id {id}"), Some(id)));
        }
    }
    let prefs = CollatorPreferences::from_locale_strict(
        &request
            .locale
            .parse()
            .map_err(|_| failure("Error", "Invalid composition locale", None))?,
    )
    .map_err(|_| failure("Error", "Unsupported composition locale preferences", None))?;
    let collator = Collator::try_new(prefs, Default::default())
        .map_err(|e| failure("Error", e.to_string(), None))?;
    let mut header = json!({"$schema":"./schemas/metamap-graph.schema.json","schemaVersion":"2.0.0","metadata":{"composedFrom":documents.iter().map(|d|identifier(d).expect("checked string id")).collect::<Vec<_>>()}});
    for field in ["id", "namespace", "label", "revision"] {
        if let Some(value) = request.options.get(field) {
            header[field] = value.clone();
        }
    }
    Ok(
        json!({"header":header,"relationPacks":selected(&documents,"relationPacks","relation pack",&collator)?,"entities":selected(&documents,"entities","entity",&collator)?,"mappings":selected(&documents,"mappings","mapping",&collator)?,"authorities":selected(&documents,"authorities","authority",&collator)?}),
    )
}
