//! Explicit portable memory activation, with owner-provided current context.
use crate::{
    ActivationError, ActivationRequest,
    error::{Result, fail},
};
use patamaps_contracts::{ProtocolVersion, canonical_bytes, canonical_digest, parse, parse_value};
use patamaps_governance::{
    ChangeProposal, GovernedBaseline, PreparedCandidate, PreparedType, SignedApproval,
    TrustedConsumer, VerificationContext, check_prepared, check_trusted_consumer, document_digest,
    governance_executor_id, verify_approval,
};
use serde::{Deserialize, Serialize};
use std::{
    collections::BTreeMap,
    panic::{AssertUnwindSafe, catch_unwind},
    sync::OnceLock,
};

pub const MEMORY_PROFILE: &str = "patamaps-memory-draft-1";

/// Source identity, not authentication of a host or a reproducible binary.
pub fn memory_executor_id() -> &'static str {
    static ID: OnceLock<String> = OnceLock::new();
    ID.get_or_init(|| {
        canonical_digest(&serde_json::json!({
            "profile": MEMORY_PROFILE,
            "governance": governance_executor_id(),
            "manifest": include_str!("../Cargo.toml"),
            "lib": include_str!("lib.rs"),
            "model": include_str!("model.rs"),
            "memory": include_str!("memory.rs"),
            "error": include_str!("error.rs")
        }))
        .expect("embedded source is JSON")
    })
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum MemoryProfile {
    #[serde(rename = "patamaps-memory-draft-1")]
    Draft1,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum MemoryManifestType {
    #[serde(rename = "memory-activation-manifest")]
    Draft1,
}

/// Untrusted transport. Verification is required before historical use.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct MemoryManifest {
    pub schema_version: ProtocolVersion,
    pub document_type: MemoryManifestType,
    pub profile: MemoryProfile,
    pub executor: String,
    pub id: String,
    pub digest: String,
    pub consumer: String,
    pub environment: String,
    pub proposal: ChangeProposal,
    pub approval: SignedApproval,
    pub accepted_trust: TrustedConsumer,
    #[serde(deserialize_with = "patamaps_contracts::nullable")]
    pub previous_manifest: Option<String>,
    pub authorized_at: String,
}

/// Historical checked evidence; only a host transition selects active state.
///
/// ```compile_fail
/// let forged: patamaps_activator::MemoryState = serde_json::from_str("{}").unwrap();
/// ```
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MemoryState {
    manifest: MemoryManifest,
    files: BTreeMap<String, String>,
}

impl MemoryState {
    pub fn manifest(&self) -> &MemoryManifest {
        &self.manifest
    }

    pub fn files(&self) -> &BTreeMap<String, String> {
        &self.files
    }

    pub fn baseline(&self) -> GovernedBaseline {
        GovernedBaseline {
            manifest_digest: self.manifest.digest.clone(),
            candidate: self.manifest.proposal.candidate.clone(),
        }
    }
}

fn memory_trust(trust: &TrustedConsumer) -> Result<()> {
    check_trusted_consumer(trust)?;
    if trust.deployment.is_some() {
        return fail(
            "ACTIVATION_MEMORY_PROFILE_REQUIRED",
            "Memory trust cannot name a protected Linux deployment",
        );
    }
    Ok(())
}

fn manifest_id(digest: &str) -> String {
    // Called only with a freshly calculated canonical SHA-256 digest.
    format!("urn:patamaps:memory-activation:{}", &digest[7..])
}

/// Recompute historical memory evidence. Recorded trust/time do not establish
/// present authorization, and this result cannot restore a host's active state.
pub fn verify_memory_state(
    manifest: &MemoryManifest,
    files: &BTreeMap<String, String>,
) -> Result<MemoryState> {
    let manifest: MemoryManifest = parse(&canonical_bytes(manifest)?)?;
    if manifest.executor != memory_executor_id() {
        return fail("ACTIVATION_FOREIGN_EXECUTOR", "Memory executor differs");
    }
    let digest = document_digest(&manifest)?;
    if manifest.digest != digest || manifest.id != manifest_id(&digest) {
        return fail(
            "ACTIVATION_CONTENT_MISMATCH",
            "Memory manifest address differs",
        );
    }
    memory_trust(&manifest.accepted_trust)?;
    if manifest.consumer != manifest.accepted_trust.consumer
        || manifest.environment != manifest.accepted_trust.environment
        || manifest.previous_manifest
            != manifest
                .proposal
                .baseline
                .as_ref()
                .map(|b| b.manifest_digest.clone())
    {
        return fail(
            "ACTIVATION_CONTENT_MISMATCH",
            "Memory manifest binding differs",
        );
    }
    let checked = check_prepared(&PreparedCandidate {
        schema_version: ProtocolVersion::Draft1,
        document_type: PreparedType::Draft1,
        proposal: manifest.proposal.clone(),
        files: files.clone(),
    })?;
    verify_approval(
        &checked,
        &manifest.approval,
        VerificationContext {
            trust: &manifest.accepted_trust,
            baseline: manifest.proposal.baseline.as_ref(),
            now: &manifest.authorized_at,
        },
    )?;
    let state = MemoryState {
        manifest,
        files: checked.files().clone(),
    };
    // The complete evidence, including files, must obey the ingress bounds.
    parse_value(&canonical_bytes(&state)?)?;
    Ok(state)
}

/// Obtained by trusted host code; this is deliberately absent from requests.
#[derive(Debug, Clone)]
pub struct MemoryContext {
    pub trust: TrustedConsumer,
    pub now: String,
}

#[derive(Debug, Serialize)]
#[serde(tag = "status", rename_all = "kebab-case")]
pub enum MemoryActivation<'a> {
    Activated { current: &'a MemoryState },
    AlreadyActive { current: &'a MemoryState },
}

/// An owner-selected context provider and one immutable accepted state.
///
/// `&mut self` serializes transitions. The provider is trusted in-process host
/// code, not a sandbox. Revocation does not erase historical accepted state;
/// it prevents later publication and retry. This host performs no filesystem
/// persistence and cannot establish independent-UID or crash guarantees.
pub struct MemoryHost<F> {
    authority: F,
    trust_id: String,
    consumer: String,
    environment: String,
    current: Option<MemoryState>,
}

impl<F> MemoryHost<F>
where
    F: Fn() -> std::result::Result<MemoryContext, ActivationError>,
{
    pub fn new(authority: F) -> Result<Self> {
        let initial = owner_context(&authority)?;
        memory_trust(&initial.trust)?;
        Ok(Self {
            authority,
            trust_id: initial.trust.id,
            consumer: initial.trust.consumer,
            environment: initial.trust.environment,
            current: None,
        })
    }

    pub fn current(&self) -> Option<&MemoryState> {
        self.current.as_ref()
    }

    pub fn activate(&mut self, request: &ActivationRequest) -> Result<MemoryActivation<'_>> {
        let changed = self.transition(request)?;
        let current = self
            .current
            .as_ref()
            .expect("successful transition has state");
        Ok(if changed {
            MemoryActivation::Activated { current }
        } else {
            MemoryActivation::AlreadyActive { current }
        })
    }

    fn context(&self) -> Result<MemoryContext> {
        let context = owner_context(&self.authority)?;
        memory_trust(&context.trust)?;
        if context.trust.id != self.trust_id
            || context.trust.consumer != self.consumer
            || context.trust.environment != self.environment
        {
            return fail(
                "ACTIVATION_HOST_MIGRATION_REQUIRED",
                "Owner context cannot silently change host identity or environment",
            );
        }
        Ok(context)
    }

    fn transition(&mut self, request: &ActivationRequest) -> Result<bool> {
        // Typed library callers obey the same closed ingress as transport.
        let checked = check_prepared(&request.prepared)?;
        let request: ActivationRequest = parse(&canonical_bytes(request)?)?;
        let context = self.context()?;
        let retry = match &self.current {
            Some(state) => {
                canonical_bytes(&state.manifest.proposal)? == canonical_bytes(checked.record())?
                    && canonical_bytes(&state.manifest.approval)?
                        == canonical_bytes(&request.approval)?
            }
            None => false,
        };
        let baseline = if retry {
            self.current
                .as_ref()
                .and_then(|s| s.manifest.proposal.baseline.clone())
        } else {
            self.current.as_ref().map(MemoryState::baseline)
        };
        let accepted = verify_approval(
            &checked,
            &request.approval,
            VerificationContext {
                trust: &context.trust,
                baseline: baseline.as_ref(),
                now: &context.now,
            },
        )?;
        let next = if retry {
            None
        } else {
            let mut manifest = MemoryManifest {
                schema_version: ProtocolVersion::Draft1,
                document_type: MemoryManifestType::Draft1,
                profile: MemoryProfile::Draft1,
                executor: memory_executor_id().into(),
                id: String::new(),
                digest: String::new(),
                consumer: self.consumer.clone(),
                environment: self.environment.clone(),
                proposal: checked.record().clone(),
                approval: accepted.approval().clone(),
                accepted_trust: accepted.accepted_trust().clone(),
                previous_manifest: baseline.as_ref().map(|b| b.manifest_digest.clone()),
                authorized_at: context.now,
            };
            manifest.digest = document_digest(&manifest)?;
            manifest.id = manifest_id(&manifest.digest);
            Some(verify_memory_state(&manifest, checked.files())?)
        };
        // Re-read current authority after preparation, including identical
        // retries. No owner callback occurs between verification and commit.
        let fresh = self.context()?;
        verify_approval(
            &checked,
            &request.approval,
            VerificationContext {
                trust: &fresh.trust,
                baseline: baseline.as_ref(),
                now: &fresh.now,
            },
        )?;
        if let Some(next) = next {
            self.current = Some(next);
            Ok(true)
        } else {
            Ok(false)
        }
    }
}

fn owner_context<F>(authority: &F) -> Result<MemoryContext>
where
    F: Fn() -> std::result::Result<MemoryContext, ActivationError>,
{
    match catch_unwind(AssertUnwindSafe(authority)) {
        Ok(Ok(context)) => Ok(context),
        _ => fail(
            "ACTIVATION_HOST_UNAVAILABLE",
            "Owner context is unavailable",
        ),
    }
}
