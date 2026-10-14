//! Preserve legacy pack data and its address while interpreting its versioned
//! portable schema. An imported view is not a checked or admitted generation.
use jsonschema::error::{TypeKind, ValidationErrorKind};
use patamaps_contracts::{
    COMPATIBILITY_JSON_LIMITS, LegacyOrderedJson as J, LegacyPackJson, LegacyReadOnlyJson as Data,
    RelationPack, byte_digest, canonical_bytes, canonical_digest,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::{borrow::Cow, collections::HashSet, sync::OnceLock};

// The same schema engine can inspect legacy JS observations before their JSON
// projection erases NaN/infinity and array holes. These nodes are read-only;
// they never enter strict JSON parsing or native checked/admitted values.
struct LegacySchemaJson;
#[derive(Clone, Copy)]
struct LegacySchemaNode<'a> {
    value: &'a J,
    holes: &'a HashSet<usize>,
}
impl LegacySchemaNode<'_> {
    fn hole(&self) -> bool {
        self.holes
            .contains(&(std::ptr::from_ref(self.value) as usize))
    }
}
impl jsonschema::json::Json for LegacySchemaJson {
    type Node<'a> = LegacySchemaNode<'a>;
    type PreparedKey = String;
    type StringBuffer = String;
    fn prepare_key(key: &str) -> String {
        key.to_owned()
    }
    fn with_string_node<T>(
        buffer: &mut String,
        string: &str,
        f: impl FnOnce(Self::Node<'_>) -> T,
    ) -> T {
        buffer.clear();
        buffer.push_str(string);
        let value = J::String(buffer.clone());
        f(LegacySchemaNode {
            value: &value,
            holes: &HashSet::new(),
        })
    }
}
struct LegacySchemaNumber(f64);
impl jsonschema::json::JsonNumber for LegacySchemaNumber {
    fn as_u64(&self) -> Option<u64> {
        serde_json::Number::from_f64(self.0)?.as_u64()
    }
    fn as_i64(&self) -> Option<i64> {
        serde_json::Number::from_f64(self.0)?.as_i64()
    }
    fn as_f64(&self) -> Option<f64> {
        Some(self.0)
    }
    fn as_str(&self) -> Cow<'_, str> {
        Cow::Owned(self.0.to_string())
    }
    fn to_number(&self) -> Cow<'_, serde_json::Number> {
        Cow::Owned(serde_json::Number::from_f64(self.0).expect("finite schema number"))
    }
    fn is_integer(&self) -> bool {
        self.0.fract() == 0.0
    }
}
impl<'a> jsonschema::json::Node<'a, LegacySchemaJson> for LegacySchemaNode<'a> {
    type Object = Self;
    type Array = Self;
    type Number = LegacySchemaNumber;
    fn as_object(&self) -> Option<Self> {
        matches!(self.value, J::Object(_)).then_some(*self)
    }
    fn as_array(&self) -> Option<Self> {
        matches!(self.value, J::Array(_)).then_some(*self)
    }
    fn as_string(&self) -> Option<Cow<'a, str>> {
        self.value.string().map(Cow::Borrowed)
    }
    fn as_number(&self) -> Option<Self::Number> {
        match self.value {
            J::Number(v) if v.is_finite() && !self.hole() => Some(LegacySchemaNumber(*v)),
            _ => None,
        }
    }
    fn as_boolean(&self) -> Option<bool> {
        if let J::Bool(v) = self.value {
            Some(*v)
        } else {
            None
        }
    }
    fn is_null(&self) -> bool {
        matches!(self.value, J::Null) && !self.hole()
    }
    fn json_type(&self) -> jsonschema::JsonType {
        use jsonschema::JsonType as T;
        if self.hole() {
            return T::Number;
        }
        match self.value {
            J::Null => T::Null,
            J::Bool(_) => T::Boolean,
            J::Number(_) => T::Number,
            J::String(_) => T::String,
            J::Array(_) => T::Array,
            J::Object(_) => T::Object,
        }
    }
    fn equals_value(&self, expected: &Value) -> bool {
        if self.hole() {
            return false;
        }
        match self.value {
            J::Null => expected.is_null(),
            J::Bool(v) => expected.as_bool() == Some(*v),
            J::Number(v) => v.is_finite() && expected.as_f64() == Some(*v),
            J::String(v) => expected.as_str() == Some(v),
            J::Array(values) => expected.as_array().is_some_and(|other| {
                values.len() == other.len()
                    && values
                        .iter()
                        .zip(other)
                        .all(|(value, other)| Self { value, ..*self }.equals_value(other))
            }),
            J::Object(pairs) => expected.as_object().is_some_and(|other| {
                pairs.len() == other.len()
                    && pairs.iter().all(|(key, value)| {
                        other
                            .get(key)
                            .is_some_and(|other| Self { value, ..*self }.equals_value(other))
                    })
            }),
        }
    }
    fn to_value(&self) -> Cow<'a, Value> {
        Cow::Owned(Data::projected_value(self.value).expect("bounded read-only schema value"))
    }
    fn identity(&self) -> Option<jsonschema::json::NodeIdentity> {
        None
    }
}
impl<'a> jsonschema::json::Object<'a, LegacySchemaJson> for LegacySchemaNode<'a> {
    type Node = Self;
    type MemberName = &'a str;
    type MembersIter = std::vec::IntoIter<(&'a str, Self)>;
    fn len(&self) -> usize {
        if let J::Object(pairs) = self.value {
            pairs.len()
        } else {
            0
        }
    }
    fn get(&self, key: &String) -> Option<Self> {
        self.value.get(key).map(|value| Self { value, ..*self })
    }
    fn members(&self) -> Self::MembersIter {
        let J::Object(pairs) = self.value else {
            unreachable!()
        };
        pairs
            .iter()
            .map(|(key, value)| (key.as_str(), Self { value, ..*self }))
            .collect::<Vec<_>>()
            .into_iter()
    }
}
impl<'a> jsonschema::json::Array<'a, LegacySchemaJson> for LegacySchemaNode<'a> {
    type Node = Self;
    type ElementsIter = std::vec::IntoIter<Self>;
    fn len(&self) -> usize {
        self.value.array().map_or(0, <[J]>::len)
    }
    fn elements(&self) -> Self::ElementsIter {
        self.value
            .array()
            .expect("schema array")
            .iter()
            .map(|value| Self { value, ..*self })
            .collect::<Vec<_>>()
            .into_iter()
    }
    fn is_unique(&self) -> bool {
        // Typed fingerprints retain exceptional values without aliasing a user
        // object to an internal numeric marker. Signed zeros compare equally,
        // as they do in AJV's array uniqueness check.
        fn key(node: LegacySchemaNode<'_>) -> Value {
            if node.hole() {
                return serde_json::json!(["hole"]);
            }
            match node.value {
                J::Null => serde_json::json!(["null"]),
                J::Bool(v) => serde_json::json!(["boolean", v]),
                J::String(v) => serde_json::json!(["string", v]),
                J::Number(v) if v.is_nan() => serde_json::json!(["nan"]),
                J::Number(v) if v.is_infinite() => serde_json::json!([if v.is_sign_positive() {
                    "positive-infinity"
                } else {
                    "negative-infinity"
                }]),
                J::Number(v) => serde_json::json!(["number", if *v == 0.0 { 0.0 } else { *v }]),
                J::Array(values) => serde_json::json!([
                    "array",
                    values
                        .iter()
                        .map(|value| key(LegacySchemaNode { value, ..node }))
                        .collect::<Vec<_>>()
                ]),
                J::Object(pairs) => {
                    let mut values = pairs
                        .iter()
                        .map(|(name, value)| (name, key(LegacySchemaNode { value, ..node })))
                        .collect::<Vec<_>>();
                    values.sort_by(|a, b| a.0.cmp(b.0));
                    serde_json::json!(["object", values])
                }
            }
        }
        let mut seen = HashSet::new();
        self.value
            .array()
            .expect("schema array")
            .iter()
            .all(|value| {
                seen.insert(
                    serde_json::to_string(&key(Self { value, ..*self }))
                        .expect("schema equality key"),
                )
            })
    }
}

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
    #[serde(skip_serializing_if = "Option::is_none")]
    pub native_message: Option<Box<str>>,
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
        native_message: None,
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
            let mut refusal = refuse(diagnostic.code, diagnostic.message);
            refusal.native_message = Some(diagnostic.native_message.into_boxed_str());
            refusal
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
                native_message: None,
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

/// Pinned portable schemas share the legacy AJV diagnostic adapter. This
/// observes JSON shape only and conveys no checked or admitted capability.
pub struct LegacyPortableSchema {
    validator: jsonschema::Validator,
    legacy_validator: jsonschema::Validator<LegacySchemaJson>,
    ordering: SchemaOrdering,
}
impl LegacyPortableSchema {
    /// Bundle preserved cross-document references without network retrieval.
    /// The source schemas are unchanged; this ordered compiler input retains
    /// each resource's original property order for diagnostic reconstruction.
    pub(crate) fn with_resources(text: &str, resources: &[&str]) -> Self {
        let parse = |text: &str| {
            Data::parse(text, COMPATIBILITY_JSON_LIMITS)
                .expect("preserved schema resource")
                .value()
                .clone()
        };
        let mut root = parse(text);
        let mut documents = resources.iter().map(|text| parse(text)).collect::<Vec<_>>();
        let identities = documents
            .iter()
            .enumerate()
            .map(|(index, value)| {
                (
                    value
                        .get("$id")
                        .and_then(J::string)
                        .expect("preserved resource identity")
                        .to_owned(),
                    index,
                )
            })
            .collect::<std::collections::HashMap<_, _>>();
        fn rewrite(
            value: &mut J,
            owner: Option<usize>,
            identities: &std::collections::HashMap<String, usize>,
        ) {
            match value {
                J::Object(pairs) => {
                    pairs.retain(|(key, _)| key != "$id");
                    for (key, child) in pairs {
                        if key == "$ref" {
                            let J::String(reference) = child else {
                                panic!("preserved schema reference")
                            };
                            if reference.starts_with('#') {
                                if let Some(index) = owner {
                                    *reference = format!(
                                        "#/$defs/patamaps_source_schema_{index}{}",
                                        &reference[1..]
                                    );
                                }
                            } else {
                                let (base, fragment) =
                                    reference.split_once('#').unwrap_or((reference, ""));
                                let index = identities
                                    .get(base)
                                    .expect("every preserved schema dependency is supplied");
                                *reference =
                                    format!("#/$defs/patamaps_source_schema_{index}{fragment}");
                            }
                        } else {
                            rewrite(child, owner, identities);
                        }
                    }
                }
                J::Array(items) => {
                    for child in items {
                        rewrite(child, owner, identities);
                    }
                }
                _ => {}
            }
        }
        rewrite(&mut root, None, &identities);
        for (index, document) in documents.iter_mut().enumerate() {
            rewrite(document, Some(index), &identities);
        }
        let J::Object(root_pairs) = &mut root else {
            panic!("preserved schema object")
        };
        if !root_pairs.iter().any(|(key, _)| key == "$defs") {
            root_pairs.push(("$defs".into(), J::Object(Vec::new())));
        }
        let J::Object(definitions) = &mut root_pairs
            .iter_mut()
            .find(|(key, _)| key == "$defs")
            .expect("schema definitions")
            .1
        else {
            panic!("preserved definitions object")
        };
        for (index, document) in documents.into_iter().enumerate() {
            definitions.push((format!("patamaps_source_schema_{index}"), document));
        }
        Self::new(&crate::legacy_workspace::raw(&root).expect("ordered bundled schema"))
    }
    pub fn new(text: &str) -> Self {
        let mut ordering = SchemaOrdering {
            schema: serde_json::from_str(text).expect("preserved portable schema"),
            properties: std::collections::HashMap::new(),
        };
        ordering.collect_properties(text, "");
        let validator = jsonschema::options()
            .with_draft(jsonschema::Draft::Draft202012)
            .should_validate_formats(true)
            .with_format("uri-reference", |value| {
                uri_reference().is_valid(&Value::String(value.to_owned()))
            })
            .build(&ordering.schema)
            .expect("preserved portable schema compiles");
        let legacy_validator = jsonschema::options_for::<LegacySchemaJson>()
            .with_draft(jsonschema::Draft::Draft202012)
            .should_validate_formats(true)
            .with_format("uri-reference", |value| {
                uri_reference().is_valid(&Value::String(value.to_owned()))
            })
            .build(&ordering.schema)
            .expect("preserved read-only legacy schema compiles");
        Self {
            validator,
            legacy_validator,
            ordering,
        }
    }
    pub fn issues(&self, document: &Value) -> Vec<LegacyPackIssue> {
        let mut issues = Vec::new();
        for error in self.validator.iter_errors(document) {
            append_schema_issues(&error, document, &self.ordering, &mut issues);
        }
        issues.sort_by_cached_key(|error| {
            self.ordering
                .issue_order(&error.issue, &error.evaluation_path)
        });
        issues.into_iter().map(|error| error.issue).collect()
    }
    pub(crate) fn legacy_issues(
        &self,
        document: &J,
        holes: &HashSet<usize>,
    ) -> Vec<LegacyPackIssue> {
        let projected = Data::projected_value(document).expect("bounded read-only schema value");
        let mut issues = Vec::new();
        for error in self.legacy_validator.iter_errors(LegacySchemaNode {
            value: document,
            holes,
        }) {
            append_schema_issues(&error, &projected, &self.ordering, &mut issues);
        }
        issues.sort_by_cached_key(|error| {
            self.ordering
                .issue_order(&error.issue, &error.evaluation_path)
        });
        issues.into_iter().map(|error| error.issue).collect()
    }
}

struct SchemaIssue {
    issue: LegacyPackIssue,
    evaluation_path: String,
}

fn schema_issues(document: &Value, executable: bool) -> Vec<LegacyPackIssue> {
    let ordering = schema_ordering(executable);
    let mut issues = Vec::new();
    for error in schema(executable).iter_errors(document) {
        append_schema_issues(&error, document, ordering, &mut issues);
    }
    // jsonschema returns the selected conditional's failures. AJV also emits a
    // summary after those failures, before the law's ordinary property checks.
    if executable {
        let mut conditionals = std::collections::HashSet::new();
        let summaries = issues
            .iter()
            .filter_map(|error: &SchemaIssue| {
                let prefix = "/properties/laws/items/allOf/0/";
                let clause = error.evaluation_path.strip_prefix(prefix)?;
                let clause = if clause.starts_with("then/") {
                    "then"
                } else if clause.starts_with("else/") {
                    "else"
                } else {
                    return None;
                };
                let index = error.issue.path.strip_prefix("/laws/")?.split('/').next()?;
                if !conditionals.insert(index.to_owned()) {
                    return None;
                }
                Some(SchemaIssue {
                    issue: LegacyPackIssue {
                        path: format!("/laws/{index}"),
                        schema_path: format!("{prefix}if"),
                        message: format!("must match \"{clause}\" schema"),
                        additional_property: None,
                    },
                    evaluation_path: format!("{prefix}if"),
                })
            })
            .collect::<Vec<_>>();
        issues.extend(summaries);
    }
    issues.sort_by_cached_key(|error| ordering.issue_order(&error.issue, &error.evaluation_path));
    issues.into_iter().map(|error| error.issue).collect()
}

fn append_schema_issues(
    error: &jsonschema::ValidationError<'_>,
    document: &Value,
    ordering: &SchemaOrdering,
    issues: &mut Vec<SchemaIssue>,
) {
    let message = match error.kind() {
        ValidationErrorKind::AnyOf { context } => {
            for branch in context {
                for child in branch {
                    append_schema_issues(child, document, ordering, issues);
                }
            }
            "must match a schema in anyOf".into()
        }
        ValidationErrorKind::OneOfNotValid { context } => {
            for branch in context {
                for child in branch {
                    append_schema_issues(child, document, ordering, issues);
                }
            }
            "must match exactly one schema in oneOf".into()
        }
        ValidationErrorKind::OneOfMultipleValid { .. } => {
            "must match exactly one schema in oneOf".into()
        }
        ValidationErrorKind::Not { .. } => "must NOT be valid".into(),
        ValidationErrorKind::FalseSchema => "boolean schema is false".into(),
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
        ValidationErrorKind::Enum { .. } => "must be equal to one of the allowed values".into(),
        ValidationErrorKind::MinLength { limit } => {
            format!("must NOT have fewer than {limit} characters")
        }
        ValidationErrorKind::MinItems { limit } => {
            format!("must NOT have fewer than {limit} items")
        }
        ValidationErrorKind::MaxItems { limit } => format!("must NOT have more than {limit} items"),
        ValidationErrorKind::MinProperties { limit } => {
            format!("must NOT have fewer than {limit} properties")
        }
        ValidationErrorKind::MaxProperties { limit } => {
            format!("must NOT have more than {limit} properties")
        }
        ValidationErrorKind::Pattern { pattern } => format!("must match pattern \"{pattern}\""),
        ValidationErrorKind::Format { format } => format!("must match format \"{format}\""),
        ValidationErrorKind::UniqueItems => {
            // Inspect the preserved schema, including its referenced item type,
            // instead of assuming only particular field names use AJV's loop.
            let schema_path = error.schema_path().as_str();
            let parent = schema_path
                .strip_suffix("/uniqueItems")
                .expect("uniqueness keyword path");
            let string_items = ordering
                .schema
                .pointer(parent)
                .and_then(|schema| schema.get("items"))
                .and_then(|schema| schema.get("type"))
                .and_then(Value::as_str)
                == Some("string");
            let path = error.instance_path().to_string();
            let Some((j, i)) = duplicate_items(
                document
                    .pointer(&path)
                    .and_then(Value::as_array)
                    .expect("array uniqueness error"),
                string_items,
            ) else {
                return;
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
    let evaluation_path = error.evaluation_path().to_string();
    match error.kind() {
        ValidationErrorKind::AdditionalProperties { unexpected } => {
            for property in unexpected {
                issues.push(SchemaIssue {
                    issue: LegacyPackIssue {
                        additional_property: Some(property.clone()),
                        ..issue.clone()
                    },
                    evaluation_path: evaluation_path.clone(),
                });
            }
        }
        _ => issues.push(SchemaIssue {
            issue,
            evaluation_path,
        }),
    }
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

    fn issue_order(&self, issue: &LegacyPackIssue, evaluation_path: &str) -> Vec<usize> {
        let mut order = Vec::new();
        let mut schema = &self.schema;
        let mut path = String::new();
        let mut instance = issue.path.split('/').skip(1);
        let mut tokens = evaluation_path.split('/').skip(1);
        while let Some(token) = tokens.next() {
            match token {
                "$ref" => {
                    path = schema
                        .get("$ref")
                        .and_then(Value::as_str)
                        .and_then(|reference| reference.strip_prefix('#'))
                        .expect("preserved local schema reference")
                        .to_owned();
                    schema = self
                        .schema
                        .pointer(&path)
                        .expect("preserved reference target");
                }
                "properties" => {
                    let token = tokens.next().expect("schema property name");
                    let name = token.replace("~1", "/").replace("~0", "~");
                    let rank = self
                        .properties
                        .get(&path)
                        .and_then(|keys| keys.iter().position(|key| key == &name))
                        .unwrap_or(usize::MAX);
                    order.extend([40, rank]);
                    schema = &schema["properties"][&name];
                    path.push_str(&format!("/properties/{token}"));
                    instance.next();
                }
                "items" => {
                    order.extend([
                        40,
                        instance
                            .next()
                            .and_then(|index| index.parse().ok())
                            .unwrap_or(usize::MAX),
                    ]);
                    schema = &schema["items"];
                    path.push_str("/items");
                }
                "anyOf" | "oneOf" | "allOf" => {
                    order.push(match token {
                        "anyOf" => 4,
                        "oneOf" => 5,
                        _ => 6,
                    });
                    if let Some(index) = tokens.next() {
                        let index: usize = index.parse().expect("preserved schema branch index");
                        order.push(index);
                        schema = &schema[token][index];
                        path.push_str(&format!("/{token}/{index}"));
                    } else {
                        // Composite summaries follow all branch diagnostics.
                        order.push(usize::MAX);
                    }
                }
                "then" | "else" => {
                    order.extend([7, 0]);
                    schema = &schema[token];
                    path.push_str(&format!("/{token}"));
                }
                "if" => order.extend([7, 1]),
                "required" => {
                    order.push(20);
                    let property = issue
                        .message
                        .strip_prefix("must have required property '")
                        .and_then(|name| name.strip_suffix('\''));
                    order.push(
                        schema
                            .get("required")
                            .and_then(Value::as_array)
                            .and_then(|required| {
                                required.iter().position(|item| item.as_str() == property)
                            })
                            .unwrap_or(usize::MAX),
                    );
                }
                "type" | "const" | "enum" => order.push(0),
                "maxItems" | "maxLength" | "maxProperties" => order.push(10),
                "minItems" | "minLength" | "minProperties" => order.push(11),
                "pattern" => order.push(12),
                "additionalProperties" => {
                    order.push(30);
                    if schema["additionalProperties"].is_object() {
                        schema = &schema["additionalProperties"];
                        path.push_str("/additionalProperties");
                        instance.next();
                    }
                }
                "not" => order.push(0),
                "uniqueItems" => order.push(50),
                "format" => order.push(60),
                _ => order.push(usize::MAX),
            }
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
        native_message: None,
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
    for (index, law) in view.laws.as_ref().into_iter().flatten().enumerate() {
        let Some(conditions) = &law.conditions else {
            continue;
        };
        for (field, values) in [
            ("sourceKinds", &conditions.source_kinds),
            ("middleKinds", &conditions.middle_kinds),
            ("targetKinds", &conditions.target_kinds),
        ] {
            if values.as_ref().is_some_and(|values| {
                values
                    .iter()
                    .filter(|value| value.as_str() == "__proto__")
                    .count()
                    > 1
            }) {
                pending_checks.push(LegacyPackPendingCheck {
                    path: format!("/laws/{index}/conditions/{field}"),
                    code: "LEGACY_VALIDATOR_UNIQUENESS_QUIRK".into(),
                    message: "The pinned legacy validator accepts repeated __proto__ items although its schema declares uniqueItems. The original data and address are retained; native admission requires its own validation".into(),
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
