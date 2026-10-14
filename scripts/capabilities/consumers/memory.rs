//! Independent installation consumer. All signing keys are public test fixtures.
use base64::{Engine, engine::general_purpose::STANDARD};
use ed25519_dalek::{Signer, SigningKey};
use patamaps_activator::{
    ActivationRequest, MemoryActivation, MemoryContext, MemoryHost, RequestType,
    memory_executor_id, verify_memory_state,
};
use patamaps_contracts::*;
use patamaps_governance::*;
use patamaps_projection::{CaptureInputs, SourceReceipt, capture};
use serde_json::json;
use std::{cell::RefCell, path::Path, rc::Rc};

const CONSUMER: &str = "urn:consumer:installed-memory";
const NOW: &str = "2026-10-10T12:00:00.000Z";
const EXPIRES: &str = "2026-10-10T13:00:00.000Z";

fn candidate(root: &Path, revision: &str, module: &str) -> GovernedCandidate {
    let mut graph: GraphDocument = parse(&std::fs::read(root.join("graph.json")).unwrap()).unwrap();
    graph.revision = Some(revision.into());
    let handler = graph.entities.iter_mut().find(|e| e.kind == "routing:handler").unwrap();
    handler.locators = Some(vec![parse(&canonical_bytes(&json!({
        "uri":format!("rust:crate::{module}::greet")
    })).unwrap()).unwrap()]);
    let mut policy: PolicyDocument = parse(&std::fs::read(root.join("policy.json")).unwrap()).unwrap();
    policy.graph.revision = Some(revision.into());
    let mut spec: ProjectionSpec = parse(&std::fs::read(root.join("projection-spec.json")).unwrap()).unwrap();
    spec.consumer = Some(CONSUMER.into());
    let source = "pub fn greet(input:&str)->String{format!(\"Hello, {}!\",input)}\n";
    let captured = capture(CaptureInputs {
        graph,
        packs: vec![parse(&std::fs::read(root.join("core.json")).unwrap()).unwrap(),parse(&std::fs::read(root.join("routing.json")).unwrap()).unwrap()],
        policy,
        context: JsonObject::new(),
        evaluated_at: NOW.into(),
        projection_spec: Some(spec),
        projection_specs: vec![],
    },vec![SourceReceipt {
        id: "urn:source:installed-memory".into(),
        locator: format!("rust:crate::{module}"),
        digest: byte_digest(source.as_bytes()),
        byte_length: SafeInteger::new(source.len() as u64).unwrap(),
        content: Some(source.into()),
    }]).unwrap();
    assert_eq!(captured.result["status"], "viable");
    GovernedCandidate {
        captures: vec![captured],
        emissions: vec![ArtifactEmission {
            projection: "urn:example:projection:command-router".into(),
            language: EmissionLanguage::Rust,
            binding_slot: Some("handler".into()),
        }],
    }
}

fn request(candidate: &GovernedCandidate, trust: &TrustedConsumer, baseline: Option<&GovernedBaseline>, intent: DeploymentIntent) -> ActivationRequest {
    let checked = create_proposal(candidate,ProposalOptions {
        consumer:CONSUMER,environment:"test",proposer:"agent",trust,baseline,intent,
    }).unwrap();
    let grants = vec!["grant".into()];
    let payload = create_approval_payload(&checked,ApprovalOptions {
        principal:"owner",key:"key",grants:&grants,issued_at:NOW,expires_at:EXPIRES,
    }).unwrap();
    let signature = SigningKey::from_bytes(&[29;32]).sign(&approval_signing_bytes(&payload).unwrap());
    ActivationRequest {
        schema_version:ProtocolVersion::Draft1,document_type:RequestType::Draft1,
        prepared:checked.prepared(),
        approval:attach_signature(payload,&STANDARD.encode(signature.to_bytes())).unwrap(),
    }
}

fn main() {
    let root = std::env::current_dir().unwrap();
    let key = SigningKey::from_bytes(&[29;32]);
    let mut der = vec![0x30,0x2a,0x30,0x05,0x06,0x03,0x2b,0x65,0x70,0x03,0x21,0];
    der.extend(key.verifying_key().as_bytes());
    let trust:TrustedConsumer = parse(&canonical_bytes(&json!({
        "schemaVersion":"0.1.0","documentType":"trusted-consumer","mode":"governed",
        "id":"urn:trust:installed-memory","revision":"1","consumer":CONSUMER,"environment":"test",
        "principals":[{"id":"owner","role":"owner","revoked":false}],
        "keys":[{"id":"key","principal":"owner","algorithm":"Ed25519","publicKey":STANDARD.encode(der),
            "validFrom":"2020-01-01T00:00:00.000Z","validUntil":"2099-01-01T00:00:00.000Z","revoked":false}],
        "grants":[{"id":"grant","principal":"owner","actions":["activate","bootstrap","rollback","rebind-implementation","change-graph","change-authority","change-policy","relax-policy","raise-budget","add-waiver","change-law","change-source","change-context","change-projection"],
            "scopes":[{"subject":"*","fact":"*"}],"validFrom":"2020-01-01T00:00:00.000Z","validUntil":"2099-01-01T00:00:00.000Z","revoked":false}]
    })).unwrap()).unwrap();
    let owner = Rc::new(RefCell::new(MemoryContext {trust:trust.clone(),now:NOW.into()}));
    let authority = owner.clone();
    let mut host = MemoryHost::new(move || Ok(authority.borrow().clone())).unwrap();
    let original = candidate(&root,"1","service");
    let first = request(&original,&trust,None,DeploymentIntent::Deploy);
    assert!(matches!(host.activate(&first).unwrap(),MemoryActivation::Activated{..}));
    let initial = canonical_bytes(host.current().unwrap()).unwrap();
    assert!(matches!(host.activate(&first).unwrap(),MemoryActivation::AlreadyActive{..}));
    owner.borrow_mut().now = EXPIRES.into();
    assert_eq!(host.activate(&first).unwrap_err().code(),"GOVERNANCE_APPROVAL_NOT_CURRENT");
    assert_eq!(canonical_bytes(host.current().unwrap()).unwrap(),initial);
    owner.borrow_mut().now = NOW.into();
    let first_base = host.current().unwrap().baseline();
    let moved = request(&candidate(&root,"2","moved_service"),&trust,Some(&first_base),DeploymentIntent::Deploy);
    assert!(matches!(host.activate(&moved).unwrap(),MemoryActivation::Activated{..}));
    assert!(host.current().unwrap().files()["bindings-0.rs"].contains("crate::moved_service::greet"));
    let second = canonical_bytes(host.current().unwrap()).unwrap();
    assert_eq!(host.activate(&first).unwrap_err().code(),"GOVERNANCE_STALE_BASELINE");
    assert_eq!(canonical_bytes(host.current().unwrap()).unwrap(),second);
    let second_base = host.current().unwrap().baseline();
    let rollback = request(&original,&trust,Some(&second_base),DeploymentIntent::Rollback);
    assert!(matches!(host.activate(&rollback).unwrap(),MemoryActivation::Activated{..}));
    let state = host.current().unwrap();
    assert_eq!(state.files(),&first.prepared.files);
    assert_ne!(state.manifest().digest,first_base.manifest_digest);
    let historical = verify_memory_state(state.manifest(),state.files()).unwrap();
    assert_eq!(canonical_bytes(&historical).unwrap(),canonical_bytes(state).unwrap());
    println!("{}",json!({"profile":"patamaps-memory-draft-1","executor":memory_executor_id(),
        "bootstrap":true,"move":true,"rollback":true,"retryRechecked":true,
        "rejectionPreservesState":true,"manifest":state.manifest().digest,"files":state.files().len()}));
}
