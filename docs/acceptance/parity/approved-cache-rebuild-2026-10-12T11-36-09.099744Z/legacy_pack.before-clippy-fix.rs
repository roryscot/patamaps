//! Preserve legacy pack data and its address while interpreting its versioned
//! portable schema. An imported view is not a checked or admitted generation.
use jsonschema::error::ValidationErrorKind;
use patamaps_contracts::{
    COMPATIBILITY_JSON_LIMITS, LegacyPackJson, RelationPack, byte_digest, canonical_bytes,
    canonical_digest,
};
use serde::Serialize;
use serde_json::Value;
use std::sync::OnceLock;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LegacyPackIssue {
    pub path: String,
    pub schema_path: String,
    pub message: String,
}

#[derive(Debug, thiserror::Error, Serialize)]
#[serde(rename_all = "camelCase")]
#[error("{message}")]
pub struct LegacyRelationPackError {
    pub code: String,
    pub message: String,
    pub issues: Vec<LegacyPackIssue>,
    #[serde(rename = "source", skip_serializing_if = "Option::is_none")]
    pub source_record: Option<LegacyPackSourceRecord>,
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
                }).collect(),
                source_record: Some(self.source_record()),
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
    schema(executable)
        .iter_errors(document)
        .map(|error| {
            let message = match error.kind() {
                ValidationErrorKind::AdditionalProperties { unexpected } => {
                    format!(
                        "must NOT have additional properties: {}",
                        unexpected.join(", ")
                    )
                }
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
                _ => error.to_string(),
            };
            LegacyPackIssue {
                path: error.instance_path().to_string(),
                schema_path: error.schema_path().to_string(),
                message,
            }
        })
        .collect()
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
