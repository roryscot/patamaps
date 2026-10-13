use crate::{compile_path_tree, project};
use patamaps_contracts::*;
use patamaps_core::{CheckError, CheckedGraph, EvaluationOptions, Issue, admit};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{collections::HashSet, sync::OnceLock};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct CaptureInputs {
    pub graph: GraphDocument,
    pub packs: Vec<RelationPack>,
    pub policy: PolicyDocument,
    pub context: JsonObject,
    pub evaluated_at: String,
    #[serde(
        default,
        deserialize_with = "patamaps_contracts::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub projection_spec: Option<ProjectionSpec>,
    /// Collection captures have their own wire version. Historical single-spec
    /// captures retain their original field representation and executor binding.
    #[serde(
        default,
        deserialize_with = "projection_collection",
        skip_serializing_if = "Vec::is_empty"
    )]
    pub projection_specs: Vec<ProjectionSpec>,
}

fn projection_collection<'de, D: serde::Deserializer<'de>>(
    deserializer: D,
) -> Result<Vec<ProjectionSpec>, D::Error> {
    let specs = Vec::<ProjectionSpec>::deserialize(deserializer)?;
    if specs.is_empty() {
        return Err(serde::de::Error::custom(
            "CAPTURE_EMPTY_PROJECTION_COLLECTION",
        ));
    }
    Ok(specs)
}

impl CaptureInputs {
    pub fn specs(&self) -> impl Iterator<Item = &ProjectionSpec> {
        self.projection_spec.iter().chain(&self.projection_specs)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SourceReceipt {
    pub id: String,
    pub locator: String,
    pub digest: String,
    pub byte_length: SafeInteger,
    #[serde(
        default,
        deserialize_with = "patamaps_contracts::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub content: Option<String>,
}
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum CaptureType {
    #[serde(rename = "capture")]
    Capture,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum CaptureVersion {
    #[serde(rename = "0.1.0")]
    Draft1,
    #[serde(rename = "0.2.0")]
    Collection1,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct CaptureRecord {
    pub schema_version: CaptureVersion,
    pub document_type: CaptureType,
    pub profile: String,
    pub executor: String,
    pub id: String,
    pub digest: String,
    pub inputs: CaptureInputs,
    pub sources: Vec<SourceReceipt>,
    pub result: Value,
}

/// Source identity binds actual production code and dependency resolution.
/// Historical MetaMap captures never acquire this Rust executor identity.
pub fn executor_id() -> &'static str {
    static ID: OnceLock<String> = OnceLock::new();
    ID.get_or_init(|| {
        canonical_digest(&std::collections::BTreeMap::from([
            ("profile", PROFILE),
            ("toolchain", include_str!("../../../rust-toolchain.toml")),
            ("lock", include_str!("../../../Cargo.lock")),
            ("workspace", include_str!("../../../Cargo.toml")),
            (
                "contractsManifest",
                include_str!("../../patamaps-contracts/Cargo.toml"),
            ),
            (
                "contractsBuild",
                include_str!("../../patamaps-contracts/build.rs"),
            ),
            (
                "legacyCollatorSource",
                patamaps_contracts::LEGACY_COLLATOR_SOURCE_DIGEST,
            ),
            (
                "coreManifest",
                include_str!("../../patamaps-core/Cargo.toml"),
            ),
            ("projectionManifest", include_str!("../Cargo.toml")),
            (
                "contractsLib",
                include_str!("../../patamaps-contracts/src/lib.rs"),
            ),
            ("coreLib", include_str!("../../patamaps-core/src/lib.rs")),
            (
                "contracts",
                include_str!("../../patamaps-contracts/src/model.rs"),
            ),
            (
                "semanticTypes",
                include_str!("../../patamaps-contracts/src/semantic.rs"),
            ),
            ("json", include_str!("../../patamaps-contracts/src/json.rs")),
            (
                "jsonScan",
                include_str!("../../patamaps-contracts/src/json_scan.rs"),
            ),
            (
                "legacyJson",
                include_str!("../../patamaps-contracts/src/legacy_json.rs"),
            ),
            (
                "legacyStable",
                include_str!("../../patamaps-contracts/src/legacy_stable.rs"),
            ),
            (
                "integer",
                include_str!("../../patamaps-contracts/src/integer.rs"),
            ),
            ("graph", include_str!("../../patamaps-core/src/graph.rs")),
            (
                "registry",
                include_str!("../../patamaps-core/src/registry.rs"),
            ),
            (
                "legacyPack",
                include_str!("../../patamaps-core/src/legacy_pack.rs"),
            ),
            (
                "legacyRegistry",
                include_str!("../../patamaps-core/src/legacy_registry.rs"),
            ),
            (
                "legacyGraph",
                include_str!("../../patamaps-core/src/legacy_graph.rs"),
            ),
            (
                "legacyComposition",
                include_str!("../../patamaps-core/src/legacy_composition.rs"),
            ),
            (
                "legacyReporting",
                include_str!("../../patamaps-core/src/legacy_reporting.rs"),
            ),
            (
                "legacyUriReference",
                include_str!("../../patamaps-core/src/legacy_uri_reference.json"),
            ),
            (
                "legacyPackSchema",
                include_str!("../../../fixtures/reference/schemas/relation-pack.schema.json"),
            ),
            (
                "executableLegacyPackSchema",
                include_str!("../../../fixtures/reference/schemas/relation-pack-v2.schema.json"),
            ),
            (
                "legacyValidation",
                include_str!("../../patamaps-core/src/legacy_validation.rs"),
            ),
            (
                "legacyCore",
                include_str!("../../patamaps-core/src/legacy_core.json"),
            ),
            (
                "admission",
                include_str!("../../patamaps-core/src/admission.rs"),
            ),
            (
                "topology",
                include_str!("../../patamaps-core/src/topology.rs"),
            ),
            ("laws", include_str!("../../patamaps-core/src/laws.rs")),
            (
                "derivation",
                include_str!("../../patamaps-core/src/derivation.rs"),
            ),
            (
                "uncertainty",
                include_str!("../../patamaps-core/src/uncertainty.rs"),
            ),
            ("risk", include_str!("../../patamaps-core/src/risk.rs")),
            ("diff", include_str!("../../patamaps-core/src/diff.rs")),
            ("impact", include_str!("../../patamaps-core/src/impact.rs")),
            (
                "preflight",
                include_str!("../../patamaps-core/src/preflight.rs"),
            ),
            (
                "control",
                include_str!("../../patamaps-core/src/control.rs"),
            ),
            ("projection", include_str!("lib.rs")),
            ("capture", include_str!("capture.rs")),
            ("comparison", include_str!("compare.rs")),
            ("pathTree", include_str!("path_tree.rs")),
        ]))
        .expect("embedded source is finite JSON")
    })
}

pub fn evaluate(inputs: &CaptureInputs) -> Result<Value, CheckError> {
    patamaps_core::check_input_bounds(
        &inputs.graph,
        &inputs.packs,
        &inputs.policy,
        &inputs.context,
    )?;
    let mut spec_ids = HashSet::new();
    if inputs.projection_spec.is_some() && !inputs.projection_specs.is_empty() {
        return Err(CheckError(vec![Issue::error(
            "CAPTURE_PROJECTION_PROFILE",
            "A capture must select the single-spec or collection representation",
            "capture",
        )]));
    }
    for spec in inputs.specs() {
        if !spec_ids.insert(&spec.id) {
            return Err(CheckError(vec![Issue::error(
                "CAPTURE_DUPLICATE_PROJECTION",
                "Capture repeats a projection identity",
                &spec.id,
            )]));
        }
        patamaps_core::check_metadata_bounds(
            spec.metadata.iter().map(|v| (v, 2)),
            &spec.id,
            "PROJECTION_RESOURCE_LIMIT",
        )?;
    }
    let result = (|| {
        let graph = CheckedGraph::check(inputs.graph.clone(), inputs.packs.clone())?;
        let generation = admit(
            &graph,
            &inputs.policy,
            EvaluationOptions {
                context: inputs.context.clone(),
                evaluated_at: inputs.evaluated_at.clone(),
            },
        )?;
        if !inputs.projection_specs.is_empty() {
            let mut specs: Vec<_> = inputs.projection_specs.iter().collect();
            specs.sort_by(|a, b| a.id.encode_utf16().cmp(b.id.encode_utf16()));
            let mut outcomes = Vec::new();
            let mut issues = generation.issues().to_vec();
            let mut admitted = true;
            for spec in specs {
                match project(&generation, spec) {
                    Ok(projection) => {
                        let tree = spec
                            .path_tree
                            .as_ref()
                            .map(|_| compile_path_tree(&projection, spec))
                            .transpose();
                        match tree {
                            Ok(tree) => outcomes.push(json!({"specId":spec.id,"status":"projected","projection":projection.record(),"pathTree":tree.as_ref().map(|t|t.record()),"issues":[]})),
                            Err(error) => {
                                admitted = false;
                                issues.extend(error.0.iter().cloned());
                                outcomes.push(json!({"specId":spec.id,"status":"path-tree-rejected","projection":projection.record(),"pathTree":null,"issues":error.0}));
                            }
                        }
                    }
                    Err(error) => {
                        admitted = false;
                        issues.extend(error.0.iter().cloned());
                        outcomes.push(json!({"specId":spec.id,"status":"rejected","projection":null,"pathTree":null,"issues":error.0}));
                    }
                }
            }
            return Ok(
                json!({"status":if admitted {"viable"} else {"rejected"},"compilationStatus":"viable","generation":generation.record(),"projections":outcomes,"issues":issues}),
            );
        }
        let projection = inputs
            .projection_spec
            .as_ref()
            .map(|s| project(&generation, s))
            .transpose()?;
        let tree = projection
            .as_ref()
            .zip(inputs.projection_spec.as_ref())
            .filter(|(_, s)| s.path_tree.is_some())
            .map(|(p, s)| compile_path_tree(p, s))
            .transpose()?;
        Ok::<_, CheckError>(
            json!({"status":"viable","generation":generation.record(),"projection":projection.as_ref().map(|p|p.record()),"pathTree":tree.as_ref().map(|t|t.record()),"issues":generation.issues()}),
        )
    })();
    Ok(match result {
        Ok(value) => value,
        Err(error) if !inputs.projection_specs.is_empty() => {
            json!({"status":"rejected","compilationStatus":"rejected","generation":null,"projections":[],"issues":error.0})
        }
        Err(error) => json!({"status":"rejected","issues":error.0}),
    })
}

fn address(record: &CaptureRecord) -> Result<String, CheckError> {
    let mut value = serde_json::to_value(record).map_err(ContractError::from)?;
    let object = value.as_object_mut().expect("capture object");
    object.remove("id");
    object.remove("digest");
    Ok(canonical_digest(&value)?)
}
fn sources_valid(sources: &[SourceReceipt]) -> Result<(), CheckError> {
    let mut ids = HashSet::new();
    let mut total = 0usize;
    if sources.len() > 1024 {
        return Err(CheckError(vec![Issue::error(
            "SOURCE_RECEIPT_LIMIT",
            "Too many source receipts",
            "capture",
        )]));
    }
    for s in sources {
        if !patamaps_core::valid_identifier(&s.id)
            || !patamaps_core::valid_identifier(&s.locator)
            || !ids.insert(&s.id)
            || s.digest.len() != 71
            || !s.digest.starts_with("sha256:")
            || !s.digest[7..]
                .bytes()
                .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
        {
            return Err(CheckError(vec![Issue::error(
                "INVALID_SOURCE_RECEIPT",
                "Receipt identity/locator/digest is invalid or duplicated",
                &s.id,
            )]));
        }
        if let Some(content) = &s.content {
            total = total.saturating_add(content.len());
            if content.len() as u64 != s.byte_length.get()
                || byte_digest(content.as_bytes()) != s.digest
            {
                return Err(CheckError(vec![Issue::error(
                    "SOURCE_BYTES_MISMATCH",
                    "Captured source differs from its receipt",
                    &s.id,
                )]));
            }
        }
    }
    if total > MAX_INPUT_BYTES {
        return Err(CheckError(vec![Issue::error(
            "SOURCE_BYTE_LIMIT",
            "Captured sources exceed byte limit",
            "capture",
        )]));
    }
    Ok(())
}

pub fn capture(
    mut inputs: CaptureInputs,
    mut sources: Vec<SourceReceipt>,
) -> Result<CaptureRecord, CheckError> {
    sources_valid(&sources)?;
    sources.sort_by(|a, b| a.id.cmp(&b.id));
    inputs
        .projection_specs
        .sort_by(|a, b| a.id.encode_utf16().cmp(b.id.encode_utf16()));
    let result = evaluate(&inputs)?;
    let mut record = CaptureRecord {
        schema_version: if inputs.projection_specs.is_empty() {
            CaptureVersion::Draft1
        } else {
            CaptureVersion::Collection1
        },
        document_type: CaptureType::Capture,
        profile: evaluation_profile(&inputs.packs, &inputs.policy).into(),
        executor: executor_id().into(),
        id: String::new(),
        digest: String::new(),
        inputs,
        sources,
        result,
    };
    record.digest = address(&record)?;
    record.id = format!("urn:patamaps:capture:{}", &record.digest[7..]);
    // Every emitted capture must itself fit strict ingress, including the
    // additional envelope nesting and captured result copies.
    parse_value(&canonical_bytes(&record)?)?;
    Ok(record)
}

/// A replay recomputes everything; serialized reports cannot construct this.
#[derive(Debug)]
pub struct VerifiedReplay<'a> {
    capture: &'a CaptureRecord,
    missing_sources: Vec<String>,
}
impl VerifiedReplay<'_> {
    pub fn result(&self) -> &Value {
        &self.capture.result
    }
    pub fn record(&self) -> &CaptureRecord {
        self.capture
    }
    pub fn missing_sources(&self) -> &[String] {
        &self.missing_sources
    }
}
pub fn replay(record: &CaptureRecord) -> Result<VerifiedReplay<'_>, CheckError> {
    let expected_version = if record.inputs.projection_specs.is_empty() {
        CaptureVersion::Draft1
    } else {
        CaptureVersion::Collection1
    };
    if record.schema_version != expected_version {
        return Err(CheckError(vec![Issue::error(
            "CAPTURE_VERSION_MISMATCH",
            "Capture version must match its input representation",
            &record.id,
        )]));
    }
    patamaps_core::check_input_bounds(
        &record.inputs.graph,
        &record.inputs.packs,
        &record.inputs.policy,
        &record.inputs.context,
    )?;
    if !record.result.is_object() {
        return Err(CheckError(vec![Issue::error(
            "CAPTURE_INVALID_RESULT",
            "Captured result must be a bounded object",
            &record.id,
        )]));
    }
    patamaps_core::check_value_bounds(&record.result, &record.id, "CAPTURE_RESOURCE_LIMIT")?;
    for spec in record.inputs.specs() {
        patamaps_core::check_metadata_bounds(
            spec.metadata.iter().map(|v| (v, 3)),
            &spec.id,
            "PROJECTION_RESOURCE_LIMIT",
        )?;
    }
    if record.profile != evaluation_profile(&record.inputs.packs, &record.inputs.policy)
        || record.executor != executor_id()
    {
        return Err(CheckError(vec![Issue::error(
            "EXECUTOR_MISMATCH",
            "Replay requires its exact declared executor and profile",
            &record.id,
        )]));
    }
    sources_valid(&record.sources)?;
    if address(record)? != record.digest
        || record.id != format!("urn:patamaps:capture:{}", &record.digest[7..])
    {
        return Err(CheckError(vec![Issue::error(
            "CAPTURE_DIGEST_MISMATCH",
            "Captured inputs/result do not match the content address",
            &record.id,
        )]));
    }
    let actual = evaluate(&record.inputs)?;
    if canonical_bytes(&actual)? != canonical_bytes(&record.result)? {
        return Err(CheckError(vec![Issue::error(
            "REPLAY_RESULT_MISMATCH",
            "Fresh evaluation differs from captured result",
            &record.id,
        )]));
    }
    Ok(VerifiedReplay {
        capture: record,
        missing_sources: record
            .sources
            .iter()
            .filter(|s| s.content.is_none())
            .map(|s| s.id.clone())
            .collect(),
    })
}
