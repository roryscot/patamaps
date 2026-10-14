use base64::{Engine, engine::general_purpose::STANDARD};
use ed25519_dalek::{Signer, SigningKey};
use patamaps_activator::{
    ActivationError, ActivationRequest, MemoryActivation, MemoryContext, MemoryHost,
    MemoryManifest, RequestType, memory_executor_id, verify_memory_state,
};
use patamaps_contracts::{ProtocolVersion, canonical_bytes, parse};
use patamaps_governance::{
    ApprovalOptions, ArtifactEmission, CheckedProposal, DeploymentIntent, EmissionLanguage,
    GovernedBaseline, GovernedCandidate, ProposalOptions, TrustedConsumer, approval_signing_bytes,
    attach_signature, create_approval_payload, create_proposal, document_digest,
};
use serde_json::json;
use std::{
    cell::{Cell, RefCell},
    rc::Rc,
};

#[path = "support/lifecycle.rs"]
mod lifecycle;

const NOW: &str = "2026-10-10T01:00:00.000Z";
const EXPIRES: &str = "2026-10-10T02:00:00.000Z";

fn trust() -> TrustedConsumer {
    let key = SigningKey::from_bytes(&[29; 32]);
    let mut der = vec![
        0x30, 0x2a, 0x30, 0x05, 0x06, 0x03, 0x2b, 0x65, 0x70, 0x03, 0x21, 0,
    ];
    der.extend(key.verifying_key().as_bytes());
    parse(&canonical_bytes(&json!({
        "schemaVersion":"0.1.0","documentType":"trusted-consumer","mode":"governed",
        "id":"urn:trust:memory","revision":"1","consumer":"urn:consumer:linux","environment":"test",
        "principals":[{"id":"owner","role":"owner","revoked":false}],
        "keys":[{"id":"key","principal":"owner","algorithm":"Ed25519","publicKey":STANDARD.encode(der),
            "validFrom":"2020-01-01T00:00:00.000Z","validUntil":"2099-01-01T00:00:00.000Z","revoked":false}],
        "grants":[{"id":"grant","principal":"owner","actions":["activate","bootstrap","rollback","rebind-implementation","change-graph","change-authority","change-policy","relax-policy","raise-budget","add-waiver","change-law","change-source","change-context","change-projection"],
            "scopes":[{"subject":"*","fact":"*"}],"validFrom":"2020-01-01T00:00:00.000Z","validUntil":"2099-01-01T00:00:00.000Z","revoked":false}]
    })).unwrap()).unwrap()
}

fn context() -> MemoryContext {
    MemoryContext {
        trust: trust(),
        now: NOW.into(),
    }
}

fn candidate(revision: &str, module: &str) -> GovernedCandidate {
    GovernedCandidate {
        captures: vec![lifecycle::consumer_capture(revision, module)],
        emissions: vec![ArtifactEmission {
            projection: "urn:projection:linux".into(),
            language: EmissionLanguage::Rust,
            binding_slot: Some("handler".into()),
        }],
    }
}

fn request(
    candidate: &GovernedCandidate,
    trust: &TrustedConsumer,
    baseline: Option<&GovernedBaseline>,
    intent: DeploymentIntent,
) -> ActivationRequest {
    let proposal = create_proposal(
        candidate,
        ProposalOptions {
            consumer: &trust.consumer,
            environment: &trust.environment,
            proposer: "agent",
            intent,
            trust,
            baseline,
        },
    )
    .unwrap();
    sign(proposal)
}

fn sign(proposal: CheckedProposal) -> ActivationRequest {
    let grants = vec!["grant".into()];
    let payload = create_approval_payload(
        &proposal,
        ApprovalOptions {
            principal: "owner",
            key: "key",
            grants: &grants,
            issued_at: "2026-10-10T00:00:00.000Z",
            expires_at: EXPIRES,
        },
    )
    .unwrap();
    let signature =
        SigningKey::from_bytes(&[29; 32]).sign(&approval_signing_bytes(&payload).unwrap());
    ActivationRequest {
        schema_version: ProtocolVersion::Draft1,
        document_type: RequestType::Draft1,
        prepared: proposal.prepared(),
        approval: attach_signature(payload, &STANDARD.encode(signature.to_bytes())).unwrap(),
    }
}

fn activated(
    host: &mut MemoryHost<impl Fn() -> Result<MemoryContext, ActivationError>>,
    request: &ActivationRequest,
) {
    assert!(matches!(
        host.activate(request).unwrap(),
        MemoryActivation::Activated { .. }
    ));
}

fn state_bytes(host: &MemoryHost<impl Fn() -> Result<MemoryContext, ActivationError>>) -> Vec<u8> {
    canonical_bytes(host.current().unwrap()).unwrap()
}

fn readdress(manifest: &mut MemoryManifest) {
    manifest.digest = document_digest(manifest).unwrap();
    manifest.id = format!("urn:patamaps:memory-activation:{}", &manifest.digest[7..]);
}

#[test]
fn signed_bootstrap_move_and_freshly_approved_rollback_are_complete_native_states() {
    let owner = context();
    let first_candidate = candidate("1", "service");
    let first = request(
        &first_candidate,
        &owner.trust,
        None,
        DeploymentIntent::Deploy,
    );
    let mut host = MemoryHost::new(|| Ok(owner.clone())).unwrap();
    assert!(host.current().is_none());
    activated(&mut host, &first);
    let original = host.current().unwrap();
    assert_eq!(original.manifest().executor, memory_executor_id());
    assert!(original.manifest().previous_manifest.is_none());
    assert_eq!(original.files(), &first.prepared.files);
    assert!(original.files()["bindings-0.rs"].contains("crate::service::greet"));
    let files = original.files().clone();
    let initial_digest = original.manifest().digest.clone();
    let baseline = original.baseline();
    let moved = request(
        &candidate("2", "moved_service"),
        &owner.trust,
        Some(&baseline),
        DeploymentIntent::Deploy,
    );
    activated(&mut host, &moved);
    assert!(
        host.current().unwrap().files()["bindings-0.rs"].contains("crate::moved_service::greet")
    );
    assert_eq!(
        host.current()
            .unwrap()
            .manifest()
            .previous_manifest
            .as_ref(),
        Some(&initial_digest)
    );
    let before = state_bytes(&host);
    assert_eq!(
        host.activate(&first).unwrap_err().code(),
        "GOVERNANCE_STALE_BASELINE"
    );
    assert_eq!(state_bytes(&host), before);
    let second = host.current().unwrap().baseline();
    let rollback = request(
        &first_candidate,
        &owner.trust,
        Some(&second),
        DeploymentIntent::Rollback,
    );
    activated(&mut host, &rollback);
    let restored = host.current().unwrap();
    assert_eq!(restored.files(), &files);
    assert_ne!(restored.manifest().digest, initial_digest);
    assert_eq!(
        restored.manifest().previous_manifest.as_ref(),
        Some(&second.manifest_digest)
    );
    let verified = verify_memory_state(restored.manifest(), restored.files()).unwrap();
    assert_eq!(canonical_bytes(&verified).unwrap(), state_bytes(&host));
}

#[test]
fn exact_retry_rechecks_expiry_and_revocation_without_retiring_accepted_state() {
    let owner = Rc::new(RefCell::new(context()));
    let authority = owner.clone();
    let mut host = MemoryHost::new(move || Ok(authority.borrow().clone())).unwrap();
    let first = request(
        &candidate("1", "service"),
        &owner.borrow().trust,
        None,
        DeploymentIntent::Deploy,
    );
    activated(&mut host, &first);
    let before = state_bytes(&host);
    owner.borrow_mut().now = "2026-10-10T01:30:00.000Z".into();
    assert!(matches!(
        host.activate(&first).unwrap(),
        MemoryActivation::AlreadyActive { .. }
    ));
    assert_eq!(state_bytes(&host), before);
    owner.borrow_mut().now = EXPIRES.into();
    assert_eq!(
        host.activate(&first).unwrap_err().code(),
        "GOVERNANCE_APPROVAL_NOT_CURRENT"
    );
    assert_eq!(state_bytes(&host), before);
    owner.borrow_mut().now = NOW.into();
    owner.borrow_mut().trust.keys[0].revoked = true;
    assert_eq!(
        host.activate(&first).unwrap_err().code(),
        "GOVERNANCE_STALE_TRUST"
    );
    assert_eq!(state_bytes(&host), before);
    let historical = host.current().unwrap();
    assert!(verify_memory_state(historical.manifest(), historical.files()).is_ok());
}

#[test]
fn changed_bytes_inventory_proposal_and_signature_cannot_replace_state() {
    let owner = context();
    let mut host = MemoryHost::new(|| Ok(owner.clone())).unwrap();
    let first = request(
        &candidate("1", "service"),
        &owner.trust,
        None,
        DeploymentIntent::Deploy,
    );
    activated(&mut host, &first);
    let before = state_bytes(&host);
    for kind in ["bytes", "missing", "extra", "proposal", "signature"] {
        let mut bad = first.clone();
        match kind {
            "bytes" => bad
                .prepared
                .files
                .get_mut("bindings-0.rs")
                .unwrap()
                .push_str("\n// swapped"),
            "missing" => {
                bad.prepared.files.remove("bindings-0.rs");
            }
            "extra" => {
                bad.prepared
                    .files
                    .insert("extra.rs".into(), "pub fn extra() {}".into());
            }
            "proposal" => bad.prepared.proposal.environment = "other".into(),
            "signature" => {
                bad.approval =
                    attach_signature(bad.approval.payload.clone(), &STANDARD.encode([0; 64]))
                        .unwrap();
            }
            _ => unreachable!(),
        }
        assert!(host.activate(&bad).is_err(), "{kind}");
        assert_eq!(state_bytes(&host), before, "{kind}");
    }
}

#[test]
fn host_failure_and_panic_preserve_state_and_request_cannot_select_context() {
    let unavailable = Rc::new(Cell::new(0));
    let mode = unavailable.clone();
    let owner = context();
    let mut host = MemoryHost::new(|| match mode.get() {
        1 => Err(ActivationError::Refusal {
            code: "TEST_UNAVAILABLE",
            message: "fixture host unavailable",
        }),
        2 => panic!("fixture provider panic"),
        _ => Ok(owner.clone()),
    })
    .unwrap();
    let first = request(
        &candidate("1", "service"),
        &owner.trust,
        None,
        DeploymentIntent::Deploy,
    );
    activated(&mut host, &first);
    let before = state_bytes(&host);
    for setting in [1, 2] {
        unavailable.set(setting);
        assert_eq!(
            host.activate(&first).unwrap_err().code(),
            "ACTIVATION_HOST_UNAVAILABLE"
        );
        assert_eq!(state_bytes(&host), before);
    }
    for field in ["now", "trust", "trustedConfiguration", "host"] {
        let mut wire = serde_json::to_value(&first).unwrap();
        wire[field] = json!({});
        assert!(
            parse::<ActivationRequest>(&canonical_bytes(&wire).unwrap()).is_err(),
            "{field}"
        );
    }
}

#[test]
fn authority_changes_during_preparation_refuse_both_publication_and_retry() {
    for retry in [false, true] {
        for change in ["expiry", "revocation", "environment"] {
            let count = Cell::new(0);
            let armed = Cell::new(false);
            let owner = context();
            let mut host = MemoryHost::new(|| {
                let mut current = owner.clone();
                if armed.get() {
                    count.set(count.get() + 1);
                    if count.get() == 2 {
                        match change {
                            "expiry" => current.now = EXPIRES.into(),
                            "revocation" => current.trust.keys[0].revoked = true,
                            "environment" => current.trust.environment = "other".into(),
                            _ => unreachable!(),
                        }
                    }
                }
                Ok(current)
            })
            .unwrap();
            let first = request(
                &candidate("1", "service"),
                &owner.trust,
                None,
                DeploymentIntent::Deploy,
            );
            if retry {
                activated(&mut host, &first);
            }
            let before = host.current().map(|s| canonical_bytes(s).unwrap());
            armed.set(true);
            assert!(host.activate(&first).is_err(), "retry={retry}, {change}");
            assert_eq!(count.get(), 2);
            assert_eq!(host.current().map(|s| canonical_bytes(s).unwrap()), before);
        }
    }
}

#[test]
fn historical_readdressing_cannot_hide_foreign_executor_predecessor_time_or_trust() {
    let owner = context();
    let mut host = MemoryHost::new(|| Ok(owner.clone())).unwrap();
    let first = request(
        &candidate("1", "service"),
        &owner.trust,
        None,
        DeploymentIntent::Deploy,
    );
    activated(&mut host, &first);
    let state = host.current().unwrap();
    for field in ["executor", "predecessor", "time", "trust", "consumer"] {
        let mut bad = state.manifest().clone();
        match field {
            "executor" => bad.executor = format!("sha256:{}", "0".repeat(64)),
            "predecessor" => bad.previous_manifest = Some(format!("sha256:{}", "0".repeat(64))),
            "time" => bad.authorized_at = EXPIRES.into(),
            "trust" => {
                bad.accepted_trust.principals[0].role = patamaps_governance::PrincipalRole::Agent
            }
            "consumer" => bad.consumer = "urn:consumer:other".into(),
            _ => unreachable!(),
        }
        readdress(&mut bad);
        assert!(verify_memory_state(&bad, state.files()).is_err(), "{field}");
    }
    let mut swapped = state.files().clone();
    swapped
        .get_mut("bindings-0.rs")
        .unwrap()
        .push_str("\n// altered");
    assert!(verify_memory_state(state.manifest(), &swapped).is_err());
    let mut damaged = state.manifest().clone();
    damaged.digest = format!("sha256:{}", "0".repeat(64));
    assert!(verify_memory_state(&damaged, state.files()).is_err());
}

#[test]
fn agent_role_cannot_approve_bootstrap_and_memory_cannot_claim_a_linux_deployment() {
    let mut owner = context();
    owner.trust.principals[0].role = patamaps_governance::PrincipalRole::Agent;
    let first = request(
        &candidate("1", "service"),
        &owner.trust,
        None,
        DeploymentIntent::Deploy,
    );
    let mut host = MemoryHost::new(|| Ok(owner.clone())).unwrap();
    assert_eq!(
        host.activate(&first).unwrap_err().code(),
        "GOVERNANCE_OWNER_REQUIRED"
    );
    assert!(host.current().is_none());
    let mut linux = context();
    linux.trust.deployment = Some(parse(&canonical_bytes(&json!({"profile":"patamaps-linux-root-draft-1","stateDirectory":"/isolated/state","proposalRoots":["/isolated/proposals"]})).unwrap()).unwrap());
    let result = MemoryHost::new(|| Ok(linux.clone()));
    assert!(matches!(result, Err(error) if error.code()=="ACTIVATION_MEMORY_PROFILE_REQUIRED"));
}
