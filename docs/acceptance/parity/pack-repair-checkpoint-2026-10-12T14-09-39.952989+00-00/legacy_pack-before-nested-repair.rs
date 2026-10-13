//! Preserve legacy pack data and its address while interpreting its versioned
//! portable schema. An imported view is not a checked or admitted generation.
use jsonschema::error::{TypeKind, ValidationErrorKind};
use patamaps_contracts::{
    COMPATIBILITY_JSON_LIMITS, LegacyPackJson, RelationPack, byte_digest, canonical_bytes,
    canonical_digest,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::sync::OnceLock;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LegacyPackIssue {
    pub path: String,
    pub schema_path: String,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub additional_property: Option<String>,
}

#[derive(Debug, thiserror::Error, Serialize)]
#[serde(rename_all = "camelCase")]
#[error("{message}")]
pub struct LegacyRelationPackError {
    pub code: String,
    pub message: String,
    pub issues: Vec<LegacyPackIssue>,
    #[serde(rename = "source", skip_serializing_if = "Option::is_none")]
    pub source_record: Option<Box<LegacyPackSourceRecord>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub original_document_digest: Option<String>,
}

fn refuse(code: &str, message: impl Into<String>) -> LegacyRelationPackError {
    LegacyRelationPackError {
        code: code.into(),
        message: message.into(),
        issues: Vec::new(),
        source_record: None,
        original_document_digest: None,
    }
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LegacyPackSourceRecord {
    pub byte_digest: String,
    pub byte_length: usize,
    pub utf8_replacement_occurred: bool,
    pub duplicate_property_policy: String,
}

/// Shape-validated original JSON text. Unlike a native DTO, this can retain
/// legacy UTF-16 escapes and duplicate properties without changing their value.
#[derive(Debug, Clone)]
pub struct ParsedLegacyRelationPack {
    json: LegacyPackJson,
    digest: String,
}

impl ParsedLegacyRelationPack {
    pub fn parse(bytes: Vec<u8>) -> Result<Self, LegacyRelationPackError> {
        let json = LegacyPackJson::parse(bytes, COMPATIBILITY_JSON_LIMITS).map_err(|error| {
            let diagnostic = error.json_diagnostic(COMPATIBILITY_JSON_LIMITS);
            refuse(diagnostic.code, diagnostic.message)
        })?;
        let issues = schema_issues(json.schema_projection(), json.executable());
        if !issues.is_empty() {
            return Err(schema_error(issues));
        }
        let bytes = json
            .portable_digest_bytes()
            .map_err(|error| refuse("INVALID_CANONICAL_VALUE", error.to_string()))?;
        Ok(Self {
            json,
            digest: byte_digest(&bytes),
        })
    }

    pub fn document_json(&self) -> &str {
        self.json.decoded_text()
    }

    pub fn original_digest(&self) -> &str {
        &self.digest
    }

    pub fn source_bytes(&self) -> &[u8] {
        self.json.source_bytes()
    }

    pub fn source_record(&self) -> LegacyPackSourceRecord {
        LegacyPackSourceRecord {
            byte_digest: self.json.source_byte_digest(),
            byte_length: self.source_bytes().len(),
            utf8_replacement_occurred: self.json.utf8_replacement_occurred(),
            duplicate_property_policy: if self.json.executable() {
                "reject-decoded-duplicates"
            } else {
                "last-property-wins"
            }
            .into(),
        }
    }

    pub fn import_native_view(
        &self,
    ) -> Result<ImportedLegacyRelationPack, LegacyRelationPackError> {
        let paths = self.json.unpaired_paths();
        if !paths.is_empty() {
            return Err(LegacyRelationPackError {
                code: "LEGACY_NATIVE_UTF16".into(),
                message: "The original portable pack is valid but these UTF-16 strings cannot be represented by the native scalar-Unicode view".into(),
                issues: paths.into_iter().map(|path| LegacyPackIssue {
                    path,
                    schema_path: String::new(),
                    message: "Contains an unpaired UTF-16 unit; original data and address are preserved".into(),
                    additional_property: None,
                }).collect(),
                source_record: Some(Box::new(self.source_record())),
                original_document_digest: Some(self.digest.clone()),
            });
        }
        let document = self
            .json
            .native_value()
            .map_err(|error| refuse("LEGACY_PACK_VIEW", error.to_string()))?;
        let mut imported = import_legacy_relation_pack(document)?;
        if imported.original_digest() != self.original_digest() {
            return Err(refuse(
                "LEGACY_PACK_VIEW",
                "The native interpretation changed the original document's address",
            ));
        }
        imported.report.source = Some(self.source_record());
        imported.source_bytes = Some(self.source_bytes().to_vec());
        Ok(imported)
    }
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LegacyPackChange {
    pub operation: String,
    pub path: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub before: Option<Value>,
    pub after: Value,
    pub reason: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LegacyPackPendingCheck {
    pub path: String,
    pub code: String,
    pub message: String,
}

/// Addresses describe the original document and the new internal view
/// separately. Shape validity alone does not establish executable-law validity.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LegacyPackImportReport {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source: Option<LegacyPackSourceRecord>,
    pub source_schema_version: String,
    pub original_document_digest: String,
    pub original_digest_convention: String,
    pub native_view_digest: String,
    pub native_view: RelationPack,
    pub changes: Vec<LegacyPackChange>,
    pub discarded_paths: Vec<String>,
    pub pending_checks: Vec<LegacyPackPendingCheck>,
    pub registry_validated: bool,
    pub admitted: bool,
}

/// The raw document remains available under its original schema and digest.
/// Fields are private so an unchecked view cannot overwrite its source binding.
#[derive(Debug, Clone)]
pub struct ImportedLegacyRelationPack {
    original: Value,
    report: LegacyPackImportReport,
    source_bytes: Option<Vec<u8>>,
}

impl ImportedLegacyRelationPack {
    pub fn source_bytes(&self) -> Option<&[u8]> {
        self.source_bytes.as_deref()
    }
    pub fn original_document(&self) -> &Value {
        &self.original
    }
    pub fn native_view(&self) -> &RelationPack {
        &self.report.native_view
    }
    pub fn original_digest(&self) -> &str {
        &self.report.original_document_digest
    }
    pub fn report(&self) -> &LegacyPackImportReport {
        &self.report
    }
}

fn schema(executable: bool) -> &'static jsonschema::Validator {
    static LEGACY: OnceLock<jsonschema::Validator> = OnceLock::new();
    static EXECUTABLE: OnceLock<jsonschema::Validator> = OnceLock::new();
    let slot = if executable { &EXECUTABLE } else { &LEGACY };
    slot.get_or_init(|| {
        let raw = if executable {
            include_bytes!("../../../fixtures/reference/schemas/relation-pack-v2.schema.json")
                .as_slice()
        } else {
            include_bytes!("../../../fixtures/reference/schemas/relation-pack.schema.json")
                .as_slice()
        };
        let schema: Value = serde_json::from_slice(raw).expect("preserved relation-pack schema");
        // This is the same validator used for native scientific configuration.
        // No schema is fetched, re-authored or relaxed during import.
        jsonschema::options()
            .with_draft(jsonschema::Draft::Draft202012)
            .should_validate_formats(true)
            .with_format("uri-reference", |value| {
                uri_reference().is_valid(&Value::String(value.to_owned()))
            })
            .build(&schema)
            .expect("preserved relation-pack schema compiles")
    })
}

// The pinned AJV format includes URI characters its separate standards parser
// might reject (for example quoted relative references). Preserve that exact
// format grammar instead of substituting the Rust library's built-in format.
fn uri_reference() -> &'static jsonschema::Validator {
    static URI: OnceLock<jsonschema::Validator> = OnceLock::new();
    URI.get_or_init(|| {
        let data: Value = serde_json::from_str(include_str!("legacy_uri_reference.json"))
            .expect("preserved URI format provenance");
        jsonschema::options()
            .with_draft(jsonschema::Draft::Draft202012)
            .build(&serde_json::json!({"type":"string", "pattern":data["nativePattern"]}))
            .expect("preserved URI format pattern compiles")
    })
}

fn schema_issues(document: &Value, executable: bool) -> Vec<LegacyPackIssue> {
    let mut issues = schema(executable)
        .iter_errors(document)
        .flat_map(|error| {
            let message = match error.kind() {
                ValidationErrorKind::AdditionalProperties { .. } => {
                    "must NOT have additional properties".into()
                }
                ValidationErrorKind::Type {
                    kind: TypeKind::Single(kind),
                } => format!("must be {kind}"),
                ValidationErrorKind::Required { property } => {
                    let property = property.as_str().expect("required schema property name");
                    format!("must have required property '{property}'")
                }
                ValidationErrorKind::Constant { .. } => "must be equal to constant".into(),
                ValidationErrorKind::Enum { .. } => {
                    "must be equal to one of the allowed values".into()
                }
                ValidationErrorKind::MinLength { limit } => {
                    format!("must NOT have fewer than {limit} characters")
                }
                ValidationErrorKind::MinItems { limit } => {
                    format!("must NOT have fewer than {limit} items")
                }
                ValidationErrorKind::MaxItems { limit } => {
                    format!("must NOT have more than {limit} items")
                }
                ValidationErrorKind::Pattern { pattern } => {
                    format!("must match pattern \"{pattern}\"")
                }
                ValidationErrorKind::Format { format } => {
                    format!("must match format \"{format}\"")
                }
                ValidationErrorKind::UniqueItems => {
                    let path = error.instance_path().to_string();
                    // The pinned pack schemas give these arrays string items;
                    // AJV skips other types in its optimized uniqueness loop.
                    let string_items = ["/sourceKinds", "/targetKinds", "/composesWith"]
                        .iter()
                        .any(|suffix| path.ends_with(suffix));
                    let Some((j, i)) = duplicate_items(
                        document
                            .pointer(&path)
                            .and_then(Value::as_array)
                            .expect("array uniqueness error"),
                        string_items,
                    ) else {
                        return Vec::new();
                    };
                    format!("must NOT have duplicate items (items ## {j} and {i} are identical)")
                }
                _ => error.to_string(),
            };
            let issue = LegacyPackIssue {
                path: error.instance_path().to_string(),
                schema_path: error.schema_path().to_string(),
                message,
                additional_property: None,
            };
            match error.kind() {
                // Preserve the exact unknown fields separately from AJV's
                // observable wording, with one issue per unknown property.
                ValidationErrorKind::AdditionalProperties { unexpected } => unexpected
                    .iter()
                    .map(|property| LegacyPackIssue {
                        additional_property: Some(property.clone()),
                        ..issue.clone()
                    })
                    .collect::<Vec<_>>(),
                _ => vec![issue],
            }
        })
        .collect::<Vec<_>>();
    let ordering = schema_ordering(executable);
    issues.sort_by_cached_key(|issue| ordering.issue_order(issue));
    issues
}

// Adapt diagnostic order without replacing schema validation. Read property
// declaration order from the preserved bytes; Value itself sorts object keys.
struct OrderedSchemaObject(Vec<(String, Box<serde_json::value::RawValue>)>);
impl<'de> Deserialize<'de> for OrderedSchemaObject {
    fn deserialize<D: serde::Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        struct ObjectVisitor;
        impl<'de> serde::de::Visitor<'de> for ObjectVisitor {
            type Value = OrderedSchemaObject;
            fn expecting(&self, formatter: &mut std::fmt::Formatter) -> std::fmt::Result {
                formatter.write_str("a preserved schema object")
            }
            fn visit_map<A: serde::de::MapAccess<'de>>(
                self,
                mut map: A,
            ) -> Result<Self::Value, A::Error> {
                let mut entries = Vec::new();
                while let Some(entry) = map.next_entry()? {
                    entries.push(entry);
                }
                Ok(OrderedSchemaObject(entries))
            }
        }
        deserializer.deserialize_map(ObjectVisitor)
    }
}

struct SchemaOrdering {
    schema: Value,
    properties: std::collections::HashMap<String, Vec<String>>,
}

impl SchemaOrdering {
    fn collect_properties(&mut self, text: &str, path: &str) {
        match text.trim_start().as_bytes().first() {
            Some(b'{') => {
                let object: OrderedSchemaObject =
                    serde_json::from_str(text).expect("preserved schema object");
                for (name, value) in object.0 {
                    if name == "properties" {
                        let properties: OrderedSchemaObject =
                            serde_json::from_str(value.get()).expect("preserved properties");
                        self.properties.insert(
                            path.to_owned(),
                            properties.0.into_iter().map(|(key, _)| key).collect(),
                        );
                    }
                    let name = name.replace('~', "~0").replace('/', "~1");
                    self.collect_properties(value.get(), &format!("{path}/{name}"));
                }
            }
            Some(b'[') => {
                let entries: Vec<Box<serde_json::value::RawValue>> =
                    serde_json::from_str(text).expect("preserved schema array");
                for (index, entry) in entries.into_iter().enumerate() {
                    self.collect_properties(entry.get(), &format!("{path}/{index}"));
                }
            }
            _ => {}
        }
    }

    fn issue_order(&self, issue: &LegacyPackIssue) -> Vec<usize> {
        let mut order = Vec::new();
        let mut schema = &self.schema;
        let mut path = String::new();
        for token in issue.path.split('/').skip(1) {
            while let Some(reference) = schema.get("$ref").and_then(Value::as_str) {
                path = reference
                    .strip_prefix('#')
                    .expect("preserved local schema reference")
                    .to_owned();
                schema = self
                    .schema
                    .pointer(&path)
                    .expect("preserved reference target");
            }
            let name = token.replace("~1", "/").replace("~0", "~");
            if let Some(properties) = schema.get("properties") {
                let rank = self
                    .properties
                    .get(&path)
                    .and_then(|keys| keys.iter().position(|key| key == &name))
                    .unwrap_or(usize::MAX);
                order.extend([3, rank]);
                schema = properties.get(&name).unwrap_or(&Value::Null);
                path.push_str(&format!("/properties/{token}"));
            } else if let Some(items) = schema.get("items") {
                order.extend([3, name.parse().unwrap_or(usize::MAX)]);
                schema = items;
                path.push_str("/items");
            } else {
                order.extend([3, usize::MAX]);
                schema = &Value::Null;
            }
        }
        while let Some(reference) = schema.get("$ref").and_then(Value::as_str) {
            path = reference
                .strip_prefix('#')
                .expect("preserved local schema reference")
                .to_owned();
            schema = self
                .schema
                .pointer(&path)
                .expect("preserved reference target");
        }
        let keyword = issue.schema_path.rsplit('/').next().unwrap_or("");
        let rank = match keyword {
            "type" | "const" | "enum" => 0,
            "required" => 1,
            "additionalProperties" => 2,
            "uniqueItems" => 4,
            _ => 1,
        };
        order.push(rank);
        if keyword == "required" {
            let property = issue
                .message
                .strip_prefix("must have required property '")
                .and_then(|name| name.strip_suffix('\''));
            order.push(
                schema
                    .get("required")
                    .and_then(Value::as_array)
                    .and_then(|required| required.iter().position(|item| item.as_str() == property))
                    .unwrap_or(usize::MAX),
            );
        }
        order
    }
}

fn schema_ordering(executable: bool) -> &'static SchemaOrdering {
    static PORTABLE: OnceLock<SchemaOrdering> = OnceLock::new();
    static EXECUTABLE: OnceLock<SchemaOrdering> = OnceLock::new();
    let slot = if executable { &EXECUTABLE } else { &PORTABLE };
    slot.get_or_init(|| {
        let text = if executable {
            include_str!("../../../fixtures/reference/schemas/relation-pack-v2.schema.json")
        } else {
            include_str!("../../../fixtures/reference/schemas/relation-pack.schema.json")
        };
        let mut ordering = SchemaOrdering {
            schema: serde_json::from_str(text).expect("preserved schema"),
            properties: std::collections::HashMap::new(),
        };
        ordering.collect_properties(text, "");
        ordering
    })
}

// Follow the pinned AJV uniqueItems loop's pair selection. Diagnostic pair
// order is observable even when both validators reject the same array.
fn duplicate_items(items: &[Value], string_items: bool) -> Option<(usize, usize)> {
    if string_items {
        let mut indices = std::collections::HashMap::new();
        for (i, item) in items.iter().enumerate().rev() {
            let Some(item) = item.as_str() else { continue };
            // AJV writes numeric indices into an ordinary JS object. Its
            // __proto__ setter ignores those writes. Retain the observed
            // legacy parsing behavior without changing native admission.
            if item == "__proto__" {
                continue;
            }
            if let Some(j) = indices.insert(item, i) {
                return Some((j, i));
            }
        }
    } else {
        let mut indices = std::collections::HashMap::new();
        let mut duplicate = None;
        for (i, item) in items.iter().enumerate() {
            if let Some(j) = indices.insert(item, i) {
                // AJV's reverse nested loop chooses the greatest repeated i,
                // then its nearest preceding j. Indexed equality preserves
                // that pair without repeating the quadratic search.
                duplicate = Some((j, i));
            }
        }
        return duplicate;
    }
    None
}

fn schema_error(issues: Vec<LegacyPackIssue>) -> LegacyRelationPackError {
    let message = format!(
        "Relation pack does not match the portable schema: {}",
        issues
            .iter()
            .map(|issue| format!(
                "{} {}",
                if issue.path.is_empty() {
                    "$"
                } else {
                    &issue.path
                },
                issue.message
            ))
            .collect::<Vec<_>>()
            .join("; ")
    );
    LegacyRelationPackError {
        code: "LEGACY_PACK_SCHEMA".into(),
        message,
        issues,
        source_record: None,
        original_document_digest: None,
    }
}

fn check_bounds(document: &Value) -> Result<(), LegacyRelationPackError> {
    let mut stack = vec![(document, 0usize)];
    let (mut nodes, mut text_bytes) = (0usize, 0usize);
    while let Some((value, depth)) = stack.pop() {
        nodes = nodes.saturating_add(1);
        match value {
            Value::Object(object) => {
                for (key, child) in object {
                    text_bytes = text_bytes.saturating_add(key.len());
                    stack.push((child, depth + 1));
                }
            }
            Value::Array(array) => stack.extend(array.iter().map(|child| (child, depth + 1))),
            Value::String(text) => text_bytes = text_bytes.saturating_add(text.len()),
            _ => {}
        }
        if depth > COMPATIBILITY_JSON_LIMITS.max_depth
            || nodes > COMPATIBILITY_JSON_LIMITS.max_values
            || text_bytes > COMPATIBILITY_JSON_LIMITS.max_bytes
        {
            return Err(refuse(
                "LEGACY_PACK_RESOURCE_LIMIT",
                "Legacy pack exceeds the declared compatibility JSON bounds",
            ));
        }
    }
    Ok(())
}

/// Version-dispatched portable-shape import. Caller-owned data is never changed.
/// Unsupported mandatory fields are rejected rather than dropped. Executable
/// law checks occur separately with the exact imported dependency registry.
pub fn import_legacy_relation_pack(
    document: Value,
) -> Result<ImportedLegacyRelationPack, LegacyRelationPackError> {
    check_bounds(&document)?;
    let executable = document.get("schemaVersion").and_then(Value::as_str) == Some("2.0.0");
    let mut original_bytes = canonical_bytes(&document)
        .map_err(|error| refuse("INVALID_CANONICAL_VALUE", error.to_string()))?;
    if original_bytes.len() > COMPATIBILITY_JSON_LIMITS.max_bytes {
        return Err(refuse(
            "LEGACY_PACK_RESOURCE_LIMIT",
            "Encoded legacy pack exceeds the declared compatibility JSON byte bound",
        ));
    }
    let issues = schema_issues(&document, executable);
    if !issues.is_empty() {
        return Err(schema_error(issues));
    }
    // Schema 1.0 is closed. Every accepted object key is a fixed schema key;
    // those keys have the same order under MetaMap's locale comparison and JCS.
    // The legacy convention hashes compact stable JSON followed by one LF.
    // This is not a digest implementation for arbitrary unchecked JS objects.
    if !executable {
        original_bytes.push(b'\n');
    }
    let original_document_digest = byte_digest(&original_bytes);
    let source_schema_version = document["schemaVersion"]
        .as_str()
        .expect("portable schema version")
        .to_owned();
    let mut mapped = document.clone();
    let object = mapped.as_object_mut().expect("portable schema object");
    object.insert("schemaVersion".into(), "0.1.0".into());
    object.insert("documentType".into(), "relation-pack".into());
    let view: RelationPack = serde_json::from_value(mapped.clone())
        .map_err(|error| refuse("LEGACY_PACK_VIEW", error.to_string()))?;
    let roundtrip = serde_json::to_value(&view)
        .map_err(|error| refuse("LEGACY_PACK_VIEW", error.to_string()))?;
    if roundtrip != mapped {
        return Err(refuse(
            "LEGACY_PACK_VIEW",
            "The native view did not preserve all non-envelope fields",
        ));
    }
    let native_view_digest = canonical_digest(&view)
        .map_err(|error| refuse("INVALID_CANONICAL_VALUE", error.to_string()))?;
    let mut pending_checks = vec![LegacyPackPendingCheck {
        path: "".into(),
        code: "NATIVE_PACK_VALIDATION_REQUIRED".into(),
        message: "The internal view still requires modern field, law and resource checks before native admission".into(),
    }];
    for (index, relation) in view.relations.iter().enumerate() {
        for (field, values) in [
            ("sourceKinds", &relation.source_kinds),
            ("targetKinds", &relation.target_kinds),
            ("composesWith", &relation.composes_with),
        ] {
            if values.as_ref().is_some_and(|values| {
                values
                    .iter()
                    .filter(|value| value.as_str() == "__proto__")
                    .count()
                    > 1
            }) {
                pending_checks.push(LegacyPackPendingCheck {
                    path: format!("/relations/{index}/{field}"),
                    code: "LEGACY_VALIDATOR_UNIQUENESS_QUIRK".into(),
                    message: "The pinned legacy validator accepts repeated __proto__ items although its schema declares uniqueItems. The original data and address are retained; native admission requires its own validation".into(),
                });
            }
        }
        for (field, empty) in [
            (
                "sourceKinds",
                relation.source_kinds.as_ref().is_some_and(Vec::is_empty),
            ),
            (
                "targetKinds",
                relation.target_kinds.as_ref().is_some_and(Vec::is_empty),
            ),
            (
                "cardinalities",
                relation.cardinalities.as_ref().is_some_and(Vec::is_empty),
            ),
        ] {
            if empty {
                pending_checks.push(LegacyPackPendingCheck {
                    path: format!("/relations/{index}/{field}"),
                    code: "NATIVE_EMPTY_LIST_INCOMPATIBILITY".into(),
                    message: "The portable legacy schema permits this empty list; the modern native pack checker rejects it. Its original meaning has been preserved, not changed".into(),
                });
            }
        }
    }
    for index in 0..view.imports.as_ref().map_or(0, Vec::len) {
        pending_checks.push(LegacyPackPendingCheck {
            path: format!("/imports/{index}/digest"),
            code: "NATIVE_DEPENDENCY_ADDRESS_REQUIRED".into(),
            message: "This remains an exact original-document binding for legacy interpretation. Native compilation requires the separately validated migrated dependency's new address".into(),
        });
    }
    let report = LegacyPackImportReport {
        source: None,
        source_schema_version,
        original_document_digest,
        original_digest_convention: if executable {
            "rfc8785-jcs-sha256"
        } else {
            "metamap-stable-json-lf-sha256"
        }
        .into(),
        native_view_digest,
        native_view: view,
        changes: vec![
            LegacyPackChange {
                operation: "replace".into(),
                path: "/schemaVersion".into(),
                before: document.get("schemaVersion").cloned(),
                after: "0.1.0".into(),
                reason: "Interpret the preserved definitions with the native draft envelope".into(),
            },
            LegacyPackChange {
                operation: "add".into(),
                path: "/documentType".into(),
                before: None,
                after: "relation-pack".into(),
                reason: "Identify the native internal view's document type".into(),
            },
        ],
        discarded_paths: Vec::new(),
        pending_checks,
        registry_validated: false,
        admitted: false,
    };
    Ok(ImportedLegacyRelationPack {
        original: document,
        report,
        source_bytes: None,
    })
}
