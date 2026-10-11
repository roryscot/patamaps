//! Real Linux/root process tests, compiled only into the test executable.
use super::*;
use base64::{Engine, engine::general_purpose::STANDARD};
use ed25519_dalek::{Signer, SigningKey};
use patamaps_contracts::*;
use patamaps_projection::{CaptureInputs, SourceReceipt, capture};
use serde::{Serialize, de::DeserializeOwned};
use serde_json::{Value, json};
use std::{
    fs,
    io::Write,
    os::unix::{
        fs::{PermissionsExt, symlink},
        process::CommandExt,
    },
    process::{Command, Stdio},
    thread,
    time::{Duration, Instant},
};

#[path = "../tests/support/lifecycle.rs"]
mod lifecycle_fixture;

fn typed<T: DeserializeOwned>(value: Value) -> T {
    parse(&canonical_bytes(&value).unwrap()).unwrap()
}
fn write(path: &Path, data: &impl Serialize) {
    fs::write(path, canonical_bytes(data).unwrap()).unwrap();
}
fn chmod(path: &Path, mode: u32) {
    fs::set_permissions(path, fs::Permissions::from_mode(mode)).unwrap();
}
fn assert_rejected(outcome: ActivationOutcome, code: &str) {
    let ActivationOutcome::Rejected { issues, .. } = outcome else {
        panic!("expected rejection: {outcome:?}")
    };
    assert!(
        issues.iter().any(|i| i.code == code),
        "expected {code}: {issues:?}"
    );
}
fn root() {
    assert!(
        rustix::process::geteuid().is_root(),
        "Linux lifecycle tests require a disposable root test host"
    );
}
struct Fixture {
    dir: PathBuf,
    host: ProtectedHost,
    trust: TrustedConsumer,
}
impl Fixture {
    fn new() -> Self {
        root();
        let dir = std::env::temp_dir().join(stage_name("linux-test"));
        fs::create_dir(&dir).unwrap();
        chmod(&dir, 0o755);
        fs::create_dir(dir.join("state")).unwrap();
        fs::create_dir(dir.join("proposals")).unwrap();
        chmod(&dir.join("proposals"), 0o777);
        let signing = SigningKey::from_bytes(&[29; 32]);
        let mut der = vec![
            0x30, 0x2a, 0x30, 0x05, 0x06, 0x03, 0x2b, 0x65, 0x70, 0x03, 0x21, 0,
        ];
        der.extend(signing.verifying_key().as_bytes());
        let from = "2020-01-01T00:00:00.000Z";
        let until = "2099-01-01T00:00:00.000Z";
        let trust = typed(
            json!({"schemaVersion":"0.1.0","documentType":"trusted-consumer","mode":"governed","id":"urn:trust:linux","revision":"1","consumer":"urn:consumer:linux","environment":"test","principals":[{"id":"owner","role":"owner","revoked":false}],"keys":[{"id":"key","principal":"owner","algorithm":"Ed25519","publicKey":STANDARD.encode(der),"validFrom":from,"validUntil":until,"revoked":false}],"grants":[{"id":"grant","principal":"owner","actions":["activate","bootstrap","rollback","rebind-implementation","change-graph","change-authority","change-policy","relax-policy","raise-budget","add-waiver","change-law","change-source","change-context","change-projection"],"scopes":[{"subject":"*","fact":"*"}],"validFrom":from,"validUntil":until,"revoked":false}],"deployment":{"profile":"patamaps-linux-root-draft-1","stateDirectory":dir.join("state"),"proposalRoots":[dir.join("proposals")]}}),
        );
        write(&dir.join("trust.json"), &trust);
        chmod(&dir.join("trust.json"), 0o644);
        let host = ProtectedHost::new(dir.join("trust.json")).unwrap();
        Self { dir, host, trust }
    }
    fn request(
        &self,
        revision: &str,
        baseline: Option<&GovernedBaseline>,
        intent: DeploymentIntent,
    ) -> ActivationRequest {
        self.request_at(revision, baseline, intent, "service")
    }
    fn request_at(
        &self,
        revision: &str,
        baseline: Option<&GovernedBaseline>,
        intent: DeploymentIntent,
        module: &str,
    ) -> ActivationRequest {
        let locator = format!("rust:crate::{module}::greet");
        let graph = typed(
            json!({"schemaVersion":"0.1.0","documentType":"graph","id":"urn:graph:linux","namespace":"linux","revision":revision,"entities":[{"id":"urn:command:greet","kind":"routing:command","attributes":{"path":"/greet/:id"}},{"id":"urn:handler:greet","kind":"routing:handler","locators":[{"uri":locator}]}],"mappings":[{"id":"urn:mapping:greet","relation":"routing:handled_by","sources":["urn:command:greet"],"targets":["urn:handler:greet"],"cardinality":"one-to-one","lossiness":"lossless","provenance":{"status":"declared","assertedBy":"proposer"}}],"authorities":[]}),
        );
        let policy = typed(
            json!({"schemaVersion":"0.1.0","documentType":"policy","id":"urn:policy:linux","graph":{"id":"urn:graph:linux","revision":revision},"mappings":[{"mapping":"urn:mapping:greet","coverage":"total","determinism":"deterministic","reversibility":"irreversible"}],"constraints":[],"evidence":[]}),
        );
        let spec = typed(
            json!({"schemaVersion":"0.1.0","documentType":"projection-spec","id":"urn:projection:linux","consumer":"urn:consumer:linux","select":{"ids":["urn:command:greet"]},"slots":[{"name":"handler","relation":"routing:handled_by","direction":"outgoing","cardinality":"exactly-one","targetKinds":["routing:handler"]}],"pathTree":{}}),
        );
        let source = "pub fn greet(input:&str)->String{format!(\"Hello, {}!\",input)}\n";
        let captured = capture(
            CaptureInputs {
                graph,
                packs: vec![parse(include_bytes!("../../../relation-packs/routing.json")).unwrap()],
                policy,
                context: Default::default(),
                evaluated_at: "2026-10-10T00:00:00Z".into(),
                projection_spec: Some(spec),
            },
            vec![SourceReceipt {
                id: "urn:source:linux".into(),
                locator: format!("rust:crate::{module}"),
                digest: byte_digest(source.as_bytes()),
                byte_length: SafeInteger::new(source.len() as u64).unwrap(),
                content: Some(source.into()),
            }],
        )
        .unwrap();
        let candidate = GovernedCandidate {
            captures: vec![captured],
            emissions: vec![ArtifactEmission {
                projection: "urn:projection:linux".into(),
                language: EmissionLanguage::Rust,
                binding_slot: Some("handler".into()),
            }],
        };
        self.sign_candidate(&candidate, baseline, intent)
    }
    fn budgeted_request(
        &self,
        revision: &str,
        baseline: Option<&GovernedBaseline>,
        intent: DeploymentIntent,
        module: &str,
    ) -> ActivationRequest {
        let candidate = GovernedCandidate {
            captures: vec![lifecycle_fixture::consumer_capture(revision, module)],
            emissions: vec![ArtifactEmission {
                projection: "urn:projection:linux".into(),
                language: EmissionLanguage::Rust,
                binding_slot: Some("handler".into()),
            }],
        };
        self.sign_candidate(&candidate, baseline, intent)
    }
    fn sign_candidate(
        &self,
        candidate: &GovernedCandidate,
        baseline: Option<&GovernedBaseline>,
        intent: DeploymentIntent,
    ) -> ActivationRequest {
        let checked = create_proposal(
            candidate,
            ProposalOptions {
                consumer: &self.trust.consumer,
                environment: &self.trust.environment,
                proposer: "proposer",
                intent,
                trust: &self.trust,
                baseline,
            },
        )
        .unwrap();
        let issued = now();
        let expires = timestamp(time::OffsetDateTime::now_utc() + time::Duration::minutes(5));
        let payload = create_approval_payload(
            &checked,
            ApprovalOptions {
                principal: "owner",
                key: "key",
                grants: &["grant".into()],
                issued_at: &issued,
                expires_at: &expires,
            },
        )
        .unwrap();
        let signature =
            SigningKey::from_bytes(&[29; 32]).sign(&approval_signing_bytes(&payload).unwrap());
        ActivationRequest {
            schema_version: ProtocolVersion::Draft1,
            document_type: RequestType::Draft1,
            prepared: checked.prepared(),
            approval: attach_signature(payload, &STANDARD.encode(signature.to_bytes())).unwrap(),
        }
    }
    fn child(
        &self,
        request: &ActivationRequest,
        pause: Option<&str>,
        action: &str,
    ) -> std::process::Child {
        let request_path = self.dir.join(stage_name("request"));
        write(&request_path, request);
        let mut command = Command::new(std::env::current_exe().unwrap());
        command
            .args([
                "--exact",
                "transaction::linux_tests::child_driver",
                "--nocapture",
            ])
            .env("PATAMAPS_TEST_TRUST", self.dir.join("trust.json"))
            .env("PATAMAPS_TEST_REQUEST", request_path)
            .env("PATAMAPS_TEST_ACTION", action)
            .env("PATAMAPS_TEST_PAUSE", pause.unwrap_or(""))
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        command.spawn().unwrap()
    }
    fn phase(&self, phase: &str) {
        let limit = Instant::now() + Duration::from_secs(15);
        loop {
            if fs::read_to_string(self.dir.join("phase")).ok().as_deref() == Some(phase) {
                return;
            };
            assert!(Instant::now() < limit, "phase {phase} never reached");
            thread::sleep(Duration::from_millis(10));
        }
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.dir);
    }
}
fn timestamp(t: time::OffsetDateTime) -> String {
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

#[test]
fn child_driver() {
    let Some(path) = std::env::var_os("PATAMAPS_TEST_TRUST") else {
        return;
    };
    let host = ProtectedHost::new(PathBuf::from(path)).unwrap();
    let request: ActivationRequest =
        parse(&fs::read(std::env::var_os("PATAMAPS_TEST_REQUEST").unwrap()).unwrap()).unwrap();
    if std::env::var("PATAMAPS_TEST_ACTION").unwrap() == "read" {
        assert!(host.read().unwrap().is_some());
        return;
    }
    root();
    let pause = std::env::var("PATAMAPS_TEST_PAUSE").unwrap();
    let outcome = host.activate_observed(&request, |phase| {
        if pause == phase {
            fs::write(host.trust_path.parent().unwrap().join("phase"), phase).unwrap();
            loop {
                thread::sleep(Duration::from_secs(1));
            }
        }
        Ok(())
    });
    match outcome {
        ActivationOutcome::Activated { .. } | ActivationOutcome::AlreadyActive { .. } => (),
        other => panic!("child activation: {other:?}"),
    }
}

#[test]
fn complete_publication_retry_current_revocation_and_fresh_rollback() {
    let f = Fixture::new();
    assert!(f.host.read().unwrap().is_none());
    let first = f.request("1", None, DeploymentIntent::Deploy);
    assert!(matches!(
        f.host.activate(&first),
        ActivationOutcome::Activated { .. }
    ));
    let old = f.host.read().unwrap().unwrap();
    assert_eq!(old.files, first.prepared.files);
    let pointer = fs::read(f.dir.join("state/current.json")).unwrap();
    assert!(matches!(
        f.host.activate(&first),
        ActivationOutcome::AlreadyActive { .. }
    ));
    assert_eq!(pointer, fs::read(f.dir.join("state/current.json")).unwrap());
    let mut revoked = f.trust.clone();
    revoked.keys[0].revoked = true;
    write(&f.dir.join("trust.json"), &revoked);
    let outcome = f.host.activate(&first);
    assert!(matches!(outcome, ActivationOutcome::Rejected { .. }));
    assert_eq!(
        f.host.read().unwrap().unwrap().manifest.digest,
        old.manifest.digest
    );
    write(&f.dir.join("trust.json"), &f.trust);
    let next = f.request("2", Some(&old.baseline()), DeploymentIntent::Deploy);
    assert!(matches!(
        f.host.activate(&next),
        ActivationOutcome::Activated { .. }
    ));
    assert_rejected(f.host.activate(&first), "GOVERNANCE_STALE_BASELINE");
    let current = f.host.read().unwrap().unwrap();
    let rollback = f.request("1", Some(&current.baseline()), DeploymentIntent::Rollback);
    assert!(matches!(
        f.host.activate(&rollback),
        ActivationOutcome::Activated { .. }
    ));
    assert_eq!(f.host.read().unwrap().unwrap().files, old.files);
}

#[test]
fn owner_trust_administration_holds_promotion_lock_and_preserves_host_layout() {
    let f = Fixture::new();
    let request = f.request("1", None, DeploymentIntent::Deploy);
    assert!(matches!(
        f.host.activate(&request),
        ActivationOutcome::Activated { .. }
    ));
    let accepted = f.host.read().unwrap().unwrap().manifest.digest;
    let mut next = f.trust.clone();
    next.keys[0].revoked = true;
    assert!(
        f.host
            .replace_trust(&next)
            .unwrap_err()
            .to_string()
            .contains("ACTIVATION_TRUST_REVISION_REQUIRED")
    );
    next.revision = "2".into();
    let state = Directory::absolute(&f.dir.join("state")).unwrap();
    let held = state.lock().unwrap();
    assert!(
        f.host
            .replace_trust(&next)
            .unwrap_err()
            .to_string()
            .contains("ACTIVATION_BUSY")
    );
    drop(held);
    let binding = f.host.replace_trust(&next).unwrap();
    assert_eq!(binding.digest, canonical_digest(&next).unwrap());
    assert_eq!(f.host.replace_trust(&next).unwrap().digest, binding.digest);
    assert_eq!(f.host.read().unwrap().unwrap().manifest.digest, accepted);
    assert!(matches!(
        f.host.activate(&request),
        ActivationOutcome::Rejected { .. }
    ));
    let mut migrated = next;
    migrated.revision = "3".into();
    migrated.environment = "different-host".into();
    assert!(
        f.host
            .replace_trust(&migrated)
            .unwrap_err()
            .to_string()
            .contains("ACTIVATION_HOST_MIGRATION_REQUIRED")
    );
}

#[test]
fn distinct_proposer_uid_cannot_modify_trust_lock_pointer_runtime_or_artifacts() {
    let f = Fixture::new();
    let request = f.request("1", None, DeploymentIntent::Deploy);
    assert!(matches!(
        f.host.activate(&request),
        ActivationOutcome::Activated { .. }
    ));
    // A fixed protected runtime and owner-only synthetic secret are separately
    // installed in this disposable host; neither enters proposal records.
    fs::copy(std::env::current_exe().unwrap(), f.dir.join("runtime")).unwrap();
    chmod(&f.dir.join("runtime"), 0o555);
    fs::write(f.dir.join("owner-secret"), b"synthetic test secret").unwrap();
    chmod(&f.dir.join("owner-secret"), 0o600);
    let active = f.host.read().unwrap().unwrap();
    // Execute the protected native reader under the separate proposer/consumer UID.
    let request_path = f.dir.join("reader-request.json");
    write(&request_path, &request);
    let reader = Command::new(f.dir.join("runtime"))
        .args([
            "--exact",
            "transaction::linux_tests::child_driver",
            "--nocapture",
        ])
        .env("PATAMAPS_TEST_TRUST", f.dir.join("trust.json"))
        .env("PATAMAPS_TEST_REQUEST", &request_path)
        .env("PATAMAPS_TEST_ACTION", "read")
        .env("PATAMAPS_TEST_PAUSE", "")
        .uid(65534)
        .gid(65534)
        .output()
        .unwrap();
    assert!(
        reader.status.success(),
        "{}",
        String::from_utf8_lossy(&reader.stderr)
    );
    let artifacts = f
        .dir
        .join("state/artifacts")
        .join(digest_name(&active.manifest.proposal.artifacts.digest).unwrap());
    let manifest = f.dir.join("state/manifests").join(format!(
        "{}.json",
        digest_name(&active.manifest.digest).unwrap()
    ));
    for path in [
        f.dir.join("trust.json"),
        f.dir.join("runtime"),
        f.dir.join("state/.promotion.lock"),
        f.dir.join("state/current.json"),
        manifest,
        artifacts.join("bindings-0.rs"),
    ] {
        for operation in ["printf tampered > \"$1\"", "chmod 777 \"$1\"", "rm \"$1\""] {
            let output = Command::new("/bin/sh")
                .args(["-c", operation, "denial", path.to_str().unwrap()])
                .uid(65534)
                .gid(65534)
                .output()
                .unwrap();
            assert!(
                !output.status.success(),
                "proposer changed {}",
                path.display()
            );
        }
    }
    assert!(
        !Command::new("/bin/cat")
            .arg(f.dir.join("owner-secret"))
            .uid(65534)
            .gid(65534)
            .status()
            .unwrap()
            .success()
    );
    let output = Command::new("/bin/sh")
        .args([
            "-c",
            "printf writable > \"$1\"",
            "proposal",
            f.dir.join("proposals/new").to_str().unwrap(),
        ])
        .uid(65534)
        .gid(65534)
        .output()
        .unwrap();
    assert!(output.status.success());
    assert!(
        Command::new("/bin/cat")
            .arg(artifacts.join("bindings-0.rs"))
            .uid(65534)
            .gid(65534)
            .output()
            .unwrap()
            .status
            .success()
    );
    // The native reader does not appoint its own UID as a filesystem root.
    fs::copy(
        f.dir.join("state/current.json"),
        f.dir.join("proposals/copied-pointer"),
    )
    .unwrap();
    let status = Command::new("/usr/bin/chown")
        .args([
            "65534:65534",
            f.dir.join("proposals/copied-pointer").to_str().unwrap(),
        ])
        .status()
        .unwrap();
    assert!(status.success());
    fs::remove_file(f.dir.join("state/current.json")).unwrap();
    fs::rename(
        f.dir.join("proposals/copied-pointer"),
        f.dir.join("state/current.json"),
    )
    .unwrap();
    assert_eq!(
        f.host.read().unwrap_err().code(),
        "ACTIVATION_UNPROTECTED_FILE"
    );
}

#[test]
fn symlinks_hardlinks_and_complete_inventory_swaps_refuse() {
    let f = Fixture::new();
    let request = f.request("1", None, DeploymentIntent::Deploy);
    fs::rename(f.dir.join("trust.json"), f.dir.join("real-trust")).unwrap();
    symlink("real-trust", f.dir.join("trust.json")).unwrap();
    assert!(f.host.read().is_err());
    fs::remove_file(f.dir.join("trust.json")).unwrap();
    fs::rename(f.dir.join("real-trust"), f.dir.join("trust.json")).unwrap();
    fs::hard_link(f.dir.join("trust.json"), f.dir.join("linked-trust")).unwrap();
    assert_eq!(
        f.host.read().unwrap_err().code(),
        "ACTIVATION_UNPROTECTED_FILE"
    );
    fs::remove_file(f.dir.join("linked-trust")).unwrap();
    assert!(matches!(
        f.host.activate(&request),
        ActivationOutcome::Activated { .. }
    ));
    let current = f.host.read().unwrap().unwrap();
    let dir = f
        .dir
        .join("state/artifacts")
        .join(digest_name(&current.manifest.proposal.artifacts.digest).unwrap());
    chmod(&dir, 0o755);
    fs::write(dir.join("extra"), b"unexpected").unwrap();
    chmod(&dir.join("extra"), 0o444);
    chmod(&dir, 0o555);
    assert_eq!(
        f.host.read().unwrap_err().code(),
        "ACTIVATION_INVENTORY_MISMATCH"
    );
}

#[test]
fn concurrent_stale_base_cannot_both_publish_and_readers_bind_one_generation() {
    let f = Fixture::new();
    let first = f.request("1", None, DeploymentIntent::Deploy);
    assert!(matches!(
        f.host.activate(&first),
        ActivationOutcome::Activated { .. }
    ));
    let old = f.host.read().unwrap().unwrap();
    let next = f.request("2", Some(&old.baseline()), DeploymentIntent::Deploy);
    let other = f.request("3", Some(&old.baseline()), DeploymentIntent::Deploy);
    let mut child = f.child(&next, Some("precommit"), "activate");
    f.phase("precommit");
    assert_rejected(f.host.activate(&other), "ACTIVATION_BUSY");
    for _ in 0..3 {
        assert_eq!(
            f.host.read().unwrap().unwrap().manifest.digest,
            old.manifest.digest
        );
    }
    child.kill().unwrap();
    child.wait().unwrap();
    assert_eq!(
        f.host.read().unwrap().unwrap().manifest.digest,
        old.manifest.digest
    );
    assert!(matches!(
        f.host.activate(&next),
        ActivationOutcome::Activated { .. }
    ));
    assert_rejected(f.host.activate(&other), "GOVERNANCE_STALE_BASELINE");
    let new = f.host.read().unwrap().unwrap();
    assert_eq!(new.files, next.prepared.files);
}

#[test]
fn real_sigkill_at_all_five_phases_preserves_one_complete_pointer() {
    for phase in [
        "locked",
        "artifacts-ready",
        "manifest-ready",
        "precommit",
        "committed",
    ] {
        let f = Fixture::new();
        let first = f.request("1", None, DeploymentIntent::Deploy);
        assert!(matches!(
            f.host.activate(&first),
            ActivationOutcome::Activated { .. }
        ));
        let old = f.host.read().unwrap().unwrap();
        let next = f.request("2", Some(&old.baseline()), DeploymentIntent::Deploy);
        let mut child = f.child(&next, Some(phase), "activate");
        f.phase(phase);
        child.kill().unwrap();
        let status = child.wait().unwrap();
        assert!(!status.success());
        let current = f.host.read().unwrap().unwrap();
        if phase == "committed" {
            assert_eq!(current.files, next.prepared.files);
            assert!(matches!(
                f.host.activate(&next),
                ActivationOutcome::AlreadyActive { .. }
            ));
        } else {
            assert_eq!(current.manifest.digest, old.manifest.digest);
            assert_eq!(current.files, old.files);
            assert!(matches!(
                f.host.activate(&next),
                ActivationOutcome::Activated { .. }
            ));
        }
    }
}

#[test]
fn precommit_revocation_expiry_lost_lock_and_postcommit_failure_are_distinct() {
    for change in ["revocation", "expiry", "lock", "swap", "response"] {
        let f = Fixture::new();
        let first = f.request("1", None, DeploymentIntent::Deploy);
        assert!(matches!(
            f.host.activate(&first),
            ActivationOutcome::Activated { .. }
        ));
        let old = f.host.read().unwrap().unwrap();
        let mut next = f.request("2", Some(&old.baseline()), DeploymentIntent::Deploy);
        if change == "expiry" {
            let checked = check_prepared(&next.prepared).unwrap();
            let issued = now();
            let expires = timestamp(time::OffsetDateTime::now_utc() + time::Duration::seconds(2));
            let payload = create_approval_payload(
                &checked,
                ApprovalOptions {
                    principal: "owner",
                    key: "key",
                    grants: &["grant".into()],
                    issued_at: &issued,
                    expires_at: &expires,
                },
            )
            .unwrap();
            next.approval = attach_signature(
                payload.clone(),
                &STANDARD.encode(
                    SigningKey::from_bytes(&[29; 32])
                        .sign(&approval_signing_bytes(&payload).unwrap())
                        .to_bytes(),
                ),
            )
            .unwrap();
        }
        let outcome = f.host.activate_observed(&next, |phase| {
            if phase == "precommit" {
                match change {
                    "revocation" => {
                        let mut trust = f.trust.clone();
                        trust.keys[0].revoked = true;
                        write(&f.dir.join("trust.json"), &trust);
                    }
                    "expiry" => {
                        while now() < next.approval.payload.expires_at {
                            thread::sleep(Duration::from_millis(10));
                        }
                    }
                    "lock" => {
                        fs::remove_file(f.dir.join("state/.promotion.lock")).unwrap();
                        fs::write(f.dir.join("state/.promotion.lock"), b"").unwrap();
                        chmod(&f.dir.join("state/.promotion.lock"), 0o600);
                    }
                    "swap" => {
                        let path = f
                            .dir
                            .join("state/artifacts")
                            .join(digest_name(&next.prepared.proposal.artifacts.digest).unwrap())
                            .join("bindings-0.rs");
                        chmod(&path, 0o644);
                        fs::write(&path, b"changed").unwrap();
                        chmod(&path, 0o444);
                    }
                    _ => (),
                }
            }
            if phase == "committed" && change == "response" {
                return fail(
                    "ACTIVATION_TEST_RESPONSE_FAILURE",
                    "Synthetic response failure after commit",
                );
            }
            Ok(())
        });
        if change == "response" {
            assert!(matches!(
                outcome,
                ActivationOutcome::Indeterminate {
                    activated: None,
                    current: Some(_),
                    ..
                }
            ));
            assert_eq!(f.host.read().unwrap().unwrap().files, next.prepared.files);
        } else {
            assert!(
                matches!(outcome, ActivationOutcome::Rejected { .. }),
                "{change}: {outcome:?}"
            );
            if change != "swap" {
                assert_eq!(
                    f.host.read().unwrap().unwrap().manifest.digest,
                    old.manifest.digest
                );
            }
        }
    }
}

#[test]
fn installed_production_wire_and_protected_native_output_execute() {
    let f = Fixture::new();
    let request = f.request("1", None, DeploymentIntent::Deploy);
    let production = std::env::var_os("PATAMAPS_TEST_ACTIVATOR_BINARY")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            std::env::current_exe()
                .unwrap()
                .parent()
                .unwrap()
                .parent()
                .unwrap()
                .join("patamaps-activator")
        });
    let installed = f.dir.join("patamaps-activator");
    fs::copy(&production, &installed)
        .expect("Build the production activator before its Linux acceptance suite");
    chmod(&installed, 0o555);
    let mut process = Command::new(&installed)
        .arg("activate")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    process
        .stdin
        .take()
        .unwrap()
        .write_all(&canonical_bytes(&request).unwrap())
        .unwrap();
    let output = process.wait_with_output().unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let reply: Value = parse(&output.stdout).unwrap();
    assert_eq!(reply["status"], "activated");
    let read = Command::new(&installed)
        .arg("active")
        .uid(65534)
        .gid(65534)
        .output()
        .unwrap();
    assert!(
        read.status.success(),
        "{}",
        String::from_utf8_lossy(&read.stderr)
    );
    let reply: Value = parse(&read.stdout).unwrap();
    assert_eq!(reply["status"], "active");
    let denied = Command::new(&installed)
        .args(["active", "--trust", "/tmp/self-appointed"])
        .uid(65534)
        .gid(65534)
        .output()
        .unwrap();
    assert!(!denied.status.success());
    let mut denied = Command::new(&installed)
        .arg("activate")
        .uid(65534)
        .gid(65534)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .unwrap();
    denied
        .stdin
        .take()
        .unwrap()
        .write_all(&canonical_bytes(&request).unwrap())
        .unwrap();
    assert!(!denied.wait().unwrap().success());
    let state = f.host.read().unwrap().unwrap();
    let consumer = f.dir.join("native-consumer");
    fs::create_dir(&consumer).unwrap();
    fs::write(consumer.join("bindings.rs"), &state.files["bindings-0.rs"]).unwrap();
    fs::write(
        consumer.join("service.rs"),
        state.manifest.proposal.candidate.captures[0].sources[0]
            .content
            .as_ref()
            .unwrap(),
    )
    .unwrap();
    fs::write(consumer.join("main.rs"),"mod service;mod bindings;fn main(){let id=bindings::SemanticId::parse(\"urn:command:greet\").unwrap();println!(\"{}\",bindings::dispatch(id,\"Ada\"));}").unwrap();
    let compilation = Command::new("rustc")
        .current_dir(&consumer)
        .args(["--edition=2024", "main.rs", "-o", "consumer"])
        .output()
        .unwrap();
    assert!(
        compilation.status.success(),
        "{}",
        String::from_utf8_lossy(&compilation.stderr)
    );
    chmod(&consumer.join("consumer"), 0o555);
    let output = Command::new(consumer.join("consumer"))
        .uid(65534)
        .gid(65534)
        .output()
        .unwrap();
    assert!(output.status.success());
    assert_eq!(
        String::from_utf8(output.stdout).unwrap().trim(),
        "Hello, Ada!"
    );
}

#[test]
fn native_consumer_executes_after_approved_module_move_and_fresh_rollback() {
    let f = Fixture::new();
    let first = f.budgeted_request("1", None, DeploymentIntent::Deploy, "service");
    let mut over_budget = first.prepared.proposal.candidate.captures[0].inputs.clone();
    over_budget.policy.semantics.as_mut().unwrap().risk_budgets[0].maximum_total_cost =
        SafeInteger::new(0).unwrap();
    let refused = capture(
        over_budget,
        first.prepared.proposal.candidate.captures[0]
            .sources
            .clone(),
    )
    .unwrap();
    assert_eq!(refused.result["status"], "rejected");
    assert!(
        refused.result["issues"]
            .as_array()
            .unwrap()
            .iter()
            .any(|i| i["code"] == "CONSUMER_RISK_BUDGET_EXCEEDED")
    );
    assert!(f.host.read().unwrap().is_none());
    assert!(matches!(
        f.host.activate(&first),
        ActivationOutcome::Activated { .. }
    ));
    let before = f.host.read().unwrap().unwrap();
    // Inspection and finite repair are actual native CLI calls. They must not
    // publish their viable but unapproved proposal over the protected baseline.
    let compiler = std::env::var_os("PATAMAPS_TEST_COMPILER_BINARY")
        .expect("Linux lifecycle requires the actual built native compiler");
    let captured = &first.prepared.proposal.candidate.captures[0];
    let capture_path = f.dir.join("inspection-capture.json");
    write(&capture_path, captured);
    let inspected = Command::new(&compiler)
        .args(["inspect"])
        .arg(&capture_path)
        .args(["--subject", "urn:command:greet"])
        .output()
        .unwrap();
    assert!(
        inspected.status.success(),
        "{}",
        String::from_utf8_lossy(&inspected.stderr)
    );
    let report: Value = serde_json::from_slice(&inspected.stdout).unwrap();
    assert_eq!(report["record"]["admission"], "viable");
    let mut undeclared = captured.inputs.clone();
    undeclared.policy.mappings = typed(json!([
        {"mapping":"urn:mapping:alias", "coverage":"total", "determinism":"deterministic", "reversibility":"irreversible"},
        {"mapping":"urn:mapping:implementation-handler", "coverage":"total", "determinism":"deterministic", "reversibility":"irreversible"}
    ]));
    let rejected = capture(undeclared, captured.sources.clone()).unwrap();
    assert_eq!(rejected.result["status"], "rejected");
    let repair_path = f.dir.join("repair-request.json");
    write(
        &repair_path,
        &json!({
            "schemaVersion":"0.1.0", "documentType":"repair-request", "baseline":rejected,
            "consumer":"urn:consumer:linux", "allowedFacts":[{"subject":"urn:policy:linux","fact":"policy.mappings"}],
            "protectedFacts":[], "edits":[{"id":"restore-declaration", "semanticCost":1,
                "operation":{"kind":"supply-declaration", "declaration":{"mapping":"urn:mapping:greet", "coverage":"total",
                    "determinism":"deterministic", "reversibility":"irreversible"}}}],
            "bounds":{"maximumCandidates":2,"maximumEdits":1,"maximumDerivationDepth":8,
                "maximumElapsedMilliseconds":60000,"maximumWorkUnits":2000000}
        }),
    );
    let repaired = Command::new(&compiler)
        .arg("repair")
        .arg(&repair_path)
        .output()
        .unwrap();
    assert!(
        repaired.status.success(),
        "{}",
        String::from_utf8_lossy(&repaired.stderr)
    );
    let proposals: Value = serde_json::from_slice(&repaired.stdout).unwrap();
    assert_eq!(proposals["status"], "complete");
    assert_eq!(proposals["applied"], false);
    assert_eq!(proposals["proposals"].as_array().unwrap().len(), 1);
    assert!(
        proposals["attempts"]
            .as_array()
            .unwrap()
            .iter()
            .any(|a| a["viable"] == true && a["authorization"] == "approval-required")
    );
    assert_eq!(
        f.host.read().unwrap().unwrap().manifest.digest,
        before.manifest.digest
    );
    let execute = |state: &ProtectedState, module: &str, name: &str| {
        let projection: Value = serde_json::from_str(&state.files["projection-0.json"]).unwrap();
        assert_eq!(projection["semantics"]["risk"]["totalCost"], json!(3));
        assert_eq!(
            state.manifest.proposal.candidate.captures[0].sources.len(),
            3
        );
        let consumer = f.dir.join(name);
        fs::create_dir(&consumer).unwrap();
        chmod(&consumer, 0o755);
        fs::write(consumer.join("bindings.rs"), &state.files["bindings-0.rs"]).unwrap();
        fs::write(
            consumer.join(format!("{module}.rs")),
            state.manifest.proposal.candidate.captures[0]
                .sources
                .iter()
                .find(|source| source.id == "urn:source:linux")
                .unwrap()
                .content
                .as_ref()
                .unwrap(),
        )
        .unwrap();
        fs::write(consumer.join("main.rs"), format!("mod {module}; mod bindings; fn main(){{let id=bindings::SemanticId::parse(\"urn:command:greet\").unwrap();println!(\"{{}}\",bindings::dispatch(id,\"Ada\"));}}" )).unwrap();
        let built = Command::new("rustc")
            .current_dir(&consumer)
            .args(["--edition=2024", "main.rs", "-o", "consumer"])
            .output()
            .unwrap();
        assert!(
            built.status.success(),
            "{}",
            String::from_utf8_lossy(&built.stderr)
        );
        chmod(&consumer.join("consumer"), 0o555);
        let consumed = Command::new(consumer.join("consumer"))
            .uid(65534)
            .gid(65534)
            .output()
            .unwrap();
        assert!(consumed.status.success());
        assert_eq!(
            String::from_utf8(consumed.stdout).unwrap().trim(),
            "Hello, Ada!"
        );
        assert_eq!(
            state.manifest.proposal.candidate.captures[0]
                .inputs
                .graph
                .entities[0]
                .id,
            "urn:command:greet"
        );
    };
    execute(&before, "service", "consumer-before");
    let moved = f.budgeted_request(
        "2",
        Some(&before.baseline()),
        DeploymentIntent::Deploy,
        "renamed_service",
    );
    assert!(moved.prepared.files["bindings-0.rs"].contains("crate::renamed_service::greet"));
    let mut stale_approval = moved.clone();
    stale_approval.approval = first.approval.clone();
    assert!(matches!(
        f.host.activate(&stale_approval),
        ActivationOutcome::Rejected { .. }
    ));
    assert_eq!(
        f.host.read().unwrap().unwrap().manifest.digest,
        before.manifest.digest
    );
    assert!(matches!(
        f.host.activate(&moved),
        ActivationOutcome::Activated { .. }
    ));
    let after = f.host.read().unwrap().unwrap();
    execute(&after, "renamed_service", "consumer-after");
    assert_rejected(f.host.activate(&first), "GOVERNANCE_STALE_BASELINE");
    let rollback = f.budgeted_request(
        "1",
        Some(&after.baseline()),
        DeploymentIntent::Rollback,
        "service",
    );
    assert_ne!(rollback.approval.digest, first.approval.digest);
    assert!(matches!(
        f.host.activate(&rollback),
        ActivationOutcome::Activated { .. }
    ));
    let restored = f.host.read().unwrap().unwrap();
    execute(&restored, "service", "consumer-restored");
    assert_eq!(restored.files, before.files);
    assert_ne!(restored.manifest.digest, before.manifest.digest);
}
