//! Pure authorization under explicitly supplied current context. This crate
//! cannot establish host provenance, read a clock, sign, or activate a consumer.
#![forbid(unsafe_code)]
mod approval;
mod artifacts;
mod delta;
mod model;
mod proposal;
mod trust;
mod util;
pub use approval::{
    AuthorizationRecord, AuthorizedChange, approval_signing_bytes, attach_signature,
    check_signed_approval, create_approval_payload, verify_approval,
};
pub use delta::change_requirements;
pub use model::*;
pub use proposal::{
    CheckedProposal, check_prepared, check_proposal, create_proposal, governance_executor_id,
    verify_artifact_bytes,
};
pub use trust::{check_trusted_consumer, verify_ed25519_signature};
pub use util::document_digest;

/// Deterministic, replay-checked artifact bytes. This carries no authorization.
/// ```compile_fail
/// let forged: patamaps_governance::CheckedArtifacts = serde_json::from_str("{}").unwrap();
/// ```
#[derive(Debug)]
pub struct CheckedArtifacts {
    manifest: ArtifactManifest,
    files: std::collections::BTreeMap<String, String>,
}
impl CheckedArtifacts {
    pub fn manifest(&self) -> &ArtifactManifest {
        &self.manifest
    }
    pub fn files(&self) -> &std::collections::BTreeMap<String, String> {
        &self.files
    }
}
/// Reuses proposal preparation without pretending that preparation is approval.
pub fn prepare_candidate_artifacts(
    candidate: &GovernedCandidate,
    consumer: &str,
    environment: &str,
) -> util::Result<CheckedArtifacts> {
    prepare(candidate, consumer, environment, true)
}

/// Prepare exploratory outputs while retaining missing source receipts as
/// references. Proposal and authorization entry points still require all source
/// bytes and independently reproduce their artifacts.
pub fn prepare_reference_artifacts(
    candidate: &GovernedCandidate,
    consumer: &str,
    environment: &str,
) -> util::Result<CheckedArtifacts> {
    prepare(candidate, consumer, environment, false)
}

fn prepare(
    candidate: &GovernedCandidate,
    consumer: &str,
    environment: &str,
    require_source_bytes: bool,
) -> util::Result<CheckedArtifacts> {
    if !patamaps_core::valid_identifier(consumer)
        || environment.is_empty()
        || environment.len() > 4096
    {
        return util::fail(
            "GOVERNANCE_INVALID_CONTEXT",
            "Invalid artifact consumer/environment",
        );
    }
    let candidate = if require_source_bytes {
        artifacts::normalized_candidate(candidate, consumer)?
    } else {
        artifacts::normalized_reference_candidate(candidate, consumer)?
    };
    let prepared = artifacts::prepare_artifacts(&candidate, consumer, environment)?;
    Ok(CheckedArtifacts {
        manifest: prepared.manifest,
        files: prepared.files,
    })
}
