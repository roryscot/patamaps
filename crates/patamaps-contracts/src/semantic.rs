use crate::{
    ContextExpression, Evidence, JsonObject, Mapping, MappingSelector, ProtocolVersion, SafeInteger,
};
use serde::{Deserialize, Serialize};

pub const DERIVATION_ATTRIBUTE: &str = "metamap:derivation";

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ContentBinding {
    pub id: String,
    pub digest: String,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct PackContentBinding {
    pub id: String,
    pub version: String,
    pub digest: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum LawOperation {
    Reverse,
    Chain,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename = "conservative")]
pub enum Conservative {
    #[serde(rename = "conservative")]
    Conservative,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum NoAuthority {
    #[serde(rename = "none")]
    None,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct LawHandling {
    pub lossiness: Conservative,
    pub uncertainty: Conservative,
    pub authority: NoAuthority,
}

#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct LawConditions {
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub context: Option<ContextExpression>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub source_kinds: Option<Vec<String>>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub middle_kinds: Option<Vec<String>>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub target_kinds: Option<Vec<String>>,
}
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct RelationLaw {
    pub id: String,
    pub operation: LawOperation,
    pub operands: Vec<String>,
    pub result_relation: String,
    pub handling: LawHandling,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub conditions: Option<LawConditions>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Interpretation {
    DeclaredLawApplication,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum UncertaintyDimension {
    Identity,
    Context,
    Provenance,
    Completeness,
    CausalRelevance,
    ConflictingAuthority,
}
pub const UNCERTAINTY_DIMENSIONS: [UncertaintyDimension; 6] = [
    UncertaintyDimension::Identity,
    UncertaintyDimension::Context,
    UncertaintyDimension::Provenance,
    UncertaintyDimension::Completeness,
    UncertaintyDimension::CausalRelevance,
    UncertaintyDimension::ConflictingAuthority,
];
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum UncertaintyStatus {
    Supported,
    Contradicted,
    Unknown,
    NotApplicable,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct DerivationUncertainty {
    pub dimension: UncertaintyDimension,
    pub status: UncertaintyStatus,
    pub evidence: Vec<String>,
    pub assessments: Vec<String>,
    pub measurement_models: Vec<String>,
    pub source_revisions: Vec<String>,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct DerivationPremise {
    pub mapping: String,
    pub digest: String,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub derivation: Option<ContentBinding>,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct DerivationRule {
    pub id: String,
    pub pack: PackContentBinding,
    pub imports: Vec<PackContentBinding>,
}
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct CorrespondenceDerivation {
    pub schema_version: ProtocolVersion,
    pub document_type: DerivationType,
    pub id: String,
    pub digest: String,
    pub interpretation: Interpretation,
    pub rule: DerivationRule,
    pub premises: Vec<DerivationPremise>,
    pub result: Mapping,
    pub context: JsonObject,
    pub context_digest: String,
    pub dependencies: Vec<ContentBinding>,
    pub depth: SafeInteger,
    pub derivation_count: SafeInteger,
    pub uncertainty: Vec<DerivationUncertainty>,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum DerivationType {
    #[serde(rename = "derivation")]
    Derivation,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct DerivationBounds {
    pub max_depth: SafeInteger,
    pub max_derivations: SafeInteger,
}
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SemanticPolicy {
    pub interpretation: Interpretation,
    pub derivations: Vec<CorrespondenceDerivation>,
    pub derivation_limits: DerivationBounds,
    pub assessments: Vec<UncertaintyAssessment>,
    pub uncertainty_requirements: Vec<UncertaintyRequirement>,
    pub risk_budgets: Vec<ConsumerRiskBudget>,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct MappingDependency {
    pub mapping: String,
    pub premises: Vec<String>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub derivation: Option<ContentBinding>,
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SemanticGeneration {
    pub interpretation: Interpretation,
    pub derivations: Vec<CorrespondenceDerivation>,
    pub derivation_limits: DerivationBounds,
    pub dependencies: Vec<MappingDependency>,
    pub uncertainty: Vec<MappingUncertainty>,
    pub risk_evaluation: &'static str,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum CompositionRequestType {
    #[serde(rename = "composition-request")]
    CompositionRequest,
}
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct CompositionRequest {
    pub schema_version: ProtocolVersion,
    pub document_type: CompositionRequestType,
    pub law: String,
    pub premises: Vec<String>,
    pub context: JsonObject,
    pub bounds: DerivationBounds,
    pub derivations: Vec<CorrespondenceDerivation>,
    pub assessments: Vec<UncertaintyAssessment>,
    pub evidence: Vec<Evidence>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub result_id: Option<String>,
}

pub fn evaluation_profile(
    packs: &[crate::RelationPack],
    policy: &crate::PolicyDocument,
) -> &'static str {
    if policy.semantics.is_some() || packs.iter().any(|p| p.laws.is_some()) {
        crate::SEMANTIC_PROFILE
    } else {
        crate::PROFILE
    }
}

impl UncertaintyDimension {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Identity => "identity",
            Self::Context => "context",
            Self::Provenance => "provenance",
            Self::Completeness => "completeness",
            Self::CausalRelevance => "causal-relevance",
            Self::ConflictingAuthority => "conflicting-authority",
        }
    }
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct UncertaintyAssessment {
    pub id: String,
    pub subject: String,
    pub dimension: UncertaintyDimension,
    pub status: UncertaintyStatus,
    pub evidence: Vec<String>,
    pub assessor: String,
    pub source_revision: String,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub measurement_model: Option<String>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub not_applicable_reason: Option<String>,
}
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct UncertaintyRequirement {
    pub id: String,
    pub select: MappingSelector,
    pub dimension: UncertaintyDimension,
    pub allowed_states: Vec<UncertaintyStatus>,
    pub require_evidence: bool,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct MappingUncertainty {
    pub mapping: String,
    pub dimensions: Vec<DerivationUncertainty>,
}
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct RiskClassification {
    pub id: String,
    pub select: MappingSelector,
    pub classification: String,
    pub cost: SafeInteger,
}
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ConsumerRiskBudget {
    pub id: String,
    pub consumer: String,
    pub classifications: Vec<RiskClassification>,
    pub maximum_total_cost: SafeInteger,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub maximum_lossy_mappings: Option<SafeInteger>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub maximum_inferred_mappings: Option<SafeInteger>,
    pub require_complete_classification: bool,
    pub require_complete_dependencies: bool,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ProjectionRequirements {
    pub consumer: String,
    /// Explicit null selects no budget; policy cannot be opted out this way.
    #[serde(deserialize_with = "crate::nullable")]
    pub budget: Option<String>,
}
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProjectionClassification {
    pub mapping: String,
    pub classification: String,
    pub cost: SafeInteger,
}
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProjectionRisk {
    pub status: &'static str,
    pub budget: Option<ContentBinding>,
    pub classifications: Vec<ProjectionClassification>,
    pub total_cost: Option<SafeInteger>,
    pub lossy_mappings: Vec<String>,
    pub inferred_mappings: Vec<String>,
    pub uncertainty: Vec<MappingUncertainty>,
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProjectionSemantics {
    pub consumer: String,
    pub used_mappings: Vec<String>,
    pub dependencies: Vec<MappingDependency>,
    pub derivations: Vec<ContentBinding>,
    pub risk: ProjectionRisk,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
pub enum PathDelimiter {
    #[default]
    #[serde(rename = "/")]
    Slash,
    #[serde(rename = "--")]
    Hyphen,
    #[serde(rename = ".")]
    Dot,
}
impl PathDelimiter {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Slash => "/",
            Self::Hyphen => "--",
            Self::Dot => ".",
        }
    }
}
#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct PathTreeSpec {
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub attribute: Option<String>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub delimiter: Option<PathDelimiter>,
}
