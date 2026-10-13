//! Retained legacy object order for composition and unchecked stable digests.
//! Callers must check JSON grammar, value domain and resource limits first.
use icu_collator::CollatorBorrowed;
use serde::{
    Deserialize,
    de::{MapAccess, SeqAccess, Visitor},
};
use serde_json::json;
use std::{cmp::Ordering, fmt};

/// The native compatibility parser first checks grammar, duplicates, Unicode,
/// values and bounds. This visitor only retains member order for the original
/// stable-sort equivalence, including locale-equal but distinct Unicode keys.
#[derive(Debug)]
pub enum LegacyOrderedJson {
    Null,
    Bool(bool),
    Number(f64),
    String(String),
    Array(Vec<Self>),
    Object(Vec<(String, Self)>),
}
impl<'de> Deserialize<'de> for LegacyOrderedJson {
    fn deserialize<D: serde::Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        struct OrderedVisitor;
        impl<'de> Visitor<'de> for OrderedVisitor {
            type Value = LegacyOrderedJson;
            fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
                f.write_str("ordered JSON data")
            }
            fn visit_unit<E>(self) -> Result<Self::Value, E> {
                Ok(LegacyOrderedJson::Null)
            }
            fn visit_bool<E>(self, v: bool) -> Result<Self::Value, E> {
                Ok(LegacyOrderedJson::Bool(v))
            }
            fn visit_i64<E>(self, v: i64) -> Result<Self::Value, E> {
                Ok(LegacyOrderedJson::Number(v as f64))
            }
            fn visit_u64<E>(self, v: u64) -> Result<Self::Value, E> {
                Ok(LegacyOrderedJson::Number(v as f64))
            }
            fn visit_f64<E>(self, v: f64) -> Result<Self::Value, E> {
                Ok(LegacyOrderedJson::Number(v))
            }
            fn visit_str<E: serde::de::Error>(self, v: &str) -> Result<Self::Value, E> {
                Ok(LegacyOrderedJson::String(v.into()))
            }
            fn visit_string<E>(self, v: String) -> Result<Self::Value, E> {
                Ok(LegacyOrderedJson::String(v))
            }
            fn visit_seq<A: SeqAccess<'de>>(self, mut seq: A) -> Result<Self::Value, A::Error> {
                let mut values = Vec::new();
                while let Some(value) = seq.next_element()? {
                    values.push(value);
                }
                Ok(LegacyOrderedJson::Array(values))
            }
            fn visit_map<A: MapAccess<'de>>(self, mut map: A) -> Result<Self::Value, A::Error> {
                let mut values = Vec::new();
                let mut slots = std::collections::HashMap::<String, usize>::new();
                while let Some((key, value)) = map.next_entry::<String, LegacyOrderedJson>()? {
                    if let Some(slot) = slots.get(&key) {
                        values[*slot] = (key, value);
                    } else {
                        slots.insert(key.clone(), values.len());
                        values.push((key, value));
                    }
                }
                Ok(LegacyOrderedJson::Object(values))
            }
        }
        deserializer.deserialize_any(OrderedVisitor)
    }
}
impl LegacyOrderedJson {
    pub fn get(&self, key: &str) -> Option<&Self> {
        if let Self::Object(items) = self {
            items.iter().find(|(k, _)| k == key).map(|(_, v)| v)
        } else {
            None
        }
    }
    pub fn string(&self) -> Option<&str> {
        if let Self::String(text) = self {
            Some(text)
        } else {
            None
        }
    }
    pub fn array(&self) -> Option<&[Self]> {
        if let Self::Array(items) = self {
            Some(items)
        } else {
            None
        }
    }
    pub fn js_text(&self) -> String {
        match self {
            Self::Null => "null".into(),
            Self::Bool(v) => v.to_string(),
            Self::String(v) => v.clone(),
            Self::Object(_) => "[object Object]".into(),
            Self::Number(v) => {
                String::from_utf8(crate::canonical_bytes(&json!(v)).expect("finite source number"))
                    .expect("canonical UTF-8")
            }
            Self::Array(items) => items
                .iter()
                .map(|v| {
                    if matches!(v, Self::Null) {
                        String::new()
                    } else {
                        v.js_text()
                    }
                })
                .collect::<Vec<_>>()
                .join(","),
        }
    }
}

fn integer_key(units: &[u16]) -> Option<u32> {
    let key = String::from_utf16(units).ok()?;
    let value = key.parse::<u32>().ok()?;
    (value < u32::MAX && value.to_string() == key).then_some(value)
}
fn key_order(left: &[u16], right: &[u16], collator: &CollatorBorrowed<'_>) -> Ordering {
    // Object.fromEntries/JSON.stringify enumerate integer-index keys first.
    match (integer_key(left), integer_key(right)) {
        (Some(a), Some(b)) => a.cmp(&b),
        (Some(_), None) => Ordering::Less,
        (None, Some(_)) => Ordering::Greater,
        (None, None) => collator.compare_legacy_utf16(left, right),
    }
}
impl LegacyOrderedJson {
    /// Scalar JSON composition comparison. Locale-equal distinct keys preserve
    /// input order, so ordinary unordered object equality is insufficient.
    pub fn stable_equivalent(&self, right: &Self, collator: &CollatorBorrowed<'_>) -> bool {
        match (self, right) {
            (Self::Null, Self::Null) => true,
            (Self::Bool(a), Self::Bool(b)) => a == b,
            (Self::Number(a), Self::Number(b)) => a == b,
            (Self::String(a), Self::String(b)) => a == b,
            (Self::Array(a), Self::Array(b)) => {
                a.len() == b.len()
                    && a.iter()
                        .zip(b)
                        .all(|(a, b)| a.stable_equivalent(b, collator))
            }
            (Self::Object(a), Self::Object(b)) => {
                if a.len() != b.len() {
                    return false;
                }
                let mut a = a.iter().collect::<Vec<_>>();
                let mut b = b.iter().collect::<Vec<_>>();
                a.sort_by(|a, b| {
                    key_order(
                        &a.0.encode_utf16().collect::<Vec<_>>(),
                        &b.0.encode_utf16().collect::<Vec<_>>(),
                        collator,
                    )
                });
                b.sort_by(|a, b| {
                    key_order(
                        &a.0.encode_utf16().collect::<Vec<_>>(),
                        &b.0.encode_utf16().collect::<Vec<_>>(),
                        collator,
                    )
                });
                a.iter()
                    .zip(b)
                    .all(|(a, b)| a.0 == b.0 && a.1.stable_equivalent(&b.1, collator))
            }
            _ => false,
        }
    }

    /// Only the legacy parser may restore its reversible string projection.
    /// No JSON tag objects or modern scalar values stand for UTF-16 units.
    pub(crate) fn stable_bytes_with_units(
        &self,
        collator: &CollatorBorrowed<'_>,
        units: fn(&str) -> Vec<u16>,
    ) -> Result<Vec<u8>, crate::ContractError> {
        fn write(
            value: &LegacyOrderedJson,
            output: &mut Vec<u8>,
            collator: &CollatorBorrowed<'_>,
            units: fn(&str) -> Vec<u16>,
        ) -> Result<(), crate::ContractError> {
            match value {
                LegacyOrderedJson::Null => output.extend(b"null"),
                LegacyOrderedJson::Bool(v) => {
                    output.extend(if *v { &b"true"[..] } else { &b"false"[..] })
                }
                LegacyOrderedJson::Number(v) => output.extend(crate::canonical_bytes(&json!(v))?),
                LegacyOrderedJson::String(v) => {
                    output.extend(crate::json_scan::display_key(&units(v)).as_bytes())
                }
                LegacyOrderedJson::Array(values) => {
                    output.push(b'[');
                    for (index, value) in values.iter().enumerate() {
                        if index != 0 {
                            output.push(b',');
                        }
                        write(value, output, collator, units)?;
                    }
                    output.push(b']');
                }
                LegacyOrderedJson::Object(values) => {
                    let mut values = values
                        .iter()
                        .map(|(key, value)| (units(key), value))
                        .collect::<Vec<_>>();
                    // Stable sorting retains the original order of collation
                    // ties. Integer keys then enumerate by numeric index.
                    values.sort_by(|a, b| key_order(&a.0, &b.0, collator));
                    output.push(b'{');
                    for (index, (key, value)) in values.iter().enumerate() {
                        if index != 0 {
                            output.push(b',');
                        }
                        output.extend(crate::json_scan::display_key(key).as_bytes());
                        output.push(b':');
                        write(value, output, collator, units)?;
                    }
                    output.push(b'}');
                }
            }
            Ok(())
        }
        let mut output = Vec::new();
        write(self, &mut output, collator, units)?;
        output.push(b'\n');
        Ok(output)
    }
}
