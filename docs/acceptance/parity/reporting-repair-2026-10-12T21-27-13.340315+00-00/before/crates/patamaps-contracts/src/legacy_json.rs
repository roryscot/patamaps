//! A reversible schema projection for JSON.parse's legacy UTF-16 strings.
//! It supplies no checked/admitted capability and never changes JCS parsing.
use crate::{ContractError, JsonLimits, byte_digest, canonical_bytes, parse_value_with_limits};
use icu_collator::{Collator, CollatorPreferences};
use serde::Deserialize;
use serde_json::Value;

const PREFIX: char = '\u{e000}';
const SURROGATE_BASE: u32 = 0xe001;

/// Original text remains available for read-only output. The private projection
/// is suitable only for the pinned 1.0 pack schema: its URI/ASCII patterns,
/// nonempty strings and string-array equality are preserved by this encoding.
/// It must never become a modern view when original strings are non-scalar.
#[derive(Debug, Clone)]
pub struct LegacyPackJson {
    raw_bytes: Vec<u8>,
    decoded_text: String,
    projection: Value,
    executable: bool,
    utf8_replacement: bool,
    limits: JsonLimits,
}

impl LegacyPackJson {
    pub fn parse(bytes: Vec<u8>, limits: JsonLimits) -> Result<Self, ContractError> {
        if bytes.len() > limits.max_bytes {
            return Err(ContractError::ScopedInputLimit {
                max_bytes: limits.max_bytes,
            });
        }
        if limits.max_depth > 512 || limits.max_values == 0 {
            return Err(ContractError::InvalidProfile);
        }
        // Match the original file loader's readFile(..., 'utf8') decoding.
        // Preserve the exact bytes separately from any replacement characters.
        let utf8_replacement = std::str::from_utf8(&bytes).is_err();
        let decoded_text = String::from_utf8_lossy(&bytes).into_owned();
        if decoded_text.len() > limits.max_bytes {
            return Err(ContractError::ScopedInputLimit {
                max_bytes: limits.max_bytes,
            });
        }
        let executable =
            crate::json_scan::legacy_pack_profile(decoded_text.as_bytes(), limits.max_depth)
                .map_err(|error| match error {
                    ContractError::Json(error) => ContractError::LegacyJsonSyntax {
                        message: crate::json_scan::legacy_syntax_message(&decoded_text, &error),
                        native_message: error.to_string(),
                    },
                    other => other,
                })?;
        let projection = if executable {
            parse_value_with_limits(decoded_text.as_bytes(), limits)?
        } else {
            let encoded = project_strings(&decoded_text);
            // The internal projection may expand one UTF-16 escape into two
            // scalar runes. It is not another source input or public byte cap.
            let projected_limits = JsonLimits {
                max_bytes: encoded.len().max(limits.max_bytes),
                ..limits
            };
            crate::json::parse_last_wins_value(encoded.as_bytes(), projected_limits)?
        };
        Ok(Self {
            raw_bytes: bytes,
            decoded_text,
            projection,
            executable,
            utf8_replacement,
            limits,
        })
    }

    pub fn executable(&self) -> bool {
        self.executable
    }
    pub fn decoded_text(&self) -> &str {
        &self.decoded_text
    }
    pub fn source_bytes(&self) -> &[u8] {
        &self.raw_bytes
    }
    pub fn source_byte_digest(&self) -> String {
        byte_digest(&self.raw_bytes)
    }
    pub fn utf8_replacement_occurred(&self) -> bool {
        self.utf8_replacement
    }

    /// A read-only schema projection, not the original source value.
    pub fn schema_projection(&self) -> &Value {
        &self.projection
    }

    /// Read-only registry comparison data, never a native pack or schema view.
    /// Restore scalar strings so private-use characters keep their identities.
    /// Non-scalar strings use tagged code units and cannot collide with scalar
    /// kind names. Non-scalar registration keys still require host transport
    /// support; this representation must not be admitted as ordinary JSON.
    pub fn registry_comparison_projection(&self) -> Value {
        fn restore(value: &Value) -> Value {
            match value {
                Value::String(text) => {
                    let units = original_units(text);
                    match String::from_utf16(&units) {
                        Ok(text) => Value::String(text),
                        Err(_) => serde_json::json!({"legacyUtf16Units":units}),
                    }
                }
                Value::Array(items) => Value::Array(items.iter().map(restore).collect()),
                Value::Object(items) => Value::Object(
                    items
                        .iter()
                        .map(|(key, value)| {
                            (
                                String::from_utf16(&original_units(key))
                                    .unwrap_or_else(|_| key.clone()),
                                restore(value),
                            )
                        })
                        .collect(),
                ),
                _ => value.clone(),
            }
        }
        if self.executable {
            self.projection.clone()
        } else {
            restore(&self.projection)
        }
    }

    /// Default-locale legacy address for callers without host locale metadata.
    /// This addresses data; it does not validate its portable pack shape.
    pub fn portable_digest_bytes(&self) -> Result<Vec<u8>, ContractError> {
        self.digest_bytes_for_locale("en-US")
    }

    /// Executable packs retain JCS. Other finite JSON values use the legacy
    /// stable JSON convention, including last-wins member positions, numeric
    /// property enumeration and original UTF-16 strings. Collation uses pinned
    /// ICU4X data; exhaustive equivalence to every host ICU version is unverified.
    pub fn digest_bytes_for_locale(&self, locale: &str) -> Result<Vec<u8>, ContractError> {
        if self.executable {
            return canonical_bytes(&self.projection);
        }
        if self.projection.is_null() {
            return Err(ContractError::LegacyDigestNull);
        }
        let prefs =
            CollatorPreferences::from_locale_strict(&locale.parse().map_err(|_| {
                ContractError::LegacyCollation("Invalid legacy digest locale".into())
            })?)
            .map_err(|_| {
                ContractError::LegacyCollation(
                    "Unsupported legacy digest locale preferences".into(),
                )
            })?;
        let collator = Collator::try_new(prefs, Default::default())
            .map_err(|e| ContractError::LegacyCollation(e.to_string()))?;
        let encoded = project_strings(&self.decoded_text);
        let mut de = serde_json::Deserializer::from_str(&encoded);
        de.disable_recursion_limit();
        let ordered = crate::LegacyOrderedJson::deserialize(&mut de)?;
        de.end()?;
        ordered.stable_bytes_with_units(&collator, original_units)
    }

    /// Explicitly refuse a typed scalar-Unicode view when the original contains
    /// unpaired UTF-16 units. Source parsing/output/digests remain available.
    pub fn native_value(&self) -> Result<Value, ContractError> {
        if self.executable {
            return Ok(self.projection.clone());
        }
        let raw = canonical_bytes(&self.projection)?;
        let restored = restore_strings(std::str::from_utf8(&raw).expect("canonical UTF-8 JSON"));
        parse_value_with_limits(
            restored.as_bytes(),
            JsonLimits {
                max_bytes: restored.len().max(self.limits.max_bytes),
                ..self.limits
            },
        )
    }

    pub fn unpaired_paths(&self) -> Vec<String> {
        if self.executable {
            return Vec::new();
        }
        let mut paths = Vec::new();
        let mut stack = vec![(&self.projection, String::new())];
        while let Some((value, path)) = stack.pop() {
            match value {
                Value::String(text) if has_unpaired(text) => paths.push(path),
                Value::Array(array) => {
                    stack.extend(
                        array
                            .iter()
                            .enumerate()
                            .rev()
                            .map(|(i, child)| (child, format!("{path}/{i}"))),
                    );
                }
                Value::Object(object) => {
                    // A validated portable pack has only fixed ASCII keys.
                    stack.extend(object.iter().rev().map(|(key, child)| {
                        (
                            child,
                            format!("{path}/{}", key.replace('~', "~0").replace('/', "~1")),
                        )
                    }));
                }
                _ => {}
            }
        }
        paths
    }
}

fn project_string(raw: &str) -> String {
    let units = crate::json_scan::decode_key(raw);
    let mut output = String::new();
    for scalar in char::decode_utf16(units) {
        match scalar {
            Ok(ch) => {
                output.push(ch);
                if ch == PREFIX {
                    output.push(PREFIX);
                }
            }
            Err(error) => {
                output.push(PREFIX);
                output.push(
                    char::from_u32(SURROGATE_BASE + u32::from(error.unpaired_surrogate() - 0xd800))
                        .expect("private-use surrogate marker"),
                );
            }
        }
    }
    serde_json::to_string(&output).expect("scalar Unicode projection")
}

fn original_units(projected: &str) -> Vec<u16> {
    let mut units = Vec::new();
    let mut chars = projected.chars();
    while let Some(ch) = chars.next() {
        if ch == PREFIX {
            let next = chars.next().expect("complete private projection marker");
            if next == PREFIX {
                units.push(PREFIX as u16);
            } else {
                let offset = next as u32 - SURROGATE_BASE;
                assert!(offset < 2048, "private projection marker range");
                units.push(0xd800 + offset as u16);
            }
        } else {
            units.extend(ch.encode_utf16(&mut [0; 2]).iter().copied());
        }
    }
    units
}

fn has_unpaired(projected: &str) -> bool {
    char::decode_utf16(original_units(projected)).any(|unit| unit.is_err())
}

/// Complete JSON grammar was checked before this lexical string walk.
fn map_strings(text: &str, map: impl Fn(&str) -> String) -> String {
    let mut output = String::new();
    let (mut cursor, mut copied) = (0usize, 0usize);
    while cursor < text.len() {
        if text.as_bytes()[cursor] != b'"' {
            cursor += 1;
            continue;
        }
        let start = cursor;
        cursor += 1;
        loop {
            match text.as_bytes()[cursor] {
                b'\\' => cursor += 2,
                b'"' => {
                    cursor += 1;
                    break;
                }
                _ => cursor += 1,
            }
        }
        output.push_str(&text[copied..start]);
        output.push_str(&map(&text[start..cursor]));
        copied = cursor;
    }
    output.push_str(&text[copied..]);
    output
}

fn project_strings(text: &str) -> String {
    map_strings(text, project_string)
}
fn restore_strings(text: &str) -> String {
    map_strings(text, |raw| {
        let projected: String = serde_json::from_str(raw).expect("canonical projected string");
        crate::json_scan::display_key(&original_units(&projected))
    })
}
