//! Legacy shard composition selects retained source handles. It performs no
//! graph validation, admission, ownership evaluation or authorization.
use icu_collator::{Collator, CollatorBorrowed, CollatorPreferences};
use patamaps_contracts::{
    COMPATIBILITY_JSON_LIMITS, LegacyOrderedJson, SafeInteger, parse_value_with_limits,
};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::{HashMap, HashSet};

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

fn property_text(value: &LegacyOrderedJson, key: &str) -> String {
    value
        .get(key)
        .map(LegacyOrderedJson::js_text)
        .unwrap_or_else(|| "undefined".into())
}
fn identifier(value: &LegacyOrderedJson) -> Result<&str, LegacyCompositionError> {
    value
        .get("id")
        .and_then(LegacyOrderedJson::string)
        .ok_or_else(|| {
            failure(
                "TypeError",
                "Legacy composition requires string identifiers",
                None,
            )
        })
}
fn list<'a>(
    document: &'a LegacyOrderedJson,
    field: &str,
) -> Result<&'a [LegacyOrderedJson], LegacyCompositionError> {
    document
        .get(field)
        .and_then(LegacyOrderedJson::array)
        .ok_or_else(|| {
            failure(
                "TypeError",
                "select is not a function or its return value is not iterable",
                None,
            )
        })
}
pub(crate) fn selected(
    documents: &[LegacyOrderedJson],
    field: &str,
    kind: &str,
    collator: &CollatorBorrowed<'_>,
    read_only: bool,
) -> Result<Vec<Value>, LegacyCompositionError> {
    let equivalent =
        |a: &LegacyOrderedJson, b: &LegacyOrderedJson| -> Result<bool, LegacyCompositionError> {
            if read_only {
                let a = patamaps_contracts::LegacyReadOnlyJson::stable_bytes(a, collator)
                    .map_err(|e| failure("Error", e.to_string(), None))?;
                let b = patamaps_contracts::LegacyReadOnlyJson::stable_bytes(b, collator)
                    .map_err(|e| failure("Error", e.to_string(), None))?;
                Ok(a == b)
            } else {
                Ok(a.stable_equivalent(b, collator))
            }
        };
    let mut keys = HashMap::new();
    let mut items = Vec::new();
    let mut handles = Vec::new();
    for (di, document) in documents.iter().enumerate() {
        let values = if field == "relationPacks"
            && document
                .get(field)
                .is_none_or(|v| matches!(v, LegacyOrderedJson::Null))
        {
            &[][..]
        } else {
            list(document, field)?
        };
        for (ii, item) in values.iter().enumerate() {
            let id = identifier(item)?;
            if let Some(&slot) = keys.get(id) {
                let existing: &LegacyOrderedJson = items[slot];
                if field == "relationPacks"
                    && !equivalent(
                        existing.get("version").unwrap_or(&LegacyOrderedJson::Null),
                        item.get("version").unwrap_or(&LegacyOrderedJson::Null),
                    )?
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
                if !equivalent(existing, item)? {
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

pub(crate) fn validate_shards(
    documents: &[LegacyOrderedJson],
) -> Result<(), LegacyCompositionError> {
    let mut ids = HashSet::new();
    for document in documents {
        if document
            .get("schemaVersion")
            .and_then(LegacyOrderedJson::string)
            != Some("2.0.0")
        {
            return Err(conflict(
                format!(
                    "Cannot compose {}: unsupported schema {}",
                    property_text(document, "id"),
                    property_text(document, "schemaVersion")
                ),
                document.get("id").and_then(LegacyOrderedJson::string),
            ));
        }
        let id = identifier(document)?;
        if !ids.insert(id) {
            return Err(conflict(format!("Duplicate shard id {id}"), Some(id)));
        }
    }
    Ok(())
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
        let ordered = LegacyOrderedJson::deserialize(&mut de)
            .map_err(|e| failure("Error", e.to_string(), None))?;
        documents.push(ordered);
    }
    validate_shards(&documents)?;
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
        json!({"header":header,"relationPacks":selected(&documents,"relationPacks","relation pack",&collator, false)?,"entities":selected(&documents,"entities","entity",&collator, false)?,"mappings":selected(&documents,"mappings","mapping",&collator, false)?,"authorities":selected(&documents,"authorities","authority",&collator, false)?}),
    )
}
