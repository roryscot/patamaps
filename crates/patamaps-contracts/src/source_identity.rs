//! Exact source fragments exported by their owning crate for compiler identity.
pub const IDENTITY_RECIPE: &str = include_str!("source_identity.rs");
pub const CONTRACTS_MANIFEST: &str = include_str!("../Cargo.toml");
pub const CONTRACTS_BUILD: &str = include_str!("../build.rs");
pub const CONTRACTS_LIB: &str = include_str!("lib.rs");
pub const CONTRACTS: &str = include_str!("model.rs");
pub const SEMANTIC_TYPES: &str = include_str!("semantic.rs");
pub const JSON: &str = include_str!("json.rs");
pub const JSON_SCAN: &str = include_str!("json_scan.rs");
pub const LEGACY_JSON: &str = include_str!("legacy_json.rs");
pub const LEGACY_STABLE: &str = include_str!("legacy_stable.rs");
pub const INTEGER: &str = include_str!("integer.rs");

/// Digest of the exact bundled input bytes used by this dependency crate.
pub const PACKAGE_INPUTS_DIGEST: &str = env!("PATAMAPS_PACKAGE_INPUTS_DIGEST");
