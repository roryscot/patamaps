use crate::{
    model::*,
    proposal::{CheckedProposal, baseline},
    trust::*,
    util::*,
};
use patamaps_contracts::{ContentBinding, ProtocolVersion, canonical_bytes};
use serde::Serialize;
use std::collections::BTreeSet;

fn validate_payload(payload: &ApprovalPayload) -> Result<()> {
    interval(&payload.issued_at, &payload.expires_at)?;
    if !text(&payload.principal)
        || !text(&payload.key)
        || payload.grants.is_empty()
        || payload.grants.len() > 4096
        || payload.grants.iter().any(|g| !text(g))
        || payload.grants.iter().collect::<BTreeSet<_>>().len() != payload.grants.len()
        || !payload
            .grants
            .windows(2)
            .all(|g| g[0].encode_utf16().cmp(g[1].encode_utf16()).is_le())
        || payload.requirements.len() > 100_000
    {
        return fail(
            "GOVERNANCE_INVALID_SHAPE",
            "Approval identities/grants must be valid, unique, sorted and bounded",
        );
    }
    Ok(())
}
pub fn approval_signing_bytes(payload: &ApprovalPayload) -> Result<Vec<u8>> {
    validate_payload(payload)?;
    let bytes = canonical_bytes(payload)?;
    patamaps_contracts::parse_value(&bytes)?;
    Ok(bytes)
}
pub fn create_approval_payload(
    proposal: &CheckedProposal,
    options: ApprovalOptions<'_>,
) -> Result<ApprovalPayload> {
    let p = proposal.record();
    let mut grants = options.grants.to_vec();
    grants.sort_by(|a, b| a.encode_utf16().cmp(b.encode_utf16()));
    let payload = ApprovalPayload {
        domain: ApprovalDomain::Draft1,
        schema_version: ProtocolVersion::Draft1,
        algorithm: SignatureAlgorithm::Draft1,
        profile: GovernanceProfile::Draft1,
        engine: p.engine.clone(),
        proposal: ContentBinding {
            id: p.id.clone(),
            digest: p.digest.clone(),
        },
        artifacts: ContentBinding {
            id: p.artifacts.id.clone(),
            digest: p.artifacts.digest.clone(),
        },
        baseline: p.baseline.as_ref().map(|b| b.manifest_digest.clone()),
        consumer: p.consumer.clone(),
        environment: p.environment.clone(),
        intent: p.intent,
        trust: p.trust.clone(),
        principal: options.principal.into(),
        key: options.key.into(),
        grants,
        requirements: p.requirements.clone(),
        issued_at: options.issued_at.into(),
        expires_at: options.expires_at.into(),
    };
    validate_payload(&payload)?;
    approval_signing_bytes(&payload)?;
    Ok(payload)
}
/// Attaches only an external signature; the resulting record is unapproved data.
pub fn attach_signature(payload: ApprovalPayload, signature: &str) -> Result<SignedApproval> {
    approval_signing_bytes(&payload)?;
    base64(signature, 64)?;
    let mut approval = SignedApproval {
        schema_version: ProtocolVersion::Draft1,
        document_type: ApprovalType::Draft1,
        id: String::new(),
        digest: String::new(),
        payload,
        signature: signature.into(),
    };
    approval.digest = document_digest(&approval)?;
    approval.id = address("approval", &approval.digest);
    normalized(&approval)
}
pub fn check_signed_approval(value: &SignedApproval) -> Result<SignedApproval> {
    if value.payload.requirements.len() > 100_000 || value.payload.grants.len() > 4096 {
        return fail(
            "GOVERNANCE_RESOURCE_LIMIT",
            "Approval lists exceed profile bounds",
        );
    }
    let value: SignedApproval = normalized(value)?;
    check_address(&value, "approval", &value.id, &value.digest)?;
    approval_signing_bytes(&value.payload)?;
    base64(&value.signature, 64)?;
    Ok(value)
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AuthorizationRecord {
    pub status: &'static str,
    pub principal: String,
    pub approval: ContentBinding,
    pub grants: Vec<String>,
    pub proposal: ContentBinding,
    pub artifacts: ContentBinding,
    pub trust: TrustBinding,
    pub evaluated_at: String,
}
/// Current authorization under supplied context; does not establish host trust.
///
/// ```compile_fail
/// use patamaps_governance::AuthorizedChange;
/// let forged:AuthorizedChange=serde_json::from_str("{}").unwrap();
/// ```
#[derive(Debug)]
pub struct AuthorizedChange<'a> {
    proposal: &'a CheckedProposal,
    approval: SignedApproval,
    trust: TrustedConsumer,
    record: AuthorizationRecord,
}
impl AuthorizedChange<'_> {
    pub fn record(&self) -> &AuthorizationRecord {
        &self.record
    }
    pub fn proposal(&self) -> &CheckedProposal {
        self.proposal
    }
    pub fn approval(&self) -> &SignedApproval {
        &self.approval
    }
    pub fn accepted_trust(&self) -> &TrustedConsumer {
        &self.trust
    }
}
/// No I/O or ambient clock. R7 must supply current protected context and repeat
/// this verification while holding the host lock immediately before publication.
pub fn verify_approval<'a>(
    proposal: &'a CheckedProposal,
    approval: &SignedApproval,
    context: VerificationContext<'_>,
) -> Result<AuthorizedChange<'a>> {
    let config = CheckedTrust::check(context.trust)?;
    let approval = check_signed_approval(approval)?;
    let payload = &approval.payload;
    let p = proposal.record();
    let now = instant(context.now)?;
    let current_base = baseline(context.baseline, &config.record.consumer)?;
    if !equal(&p.baseline, &current_base)? {
        return fail(
            "GOVERNANCE_STALE_BASELINE",
            "Proposal differs from current separately supplied baseline",
        );
    }
    if p.consumer != config.record.consumer || p.environment != config.record.environment {
        return fail(
            "GOVERNANCE_WRONG_ENVIRONMENT",
            "Proposal differs from externally configured consumer/environment",
        );
    }
    let trust = config.binding()?;
    if p.trust != trust {
        return fail(
            "GOVERNANCE_STALE_TRUST",
            "Proposal binds different current trust content/revision",
        );
    }
    let expected = create_approval_payload(
        proposal,
        ApprovalOptions {
            principal: &payload.principal,
            key: &payload.key,
            grants: &payload.grants,
            issued_at: &payload.issued_at,
            expires_at: &payload.expires_at,
        },
    )?;
    if !equal(payload, &expected)? {
        return fail(
            "GOVERNANCE_APPROVAL_CONTENT_MISMATCH",
            "Approval must bind exact proposal, artifacts, base, delta, engine, profile, consumer and intent",
        );
    }
    let (start, end) = interval(&payload.issued_at, &payload.expires_at)?;
    if now < start || now >= end {
        return fail(
            "GOVERNANCE_APPROVAL_NOT_CURRENT",
            "Approval is unissued or expired at supplied current time",
        );
    }
    let (Some(pi), Some(ki)) = (
        config.principal_indices.get(&payload.principal),
        config.key_indices.get(&payload.key),
    ) else {
        return fail(
            "GOVERNANCE_UNKNOWN_IDENTITY",
            "Principal/key is not externally registered",
        );
    };
    let (principal, key) = (&config.record.principals[*pi], &config.record.keys[*ki]);
    if key.principal != principal.id {
        return fail(
            "GOVERNANCE_UNKNOWN_IDENTITY",
            "Key is not assigned to the signed principal",
        );
    }
    if principal.revoked || key.revoked {
        return fail("GOVERNANCE_REVOKED", "Principal or key is revoked");
    }
    let (key_start, key_end) = interval(&key.valid_from, &key.valid_until)?;
    if now < key_start || now >= key_end || start < key_start || end > key_end {
        return fail(
            "GOVERNANCE_KEY_NOT_CURRENT",
            "Key must cover current time and full signed interval",
        );
    }
    if !verify_ed25519_signature(
        &approval_signing_bytes(payload)?,
        &key.public_key,
        &approval.signature,
    )? {
        return fail(
            "GOVERNANCE_BAD_SIGNATURE",
            "Signature is invalid for externally trusted key",
        );
    }
    if principal.role != PrincipalRole::Owner
        && p.requirements.iter().any(|r| r.action.owner_required())
    {
        return fail(
            "GOVERNANCE_OWNER_REQUIRED",
            "Protected changes require externally registered owner and scoped grants",
        );
    }
    let mut grants = Vec::new();
    for id in &payload.grants {
        let Some(index) = config.grant_indices.get(id) else {
            return fail(
                "GOVERNANCE_UNKNOWN_GRANT",
                "Selected grant is not externally registered",
            );
        };
        let g = &config.record.grants[*index];
        if g.principal != principal.id {
            return fail(
                "GOVERNANCE_UNKNOWN_GRANT",
                "Selected grant belongs to another principal",
            );
        }
        if g.revoked {
            return fail("GOVERNANCE_REVOKED", "Selected grant is revoked");
        }
        let (gs, ge) = interval(&g.valid_from, &g.valid_until)?;
        if now < gs || now >= ge || start < gs || end > ge {
            return fail(
                "GOVERNANCE_GRANT_NOT_CURRENT",
                "Grant must cover current time and entire signed interval",
            );
        }
        grants.push(g);
    }
    let mut work = 0usize;
    for r in &p.requirements {
        let mut covered = false;
        for g in &grants {
            work += 1;
            if work > 2_000_000 {
                return fail(
                    "GOVERNANCE_RESOURCE_LIMIT",
                    "Grant verification work bound exhausted",
                );
            }
            if !g.actions.contains(&r.action) {
                continue;
            }
            for s in &g.scopes {
                work += 1;
                if work > 2_000_000 {
                    return fail(
                        "GOVERNANCE_RESOURCE_LIMIT",
                        "Grant verification work bound exhausted",
                    );
                }
                if (s.subject == "*" || s.subject == r.subject)
                    && (s.fact == "*" || s.fact == r.fact)
                {
                    covered = true;
                    break;
                }
            }
            if covered {
                break;
            }
        }
        if !covered {
            return fail(
                "GOVERNANCE_SCOPE_DENIED",
                "No selected external grant covers a required action and subject/fact together",
            );
        }
    }
    let record = AuthorizationRecord {
        status: "authorized-under-supplied-context",
        principal: principal.id.clone(),
        approval: ContentBinding {
            id: approval.id.clone(),
            digest: approval.digest.clone(),
        },
        grants: payload.grants.clone(),
        proposal: ContentBinding {
            id: p.id.clone(),
            digest: p.digest.clone(),
        },
        artifacts: ContentBinding {
            id: p.artifacts.id.clone(),
            digest: p.artifacts.digest.clone(),
        },
        trust,
        evaluated_at: context.now.into(),
    };
    Ok(AuthorizedChange {
        proposal,
        approval,
        trust: config.record,
        record,
    })
}
