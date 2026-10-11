use crate::{
    error::{Result, fail},
    model::*,
    storage::{Directory, installation_file, normalized_path},
};
use patamaps_contracts::{
    ContentBinding, ProtocolVersion, canonical_bytes, canonical_digest, parse,
};
use patamaps_core::Issue;
use patamaps_governance::*;
use serde::Serialize;
use std::{
    collections::{BTreeMap, BTreeSet},
    path::{Path, PathBuf},
    sync::atomic::{AtomicU64, Ordering},
};

/// Obtained only by verifying a single pointer and its complete immutable state.
/// ```compile_fail
/// let forged: patamaps_activator::ProtectedState = serde_json::from_str("{}").unwrap();
/// ```
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProtectedState {
    manifest: ActivationManifest,
    files: BTreeMap<String, String>,
}
impl ProtectedState {
    pub fn manifest(&self) -> &ActivationManifest {
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
#[derive(Debug, Serialize)]
#[serde(tag = "status", rename_all = "kebab-case")]
pub enum ActivationOutcome {
    Activated {
        activated: bool,
        current: ProtectedState,
    },
    AlreadyActive {
        activated: bool,
        current: ProtectedState,
    },
    Rejected {
        activated: bool,
        issues: Vec<Issue>,
    },
    Indeterminate {
        activated: Option<bool>,
        issues: Vec<Issue>,
        current: Option<ProtectedState>,
    },
}
impl ActivationOutcome {
    pub fn exit_code(&self) -> u8 {
        match self {
            Self::Activated { .. } | Self::AlreadyActive { .. } => 0,
            Self::Rejected { .. } => 1,
            Self::Indeterminate { .. } => 3,
        }
    }
}

/// Host code selects this path. Incoming requests cannot change it. The fixed
/// binary selects its installed adjacent trust.json without command options.
#[derive(Debug)]
pub struct ProtectedHost {
    trust_path: PathBuf,
}
impl ProtectedHost {
    pub fn new(trust_path: impl Into<PathBuf>) -> Result<Self> {
        platform()?;
        let trust_path = trust_path.into();
        normalized_path(&trust_path)?;
        Ok(Self { trust_path })
    }
    /// An unprivileged reader can verify root-owned accepted state. Current
    /// revocation affects publication/retry, not historical accepted state.
    pub fn read(&self) -> Result<Option<ProtectedState>> {
        let (trust, state) = self.load()?;
        read_state(&trust, &state)
    }
    /// Owner administration uses the same native lock as activation. The fixed
    /// promotion service must expose only its activate command to proposers.
    /// Layout or consumer migration requires a separately provisioned host.
    pub fn replace_trust(&self, next: &TrustedConsumer) -> Result<TrustBinding> {
        if !rustix::process::geteuid().is_root() {
            return fail(
                "ACTIVATION_WRONG_UID",
                "Trust administration requires the external root owner",
            );
        }
        check_trusted_consumer(next)?;
        let (trust, state) = self.load()?;
        let held = state.lock()?;
        let (fresh, fresh_state) = self.load()?;
        if !state.same_directory(&fresh_state)?
            || canonical_digest(&trust)? != canonical_digest(&fresh)?
        {
            return fail(
                "ACTIVATION_CHANGED_HOST",
                "Configuration changed while acquiring administration lock",
            );
        }
        if next.consumer != trust.consumer
            || next.environment != trust.environment
            || next.id != trust.id
            || canonical_bytes(&next.deployment)? != canonical_bytes(&trust.deployment)?
        {
            return fail(
                "ACTIVATION_HOST_MIGRATION_REQUIRED",
                "Trust administration cannot silently change consumer or deployment layout",
            );
        }
        let digest = canonical_digest(next)?;
        if digest != canonical_digest(&trust)? {
            if next.revision == trust.revision {
                return fail(
                    "ACTIVATION_TRUST_REVISION_REQUIRED",
                    "Changed owner trust must identify a new revision",
                );
            }
            let parent =
                Directory::absolute(self.trust_path.parent().expect("validated absolute path"))?;
            let stage = stage_name("trust");
            parent.write_new(&stage, &json_bytes(next)?)?;
            parent.sync()?;
            state.assert_lock(&held)?;
            parent.rename(
                &stage,
                &parent,
                self.trust_path
                    .file_name()
                    .and_then(|p| p.to_str())
                    .expect("validated file name"),
            )?;
            parent.sync()?;
        }
        Ok(TrustBinding {
            id: next.id.clone(),
            revision: next.revision.clone(),
            digest,
        })
    }
    pub fn activate(&self, request: &ActivationRequest) -> ActivationOutcome {
        self.activate_observed(request, |_| Ok(()))
    }
    fn activate_observed(
        &self,
        request: &ActivationRequest,
        mut observe: impl FnMut(&str) -> Result<()>,
    ) -> ActivationOutcome {
        let mut committed = false;
        let result = (|| {
            if !rustix::process::geteuid().is_root() {
                return fail(
                    "ACTIVATION_WRONG_UID",
                    "Promoter must run under separately installed root service",
                );
            }
            // Direct SDK requests must obey the same wire/resource limits.
            let checked = check_prepared(&request.prepared)?;
            check_signed_approval(&request.approval)?;
            parse::<ActivationRequest>(&canonical_bytes(request)?)?;
            let (initial_trust, state) = self.load()?;
            let held = state.lock()?;
            observe("locked")?;
            let (trust, reloaded) = self.load()?;
            if !state.same_directory(&reloaded)?
                || canonical_digest(&initial_trust)? != canonical_digest(&trust)?
            {
                return fail(
                    "ACTIVATION_CHANGED_HOST",
                    "Configuration changed while acquiring state lock",
                );
            }
            let current = read_state(&trust, &state)?;
            if let Some(c) = &current
                && canonical_bytes(&c.manifest.proposal)? == canonical_bytes(checked.record())?
                && canonical_bytes(&c.manifest.approval)? == canonical_bytes(&request.approval)?
            {
                // The actual protected state establishes exact retry identity;
                // verify its original expected base rather than re-proposing it.
                verify_approval(
                    &checked,
                    &request.approval,
                    VerificationContext {
                        trust: &trust,
                        baseline: c.manifest.proposal.baseline.as_ref(),
                        now: &now(),
                    },
                )?;
                state.assert_lock(&held)?;
                return Ok(ActivationOutcome::AlreadyActive {
                    activated: false,
                    current: current.expect("matched active state"),
                });
            }
            let baseline = current.as_ref().map(ProtectedState::baseline);
            let decision_time = now();
            let accepted = verify_approval(
                &checked,
                &request.approval,
                VerificationContext {
                    trust: &trust,
                    baseline: baseline.as_ref(),
                    now: &decision_time,
                },
            )?;
            let artifacts = state.ensure_child("artifacts")?;
            let manifests = state.ensure_child("manifests")?;
            publish_artifacts(&artifacts, &checked)?;
            observe("artifacts-ready")?;
            let mut manifest = ActivationManifest {
                schema_version: ProtocolVersion::Draft1,
                document_type: ManifestType::Draft1,
                profile: ActivationProfile::Draft1,
                id: String::new(),
                digest: String::new(),
                consumer: trust.consumer.clone(),
                environment: trust.environment.clone(),
                proposal: checked.record().clone(),
                approval: accepted.approval().clone(),
                accepted_trust: accepted.accepted_trust().clone(),
                previous_manifest: baseline.as_ref().map(|b| b.manifest_digest.clone()),
                authorized_at: decision_time,
            };
            manifest.digest = document_digest(&manifest)?;
            manifest.id = addressed("activation", &manifest.digest)?;
            let manifest_name = format!("{}.json", digest_name(&manifest.digest)?);
            let bytes = json_bytes(&manifest)?;
            // Existing addressed manifests must be exact immutable records.
            if let Some(existing) = manifests.read_optional(&manifest_name, true)? {
                if existing != bytes {
                    return fail(
                        "ACTIVATION_CONTENT_MISMATCH",
                        "Existing manifest differs at claimed address",
                    );
                }
            } else {
                let stage = stage_name("manifest");
                manifests.write_new(&stage, &bytes)?;
                manifests.publish_new(&stage, &manifest_name)?;
                manifests.sync()?;
            }
            observe("manifest-ready")?;
            let pointer = ActivePointer {
                schema_version: ProtocolVersion::Draft1,
                document_type: PointerType::Draft1,
                consumer: trust.consumer.clone(),
                environment: trust.environment.clone(),
                manifest: ContentBinding {
                    id: manifest.id.clone(),
                    digest: manifest.digest.clone(),
                },
            };
            let pointer_stage = stage_name("pointer");
            state.write_new(&pointer_stage, &json_bytes(&pointer)?)?;
            state.sync()?;
            observe("precommit")?;
            // Re-read actual published bytes, current trust, current baseline,
            // lock identity and time after all durable preparation.
            let (fresh_trust, fresh_state) = self.load()?;
            if !state.same_directory(&fresh_state)?
                || canonical_digest(&trust)? != canonical_digest(&fresh_trust)?
            {
                return fail(
                    "ACTIVATION_CHANGED_HOST",
                    "Protected configuration changed during transaction",
                );
            }
            let fresh_current = read_state(&fresh_trust, &state)?;
            let fresh_baseline = fresh_current.as_ref().map(ProtectedState::baseline);
            let published = read_manifest(&fresh_trust, &state, &pointer)?;
            if canonical_bytes(&published.manifest)? != canonical_bytes(&manifest)?
                || published.files != *checked.files()
            {
                return fail(
                    "ACTIVATION_CONTENT_MISMATCH",
                    "Prepared publication changed before commit",
                );
            }
            let prepared_pointer: ActivePointer = parse(&state.read(&pointer_stage, true)?)?;
            if canonical_bytes(&prepared_pointer)? != canonical_bytes(&pointer)? {
                return fail("ACTIVATION_CONTENT_MISMATCH", "Prepared pointer changed");
            }
            state.assert_lock(&held)?;
            verify_approval(
                &checked,
                &request.approval,
                VerificationContext {
                    trust: &fresh_trust,
                    baseline: fresh_baseline.as_ref(),
                    now: &now(),
                },
            )?;
            // No untrusted observer or executable is invoked in this interval.
            state.rename(&pointer_stage, &state, "current.json")?;
            committed = true;
            state.sync()?;
            observe("committed")?;
            let current =
                read_state(&fresh_trust, &state)?.ok_or(crate::ActivationError::Refusal {
                    code: "ACTIVATION_CONTENT_MISMATCH",
                    message: "Published pointer disappeared",
                })?;
            Ok(ActivationOutcome::Activated {
                activated: true,
                current,
            })
        })();
        match result {
            Ok(outcome) => outcome,
            Err(error) if committed => ActivationOutcome::Indeterminate {
                activated: None,
                issues: error.issues(),
                current: self.read().ok().flatten(),
            },
            Err(error) => ActivationOutcome::Rejected {
                activated: false,
                issues: error.issues(),
            },
        }
    }
    fn load(&self) -> Result<(TrustedConsumer, Directory)> {
        platform()?;
        let parent =
            Directory::absolute(self.trust_path.parent().expect("normalized absolute path"))?;
        let name = self
            .trust_path
            .file_name()
            .and_then(|p| p.to_str())
            .expect("validated UTF-8 path");
        let trust: TrustedConsumer = parse(&parent.read(name, false)?)?;
        check_trusted_consumer(&trust)?;
        let Some(deployment) = &trust.deployment else {
            return fail(
                "ACTIVATION_MISSING_DEPLOYMENT",
                "Protected host requires externally bound deployment configuration",
            );
        };
        let root = Path::new(&deployment.state_directory);
        if self.trust_path.starts_with(root) {
            return fail(
                "ACTIVATION_OVERLAPPING_PATH",
                "Trust must be outside mutable state",
            );
        }
        for proposal in &deployment.proposal_roots {
            let original = Path::new(proposal);
            let actual = std::fs::canonicalize(original)?;
            for p in [original, actual.as_path()] {
                if self.trust_path.starts_with(p) || root.starts_with(p) || p.starts_with(root) {
                    return fail(
                        "ACTIVATION_OVERLAPPING_PATH",
                        "Proposal root overlaps protected configuration or state",
                    );
                }
            }
        }
        let state = Directory::absolute(root)?;
        state.local_filesystem()?;
        Ok((trust, state))
    }
}
fn platform() -> Result<()> {
    if !cfg!(target_os = "linux") {
        return fail(
            "ACTIVATION_UNSUPPORTED_HOST",
            "Protected persistence requires Linux; portable checks do not establish host isolation",
        );
    }
    Ok(())
}
pub fn check_installed_runtime(path: &Path) -> Result<()> {
    platform()?;
    installation_file(path)
}
fn now() -> String {
    let t = time::OffsetDateTime::now_utc();
    format!(
        "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}.{:03}Z",
        t.year(),
        u8::from(t.month()),
        t.day(),
        t.hour(),
        t.minute(),
        t.second(),
        t.millisecond()
    )
}
fn digest_name(s: &str) -> Result<&str> {
    if s.len() != 71
        || !s.starts_with("sha256:")
        || !s[7..]
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
    {
        return fail(
            "ACTIVATION_INVALID_DIGEST",
            "Expected exact SHA-256 address",
        );
    }
    Ok(&s[7..])
}
fn addressed(kind: &str, digest: &str) -> Result<String> {
    Ok(format!("urn:patamaps:{kind}:{}", digest_name(digest)?))
}
fn stage_name(kind: &str) -> String {
    static SEQUENCE: AtomicU64 = AtomicU64::new(0);
    format!(
        ".stage-{kind}-{}-{}-{}",
        std::process::id(),
        time::OffsetDateTime::now_utc().unix_timestamp_nanos(),
        SEQUENCE.fetch_add(1, Ordering::Relaxed)
    )
}
fn json_bytes(value: &impl Serialize) -> Result<Vec<u8>> {
    let mut bytes = canonical_bytes(value)?;
    bytes.push(b'\n');
    patamaps_contracts::parse_value(&bytes)?;
    Ok(bytes)
}
fn read_state(trust: &TrustedConsumer, state: &Directory) -> Result<Option<ProtectedState>> {
    let Some(bytes) = state.read_optional("current.json", true)? else {
        return Ok(None);
    };
    let pointer: ActivePointer = parse(&bytes)?;
    Ok(Some(read_manifest(trust, state, &pointer)?))
}
fn read_manifest(
    trust: &TrustedConsumer,
    state: &Directory,
    pointer: &ActivePointer,
) -> Result<ProtectedState> {
    if pointer.consumer != trust.consumer
        || pointer.environment != trust.environment
        || pointer.manifest.id != addressed("activation", &pointer.manifest.digest)?
    {
        return fail(
            "ACTIVATION_WRONG_POINTER",
            "Pointer does not bind configured consumer and exact manifest address",
        );
    }
    let manifests = state.child("manifests", false)?;
    let name = format!("{}.json", digest_name(&pointer.manifest.digest)?);
    let manifest: ActivationManifest = parse(&manifests.read(&name, true)?)?;
    if manifest.digest != pointer.manifest.digest
        || manifest.id != pointer.manifest.id
        || document_digest(&manifest)? != manifest.digest
        || manifest.consumer != trust.consumer
        || manifest.environment != trust.environment
        || manifest.previous_manifest
            != manifest
                .proposal
                .baseline
                .as_ref()
                .map(|b| b.manifest_digest.clone())
    {
        return fail(
            "ACTIVATION_CONTENT_MISMATCH",
            "Manifest does not bind complete historical decision",
        );
    }
    if manifest
        .accepted_trust
        .deployment
        .as_ref()
        .map(|d| &d.state_directory)
        != trust.deployment.as_ref().map(|d| &d.state_directory)
    {
        return fail(
            "ACTIVATION_WRONG_DEPLOYMENT",
            "Historical approval names another protected state root",
        );
    }
    let checked = check_proposal(&manifest.proposal)?;
    verify_approval(
        &checked,
        &manifest.approval,
        VerificationContext {
            trust: &manifest.accepted_trust,
            baseline: manifest.proposal.baseline.as_ref(),
            now: &manifest.authorized_at,
        },
    )?;
    let files = read_artifacts(&state.child("artifacts", false)?, &checked)?;
    Ok(ProtectedState { manifest, files })
}
fn read_artifacts(
    parent: &Directory,
    checked: &CheckedProposal,
) -> Result<BTreeMap<String, String>> {
    let dir = parent.child(digest_name(&checked.record().artifacts.digest)?, true)?;
    let mut expected: BTreeSet<_> = checked.files().keys().cloned().collect();
    expected.insert("artifact-manifest.json".into());
    if dir.names()? != expected {
        return fail(
            "ACTIVATION_INVENTORY_MISMATCH",
            "Artifact directory must contain exactly the complete approved inventory",
        );
    }
    if dir.read("artifact-manifest.json", true)? != json_bytes(&checked.record().artifacts)? {
        return fail(
            "ACTIVATION_CONTENT_MISMATCH",
            "Protected artifact manifest differs",
        );
    }
    let mut files = BTreeMap::new();
    for (name, expected) in checked.files() {
        let bytes = dir.read(name, true)?;
        if bytes != expected.as_bytes() {
            return fail(
                "ACTIVATION_CONTENT_MISMATCH",
                "Actual protected bytes differ from reviewed output",
            );
        }
        files.insert(name.clone(), expected.clone());
    }
    Ok(files)
}
fn publish_artifacts(parent: &Directory, checked: &CheckedProposal) -> Result<()> {
    let name = digest_name(&checked.record().artifacts.digest)?;
    match parent.child(name, true) {
        Ok(_) => {
            read_artifacts(parent, checked)?;
            return Ok(());
        }
        Err(crate::ActivationError::Io(e)) if e.kind() == std::io::ErrorKind::NotFound => (),
        Err(e) => return Err(e),
    }
    let stage = stage_name("artifacts");
    let dir = parent.create_child(&stage)?;
    for (name, bytes) in checked.files() {
        dir.write_new(name, bytes.as_bytes())?;
    }
    dir.write_new(
        "artifact-manifest.json",
        &json_bytes(&checked.record().artifacts)?,
    )?;
    dir.immutable()?;
    parent.publish_new(&stage, name)?;
    parent.sync()?;
    read_artifacts(parent, checked)?;
    Ok(())
}

#[cfg(all(test, target_os = "linux"))]
#[path = "linux_tests.rs"]
mod linux_tests;
