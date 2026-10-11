use crate::{
    PackContentBinding, PathTreeSpec, ProjectionRequirements, RelationLaw, SemanticPolicy,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;

pub type JsonObject = BTreeMap<String, Value>;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ProtocolVersion {
    #[serde(rename = "0.1.0")]
    Draft1,
}

macro_rules! document_type {
    ($name:ident, $variant:ident, $wire:literal) => {
        #[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
        pub enum $name {
            #[serde(rename = $wire)]
            $variant,
        }
    };
}
document_type!(GraphType, Graph, "graph");
document_type!(PackType, RelationPack, "relation-pack");
document_type!(PolicyType, Policy, "policy");
document_type!(ProjectionType, ProjectionSpec, "projection-spec");

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct GraphDocument {
    #[serde(
        rename = "$schema",
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub schema: Option<String>,
    pub schema_version: ProtocolVersion,
    pub document_type: GraphType,
    pub id: String,
    pub namespace: String,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub label: Option<String>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub revision: Option<String>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub relation_packs: Option<Vec<PackReference>>,
    pub entities: Vec<Entity>,
    pub mappings: Vec<Mapping>,
    pub authorities: Vec<Authority>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub metadata: Option<JsonObject>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub extensions: Option<JsonObject>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct PackReference {
    pub id: String,
    pub version: String,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub uri: Option<String>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub digest: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Entity {
    pub id: String,
    pub kind: String,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub label: Option<String>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub schema: Option<String>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub locators: Option<Vec<Locator>>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub attributes: Option<JsonObject>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub provenance: Option<Provenance>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Locator {
    pub uri: String,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub media_type: Option<String>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub revision: Option<String>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub digest: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ProvenanceStatus {
    Declared,
    Observed,
    Generated,
    Inferred,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Provenance {
    pub status: ProvenanceStatus,
    pub asserted_by: String,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub observed_at: Option<String>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub source_revision: Option<String>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub confidence: Option<f64>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Cardinality {
    OneToOne,
    OneToMany,
    ManyToOne,
    ManyToMany,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Lossiness {
    Lossless,
    Lossy,
    Unknown,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Mapping {
    pub id: String,
    pub relation: String,
    pub sources: Vec<String>,
    pub targets: Vec<String>,
    pub cardinality: Cardinality,
    pub lossiness: Lossiness,
    pub provenance: Provenance,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub transform: Option<Transform>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub invariants: Option<Vec<String>>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub attributes: Option<JsonObject>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Transform {
    pub adapter: String,
    pub version: String,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub entrypoint: Option<String>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub deterministic: Option<bool>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub reversible: Option<bool>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub configuration: Option<JsonObject>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum AuthorityMode {
    Canonical,
    Delegated,
    Candidate,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Authority {
    pub id: String,
    pub concept: String,
    pub source: String,
    pub facts: Vec<String>,
    pub mode: AuthorityMode,
    pub provenance: Provenance,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub delegated_from: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum CyclePolicy {
    Allow,
    Forbid,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ImpactDirection {
    SourceToTarget,
    TargetToSource,
    Both,
    None,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Relation {
    pub id: String,
    pub cycle_policy: CyclePolicy,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub description: Option<String>,
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
    pub target_kinds: Option<Vec<String>>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub cardinalities: Option<Vec<Cardinality>>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub transitive: Option<bool>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub symmetric: Option<bool>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub inverse: Option<String>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub composes_with: Option<Vec<String>>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub impact_direction: Option<ImpactDirection>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub disjoint_with: Option<Vec<String>>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct RelationPack {
    #[serde(
        rename = "$schema",
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub schema: Option<String>,
    pub schema_version: ProtocolVersion,
    pub document_type: PackType,
    pub id: String,
    pub version: String,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub description: Option<String>,
    pub relations: Vec<Relation>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub imports: Option<Vec<PackContentBinding>>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub laws: Option<Vec<RelationLaw>>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct GraphBinding {
    pub id: String,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub revision: Option<String>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub digest: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct MappingSelector {
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub ids: Option<Vec<String>>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub relations: Option<Vec<String>>,
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
    pub target_kinds: Option<Vec<String>>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub provenance_statuses: Option<Vec<ProvenanceStatus>>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Coverage {
    Total,
    Partial,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Determinism {
    Deterministic,
    Nondeterministic,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Reversibility {
    Reversible,
    Irreversible,
}

// Untagged variants are closed independently: malformed or mixed expressions reject.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(untagged, deny_unknown_fields)]
pub enum ContextExpression {
    All {
        all: Vec<ContextExpression>,
    },
    Any {
        any: Vec<ContextExpression>,
    },
    Not {
        not: Box<ContextExpression>,
    },
    Comparison {
        key: String,
        operator: ComparisonOperator,
        value: Value,
    },
    Membership {
        key: String,
        operator: MembershipOperator,
        values: Vec<Value>,
    },
    Exists {
        key: String,
        operator: ExistsOperator,
        #[serde(
            default,
            deserialize_with = "crate::present",
            skip_serializing_if = "Option::is_none"
        )]
        value: Option<bool>,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ComparisonOperator {
    Equals,
    NotEquals,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum MembershipOperator {
    In,
    NotIn,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ExistsOperator {
    #[serde(rename = "exists")]
    Exists,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Applicability {
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub when: Option<ContextExpression>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub unless: Option<ContextExpression>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Declaration {
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub mapping: Option<String>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub select: Option<MappingSelector>,
    pub coverage: Coverage,
    pub determinism: Determinism,
    pub reversibility: Reversibility,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub applicability: Option<Applicability>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Constraint {
    pub id: String,
    pub kind: String,
    pub subjects: Vec<String>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub parameters: Option<JsonObject>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum EvidenceResult {
    Supports,
    Contradicts,
    Inconclusive,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Evidence {
    pub id: String,
    pub subjects: Vec<String>,
    pub kind: String,
    pub result: EvidenceResult,
    pub producer: String,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub observed_at: Option<String>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub confidence: Option<f64>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub locator: Option<Locator>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub digest: Option<String>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub attributes: Option<JsonObject>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Waiver {
    pub id: String,
    pub codes: Vec<String>,
    pub subjects: Vec<String>,
    pub reason: String,
    pub expires_at: String,
    pub asserted_by: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct PolicyDocument {
    #[serde(
        rename = "$schema",
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub schema: Option<String>,
    pub schema_version: ProtocolVersion,
    pub document_type: PolicyType,
    pub id: String,
    pub graph: GraphBinding,
    pub mappings: Vec<Declaration>,
    pub constraints: Vec<Constraint>,
    pub evidence: Vec<Evidence>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub waivers: Option<Vec<Waiver>>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub metadata: Option<JsonObject>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub semantics: Option<SemanticPolicy>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SlotDirection {
    Incoming,
    Outgoing,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SlotCardinality {
    ExactlyOne,
    ZeroOrOne,
    OneOrMore,
    Many,
}

#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct EntitySelection {
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub ids: Option<Vec<String>>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub kinds: Option<Vec<String>>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SlotSpec {
    pub name: String,
    pub relation: String,
    pub direction: SlotDirection,
    pub cardinality: SlotCardinality,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub target_kinds: Option<Vec<String>>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub allow_lossy: Option<bool>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ProjectionSpec {
    #[serde(
        rename = "$schema",
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub schema: Option<String>,
    pub schema_version: ProtocolVersion,
    pub document_type: ProjectionType,
    pub id: String,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub consumer: Option<String>,
    pub select: EntitySelection,
    pub slots: Vec<SlotSpec>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub semantics: Option<ProjectionRequirements>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub path_tree: Option<PathTreeSpec>,
    #[serde(
        default,
        deserialize_with = "crate::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub metadata: Option<JsonObject>,
}
