use serde::Serialize;
use serde::de::{DeserializeOwned, DeserializeSeed, MapAccess, SeqAccess, Visitor};
use serde_json::{Map, Number, Value};
use sha2::{Digest, Sha256};
use std::fmt;

use crate::{MAX_INPUT_BYTES, MAX_JSON_DEPTH, MAX_JSON_VALUES};

/// Resource profiles are explicit. Compatibility nesting does not change the
/// narrower host/wire admission profile used by `parse` and `parse_value`.
#[derive(Debug, Clone, Copy)]
pub struct JsonLimits {
    pub max_bytes: usize,
    pub max_depth: usize,
    pub max_values: usize,
}

pub const STRICT_JSON_LIMITS: JsonLimits = JsonLimits {
    max_bytes: MAX_INPUT_BYTES,
    max_depth: MAX_JSON_DEPTH,
    max_values: MAX_JSON_VALUES,
};
pub const COMPATIBILITY_JSON_LIMITS: JsonLimits = JsonLimits {
    max_depth: 512,
    ..STRICT_JSON_LIMITS
};

#[derive(Debug, thiserror::Error)]
pub enum ContractError {
    #[error("INPUT_BYTE_LIMIT: input exceeds {MAX_INPUT_BYTES} bytes")]
    InputLimit,
    #[error("INPUT_BYTE_LIMIT: input exceeds {max_bytes} bytes")]
    ScopedInputLimit { max_bytes: usize },
    #[error("INVALID_JSON_RESOURCE_PROFILE: nesting must be bounded through 512 levels")]
    InvalidProfile,
    #[error("DUPLICATE_JSON_KEY: Duplicate JSON property {key_json}")]
    DuplicateKey { key_json: String },
    #[error("JSON_DEPTH_LIMIT: JSON input exceeds {max_depth} levels")]
    DepthLimit { max_depth: usize },
    #[error("INVALID_JSON: {0}")]
    Json(#[from] serde_json::Error),
    #[error("INVALID_JSON_SYNTAX: {native_message}")]
    LegacyJsonSyntax {
        message: String,
        native_message: String,
    },
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct JsonDiagnostic {
    pub code: &'static str,
    pub message: String,
    pub native_message: String,
}

impl ContractError {
    /// Compatibility diagnostics retain the native cause separately. These
    /// aliases describe parser failures; they do not turn a refusal into a pass.
    pub fn json_diagnostic(&self, limits: JsonLimits) -> JsonDiagnostic {
        let native_message = self.to_string();
        let (code, message) = match self {
            Self::DuplicateKey { key_json } => (
                "DUPLICATE_JSON_KEY",
                format!("Duplicate JSON property {key_json}"),
            ),
            Self::DepthLimit { max_depth } => (
                "JSON_DEPTH_LIMIT",
                format!("JSON input exceeds {max_depth} levels"),
            ),
            Self::LegacyJsonSyntax { message, .. } => ("INVALID_JSON_SYNTAX", message.clone()),
            Self::Json(error) => {
                let raw = error.to_string();
                let suffix = format!(" at line {} column {}", error.line(), error.column());
                let cause = raw.strip_suffix(&suffix).unwrap_or(&raw);
                if let Some(key) = cause.strip_prefix("DUPLICATE_JSON_KEY: ") {
                    (
                        "DUPLICATE_JSON_KEY",
                        format!("Duplicate JSON property {key}"),
                    )
                } else if cause == "JSON_DEPTH_LIMIT" {
                    (
                        "JSON_DEPTH_LIMIT",
                        format!("JSON input exceeds {} levels", limits.max_depth),
                    )
                } else if cause == "JSON_VALUE_LIMIT" {
                    (
                        "JSON_VALUE_LIMIT",
                        "JSON input exceeds its value budget".into(),
                    )
                } else if cause == "number out of range" || cause == "NONFINITE_JSON_NUMBER" {
                    (
                        "INVALID_JSON_VALUE",
                        "JSON numbers must be finite IEEE-754 values".into(),
                    )
                } else if cause == "unexpected end of hex escape" {
                    ("INVALID_JSON_UNICODE", "Unpaired high surrogate".into())
                } else if cause.contains("surrogate") {
                    ("INVALID_JSON_UNICODE", "Unpaired low surrogate".into())
                } else {
                    ("INVALID_JSON_SYNTAX", "Invalid JSON syntax".into())
                }
            }
            _ => ("JSON_RESOURCE_LIMIT", native_message.clone()),
        };
        JsonDiagnostic {
            code,
            message,
            native_message,
        }
    }
}

struct StrictSeed<'a> {
    depth: usize,
    max_depth: usize,
    remaining: &'a mut usize,
    last_wins: bool,
}

impl<'de> DeserializeSeed<'de> for StrictSeed<'_> {
    type Value = Value;

    fn deserialize<D: serde::Deserializer<'de>>(self, deserializer: D) -> Result<Value, D::Error> {
        if self.depth > self.max_depth {
            return Err(serde::de::Error::custom("JSON_DEPTH_LIMIT"));
        }
        if *self.remaining == 0 {
            return Err(serde::de::Error::custom("JSON_VALUE_LIMIT"));
        }
        *self.remaining -= 1;
        deserializer.deserialize_any(self)
    }
}

impl<'de> Visitor<'de> for StrictSeed<'_> {
    type Value = Value;

    fn expecting(&self, formatter: &mut fmt::Formatter) -> fmt::Result {
        formatter.write_str("strict finite JSON")
    }

    fn visit_bool<E: serde::de::Error>(self, value: bool) -> Result<Value, E> {
        Ok(Value::Bool(value))
    }

    fn visit_unit<E: serde::de::Error>(self) -> Result<Value, E> {
        Ok(Value::Null)
    }

    fn visit_i64<E: serde::de::Error>(self, value: i64) -> Result<Value, E> {
        self.visit_f64(value as f64)
    }

    fn visit_u64<E: serde::de::Error>(self, value: u64) -> Result<Value, E> {
        self.visit_f64(value as f64)
    }

    fn visit_f64<E: serde::de::Error>(self, value: f64) -> Result<Value, E> {
        // JCS's numeric domain is IEEE-754 binary64, including integer tokens.
        Number::from_f64(if value == 0.0 { 0.0 } else { value })
            .map(Value::Number)
            .ok_or_else(|| E::custom("NONFINITE_JSON_NUMBER"))
    }

    fn visit_str<E: serde::de::Error>(self, value: &str) -> Result<Value, E> {
        Ok(Value::String(value.to_owned()))
    }

    fn visit_string<E: serde::de::Error>(self, value: String) -> Result<Value, E> {
        Ok(Value::String(value))
    }

    fn visit_seq<A: SeqAccess<'de>>(self, mut access: A) -> Result<Value, A::Error> {
        let mut result = Vec::new();
        while let Some(value) = access.next_element_seed(StrictSeed {
            depth: self.depth + 1,
            max_depth: self.max_depth,
            remaining: self.remaining,
            last_wins: self.last_wins,
        })? {
            result.push(value);
        }
        Ok(Value::Array(result))
    }

    fn visit_map<A: MapAccess<'de>>(self, mut access: A) -> Result<Value, A::Error> {
        let mut result = Map::new();
        while let Some(key) = access.next_key::<String>()? {
            if !self.last_wins && result.contains_key(&key) {
                return Err(serde::de::Error::custom(format!(
                    "DUPLICATE_JSON_KEY: {}",
                    serde_json::to_string(&key).expect("JSON string")
                )));
            }
            let value = access.next_value_seed(StrictSeed {
                depth: self.depth + 1,
                max_depth: self.max_depth,
                remaining: self.remaining,
                last_wins: self.last_wins,
            })?;
            result.insert(key, value);
        }
        Ok(Value::Object(result))
    }
}

pub fn parse_value(bytes: &[u8]) -> Result<Value, ContractError> {
    parse_value_with_limits(bytes, STRICT_JSON_LIMITS)
}

pub fn parse_value_with_limits(bytes: &[u8], limits: JsonLimits) -> Result<Value, ContractError> {
    value_with_limits(bytes, limits, false)
}

/// Used only after grammar checking and reversible UTF-16 projection in the
/// read-only legacy pack profile. Ordinary typed/JCS parsing stays strict.
pub(crate) fn parse_last_wins_value(
    bytes: &[u8],
    limits: JsonLimits,
) -> Result<Value, ContractError> {
    value_with_limits(bytes, limits, true)
}

fn value_with_limits(
    bytes: &[u8],
    limits: JsonLimits,
    last_wins: bool,
) -> Result<Value, ContractError> {
    if limits.max_depth > COMPATIBILITY_JSON_LIMITS.max_depth || limits.max_values == 0 {
        return Err(ContractError::InvalidProfile);
    }
    if bytes.len() > limits.max_bytes {
        return Err(if limits.max_bytes == MAX_INPUT_BYTES {
            ContractError::InputLimit
        } else {
            ContractError::ScopedInputLimit {
                max_bytes: limits.max_bytes,
            }
        });
    }
    if last_wins {
        crate::json_scan::legacy_pack_profile(bytes, limits.max_depth)?;
    } else {
        crate::json_scan::validate(bytes, limits.max_depth)?;
    }
    let mut remaining = limits.max_values;
    let mut deserializer = serde_json::Deserializer::from_slice(bytes);
    // StrictSeed supplies a checked, finite nesting budget. Serde's unrelated
    // default limit of 128 must not truncate the 512-level compatibility domain.
    deserializer.disable_recursion_limit();
    let value = StrictSeed {
        depth: 0,
        max_depth: limits.max_depth,
        remaining: &mut remaining,
        last_wins,
    }
    .deserialize(&mut deserializer)?;
    deserializer.end()?;
    Ok(value)
}

pub fn parse<T: DeserializeOwned>(bytes: &[u8]) -> Result<T, ContractError> {
    parse_with_limits(bytes, STRICT_JSON_LIMITS)
}

pub fn parse_with_limits<T: DeserializeOwned>(
    bytes: &[u8],
    limits: JsonLimits,
) -> Result<T, ContractError> {
    Ok(serde_json::from_value(parse_value_with_limits(
        bytes, limits,
    )?)?)
}

pub fn canonical_bytes<T: Serialize>(value: &T) -> Result<Vec<u8>, ContractError> {
    Ok(serde_json_canonicalizer::to_vec(value)?)
}

pub fn canonical_digest<T: Serialize>(value: &T) -> Result<String, ContractError> {
    // Feed the same encoder directly into SHA-256, avoiding a second encoded buffer.
    struct HashWriter(Sha256);
    impl std::io::Write for HashWriter {
        fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
            self.0.update(bytes);
            Ok(bytes.len())
        }
        fn flush(&mut self) -> std::io::Result<()> {
            Ok(())
        }
    }
    let mut writer = HashWriter(Sha256::new());
    serde_json_canonicalizer::to_writer(value, &mut writer)?;
    Ok(format!("sha256:{:x}", writer.0.finalize()))
}

pub fn byte_digest(bytes: &[u8]) -> String {
    format!("sha256:{:x}", Sha256::digest(bytes))
}
