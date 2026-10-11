use patamaps_contracts::{ContentBinding, ProtocolVersion};
use patamaps_governance::{ChangeProposal, PreparedCandidate, SignedApproval, TrustedConsumer};
use serde::{Deserialize, Serialize};

macro_rules! fixed {
    ($name:ident, $value:literal) => {
        #[derive(Debug, Clone, Copy, Serialize, Deserialize)]
        pub enum $name {
            #[serde(rename = $value)]
            Draft1,
        }
    };
}
fixed!(ActivationProfile, "patamaps-linux-root-draft-1");
fixed!(RequestType, "activation-request");
fixed!(ManifestType, "activation-manifest");
fixed!(PointerType, "active-pointer");

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ActivationRequest {
    pub schema_version: ProtocolVersion,
    pub document_type: RequestType,
    pub prepared: PreparedCandidate,
    pub approval: SignedApproval,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ActivationManifest {
    pub schema_version: ProtocolVersion,
    pub document_type: ManifestType,
    pub profile: ActivationProfile,
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
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ActivePointer {
    pub schema_version: ProtocolVersion,
    pub document_type: PointerType,
    pub consumer: String,
    pub environment: String,
    pub manifest: ContentBinding,
}
