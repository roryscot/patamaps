use crate::{model::*, util::*};
use base64::{Engine, engine::general_purpose::STANDARD};
use ed25519_dalek::{Signature, VerifyingKey};
use patamaps_contracts::{MAX_INPUT_BYTES, canonical_digest};
use std::collections::{BTreeMap, BTreeSet};
use time::{OffsetDateTime, format_description::well_known::Rfc3339};

pub(crate) fn instant(text: &str) -> Result<OffsetDateTime> {
    if text.len() != 24 || !text.is_ascii() {
        return fail(
            "GOVERNANCE_INVALID_TIME",
            "Expected exact UTC timestamp with milliseconds",
        );
    }
    let value = OffsetDateTime::parse(text, &Rfc3339).map_err(|_| {
        patamaps_core::CheckError(vec![patamaps_core::Issue::error(
            "GOVERNANCE_INVALID_TIME",
            "Invalid time",
            "governance",
        )])
    })?;
    let expected = format!(
        "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}.{:03}Z",
        value.year(),
        u8::from(value.month()),
        value.day(),
        value.hour(),
        value.minute(),
        value.second(),
        value.millisecond()
    );
    if value.offset() != time::UtcOffset::UTC || expected != text {
        return fail(
            "GOVERNANCE_INVALID_TIME",
            "Time is not exact UTC millisecond form",
        );
    }
    Ok(value)
}
pub(crate) fn interval(from: &str, until: &str) -> Result<(OffsetDateTime, OffsetDateTime)> {
    let (a, b) = (instant(from)?, instant(until)?);
    if a >= b {
        return fail("GOVERNANCE_INVALID_TIME", "Interval is empty or reversed");
    }
    Ok((a, b))
}
pub(crate) fn base64(value: &str, length: usize) -> Result<Vec<u8>> {
    if value.len() != length.div_ceil(3) * 4 {
        return fail("GOVERNANCE_INVALID_CRYPTO", "Wrong encoded byte length");
    }
    let Ok(bytes) = STANDARD.decode(value) else {
        return fail("GOVERNANCE_INVALID_CRYPTO", "Invalid canonical base64");
    };
    if bytes.len() != length || STANDARD.encode(&bytes) != value {
        return fail(
            "GOVERNANCE_INVALID_CRYPTO",
            "Noncanonical base64 or incorrect byte length",
        );
    }
    Ok(bytes)
}
pub(crate) fn public_key(value: &str) -> Result<VerifyingKey> {
    const PREFIX: [u8; 12] = [
        0x30, 0x2a, 0x30, 0x05, 0x06, 0x03, 0x2b, 0x65, 0x70, 0x03, 0x21, 0,
    ];
    let bytes = base64(value, 44)?;
    if bytes[..12] != PREFIX {
        return fail(
            "GOVERNANCE_INVALID_CRYPTO",
            "Expected exact Ed25519 SPKI DER",
        );
    }
    let raw: [u8; 32] = bytes[12..].try_into().expect("checked DER length");
    let Ok(key) = VerifyingKey::from_bytes(&raw) else {
        return fail("GOVERNANCE_INVALID_CRYPTO", "Invalid Ed25519 point");
    };
    if key.is_weak() || key.to_edwards().compress().to_bytes() != raw {
        return fail(
            "GOVERNANCE_INVALID_CRYPTO",
            "Weak or noncanonical public point",
        );
    }
    Ok(key)
}
/// Fixed strict Ed25519 verification, with no private key inputs.
pub fn verify_ed25519_signature(data: &[u8], key: &str, signature: &str) -> Result<bool> {
    if data.len() > MAX_INPUT_BYTES {
        return fail(
            "GOVERNANCE_RESOURCE_LIMIT",
            "Signing data exceeds byte bound",
        );
    }
    let key = public_key(key)?;
    let bytes = base64(signature, 64)?;
    let signature = Signature::from_slice(&bytes).expect("checked signature length");
    Ok(key.verify_strict(data, &signature).is_ok())
}
#[derive(Debug)]
pub(crate) struct CheckedTrust {
    pub record: TrustedConsumer,
    pub principal_indices: BTreeMap<String, usize>,
    pub key_indices: BTreeMap<String, usize>,
    pub grant_indices: BTreeMap<String, usize>,
}
impl CheckedTrust {
    pub fn check(value: &TrustedConsumer) -> Result<Self> {
        if value.principals.is_empty()
            || value.principals.len() > 1024
            || value.keys.len() > 4096
            || value.grants.len() > 4096
        {
            return fail(
                "GOVERNANCE_RESOURCE_LIMIT",
                "Trust inventories exceed profile bounds",
            );
        }
        let value: TrustedConsumer = normalized(value)?;
        if let Some(d) = &value.deployment {
            let path = |s: &str| {
                s.len() > 1
                    && s.len() <= 4096
                    && s.starts_with('/')
                    && !s.ends_with('/')
                    && !s.chars().any(char::is_control)
                    && s.split('/')
                        .skip(1)
                        .all(|v| !v.is_empty() && v != "." && v != "..")
            };
            if !path(&d.state_directory)
                || d.proposal_roots.is_empty()
                || d.proposal_roots.len() > 128
                || d.proposal_roots.iter().any(|p| !path(p))
                || d.proposal_roots.iter().collect::<BTreeSet<_>>().len() != d.proposal_roots.len()
            {
                return fail(
                    "GOVERNANCE_INVALID_DEPLOYMENT",
                    "Deployment paths must be normalized absolute paths with unique proposal roots",
                );
            }
        }
        if !patamaps_core::valid_identifier(&value.id)
            || !patamaps_core::valid_identifier(&value.consumer)
            || !text(&value.revision)
            || !text(&value.environment)
        {
            return fail(
                "GOVERNANCE_INVALID_TRUST",
                "Invalid trust identity, consumer, revision or environment",
            );
        }
        let (mut ps, mut ks, mut gs, mut owners) = (
            BTreeMap::new(),
            BTreeMap::new(),
            BTreeMap::new(),
            BTreeMap::new(),
        );
        for (i, p) in value.principals.iter().enumerate() {
            if !text(&p.id) || ps.insert(p.id.clone(), i).is_some() {
                return fail(
                    "GOVERNANCE_DUPLICATE_ID",
                    "Invalid or duplicate principal identity",
                );
            }
        }
        for (i, k) in value.keys.iter().enumerate() {
            if !text(&k.id) || ks.insert(k.id.clone(), i).is_some() {
                return fail(
                    "GOVERNANCE_DUPLICATE_ID",
                    "Invalid or duplicate key identity",
                );
            }
            if !ps.contains_key(&k.principal) {
                return fail(
                    "GOVERNANCE_UNKNOWN_PRINCIPAL",
                    "Key names unregistered principal",
                );
            }
            interval(&k.valid_from, &k.valid_until)?;
            public_key(&k.public_key)?;
            if let Some(old) = owners.insert(k.public_key.clone(), k.principal.clone())
                && old != k.principal
            {
                return fail(
                    "GOVERNANCE_SHARED_IDENTITY_KEY",
                    "One public key cannot represent independent principals",
                );
            }
        }
        for (i, g) in value.grants.iter().enumerate() {
            if !text(&g.id) || gs.insert(g.id.clone(), i).is_some() {
                return fail(
                    "GOVERNANCE_DUPLICATE_ID",
                    "Invalid or duplicate grant identity",
                );
            }
            if !ps.contains_key(&g.principal) {
                return fail(
                    "GOVERNANCE_UNKNOWN_PRINCIPAL",
                    "Grant names unregistered principal",
                );
            }
            interval(&g.valid_from, &g.valid_until)?;
            if g.actions.is_empty()
                || g.actions.iter().collect::<BTreeSet<_>>().len() != g.actions.len()
                || g.scopes.is_empty()
                || g.scopes.len() > 128
            {
                return fail(
                    "GOVERNANCE_INVALID_GRANT",
                    "Actions/scopes must be nonempty, unique and bounded",
                );
            }
            let mut scopes = BTreeSet::new();
            for s in &g.scopes {
                if !text(&s.subject) || !text(&s.fact) || !scopes.insert((&s.subject, &s.fact)) {
                    return fail(
                        "GOVERNANCE_INVALID_GRANT",
                        "Invalid or duplicate grant scope",
                    );
                }
            }
        }
        Ok(Self {
            record: value,
            principal_indices: ps,
            key_indices: ks,
            grant_indices: gs,
        })
    }
    pub fn binding(&self) -> Result<TrustBinding> {
        Ok(TrustBinding {
            id: self.record.id.clone(),
            revision: self.record.revision.clone(),
            digest: canonical_digest(&self.record)?,
        })
    }
}
pub fn check_trusted_consumer(value: &TrustedConsumer) -> Result<TrustBinding> {
    CheckedTrust::check(value)?.binding()
}
