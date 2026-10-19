//! Exact source fragments exported by their owning crate for compiler identity.
pub const IDENTITY_RECIPE: &str = include_str!("source_identity.rs");
pub const PACKAGE_BUILD: &str = include_str!("../build.rs");
pub const CORE_MANIFEST: &str = include_str!("../Cargo.toml");
pub const BUILD_OBSERVATIONS: &str = include_str!("build_observations.rs");
pub const CORE_LIB: &str = include_str!("lib.rs");
pub const GRAPH: &str = include_str!("graph.rs");
pub const REGISTRY: &str = include_str!("registry.rs");
pub const LEGACY_PACK: &str = include_str!("legacy_pack.rs");
pub const LEGACY_REGISTRY: &str = include_str!("legacy_registry.rs");
pub const LEGACY_GRAPH: &str = include_str!("legacy_graph.rs");
pub const LEGACY_COMPOSITION: &str = include_str!("legacy_composition.rs");
pub const LEGACY_REPORTING: &str = include_str!("legacy_reporting.rs");
pub const LEGACY_CORRESPONDENCE: &str = include_str!("legacy_correspondence.rs");
pub const LEGACY_EVALUATION: &str = include_str!("legacy_evaluation.rs");
pub const LEGACY_VIABILITY: &str = include_str!("legacy_viability.rs");
pub const LEGACY_SEMANTIC: &str = include_str!("legacy_semantic.rs");
pub const LEGACY_UNCERTAINTY_RISK: &str = include_str!("legacy_uncertainty_risk.rs");
pub const LEGACY_CONSTRAINTS: &str = include_str!("legacy_constraints.rs");
pub const LEGACY_CLI: &str = include_str!("legacy_cli.rs");
pub const LEGACY_CLI_USAGE: &str = include_str!("legacy_cli_usage.txt");
pub const LEGACY_WORKSPACE: &str = include_str!("legacy_workspace.rs");
pub const LEGACY_REFERENCES: &str = include_str!("legacy_references.rs");
pub const LEGACY_URI_REFERENCE: &str = include_str!("legacy_uri_reference.json");
pub const LEGACY_VALIDATION: &str = include_str!("legacy_validation.rs");
pub const LEGACY_CORE: &str = include_str!("legacy_core.json");
pub const ADMISSION: &str = include_str!("admission.rs");
pub const NATIVE_CONSTRAINTS: &str = include_str!("constraints.rs");
pub const TOPOLOGY: &str = include_str!("topology.rs");
pub const LAWS: &str = include_str!("laws.rs");
pub const DERIVATION: &str = include_str!("derivation.rs");
pub const UNCERTAINTY: &str = include_str!("uncertainty.rs");
pub const RISK: &str = include_str!("risk.rs");
pub const DIFF: &str = include_str!("diff.rs");
pub const IMPACT: &str = include_str!("impact.rs");
pub const PREFLIGHT: &str = include_str!("preflight.rs");
pub const CONTROL: &str = include_str!("control.rs");

/// Digest of the exact bundled input bytes used by this dependency crate.
pub const PACKAGE_INPUTS_DIGEST: &str = env!("PATAMAPS_PACKAGE_INPUTS_DIGEST");

pub const LEGACY_PROJECTION: &str = include_str!("legacy_projection.rs");
