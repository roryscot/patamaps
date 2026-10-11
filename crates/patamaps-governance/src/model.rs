use patamaps_contracts::{ContentBinding, ProtocolVersion, SafeInteger};
use patamaps_projection::CaptureRecord;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

macro_rules! fixed {
    ($name:ident,$value:literal) => {
        #[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
        pub enum $name {
            #[serde(rename = $value)]
            Draft1,
        }
    };
}
fixed!(GovernanceProfile, "patamaps-governance-draft-1");
fixed!(TrustType, "trusted-consumer");
fixed!(ArtifactType, "artifact-manifest");
fixed!(ProposalType, "change-proposal");
fixed!(ApprovalType, "approval");
fixed!(PreparedType, "prepared-candidate");
fixed!(TrustMode, "governed");
fixed!(SignatureAlgorithm, "Ed25519");
fixed!(ApprovalDomain, "urn:patamaps:approval:draft:1");
fixed!(DeploymentProfile, "patamaps-linux-root-draft-1");

/// Optional for portable governance; mandatory for protected activation.
/// The complete value participates in the externally signed trust binding.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct DeploymentBinding {
    pub profile: DeploymentProfile,
    pub state_directory: String,
    pub proposal_roots: Vec<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum GovernanceAction {
    Activate,
    Bootstrap,
    Rollback,
    RebindImplementation,
    ChangeGraph,
    ChangeAuthority,
    ChangePolicy,
    RelaxPolicy,
    RaiseBudget,
    AddWaiver,
    ChangeLaw,
    ChangeSource,
    ChangeContext,
    ChangeProjection,
}
impl GovernanceAction {
    pub fn owner_required(self) -> bool {
        matches!(
            self,
            Self::Bootstrap
                | Self::Rollback
                | Self::ChangeAuthority
                | Self::ChangePolicy
                | Self::RelaxPolicy
                | Self::RaiseBudget
                | Self::AddWaiver
                | Self::ChangeLaw
        )
    }
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct GovernanceScope {
    pub subject: String,
    pub fact: String,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct GovernanceRequirement {
    pub action: GovernanceAction,
    pub subject: String,
    pub fact: String,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum PrincipalRole {
    Owner,
    Agent,
    Service,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct TrustedPrincipal {
    pub id: String,
    pub role: PrincipalRole,
    pub revoked: bool,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct TrustedKey {
    pub id: String,
    pub principal: String,
    pub algorithm: SignatureAlgorithm,
    pub public_key: String,
    pub valid_from: String,
    pub valid_until: String,
    pub revoked: bool,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct TrustedGrant {
    pub id: String,
    pub principal: String,
    pub actions: Vec<GovernanceAction>,
    pub scopes: Vec<GovernanceScope>,
    pub valid_from: String,
    pub valid_until: String,
    pub revoked: bool,
}
/// Untrusted wire data. Only the protected host can establish its provenance.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct TrustedConsumer {
    pub schema_version: ProtocolVersion,
    pub document_type: TrustType,
    pub mode: TrustMode,
    pub id: String,
    pub revision: String,
    pub consumer: String,
    pub environment: String,
    pub principals: Vec<TrustedPrincipal>,
    pub keys: Vec<TrustedKey>,
    pub grants: Vec<TrustedGrant>,
    #[serde(
        default,
        deserialize_with = "patamaps_contracts::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub deployment: Option<DeploymentBinding>,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct TrustBinding {
    pub id: String,
    pub revision: String,
    pub digest: String,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum EmissionLanguage {
    Rust,
    Typescript,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ArtifactEmission {
    pub projection: String,
    pub language: EmissionLanguage,
    #[serde(
        default,
        deserialize_with = "patamaps_contracts::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub binding_slot: Option<String>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct GovernedCandidate {
    pub captures: Vec<CaptureRecord>,
    pub emissions: Vec<ArtifactEmission>,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ArtifactMediaType {
    #[serde(rename = "application/json")]
    Json,
    #[serde(rename = "text/typescript")]
    Typescript,
    #[serde(rename = "text/rust")]
    Rust,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ArtifactFile {
    pub path: String,
    pub media_type: ArtifactMediaType,
    pub byte_digest: String,
    pub byte_length: SafeInteger,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ArtifactManifest {
    pub schema_version: ProtocolVersion,
    pub document_type: ArtifactType,
    pub profile: GovernanceProfile,
    pub id: String,
    pub digest: String,
    pub consumer: String,
    pub environment: String,
    pub captures: Vec<ContentBinding>,
    pub files: Vec<ArtifactFile>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct GovernedBaseline {
    pub manifest_digest: String,
    pub candidate: GovernedCandidate,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum DeploymentIntent {
    Deploy,
    Rollback,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ChangeProposal {
    pub schema_version: ProtocolVersion,
    pub document_type: ProposalType,
    pub profile: GovernanceProfile,
    pub engine: String,
    pub id: String,
    pub digest: String,
    pub consumer: String,
    pub environment: String,
    pub intent: DeploymentIntent,
    pub proposer: String,
    pub trust: TrustBinding,
    #[serde(deserialize_with = "patamaps_contracts::nullable")]
    pub baseline: Option<GovernedBaseline>,
    pub candidate: GovernedCandidate,
    pub artifacts: ArtifactManifest,
    pub requirements: Vec<GovernanceRequirement>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct PreparedCandidate {
    pub schema_version: ProtocolVersion,
    pub document_type: PreparedType,
    pub proposal: ChangeProposal,
    pub files: BTreeMap<String, String>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ApprovalPayload {
    pub domain: ApprovalDomain,
    pub schema_version: ProtocolVersion,
    pub algorithm: SignatureAlgorithm,
    pub profile: GovernanceProfile,
    pub engine: String,
    pub proposal: ContentBinding,
    pub artifacts: ContentBinding,
    #[serde(deserialize_with = "patamaps_contracts::nullable")]
    pub baseline: Option<String>,
    pub consumer: String,
    pub environment: String,
    pub intent: DeploymentIntent,
    pub trust: TrustBinding,
    pub principal: String,
    pub key: String,
    pub grants: Vec<String>,
    pub requirements: Vec<GovernanceRequirement>,
    pub issued_at: String,
    pub expires_at: String,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SignedApproval {
    pub schema_version: ProtocolVersion,
    pub document_type: ApprovalType,
    pub id: String,
    pub digest: String,
    pub payload: ApprovalPayload,
    pub signature: String,
}
/// Current context must be obtained separately from candidate requests.
#[derive(Debug)]
pub struct VerificationContext<'a> {
    pub trust: &'a TrustedConsumer,
    pub baseline: Option<&'a GovernedBaseline>,
    pub now: &'a str,
}
#[derive(Debug)]
pub struct ProposalOptions<'a> {
    pub consumer: &'a str,
    pub environment: &'a str,
    pub proposer: &'a str,
    pub intent: DeploymentIntent,
    pub trust: &'a TrustedConsumer,
    pub baseline: Option<&'a GovernedBaseline>,
}
#[derive(Debug)]
pub struct ApprovalOptions<'a> {
    pub principal: &'a str,
    pub key: &'a str,
    pub grants: &'a [String],
    pub issued_at: &'a str,
    pub expires_at: &'a str,
}
