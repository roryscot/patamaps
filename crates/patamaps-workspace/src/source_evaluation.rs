use crate::{Error, VerifiedWorkspace, WorkspaceBaseline, verify_baseline};
use patamaps_contracts::*;
use patamaps_projection::{
    CaptureInputs, CaptureRecord, SourceReceipt, VerifiedReplay, capture, compare, replay,
};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet};

pub const SOURCE_EVALUATION_PROFILE: &str = "patamaps-source-evaluation-draft-1";
const BINDING_ID: &str = "urn:patamaps:source-evaluation:baseline-binding";

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum SourceEvaluationType {
    #[serde(rename = "source-evaluation")]
    Record,
}
/// Untrusted wire data. Verification constructs the private checked view.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SourceEvaluationRecord {
    pub schema_version: ProtocolVersion,
    pub document_type: SourceEvaluationType,
    pub profile: String,
    pub id: String,
    pub digest: String,
    pub workspace: WorkspaceBaseline,
    pub candidate: CaptureRecord,
}
fn address(record: &SourceEvaluationRecord) -> Result<String, Error> {
    let mut value = serde_json::to_value(record).map_err(ContractError::from)?;
    let fields = value.as_object_mut().expect("source evaluation record");
    fields.remove("id");
    fields.remove("digest");
    Ok(canonical_digest(&value)?)
}
fn bound_receipts(workspace: &WorkspaceBaseline) -> Result<Vec<SourceReceipt>, Error> {
    let mut sources = workspace.captures[0].sources.clone();
    if sources.iter().any(|s| s.id == BINDING_ID) {
        return Err(Error::refused(
            "SOURCE_BINDING_COLLISION",
            "Reserved source binding ID is already present",
        ));
    }
    let content = canonical_bytes(
        &json!({"profile":SOURCE_EVALUATION_PROFILE,"baseline":workspace.digest,"workspaceExecutor":workspace.workspace_executor,"compiler":workspace.executor}),
    )?;
    sources.push(SourceReceipt {
        id: BINDING_ID.into(),
        locator: BINDING_ID.into(),
        digest: byte_digest(&content),
        byte_length: SafeInteger::new(content.len() as u64).expect("small fixed binding"),
        content: Some(String::from_utf8(content).expect("canonical UTF-8")),
    });
    sources.sort_by(|a, b| a.id.cmp(&b.id));
    Ok(sources)
}
pub fn capture_source_evaluation(
    workspace: &VerifiedWorkspace<'_>,
    inputs: CaptureInputs,
) -> Result<SourceEvaluationRecord, Error> {
    if inputs.graph.id != workspace.record().config.id {
        return Err(Error::refused(
            "SOURCE_CANDIDATE_ID",
            "Candidate must use the recorded workspace graph ID",
        ));
    }
    let candidate = capture(inputs, bound_receipts(workspace.record())?)?;
    let mut record = SourceEvaluationRecord {
        schema_version: ProtocolVersion::Draft1,
        document_type: SourceEvaluationType::Record,
        profile: SOURCE_EVALUATION_PROFILE.into(),
        id: String::new(),
        digest: String::new(),
        workspace: workspace.record().clone(),
        candidate,
    };
    record.digest = address(&record)?;
    record.id = format!("urn:patamaps:source-evaluation:{}", &record.digest[7..]);
    parse_value(&canonical_bytes(&record)?)?;
    Ok(record)
}

/// Recomputed source/candidate bindings; cannot deserialize or be constructed
/// by downstream code.
/// ```compile_fail
/// let forged: patamaps_workspace::VerifiedSourceEvaluation = serde_json::from_str("{}").unwrap();
/// ```
#[derive(Debug)]
pub struct VerifiedSourceEvaluation<'a> {
    record: &'a SourceEvaluationRecord,
    workspace: VerifiedWorkspace<'a>,
    candidate: VerifiedReplay<'a>,
}
impl VerifiedSourceEvaluation<'_> {
    pub fn record(&self) -> &SourceEvaluationRecord {
        self.record
    }
    pub fn workspace(&self) -> &VerifiedWorkspace<'_> {
        &self.workspace
    }
    pub fn candidate(&self) -> &VerifiedReplay<'_> {
        &self.candidate
    }
    pub fn source_graph(&self) -> &GraphDocument {
        &self.record.workspace.captures[0].inputs.graph
    }
    pub fn inspect(&self) -> Result<CheckedSourceReport, Error> {
        let source = self.source_graph();
        let candidate = &self.record.candidate.inputs.graph;
        let source_digest = canonical_digest(source)?;
        let candidate_digest = canonical_digest(candidate)?;
        let (graph_changes, graph_comparison) = match patamaps_core::diff(source, candidate) {
            Ok(changes) => (json!(changes), json!({"status":"compared"})),
            Err(error) => (
                Value::Null,
                json!({"status":"unavailable","issues":error.0}),
            ),
        };
        let candidate_rows = occurrences(candidate);
        let mut memberships = Vec::new();
        for (config, discovered) in self
            .record
            .workspace
            .config
            .sources
            .iter()
            .zip(&self.record.workspace.discovery)
        {
            let source_rows = occurrences(&discovered.shard);
            let records = source_rows.iter().map(|((kind,id),count)| {
                let candidate_count = *candidate_rows.get(&(*kind,id.clone())).unwrap_or(&0);
                json!({"kind":kind,"id":id,"sourceOccurrences":count,"sourceState":record_state(*count),"candidateOccurrences":candidate_count,"candidateState":record_state(candidate_count)})
            }).collect::<Vec<_>>();
            memberships.push(json!({"sourceId":discovered.source_id,"adapter":discovered.adapter,"adapterVersion":discovered.adapter_version,
                "configurationDigest":canonical_digest(config)?,"requestDigest":discovered.request_digest,
                "shard":{"id":discovered.shard.id,"revision":discovered.shard.revision,"digest":discovered.shard_digest},"records":records}));
        }
        checked_report(
            json!({"schemaVersion":"0.1.0","documentType":"source-inspection","profile":SOURCE_EVALUATION_PROFILE,
            "evaluation":self.record.digest,"baseline":self.record.workspace.digest,
            "sourceGraph":{"id":source.id,"digest":source_digest},"candidateGraph":{"id":candidate.id,"digest":candidate_digest},
            "relationship":if source_digest==candidate_digest {"identical"}else{"candidate-differs"},
            "graphChanges":graph_changes,"graphComparison":graph_comparison,"graphMetadataChanged":metadata(source)?!=metadata(candidate)?,
            "sources":memberships,"candidateAdmission":self.candidate.result()["status"],
            "membershipScope":"recorded-shards-to-candidate-inputs; derived claims retain their separate checked proofs",
            "rawInputs":"captured-and-verified","sourceTruth":"not-established","sourceRediscovery":"not-performed",
            "authentication":"not-evaluated","authorizationNow":"not-evaluated","active":"not-evaluated"}),
        )
    }
}
pub fn verify_source_evaluation(
    record: &SourceEvaluationRecord,
) -> Result<VerifiedSourceEvaluation<'_>, Error> {
    if record.profile != SOURCE_EVALUATION_PROFILE
        || record.digest.len() != 71
        || !record.digest.starts_with("sha256:")
    {
        return Err(Error::refused(
            "SOURCE_EVALUATION_PROFILE",
            "Unsupported source evaluation or address",
        ));
    }
    let workspace = verify_baseline(&record.workspace)?;
    let candidate = replay(&record.candidate)?;
    if record.candidate.inputs.graph.id != record.workspace.config.id
        || canonical_bytes(&record.candidate.sources)?
            != canonical_bytes(&bound_receipts(&record.workspace)?)?
    {
        return Err(Error::refused(
            "SOURCE_CANDIDATE_BINDING",
            "Candidate differs from the exact recorded workspace binding",
        ));
    }
    if address(record)? != record.digest
        || record.id != format!("urn:patamaps:source-evaluation:{}", &record.digest[7..])
    {
        return Err(Error::refused(
            "SOURCE_EVALUATION_ADDRESS",
            "Source evaluation address differs",
        ));
    }
    parse_value(&canonical_bytes(record)?)?;
    Ok(VerifiedSourceEvaluation {
        record,
        workspace,
        candidate,
    })
}
fn occurrences(graph: &GraphDocument) -> BTreeMap<(&'static str, String), usize> {
    let mut counts = BTreeMap::new();
    for (kind, id) in graph
        .entities
        .iter()
        .map(|v| ("entity", &v.id))
        .chain(graph.mappings.iter().map(|v| ("mapping", &v.id)))
        .chain(graph.authorities.iter().map(|v| ("authority", &v.id)))
    {
        *counts.entry((kind, id.clone())).or_insert(0) += 1;
    }
    counts
}
fn record_state(count: usize) -> &'static str {
    match count {
        0 => "missing",
        1 => "known",
        _ => "ambiguous",
    }
}
fn metadata(graph: &GraphDocument) -> Result<String, Error> {
    let mut value = serde_json::to_value(graph).map_err(ContractError::from)?;
    let fields = value.as_object_mut().expect("graph");
    for key in ["entities", "mappings", "authorities"] {
        fields.remove(key);
    }
    Ok(canonical_digest(&value)?)
}
/// A freshly computed report, never an accepted serialized claim.
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CheckedSourceReport {
    id: String,
    digest: String,
    record: Value,
}
impl CheckedSourceReport {
    pub fn record(&self) -> &Value {
        &self.record
    }
}
fn checked_report(record: Value) -> Result<CheckedSourceReport, Error> {
    parse_value(&canonical_bytes(&record)?)?;
    let digest = canonical_digest(&record)?;
    Ok(CheckedSourceReport {
        id: format!("urn:patamaps:source-report:{}", &digest[7..]),
        digest,
        record,
    })
}
pub fn compare_source_evaluations(
    before: &VerifiedSourceEvaluation<'_>,
    after: &VerifiedSourceEvaluation<'_>,
) -> Result<CheckedSourceReport, Error> {
    if before.source_graph().id != after.source_graph().id {
        return Err(Error::refused(
            "SOURCE_COMPARISON_ID",
            "Source comparison requires the same workspace graph ID",
        ));
    }
    let maps: Vec<BTreeMap<_, _>> = [before, after]
        .iter()
        .map(|v| {
            v.record
                .workspace
                .discovery
                .iter()
                .map(|d| (d.source_id.as_str(), d))
                .collect()
        })
        .collect();
    let ids: BTreeSet<_> = maps.iter().flat_map(|m| m.keys().copied()).collect();
    let mut changes = Vec::new();
    for id in ids {
        let old = maps[0].get(id);
        let new = maps[1].get(id);
        let a = old.map(canonical_digest).transpose()?;
        let b = new.map(canonical_digest).transpose()?;
        if a != b {
            changes.push(json!({"sourceId":id,"beforeDigest":a,"afterDigest":b,"change":if old.is_none(){"added"}else if new.is_none(){"removed"}else{"modified"}}));
        }
    }
    let (source_changes, source_comparison) =
        match patamaps_core::diff(before.source_graph(), after.source_graph()) {
            Ok(changes) => (json!(changes), json!({"status":"compared"})),
            Err(error) => (
                Value::Null,
                json!({"status":"unavailable","issues":error.0}),
            ),
        };
    let (candidate_changes, candidate_comparison) =
        match compare(&before.candidate, &after.candidate) {
            Ok(report) => (json!(report), json!({"status":"compared"})),
            Err(error) => (
                Value::Null,
                json!({"status":"unavailable","issues":error.0}),
            ),
        };
    checked_report(
        json!({"schemaVersion":"0.1.0","documentType":"source-comparison","profile":SOURCE_EVALUATION_PROFILE,
        "before":before.record.digest,"after":after.record.digest,"sourceChanges":changes,
        "configurationChanged":before.record.workspace.config_digest!=after.record.workspace.config_digest,
        "sourceGraphChanges":source_changes,"sourceGraphComparison":source_comparison,
        "sourceGraphMetadataChanged":metadata(before.source_graph())?!=metadata(after.source_graph())?,
        "sourceGraphChanged":canonical_digest(before.source_graph())?!=canonical_digest(after.source_graph())?,
        "candidate":candidate_changes,"candidateComparison":candidate_comparison,"sourceInspectionBefore":before.inspect()?.record(),"sourceInspectionAfter":after.inspect()?.record(),
        "sourceRediscovery":"not-performed","authentication":"not-evaluated","authorizationNow":"not-evaluated","active":"not-evaluated",
        "causality":"Observed recorded changes; unique causal responsibility is not established"}),
    )
}
