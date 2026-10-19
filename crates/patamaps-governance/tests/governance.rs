use base64::{Engine, engine::general_purpose::STANDARD};
use ed25519_dalek::{Signer, SigningKey};
use patamaps_contracts::*;
use patamaps_core::CheckError;
use patamaps_governance::*;
use patamaps_projection::{CaptureInputs, SourceReceipt, capture};
use serde::de::DeserializeOwned;
use serde_json::{Value, json};
use std::collections::BTreeSet;

const CONSUMER: &str = "urn:consumer:native";
const ENVIRONMENT: &str = "test";
const NOW: &str = "2026-10-10T01:00:00.000Z";
fn typed<T: DeserializeOwned>(value: Value) -> T {
    parse(&canonical_bytes(&value).unwrap()).unwrap()
}
fn code(error: CheckError, wanted: &str) {
    assert!(
        error.0.iter().any(|i| i.code == wanted),
        "expected {wanted}: {:?}",
        error.0
    );
}
fn key(principal: &str) -> SigningKey {
    // Synthetic test material only. The owner seed is RFC 8032 section 7.1.
    let seed = if principal == "owner" {
        hex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
            .try_into()
            .unwrap()
    } else {
        [42; 32]
    };
    SigningKey::from_bytes(&seed)
}
fn hex(value: &str) -> Vec<u8> {
    value
        .as_bytes()
        .as_chunks::<2>()
        .0
        .iter()
        .map(|p| u8::from_str_radix(std::str::from_utf8(p).unwrap(), 16).unwrap())
        .collect()
}
fn public(principal: &str) -> String {
    let mut bytes = hex("302a300506032b6570032100");
    bytes.extend(key(principal).verifying_key().as_bytes());
    STANDARD.encode(bytes)
}
fn trust() -> TrustedConsumer {
    let actions = [
        "activate",
        "bootstrap",
        "rollback",
        "rebind-implementation",
        "change-graph",
        "change-authority",
        "change-policy",
        "relax-policy",
        "raise-budget",
        "add-waiver",
        "change-law",
        "change-source",
        "change-context",
        "change-projection",
    ];
    typed(
        json!({"schemaVersion":"0.1.0","documentType":"trusted-consumer","mode":"governed","id":"urn:trust:native","revision":"1","consumer":CONSUMER,"environment":ENVIRONMENT,
        "principals":[{"id":"owner","role":"owner","revoked":false},{"id":"agent","role":"agent","revoked":false}],
        "keys":(["owner","agent"].map(|p|json!({"id":format!("{p}-key"),"principal":p,"algorithm":"Ed25519","publicKey":public(p),"validFrom":"2026-10-10T00:00:00.000Z","validUntil":"2026-10-10T08:00:00.000Z","revoked":false}))),
        "grants":(["owner","agent"].map(|p|json!({"id":format!("{p}-grant"),"principal":p,"actions":actions,"scopes":[{"subject":"*","fact":"*"}],"validFrom":"2026-10-10T00:00:00.000Z","validUntil":"2026-10-10T08:00:00.000Z","revoked":false})))}),
    )
}
fn candidate() -> GovernedCandidate {
    let graph = typed(
        json!({"schemaVersion":"0.1.0","documentType":"graph","id":"urn:graph:native","namespace":"native","revision":"1","entities":[{"id":"urn:operation:greet","kind":"routing:command","attributes":{"path":"/greet/:id"}},{"id":"urn:handler:greet","kind":"routing:handler","locators":[{"uri":"rust:crate::service::greet"},{"uri":"typescript:./service.ts#greet"}]}],"mappings":[{"id":"urn:mapping:greet","relation":"routing:handled_by","sources":["urn:operation:greet"],"targets":["urn:handler:greet"],"cardinality":"one-to-one","lossiness":"lossless","provenance":{"status":"declared","assertedBy":"agent"}}],"authorities":[{"id":"urn:authority:greet","concept":"urn:operation:greet","source":"urn:operation:greet","facts":["routing-identity"],"mode":"canonical","provenance":{"status":"declared","assertedBy":"agent"}}]}),
    );
    let policy = typed(
        json!({"schemaVersion":"0.1.0","documentType":"policy","id":"urn:policy:native","graph":{"id":"urn:graph:native","revision":"1"},"mappings":[{"mapping":"urn:mapping:greet","coverage":"total","determinism":"deterministic","reversibility":"irreversible"}],"constraints":[{"id":"urn:constraint:handler","kind":"core:requires-mapping","subjects":["urn:operation:greet"],"parameters":{"relation":"routing:handled_by","direction":"source"}}],"evidence":[]}),
    );
    let spec = typed(
        json!({"schemaVersion":"0.1.0","documentType":"projection-spec","id":"urn:spec:native","consumer":CONSUMER,"select":{"ids":["urn:operation:greet"]},"slots":[{"name":"handler","relation":"routing:handled_by","direction":"outgoing","cardinality":"exactly-one","targetKinds":["routing:handler"]}],"pathTree":{}}),
    );
    let source = "pub fn greet(input: &str) -> String { format!(\"Hello, {}!\", input) }\n";
    let sources = vec![SourceReceipt {
        id: "urn:source:handler".into(),
        locator: "rust:crate::service".into(),
        digest: byte_digest(source.as_bytes()),
        byte_length: SafeInteger::new(source.len() as u64).unwrap(),
        content: Some(source.into()),
    }];
    let c = capture(
        CaptureInputs {
            projection_specs: vec![],
            graph,
            packs: vec![
                parse(include_bytes!(
                    "../package-inputs/relation-packs/routing.json"
                ))
                .unwrap(),
            ],
            policy,
            context: JsonObject::new(),
            evaluated_at: "2026-10-09T12:00:00Z".into(),
            projection_spec: Some(spec),
        },
        sources,
    )
    .unwrap();
    assert_eq!(c.result["status"], "viable");
    GovernedCandidate {
        captures: vec![c],
        emissions: vec![
            ArtifactEmission {
                projection: "urn:spec:native".into(),
                language: EmissionLanguage::Rust,
                binding_slot: Some("handler".into()),
            },
            ArtifactEmission {
                projection: "urn:spec:native".into(),
                language: EmissionLanguage::Typescript,
                binding_slot: Some("handler".into()),
            },
        ],
    }
}

#[test]
fn collection_artifacts_include_every_specification_and_refused_or_wrong_consumers_cannot_prepare()
{
    let mut candidate = candidate();
    let previous = candidate.captures.remove(0);
    let mut input = previous.inputs;
    let spec = input.projection_spec.take().unwrap();
    let mut second = spec.clone();
    second.id = "urn:spec:collection-second".into();
    input.projection_specs = vec![second, spec];
    candidate
        .captures
        .push(capture(input.clone(), previous.sources.clone()).unwrap());
    let prepared = prepare_candidate_artifacts(&candidate, CONSUMER, ENVIRONMENT).unwrap();
    for path in [
        "projection-0-0.json",
        "projection-0-1.json",
        "path-tree-0-0.json",
        "path-tree-0-1.json",
    ] {
        assert!(
            prepared.files().contains_key(path),
            "Missing collection artifact {path}"
        );
        assert!(
            prepared
                .manifest()
                .files
                .iter()
                .any(|file| file.path == path)
        );
    }
    input.projection_specs[0].consumer = Some("urn:consumer:other".into());
    candidate.captures[0] = capture(input.clone(), previous.sources.clone()).unwrap();
    assert!(prepare_candidate_artifacts(&candidate, CONSUMER, ENVIRONMENT).is_err());
    input.projection_specs[0].consumer = Some(CONSUMER.into());
    input.projection_specs[0].slots[0].target_kinds = Some(vec!["unavailable-kind".into()]);
    candidate.captures[0] = capture(input, previous.sources).unwrap();
    assert!(prepare_candidate_artifacts(&candidate, CONSUMER, ENVIRONMENT).is_err());
}
fn recapture(candidate: &mut GovernedCandidate) {
    for c in &mut candidate.captures {
        *c = capture(c.inputs.clone(), c.sources.clone()).unwrap();
    }
}
fn propose(
    candidate: &GovernedCandidate,
    trust: &TrustedConsumer,
    base: Option<&GovernedBaseline>,
    intent: DeploymentIntent,
) -> CheckedProposal {
    create_proposal(
        candidate,
        ProposalOptions {
            consumer: CONSUMER,
            environment: ENVIRONMENT,
            proposer: "untrusted-agent-attribution",
            intent,
            trust,
            baseline: base,
        },
    )
    .unwrap()
}
fn approve(proposal: &CheckedProposal, principal: &str) -> SignedApproval {
    let grants = vec![format!("{principal}-grant")];
    let payload = create_approval_payload(
        proposal,
        ApprovalOptions {
            principal,
            key: &format!("{principal}-key"),
            grants: &grants,
            issued_at: "2026-10-10T00:30:00.000Z",
            expires_at: "2026-10-10T02:00:00.000Z",
        },
    )
    .unwrap();
    sign(payload, principal)
}
fn sign(payload: ApprovalPayload, principal: &str) -> SignedApproval {
    let signature = key(principal).sign(&approval_signing_bytes(&payload).unwrap());
    attach_signature(payload, &STANDARD.encode(signature.to_bytes())).unwrap()
}
fn context<'a>(
    trust: &'a TrustedConsumer,
    baseline: Option<&'a GovernedBaseline>,
) -> VerificationContext<'a> {
    VerificationContext {
        trust,
        baseline,
        now: NOW,
    }
}
fn base(candidate: GovernedCandidate) -> GovernedBaseline {
    GovernedBaseline {
        manifest_digest: format!("sha256:{}", "1".repeat(64)),
        candidate,
    }
}
fn readdress(proposal: &mut ChangeProposal) {
    proposal.digest = document_digest(proposal).unwrap();
    proposal.id = format!("urn:patamaps:change-proposal:{}", &proposal.digest[7..]);
}

#[test]
fn published_crypto_vector_and_strict_crypto_refusals() {
    let key = STANDARD.encode(hex(
        "302a300506032b6570032100d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
    ));
    let signature=STANDARD.encode(hex("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"));
    assert!(verify_ed25519_signature(b"", &key, &signature).unwrap());
    assert!(!verify_ed25519_signature(b"different", &key, &signature).unwrap());
    for wrong in [format!("{key}\n"),STANDARD.encode(hex("302a300506032b65700321000100000000000000000000000000000000000000000000000000000000000000")),STANDARD.encode([0xff;44])]{code(verify_ed25519_signature(b"",&wrong,&signature).unwrap_err(),"GOVERNANCE_INVALID_CRYPTO");}
    code(
        verify_ed25519_signature(b"", &key, &STANDARD.encode([0; 63])).unwrap_err(),
        "GOVERNANCE_INVALID_CRYPTO",
    );
    let mut noncanonical = hex(
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",
    );
    noncanonical[63] = 0xff;
    assert!(!verify_ed25519_signature(b"", &key, &STANDARD.encode(noncanonical)).unwrap());
}
#[test]
fn viable_agent_proposal_remains_unapproved_and_exact_owner_verifies() {
    let t = trust();
    let p = propose(&candidate(), &t, None, DeploymentIntent::Deploy);
    assert_eq!(p.files().len(), 11);
    assert!(p.files()["path-tree-1.ts"].contains("export function hydratePathTree"));
    assert!(p.files()["bindings-0.rs"].contains("crate::service::greet"));
    assert!(p.files()["bindings-1.ts"].contains("./service.js"));
    verify_artifact_bytes(&p, p.files()).unwrap();
    let signed = approve(&p, "owner");
    let authorized = verify_approval(&p, &signed, context(&t, None)).unwrap();
    assert_eq!(
        authorized.record().status,
        "authorized-under-supplied-context"
    );
    assert_eq!(authorized.record().principal, "owner");
    code(
        verify_approval(&p, &approve(&p, "agent"), context(&t, None)).unwrap_err(),
        "GOVERNANCE_OWNER_REQUIRED",
    );
    check_prepared(&p.prepared()).unwrap();
}
#[test]
fn exact_complete_file_inventory_and_recomputed_delta_cannot_be_forged() {
    let t = trust();
    let p = propose(&candidate(), &t, None, DeploymentIntent::Deploy);
    for operation in ["missing", "additional", "changed"] {
        let mut prepared = p.prepared();
        match operation {
            "missing" => {
                prepared.files.remove("graph.json");
            }
            "additional" => {
                prepared
                    .files
                    .insert("extra.rs".into(), "fn malicious() {}".into());
            }
            _ => {
                prepared
                    .files
                    .get_mut("bindings-0.rs")
                    .unwrap()
                    .push_str("// swapped\n");
            }
        }
        code(
            check_prepared(&prepared).unwrap_err(),
            "GOVERNANCE_ARTIFACT_BYTES_MISMATCH",
        );
    }
    let mut forged = p.record().clone();
    forged
        .requirements
        .retain(|r| r.action == GovernanceAction::Activate);
    readdress(&mut forged);
    code(
        check_proposal(&forged).unwrap_err(),
        "GOVERNANCE_DELTA_MISMATCH",
    );
    let mut forged = p.record().clone();
    forged.artifacts.files.pop();
    forged.artifacts.digest = document_digest(&forged.artifacts).unwrap();
    forged.artifacts.id = format!("urn:patamaps:artifacts:{}", &forged.artifacts.digest[7..]);
    readdress(&mut forged);
    code(
        check_proposal(&forged).unwrap_err(),
        "GOVERNANCE_ARTIFACT_MISMATCH",
    );
}
#[test]
fn trust_duplicates_shared_identity_and_unknown_principals_refuse() {
    for kind in ["principal", "key", "grant", "shared", "unknown"] {
        let mut t = trust();
        let expected = match kind {
            "principal" => {
                t.principals.push(t.principals[0].clone());
                "GOVERNANCE_DUPLICATE_ID"
            }
            "key" => {
                t.keys.push(t.keys[0].clone());
                "GOVERNANCE_DUPLICATE_ID"
            }
            "grant" => {
                t.grants.push(t.grants[0].clone());
                "GOVERNANCE_DUPLICATE_ID"
            }
            "shared" => {
                t.keys[1].public_key = t.keys[0].public_key.clone();
                "GOVERNANCE_SHARED_IDENTITY_KEY"
            }
            _ => {
                t.keys[0].principal = "appointed-by-candidate".into();
                "GOVERNANCE_UNKNOWN_PRINCIPAL"
            }
        };
        code(check_trusted_consumer(&t).unwrap_err(), expected);
    }
}
#[test]
fn ordinary_rebind_needs_explicit_joint_action_and_fact_scope() {
    let mut t = trust();
    let baseline = base(candidate());
    let mut c = baseline.candidate.clone();
    c.captures[0].inputs.graph.entities[1]
        .locators
        .as_mut()
        .unwrap()[0]
        .uri = "rust:crate::moved::greet".into();
    recapture(&mut c);
    let p = propose(&c, &t, Some(&baseline), DeploymentIntent::Deploy);
    let got: BTreeSet<_> = p
        .record()
        .requirements
        .iter()
        .map(|r| (r.action, r.subject.as_str(), r.fact.as_str()))
        .collect();
    assert_eq!(
        got,
        BTreeSet::from([
            (GovernanceAction::Activate, CONSUMER, "activation"),
            (
                GovernanceAction::RebindImplementation,
                "urn:handler:greet",
                "entity.locators"
            )
        ])
    );
    t.grants[1].actions = vec![GovernanceAction::Activate];
    t.grants[1].scopes = vec![
        GovernanceScope {
            subject: CONSUMER.into(),
            fact: "activation".into(),
        },
        GovernanceScope {
            subject: "urn:handler:greet".into(),
            fact: "entity.locators".into(),
        },
    ];
    t.grants.push(TrustedGrant {
        id: "agent-rebind".into(),
        principal: "agent".into(),
        actions: vec![GovernanceAction::RebindImplementation],
        scopes: vec![GovernanceScope {
            subject: CONSUMER.into(),
            fact: "activation".into(),
        }],
        ..t.grants[1].clone()
    });
    let p = propose(&c, &t, Some(&baseline), DeploymentIntent::Deploy);
    let mut payload = approve(&p, "agent").payload;
    payload.grants.push("agent-rebind".into());
    payload.grants.sort();
    code(
        verify_approval(
            &p,
            &sign(payload.clone(), "agent"),
            context(&t, Some(&baseline)),
        )
        .unwrap_err(),
        "GOVERNANCE_SCOPE_DENIED",
    );
    t.grants[2].scopes = vec![GovernanceScope {
        subject: "urn:handler:greet".into(),
        fact: "entity.locators".into(),
    }];
    let p = propose(&c, &t, Some(&baseline), DeploymentIntent::Deploy);
    let mut payload = approve(&p, "agent").payload;
    payload.grants.push("agent-rebind".into());
    payload.grants.sort();
    verify_approval(&p, &sign(payload, "agent"), context(&t, Some(&baseline))).unwrap();
}
#[test]
fn intervals_use_current_time_and_full_signed_interval_with_exclusive_expiry() {
    let mut t = trust();
    let c = candidate();
    let p = propose(&c, &t, None, DeploymentIntent::Deploy);
    let a = approve(&p, "owner");
    verify_approval(
        &p,
        &a,
        VerificationContext {
            trust: &t,
            baseline: None,
            now: "2026-10-10T00:30:00.000Z",
        },
    )
    .unwrap();
    for now in [
        "2026-10-10T00:29:59.999Z",
        "2026-10-10T02:00:00.000Z",
        "2026-10-11T01:00:00.000Z",
    ] {
        code(
            verify_approval(
                &p,
                &a,
                VerificationContext {
                    trust: &t,
                    baseline: None,
                    now,
                },
            )
            .unwrap_err(),
            "GOVERNANCE_APPROVAL_NOT_CURRENT",
        );
    }
    code(
        verify_approval(
            &p,
            &a,
            VerificationContext {
                trust: &t,
                baseline: None,
                now: "2026-10-10T01:00:00Z",
            },
        )
        .unwrap_err(),
        "GOVERNANCE_INVALID_TIME",
    );
    t.keys[0].valid_until = "2026-10-10T01:30:00.000Z".into();
    let p = propose(&c, &t, None, DeploymentIntent::Deploy);
    code(
        verify_approval(&p, &approve(&p, "owner"), context(&t, None)).unwrap_err(),
        "GOVERNANCE_KEY_NOT_CURRENT",
    );
    t.keys[0].valid_until = "2026-10-10T08:00:00.000Z".into();
    t.grants[0].valid_until = "2026-10-10T01:30:00.000Z".into();
    let p = propose(&c, &t, None, DeploymentIntent::Deploy);
    code(
        verify_approval(&p, &approve(&p, "owner"), context(&t, None)).unwrap_err(),
        "GOVERNANCE_GRANT_NOT_CURRENT",
    );
}
#[test]
fn revocation_stale_trust_environment_and_separately_supplied_base_refuse() {
    let t = trust();
    let c = candidate();
    let p = propose(&c, &t, None, DeploymentIntent::Deploy);
    let a = approve(&p, "owner");
    let mut changed = t.clone();
    changed.revision = "2".into();
    code(
        verify_approval(&p, &a, context(&changed, None)).unwrap_err(),
        "GOVERNANCE_STALE_TRUST",
    );
    changed = t.clone();
    changed.environment = "production".into();
    code(
        verify_approval(&p, &a, context(&changed, None)).unwrap_err(),
        "GOVERNANCE_WRONG_ENVIRONMENT",
    );
    code(
        verify_approval(&p, &a, context(&t, Some(&base(c.clone())))).unwrap_err(),
        "GOVERNANCE_STALE_BASELINE",
    );
    for kind in ["principal", "key", "grant"] {
        let mut changed = t.clone();
        match kind {
            "principal" => changed.principals[0].revoked = true,
            "key" => changed.keys[0].revoked = true,
            _ => changed.grants[0].revoked = true,
        };
        let p = propose(&c, &changed, None, DeploymentIntent::Deploy);
        code(
            verify_approval(&p, &approve(&p, "owner"), context(&changed, None)).unwrap_err(),
            "GOVERNANCE_REVOKED",
        );
    }
}
#[test]
fn correctly_signed_wrong_content_and_foreign_identity_cannot_authorize() {
    let t = trust();
    let p = propose(&candidate(), &t, None, DeploymentIntent::Deploy);
    let mut payload = approve(&p, "owner").payload;
    payload
        .requirements
        .retain(|r| r.action == GovernanceAction::Activate);
    code(
        verify_approval(&p, &sign(payload, "owner"), context(&t, None)).unwrap_err(),
        "GOVERNANCE_APPROVAL_CONTENT_MISMATCH",
    );
    let mut payload = approve(&p, "owner").payload;
    payload.intent = DeploymentIntent::Rollback;
    code(
        verify_approval(&p, &sign(payload, "owner"), context(&t, None)).unwrap_err(),
        "GOVERNANCE_APPROVAL_CONTENT_MISMATCH",
    );
    let mut payload = approve(&p, "owner").payload;
    payload.key = "agent-key".into();
    code(
        verify_approval(&p, &sign(payload, "owner"), context(&t, None)).unwrap_err(),
        "GOVERNANCE_UNKNOWN_IDENTITY",
    );
    let a = sign(approve(&p, "owner").payload, "agent");
    code(
        verify_approval(&p, &a, context(&t, None)).unwrap_err(),
        "GOVERNANCE_BAD_SIGNATURE",
    );
    let mut c = candidate();
    c.captures[0].inputs.evaluated_at = "2026-10-08T12:00:00Z".into();
    recapture(&mut c);
    let next = propose(&c, &t, None, DeploymentIntent::Deploy);
    code(
        verify_approval(&next, &approve(&p, "owner"), context(&t, None)).unwrap_err(),
        "GOVERNANCE_APPROVAL_CONTENT_MISMATCH",
    );
}
#[test]
fn policy_authority_pack_waiver_budget_and_rollback_edits_require_owner() {
    let t = trust();
    let original = candidate();
    let baseline = base(original.clone());
    for kind in ["policy", "authority", "pack", "waiver", "rollback"] {
        let mut c = original.clone();
        let i = &mut c.captures[0].inputs;
        let (action, intent) = match kind {
            "policy" => {
                i.policy.constraints.clear();
                (GovernanceAction::RelaxPolicy, DeploymentIntent::Deploy)
            }
            "authority" => {
                i.graph.authorities[0].facts.push("implementation".into());
                (GovernanceAction::ChangeAuthority, DeploymentIntent::Deploy)
            }
            "pack" => {
                i.packs[0].description = Some("Exact changed pack bytes".into());
                (GovernanceAction::ChangeLaw, DeploymentIntent::Deploy)
            }
            "waiver" => {
                i.policy.waivers = Some(vec![typed(
                    json!({"id":"urn:waiver:example","codes":["REQUIRED_MAPPING_MISSING"],"subjects":["urn:operation:greet"],"reason":"Recorded exception","expiresAt":"2026-10-10T12:00:00Z","assertedBy":"agent"}),
                )]);
                (GovernanceAction::AddWaiver, DeploymentIntent::Deploy)
            }
            _ => (GovernanceAction::Rollback, DeploymentIntent::Rollback),
        };
        recapture(&mut c);
        let p = propose(&c, &t, Some(&baseline), intent);
        assert!(
            p.record().requirements.iter().any(|r| r.action == action),
            "{kind}"
        );
        code(
            verify_approval(&p, &approve(&p, "agent"), context(&t, Some(&baseline))).unwrap_err(),
            "GOVERNANCE_OWNER_REQUIRED",
        );
        verify_approval(&p, &approve(&p, "owner"), context(&t, Some(&baseline))).unwrap();
    }
    let mut c = original.clone();
    c.captures[0].inputs.policy.semantics = Some(typed(
        json!({"interpretation":"declared-law-application","derivations":[],"derivationLimits":{"maxDepth":8,"maxDerivations":32},"assessments":[],"uncertaintyRequirements":[],"riskBudgets":[{"id":"urn:budget:native","consumer":CONSUMER,"maximumTotalCost":2,"requireCompleteClassification":true,"requireCompleteDependencies":true,"classifications":[{"id":"urn:class:native","select":{"ids":["urn:mapping:greet"]},"classification":"declared","cost":1}]}]}),
    ));
    c.captures[0]
        .inputs
        .projection_spec
        .as_mut()
        .unwrap()
        .semantics = Some(ProjectionRequirements {
        consumer: CONSUMER.into(),
        budget: Some("urn:budget:native".into()),
    });
    recapture(&mut c);
    let baseline = base(c.clone());
    c.captures[0]
        .inputs
        .policy
        .semantics
        .as_mut()
        .unwrap()
        .risk_budgets[0]
        .maximum_total_cost = SafeInteger::new(3).unwrap();
    recapture(&mut c);
    let p = propose(&c, &t, Some(&baseline), DeploymentIntent::Deploy);
    assert!(
        p.record()
            .requirements
            .iter()
            .any(|r| r.action == GovernanceAction::RaiseBudget && r.subject == "urn:budget:native")
    );
    code(
        verify_approval(&p, &approve(&p, "agent"), context(&t, Some(&baseline))).unwrap_err(),
        "GOVERNANCE_OWNER_REQUIRED",
    );
}
#[test]
fn multiple_selected_projections_are_complete_and_inconsistent_inputs_refuse() {
    let t = trust();
    let mut c = candidate();
    let mut second = c.captures[0].clone();
    second.inputs.projection_spec.as_mut().unwrap().id = "urn:spec:second".into();
    second = capture(second.inputs, second.sources).unwrap();
    c.captures.push(second);
    let p = propose(&c, &t, None, DeploymentIntent::Deploy);
    assert!(p.files().contains_key("projection-1.json"));
    assert_eq!(p.record().artifacts.captures.len(), 2);
    c.captures[1].inputs.evaluated_at = "2026-10-08T12:00:00Z".into();
    recapture(&mut c);
    code(
        create_proposal(
            &c,
            ProposalOptions {
                consumer: CONSUMER,
                environment: ENVIRONMENT,
                proposer: "agent",
                intent: DeploymentIntent::Deploy,
                trust: &t,
                baseline: None,
            },
        )
        .unwrap_err(),
        "GOVERNANCE_INCONSISTENT_CAPTURES",
    );
}
#[test]
fn refusal_missing_sources_and_untrusted_recursive_results_never_mint_proposals() {
    let t = trust();
    let original = candidate();
    for kind in ["rejected", "receipt-only", "wrong-consumer", "deep-result"] {
        let mut c = original.clone();
        let expected = match kind {
            "rejected" => {
                c.captures[0].inputs.graph.mappings.clear();
                recapture(&mut c);
                "GOVERNANCE_CANDIDATE_REJECTED"
            }
            "receipt-only" => {
                c.captures[0].sources[0].content = None;
                recapture(&mut c);
                "GOVERNANCE_MISSING_SOURCE_BYTES"
            }
            "wrong-consumer" => {
                c.captures[0]
                    .inputs
                    .projection_spec
                    .as_mut()
                    .unwrap()
                    .consumer = Some("urn:consumer:other".into());
                recapture(&mut c);
                "GOVERNANCE_WRONG_CONSUMER"
            }
            _ => {
                let mut value = Value::Null;
                for _ in 0..66 {
                    value = json!([value]);
                }
                c.captures[0].result = value;
                "GOVERNANCE_RESOURCE_LIMIT"
            }
        };
        code(
            create_proposal(
                &c,
                ProposalOptions {
                    consumer: CONSUMER,
                    environment: ENVIRONMENT,
                    proposer: "agent",
                    intent: DeploymentIntent::Deploy,
                    trust: &t,
                    baseline: None,
                },
            )
            .unwrap_err(),
            expected,
        );
    }
}
#[test]
fn signed_ingress_is_closed_and_explicit_nullable_baseline_is_required() {
    let t = trust();
    let p = propose(&candidate(), &t, None, DeploymentIntent::Deploy);
    let a = approve(&p, "owner");
    let text = String::from_utf8(canonical_bytes(&a).unwrap()).unwrap();
    // The renamed namespace is an explicit protocol boundary, even when an
    // external owner correctly signs bytes from the former draft namespace.
    for (field, old) in [
        ("domain", "urn:bindloom:approval:draft:1"),
        ("profile", "bindloom-governance-draft-1"),
    ] {
        let mut foreign = serde_json::to_value(&a).unwrap();
        foreign["payload"][field] = json!(old);
        let signature = key("owner").sign(&canonical_bytes(&foreign["payload"]).unwrap());
        foreign["signature"] = json!(STANDARD.encode(signature.to_bytes()));
        assert!(parse::<SignedApproval>(&canonical_bytes(&foreign).unwrap()).is_err());
    }
    assert!(
        parse::<SignedApproval>(
            text.replace(
                "\"schemaVersion\":\"0.1.0\"",
                "\"schemaVersion\":\"0.1.0\",\"schema\\u0056ersion\":\"0.1.0\""
            )
            .as_bytes()
        )
        .is_err()
    );
    let mut value = serde_json::to_value(a).unwrap();
    value["publicKey"] = json!(public("owner"));
    assert!(parse::<SignedApproval>(&canonical_bytes(&value).unwrap()).is_err());
    value.as_object_mut().unwrap().remove("publicKey");
    value["payload"].as_object_mut().unwrap().remove("baseline");
    assert!(parse::<SignedApproval>(&canonical_bytes(&value).unwrap()).is_err());
    let mut proposal = serde_json::to_value(p.record()).unwrap();
    proposal["trustedConfiguration"] = serde_json::to_value(&t).unwrap();
    assert!(parse::<ChangeProposal>(&canonical_bytes(&proposal).unwrap()).is_err());
    // Sorting is UTF-16, including supplementary characters, as in ECMAScript.
    let grants = vec!["grant:\u{e000}".into(), "grant:\u{10000}".into()];
    let payload = create_approval_payload(
        &p,
        ApprovalOptions {
            principal: "owner",
            key: "owner-key",
            grants: &grants,
            issued_at: "2026-10-10T00:30:00.000Z",
            expires_at: "2026-10-10T02:00:00.000Z",
        },
    )
    .unwrap();
    assert_eq!(payload.grants, vec!["grant:\u{10000}", "grant:\u{e000}"]);
    approval_signing_bytes(&payload).unwrap();
}

#[test]
fn requested_typescript_tree_bytes_are_exact_governed_artifacts() {
    let candidate = candidate();
    let capture = &candidate.captures[0];
    let graph = patamaps_core::CheckedGraph::check(
        capture.inputs.graph.clone(),
        capture.inputs.packs.clone(),
    )
    .unwrap();
    let generation = patamaps_core::admit(
        &graph,
        &capture.inputs.policy,
        patamaps_core::EvaluationOptions {
            context: capture.inputs.context.clone(),
            evaluated_at: capture.inputs.evaluated_at.clone(),
        },
    )
    .unwrap();
    let spec = capture.inputs.projection_spec.as_ref().unwrap();
    let projection = patamaps_projection::project(&generation, spec).unwrap();
    let tree = patamaps_projection::compile_path_tree(&projection, spec).unwrap();
    let expected = patamaps_projection::emit_typescript_path_tree(&tree, "pathTree").unwrap();
    let proposal = propose(&candidate, &trust(), None, DeploymentIntent::Deploy);
    let name = "path-tree-1.ts";
    assert_eq!(proposal.files()[name], expected);
    let manifest = &proposal.record().artifacts;
    let descriptor = manifest
        .files
        .iter()
        .find(|entry| entry.path == name)
        .unwrap();
    assert_eq!(descriptor.byte_digest, byte_digest(expected.as_bytes()));
    assert_eq!(descriptor.byte_length.get(), expected.len() as u64);
    for remove in [false, true] {
        let mut prepared = proposal.prepared();
        if remove {
            prepared.files.remove(name);
        } else {
            prepared
                .files
                .get_mut(name)
                .unwrap()
                .push_str("// unreviewed bytes");
        }
        assert!(check_prepared(&prepared).is_err());
    }
    let mut rust_only = candidate;
    rust_only
        .emissions
        .retain(|e| matches!(e.language, EmissionLanguage::Rust));
    let files = prepare_candidate_artifacts(&rust_only, CONSUMER, ENVIRONMENT).unwrap();
    assert!(!files.files().keys().any(|name| name.ends_with(".ts")));
}
