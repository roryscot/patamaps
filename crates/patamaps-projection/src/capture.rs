use crate::{compile_path_tree, project};
use patamaps_contracts::*;
use patamaps_core::{CheckError, CheckedGraph, EvaluationOptions, Issue, admit, diff};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{
    collections::{BTreeMap, BTreeSet, HashSet},
    sync::OnceLock,
};

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
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct CaptureRecord {
    pub schema_version: ProtocolVersion,
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
        canonical_digest(&json!({
            "profile":PROFILE,"toolchain":include_str!("../../../rust-toolchain.toml"),
        "lock":include_str!("../../../Cargo.lock"),
        "workspace":include_str!("../../../Cargo.toml"),
        "contractsManifest":include_str!("../../patamaps-contracts/Cargo.toml"),
        "coreManifest":include_str!("../../patamaps-core/Cargo.toml"),
        "projectionManifest":include_str!("../Cargo.toml"),
        "contractsLib":include_str!("../../patamaps-contracts/src/lib.rs"),
        "coreLib":include_str!("../../patamaps-core/src/lib.rs"),
            "contracts":include_str!("../../patamaps-contracts/src/model.rs"),
            "semanticTypes":include_str!("../../patamaps-contracts/src/semantic.rs"),
            "json":include_str!("../../patamaps-contracts/src/json.rs"),
            "integer":include_str!("../../patamaps-contracts/src/integer.rs"),
            "graph":include_str!("../../patamaps-core/src/graph.rs"),
            "admission":include_str!("../../patamaps-core/src/admission.rs"),
            "topology":include_str!("../../patamaps-core/src/topology.rs"),
            "laws":include_str!("../../patamaps-core/src/laws.rs"),
            "derivation":include_str!("../../patamaps-core/src/derivation.rs"),
            "uncertainty":include_str!("../../patamaps-core/src/uncertainty.rs"),
            "risk":include_str!("../../patamaps-core/src/risk.rs"),
        "diff":include_str!("../../patamaps-core/src/diff.rs"),
            "impact":include_str!("../../patamaps-core/src/impact.rs"),
            "preflight":include_str!("../../patamaps-core/src/preflight.rs"),
            "control":include_str!("../../patamaps-core/src/control.rs"),
            "projection":include_str!("lib.rs"),"capture":include_str!("capture.rs"),"pathTree":include_str!("path_tree.rs")
        }))
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
    if let Some(spec) = &inputs.projection_spec {
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
    inputs: CaptureInputs,
    mut sources: Vec<SourceReceipt>,
) -> Result<CaptureRecord, CheckError> {
    sources_valid(&sources)?;
    sources.sort_by(|a, b| a.id.cmp(&b.id));
    let result = evaluate(&inputs)?;
    let mut record = CaptureRecord {
        schema_version: ProtocolVersion::Draft1,
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
    if let Some(spec) = &record.inputs.projection_spec {
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

/// Compare verified inputs/results; unavailable deltas remain explicit nulls.
pub fn compare(
    before: &VerifiedReplay<'_>,
    after: &VerifiedReplay<'_>,
) -> Result<Value, CheckError> {
    let a = before.record();
    let b = after.record();
    let changes = diff(&a.inputs.graph, &b.inputs.graph)?;
    let projection_delta = match (
        a.result.get("projection").filter(|v| !v.is_null()),
        b.result.get("projection").filter(|v| !v.is_null()),
    ) {
        (Some(a), Some(b)) => Some(canonical_bytes(a)? != canonical_bytes(b)?),
        _ => None,
    };
    let tree_delta = match (
        a.result.get("pathTree").filter(|v| !v.is_null()),
        b.result.get("pathTree").filter(|v| !v.is_null()),
    ) {
        (Some(a), Some(b)) => Some(canonical_bytes(a)? != canonical_bytes(b)?),
        _ => None,
    };
    let changed_origins: Vec<_> = changes
        .iter()
        .map(|d| json!({"kind":d.kind,"id":d.id,"change":d.change}))
        .collect();
    let risk_delta = match (
        a.result.pointer("/projection/semantics/risk"),
        b.result.pointer("/projection/semantics/risk"),
    ) {
        (Some(a), Some(b)) if a["status"] == "evaluated" && b["status"] == "evaluated" => {
            let before: SafeInteger =
                serde_json::from_value(a["totalCost"].clone()).map_err(ContractError::from)?;
            let after: SafeInteger =
                serde_json::from_value(b["totalCost"].clone()).map_err(ContractError::from)?;
            Some(
                json!({"status":"available","before":a,"after":b,"totalCostChange":after.get() as i64-before.get() as i64}),
            )
        }
        _ => None,
    };
    let origins: Vec<_> = changes.iter().map(|d| d.id.clone()).collect();
    let source_maps: Vec<BTreeMap<_, _>> = [&a.sources, &b.sources]
        .iter()
        .map(|sources| sources.iter().map(|s| (s.id.clone(), s)).collect())
        .collect();
    let source_ids: BTreeSet<_> = source_maps.iter().flat_map(|m| m.keys()).collect();
    let mut source_deltas = Vec::new();
    for id in source_ids {
        let before = source_maps[0].get(id);
        let after = source_maps[1].get(id);
        let before_receipt = before.map(canonical_digest).transpose()?;
        let after_receipt = after.map(canonical_digest).transpose()?;
        if before_receipt != after_receipt {
            source_deltas.push(json!({"id":id,"change":if before.is_none(){"added"}else if after.is_none(){"removed"}else{"modified"},
            "beforeDigest":before.map(|s|&s.digest),"afterDigest":after.map(|s|&s.digest),
            "byteChange":before.map(|s|&s.digest)!=after.map(|s|&s.digest),
            "beforeReceiptDigest":before_receipt,"afterReceiptDigest":after_receipt,"graphExtractionRecomputed":false}));
        }
    }
    let declared_paths = |inputs: &CaptureInputs| -> Result<Value, CheckError> {
        match CheckedGraph::check(inputs.graph.clone(), inputs.packs.clone()) {
            Ok(g) => match patamaps_core::impact(&g, &origins, 64) {
                Ok(report) => {
                    Ok(json!({"status":"available","scope":"declared-graph","report":report}))
                }
                Err(error) => Ok(json!({"status":"unavailable","issues":error.0})),
            },
            Err(error) => Ok(json!({"status":"unavailable","issues":error.0})),
        }
    };
    Ok(
        json!({"before":a.digest,"after":b.digest,"changes":changes,"changedOrigins":changed_origins,
        "statusChanged":a.result["status"] != b.result["status"],"projectionChanged":projection_delta,"pathTreeChanged":tree_delta,
        "policyChanged":canonical_digest(&a.inputs.policy)? != canonical_digest(&b.inputs.policy)?,
        "contextChanged":canonical_bytes(&a.inputs.context)? != canonical_bytes(&b.inputs.context)?,
        "packChanged":canonical_bytes(&a.inputs.packs)? != canonical_bytes(&b.inputs.packs)?,
        "riskDelta":risk_delta,"missingSourcesBefore":before.missing_sources(),"missingSourcesAfter":after.missing_sources(),
        "declaredPathsBefore":declared_paths(&a.inputs)?,"declaredPathsAfter":declared_paths(&b.inputs)?,
        "sourceDeltas":source_deltas,
        "issueSubjectsBefore":a.result.get("issues"),"issueSubjectsAfter":b.result.get("issues"),
        "causalClaim":"Observed input differences and findings; unique causal responsibility is not established"}),
    )
}
