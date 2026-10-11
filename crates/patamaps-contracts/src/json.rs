use serde::Serialize;
use serde::de::{DeserializeOwned, DeserializeSeed, MapAccess, SeqAccess, Visitor};
use serde_json::{Map, Number, Value};
use sha2::{Digest, Sha256};
use std::fmt;

use crate::{MAX_INPUT_BYTES, MAX_JSON_DEPTH, MAX_JSON_VALUES};

#[derive(Debug, thiserror::Error)]
pub enum ContractError {
    #[error("INPUT_BYTE_LIMIT: input exceeds {MAX_INPUT_BYTES} bytes")]
    InputLimit,
    #[error("INVALID_JSON: {0}")]
    Json(#[from] serde_json::Error),
}

struct StrictSeed<'a> {
    depth: usize,
    remaining: &'a mut usize,
}

impl<'de> DeserializeSeed<'de> for StrictSeed<'_> {
    type Value = Value;

    fn deserialize<D: serde::Deserializer<'de>>(self, deserializer: D) -> Result<Value, D::Error> {
        if self.depth > MAX_JSON_DEPTH || *self.remaining == 0 {
            return Err(serde::de::Error::custom("JSON_RESOURCE_LIMIT"));
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
            remaining: self.remaining,
        })? {
            result.push(value);
        }
        Ok(Value::Array(result))
    }

    fn visit_map<A: MapAccess<'de>>(self, mut access: A) -> Result<Value, A::Error> {
        let mut result = Map::new();
        while let Some(key) = access.next_key::<String>()? {
            if result.contains_key(&key) {
                return Err(serde::de::Error::custom(format!(
                    "DUPLICATE_JSON_KEY: {key}"
                )));
            }
            let value = access.next_value_seed(StrictSeed {
                depth: self.depth + 1,
                remaining: self.remaining,
            })?;
            result.insert(key, value);
        }
        Ok(Value::Object(result))
    }
}

pub fn parse_value(bytes: &[u8]) -> Result<Value, ContractError> {
    if bytes.len() > MAX_INPUT_BYTES {
        return Err(ContractError::InputLimit);
    }
    let mut remaining = MAX_JSON_VALUES;
    let mut deserializer = serde_json::Deserializer::from_slice(bytes);
    let value = StrictSeed {
        depth: 0,
        remaining: &mut remaining,
    }
    .deserialize(&mut deserializer)?;
    deserializer.end()?;
    Ok(value)
}

pub fn parse<T: DeserializeOwned>(bytes: &[u8]) -> Result<T, ContractError> {
    Ok(serde_json::from_value(parse_value(bytes)?)?)
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
