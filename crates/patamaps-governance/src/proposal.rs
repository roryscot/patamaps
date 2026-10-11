use crate::{artifacts::*, delta::classified_requirements, model::*, trust::CheckedTrust, util::*};
use patamaps_contracts::{ProtocolVersion, canonical_digest};
use std::{collections::BTreeMap, sync::OnceLock};

/// Includes the pure kernel, governance source and locked dependency resolution.
/// This identifies source bytes, not a reproducibly built binary or host trust.
pub fn governance_executor_id() -> &'static str {
    static ID: OnceLock<String> = OnceLock::new();
    ID.get_or_init(||canonical_digest(&serde_json::json!({
        "profile":"patamaps-governance-draft-1","kernel":patamaps_projection::executor_id(),
        "manifest":include_str!("../Cargo.toml"),"lib":include_str!("lib.rs"),
        "model":include_str!("model.rs"),"util":include_str!("util.rs"),"trust":include_str!("trust.rs"),
        "artifacts":include_str!("artifacts.rs"),"delta":include_str!("delta.rs"),
        "proposal":include_str!("proposal.rs"),"approval":include_str!("approval.rs")
    })).expect("embedded source is JSON"))
}
/// Only exact recomputation creates this; no public unchecked restoration.
///
/// ```compile_fail
/// use patamaps_governance::CheckedProposal;
/// let forged:CheckedProposal=serde_json::from_str("{}").unwrap();
/// ```
#[derive(Debug)]
pub struct CheckedProposal {
    record: ChangeProposal,
    files: BTreeMap<String, String>,
}
impl CheckedProposal {
    pub fn record(&self) -> &ChangeProposal {
        &self.record
    }
    pub fn files(&self) -> &BTreeMap<String, String> {
        &self.files
    }
    pub fn prepared(&self) -> PreparedCandidate {
        PreparedCandidate {
            schema_version: ProtocolVersion::Draft1,
            document_type: PreparedType::Draft1,
            proposal: self.record.clone(),
            files: self.files.clone(),
        }
    }
}
pub(crate) fn baseline(
    value: Option<&GovernedBaseline>,
    consumer: &str,
) -> Result<Option<GovernedBaseline>> {
    value
        .map(|b| {
            if !digest(&b.manifest_digest) {
                return fail(
                    "GOVERNANCE_INVALID_BASELINE",
                    "Protected baseline needs an exact manifest digest",
                );
            }
            Ok(GovernedBaseline {
                manifest_digest: b.manifest_digest.clone(),
                candidate: normalized_candidate(&b.candidate, consumer)?,
            })
        })
        .transpose()
}
fn header(consumer: &str, environment: &str, proposer: &str) -> Result<()> {
    if !patamaps_core::valid_identifier(consumer) || !text(environment) || !text(proposer) {
        return fail(
            "GOVERNANCE_INVALID_SHAPE",
            "Invalid consumer, environment or attributed proposer",
        );
    }
    Ok(())
}
fn checked(record: ChangeProposal, files: BTreeMap<String, String>) -> Result<CheckedProposal> {
    // Checked outputs must be ingestible, including complete UTF-8 file bytes.
    let checked = CheckedProposal { record, files };
    normalized(&checked.prepared())?;
    Ok(checked)
}
pub fn create_proposal(
    candidate: &GovernedCandidate,
    options: ProposalOptions<'_>,
) -> Result<CheckedProposal> {
    header(options.consumer, options.environment, options.proposer)?;
    let trust = CheckedTrust::check(options.trust)?;
    if trust.record.consumer != options.consumer || trust.record.environment != options.environment
    {
        return fail(
            "GOVERNANCE_WRONG_ENVIRONMENT",
            "Consumer/environment must match external trust",
        );
    }
    let candidate = normalized_candidate(candidate, options.consumer)?;
    let baseline = baseline(options.baseline, options.consumer)?;
    if options.intent == DeploymentIntent::Rollback && baseline.is_none() {
        return fail(
            "GOVERNANCE_INVALID_BASELINE",
            "Rollback requires current protected baseline",
        );
    }
    let requirements = classified_requirements(
        baseline.as_ref().map(|b| &b.candidate),
        &candidate,
        options.consumer,
        options.intent,
    )?;
    let artifacts = prepare_artifacts(&candidate, options.consumer, options.environment)?;
    let mut record = ChangeProposal {
        schema_version: ProtocolVersion::Draft1,
        document_type: ProposalType::Draft1,
        profile: GovernanceProfile::Draft1,
        engine: governance_executor_id().into(),
        id: String::new(),
        digest: String::new(),
        consumer: options.consumer.into(),
        environment: options.environment.into(),
        intent: options.intent,
        proposer: options.proposer.into(),
        trust: trust.binding()?,
        baseline,
        candidate,
        artifacts: artifacts.manifest,
        requirements,
    };
    record.digest = document_digest(&record)?;
    record.id = address("change-proposal", &record.digest);
    checked(record, artifacts.files)
}
pub fn check_proposal(value: &ChangeProposal) -> Result<CheckedProposal> {
    candidate_bounds(&value.candidate)?;
    if let Some(b) = &value.baseline {
        candidate_bounds(&b.candidate)?;
    }
    // Bound recursive source/result data before any complete-record encoding.
    let value: ChangeProposal = normalized(value)?;
    header(&value.consumer, &value.environment, &value.proposer)?;
    if value.engine != governance_executor_id() {
        return fail(
            "GOVERNANCE_EXECUTOR_MISMATCH",
            "Proposal requires its exact governance executor/profile",
        );
    }
    check_address(&value, "change-proposal", &value.id, &value.digest)?;
    let candidate = normalized_candidate(&value.candidate, &value.consumer)?;
    let baseline = baseline(value.baseline.as_ref(), &value.consumer)?;
    if value.intent == DeploymentIntent::Rollback && baseline.is_none() {
        return fail(
            "GOVERNANCE_INVALID_BASELINE",
            "Rollback requires current protected baseline",
        );
    }
    let artifacts = prepare_artifacts(&candidate, &value.consumer, &value.environment)?;
    if !equal(&artifacts.manifest, &value.artifacts)? {
        return fail(
            "GOVERNANCE_ARTIFACT_MISMATCH",
            "Manifest must bind exact complete recomputed files",
        );
    }
    let requirements = classified_requirements(
        baseline.as_ref().map(|b| &b.candidate),
        &candidate,
        &value.consumer,
        value.intent,
    )?;
    if !equal(&requirements, &value.requirements)? {
        return fail(
            "GOVERNANCE_DELTA_MISMATCH",
            "Requested actions/scopes must match complete computed delta",
        );
    }
    checked(value, artifacts.files)
}
pub fn check_prepared(value: &PreparedCandidate) -> Result<CheckedProposal> {
    let mut bytes = 0usize;
    for (path, content) in &value.files {
        bytes = bytes
            .saturating_add(path.len())
            .saturating_add(content.len());
    }
    if value.files.len() > 128 || bytes > patamaps_contracts::MAX_INPUT_BYTES {
        return fail(
            "GOVERNANCE_RESOURCE_LIMIT",
            "Supplied files exceed inventory bound",
        );
    }
    let checked = check_proposal(&value.proposal)?;
    verify_artifact_bytes(&checked, &value.files)?;
    Ok(checked)
}
pub fn verify_artifact_bytes(
    proposal: &CheckedProposal,
    files: &BTreeMap<String, String>,
) -> Result<()> {
    if files != proposal.files() {
        return fail(
            "GOVERNANCE_ARTIFACT_BYTES_MISMATCH",
            "Complete file inventory or exact bytes differ from recomputed artifacts",
        );
    }
    Ok(())
}
