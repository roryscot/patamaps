//! Draft wire records carry no checked, admitted, or authorized status.
#![forbid(unsafe_code)]

mod integer;
mod json;
mod json_scan;
mod legacy_json;
mod legacy_stable;
mod model;
mod semantic;

pub use integer::{MAX_SAFE_INTEGER, SafeInteger};
pub use json::{
    COMPATIBILITY_JSON_LIMITS, ContractError, JsonDiagnostic, JsonLimits, STRICT_JSON_LIMITS,
    byte_digest, canonical_bytes, canonical_digest, parse, parse_value, parse_value_with_limits,
    parse_with_limits,
};
pub use legacy_json::{LegacyPackJson, LegacyReadOnlyJson};
#[doc(hidden)]
pub use legacy_stable::LegacyOrderedJson;
#[doc(hidden)]
pub const LEGACY_COLLATOR_SOURCE_DIGEST: &str = env!("PATAMAPS_COLLATOR_SOURCE_DIGEST");
pub use model::*;
pub use semantic::*;

pub const MAX_INPUT_BYTES: usize = 16 * 1024 * 1024;
pub const MAX_JSON_DEPTH: usize = 64;
pub const MAX_JSON_VALUES: usize = 2_000_000;
pub const PROFILE: &str = "patamaps-routing-draft-1";
pub const SEMANTIC_PROFILE: &str = "patamaps-semantic-draft-1";

/// Optional object fields may be absent, but explicit null is not absence.
pub fn present<'de, D, T>(deserializer: D) -> Result<Option<T>, D::Error>
where
    D: serde::Deserializer<'de>,
    T: serde::Deserialize<'de>,
{
    T::deserialize(deserializer).map(Some)
}

/// A nullable field must still be present when its meaning is an explicit
/// choice. Serde's ordinary Option otherwise silently treats absence as null.
pub fn nullable<'de, D, T>(deserializer: D) -> Result<Option<T>, D::Error>
where
    D: serde::Deserializer<'de>,
    T: serde::Deserialize<'de>,
{
    <Option<T> as serde::Deserialize>::deserialize(deserializer)
}
