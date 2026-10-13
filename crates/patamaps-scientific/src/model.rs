use patamaps_contracts::{JsonLimits, JsonObject};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;

pub const SSSOM_MAX_BYTES: usize = 64 * 1024 * 1024;
/// Reference-sized source/model ingress, selected separately from the original
/// strict native profile. A value count cannot exceed the encoded byte count.
pub const SSSOM_COMPATIBILITY_LIMITS: JsonLimits = JsonLimits {
    max_bytes: SSSOM_MAX_BYTES,
    max_depth: 512,
    max_values: SSSOM_MAX_BYTES,
};
/// Expanded discovery transports repeat source/document/interpretation data.
/// This bound does not change protected proposal or host transport limits.
pub const SSSOM_TRANSPORT_LIMITS: JsonLimits = JsonLimits {
    max_bytes: 1024 * 1024 * 1024,
    max_depth: 512,
    max_values: 1024 * 1024 * 1024,
};

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum FormatVersion {
    #[serde(rename = "1.0.0")]
    Sssom1,
}
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum EntityProfile {
    #[serde(rename = "sssom-1.0-entity-tsv")]
    Entity1,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SssomDocument {
    pub schema_version: FormatVersion,
    pub profile: EntityProfile,
    pub metadata: JsonObject,
    pub columns: Vec<String>,
    pub rows: Vec<Vec<String>>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum FieldOrigin {
    Record,
    Set,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SssomRecord {
    pub raw: BTreeMap<String, String>,
    pub fields: JsonObject,
    pub origins: BTreeMap<String, FieldOrigin>,
    pub expanded: BTreeMap<String, Value>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Extension {
    pub name: String,
    pub property: String,
    #[serde(rename = "type")]
    pub type_: String,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum PropagationStatus {
    Propagated,
    BlockedByRecordValue,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Propagation {
    pub slot: String,
    pub status: PropagationStatus,
    pub value: Value,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Interpretation {
    pub metadata: JsonObject,
    pub prefixes: BTreeMap<String, String>,
    pub extensions: Vec<Extension>,
    pub propagation: Vec<Propagation>,
    pub records: Vec<SssomRecord>,
}
/// Checked source syntax/model; this does not establish scientific truth.
/// ```compile_fail
/// let forged: patamaps_scientific::CheckedSssom = serde_json::from_str("{}").unwrap();
/// ```
#[derive(Debug, Serialize)]
pub struct CheckedSssom {
    pub(crate) document: SssomDocument,
    pub(crate) interpretation: Interpretation,
    #[serde(skip)]
    pub(crate) limits: JsonLimits,
}
impl CheckedSssom {
    pub fn document(&self) -> &SssomDocument {
        &self.document
    }
    pub fn interpretation(&self) -> &Interpretation {
        &self.interpretation
    }
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ExportLoss {
    pub profile: EntityProfile,
    pub semantic_fields_preserved: bool,
    pub byte_identity_preserved: bool,
    pub dropped_fields: Vec<String>,
    pub condensed_slots: Vec<String>,
    pub normalization: Vec<String>,
}
#[derive(Debug, Serialize)]
pub struct ExportedSssom {
    pub text: String,
    pub loss: ExportLoss,
}
