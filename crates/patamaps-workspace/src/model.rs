use patamaps_contracts::{GraphDocument, JsonObject, ProtocolVersion, SafeInteger};
use patamaps_projection::CaptureRecord;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

macro_rules! tag {
    ($name:ident, $wire:literal) => {
        #[derive(Debug, Clone, Copy, Serialize, Deserialize)]
        pub enum $name {
            #[serde(rename = $wire)]
            Record,
        }
    };
}
tag!(WorkspaceType, "workspace-config");
tag!(RequestType, "adapter-request");
tag!(ResponseType, "adapter-response");
tag!(BaselineType, "workspace-baseline");

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ProcessBounds {
    pub maximum_elapsed_ms: SafeInteger,
    pub maximum_stdout_bytes: SafeInteger,
    pub maximum_stderr_bytes: SafeInteger,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Invocation {
    pub executable: String,
    pub arguments: Vec<String>,
    pub code_inputs: Vec<String>,
    pub bounds: ProcessBounds,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "adapter", rename_all = "kebab-case", deny_unknown_fields)]
pub enum Source {
    PortableShard {
        id: String,
        path: String,
    },
    Process {
        id: String,
        invocation: Invocation,
        inputs: Vec<String>,
        config: JsonObject,
    },
}
impl Source {
    pub fn id(&self) -> &str {
        match self {
            Self::PortableShard { id, .. } | Self::Process { id, .. } => id,
        }
    }
}
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum OutputLanguage {
    Json,
    Rust,
    Typescript,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Emission {
    pub path: String,
    pub language: OutputLanguage,
    #[serde(
        default,
        deserialize_with = "patamaps_contracts::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub binding_slot: Option<String>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SelectedProjection {
    pub path: String,
    pub emissions: Vec<Emission>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct WorkspaceConfig {
    pub schema_version: ProtocolVersion,
    pub document_type: WorkspaceType,
    pub id: String,
    pub namespace: String,
    pub revision: String,
    pub sources: Vec<Source>,
    pub packs: Vec<String>,
    pub policy: String,
    pub projections: Vec<SelectedProjection>,
    pub context: JsonObject,
    pub evaluated_at: String,
}
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct InputReceipt {
    pub path: String,
    pub digest: String,
    pub byte_length: SafeInteger,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SuppliedInput {
    pub receipt: InputReceipt,
    pub content: String,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct AdapterRequest {
    pub schema_version: ProtocolVersion,
    pub document_type: RequestType,
    pub profile: String,
    pub source_id: String,
    pub namespace: String,
    pub config: JsonObject,
    pub inputs: Vec<SuppliedInput>,
    pub invocation_digest: String,
    pub request_digest: String,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct AdapterDiagnostic {
    pub severity: DiagnosticSeverity,
    pub code: String,
    pub message: String,
}
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum DiagnosticSeverity {
    Warning,
    Error,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct AdapterResponse {
    pub schema_version: ProtocolVersion,
    pub document_type: ResponseType,
    pub profile: String,
    pub source_id: String,
    pub adapter_version: String,
    pub request_digest: String,
    pub inputs: Vec<InputReceipt>,
    pub shard: GraphDocument,
    pub diagnostics: Vec<AdapterDiagnostic>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct DiscoveryReceipt {
    pub source_id: String,
    pub adapter: String,
    pub adapter_version: String,
    pub request_digest: String,
    /// Recorded executable bytes for reconstructing a process request. This
    /// does not authenticate a provider or cause offline verification to run it.
    #[serde(
        default,
        deserialize_with = "patamaps_contracts::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub executable_digest: Option<String>,
    pub shard_digest: String,
    pub shard: GraphDocument,
    pub diagnostics: Vec<AdapterDiagnostic>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct WorkspaceBaseline {
    pub schema_version: ProtocolVersion,
    pub document_type: BaselineType,
    pub profile: String,
    pub executor: String,
    pub workspace_executor: String,
    pub config_digest: String,
    pub config: WorkspaceConfig,
    pub discovery: Vec<DiscoveryReceipt>,
    pub captures: Vec<CaptureRecord>,
    pub outputs: BTreeMap<String, String>,
    pub digest: String,
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Generation {
    pub baseline: WorkspaceBaseline,
    pub cache_hits: usize,
    pub cache_misses: usize,
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DriftReport {
    pub status: &'static str,
    pub baseline_digest: String,
    pub current_digest: String,
    pub changes: Vec<&'static str>,
}
