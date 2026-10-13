//! Read-only legacy reference/locator helpers. No identifier grants authority.
use crate::legacy_reporting::{LegacyReportText as Text, js_text};
use patamaps_contracts::{
    COMPATIBILITY_JSON_LIMITS, LegacyOrderedJson as J, LegacyReadOnlyJson as Data,
};
use serde::{Deserialize, Serialize};
use serde_json::value::RawValue;
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct LegacyReferenceRequest {
    pub operation: LegacyReferenceOperation,
    pub input: String,
}
#[derive(Debug, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum LegacyReferenceOperation {
    ReferenceIdentifier,
    RelationIdentifier,
    Urn,
    RepositoryUri,
    AmbiguousPath,
    PathPattern,
}
#[derive(Debug, thiserror::Error, Serialize)]
#[error("{message}")]
pub struct LegacyReferenceError {
    pub code: String,
    pub name: String,
    pub message: String,
}
pub(crate) fn failure(name: &str, message: impl Into<String>) -> LegacyReferenceError {
    LegacyReferenceError {
        code: "LEGACY_REFERENCE_INPUT".into(),
        name: name.into(),
        message: message.into(),
    }
}
fn whitespace(c: u16) -> bool {
    matches!(c,9..=13|32|160|0x1680|0x2000..=0x200a|0x2028|0x2029|0x202f|0x205f|0x3000|0xfeff)
}
fn ascii_alpha(c: u16) -> bool {
    matches!(c,65..=90|97..=122)
}
fn lower(c: u16) -> bool {
    matches!(c, 97..=122)
}
fn digit(c: u16) -> bool {
    matches!(c, 48..=57)
}
pub(crate) fn reference(units: &[u16]) -> bool {
    let Some(colon) = units.iter().position(|&c| c == 58) else {
        return false;
    };
    colon > 0
        && ascii_alpha(units[0])
        && units[1..colon]
            .iter()
            .all(|&c| ascii_alpha(c) || digit(c) || matches!(c, 43 | 46 | 45))
        && colon + 1 < units.len()
        && units[colon + 1..].iter().all(|&c| !whitespace(c))
}
pub(crate) fn relation(units: &[u16]) -> bool {
    let Some(colon) = units.iter().position(|&c| c == 58) else {
        return false;
    };
    colon > 0
        && lower(units[0])
        && units[1..colon]
            .iter()
            .all(|&c| lower(c) || digit(c) || matches!(c, 46 | 95 | 45))
        && colon + 1 < units.len()
        && lower(units[colon + 1])
        && units[colon + 2..]
            .iter()
            .all(|&c| lower(c) || digit(c) || matches!(c, 46 | 95 | 45))
}
pub(crate) fn component(units: &[u16]) -> Result<String, LegacyReferenceError> {
    let text = String::from_utf16(units).map_err(|_| failure("URIError", "URI malformed"))?;
    let mut out = String::new();
    const HEX: &[u8] = b"0123456789ABCDEF";
    for b in text.bytes() {
        if b.is_ascii_alphanumeric()
            || matches!(
                b,
                b'-' | b'_' | b'.' | b'!' | b'~' | b'*' | b'\'' | b'(' | b')'
            )
        {
            out.push(b as char);
        } else {
            out.push('%');
            out.push(HEX[(b >> 4) as usize] as char);
            out.push(HEX[(b & 15) as usize] as char);
        }
    }
    Ok(out)
}
pub(crate) fn urn(
    namespace: &Text,
    kind: &Text,
    value: &Text,
) -> Result<Text, LegacyReferenceError> {
    Ok(Text::join(
        &[
            "urn:".into(),
            namespace.clone(),
            ":".into(),
            kind.clone(),
            ":".into(),
            component(&value.0)?.into(),
        ],
        "",
    ))
}
fn path_string(value: &J) -> Result<&str, LegacyReferenceError> {
    value
        .get("path")
        .and_then(J::string)
        .ok_or_else(|| failure("TypeError", "Read-only legacy path requires a string"))
}
pub fn legacy_reference_request(
    request: LegacyReferenceRequest,
) -> Result<Box<RawValue>, LegacyReferenceError> {
    let data = Data::parse(&request.input, COMPATIBILITY_JSON_LIMITS)
        .map_err(|e| failure("Error", e.to_string()))?;
    let input = data.value();
    let result = match request.operation {
        LegacyReferenceOperation::ReferenceIdentifier => J::Bool(
            input
                .get("value")
                .and_then(J::string)
                .is_some_and(|s| reference(&Data::string_units(s))),
        ),
        LegacyReferenceOperation::RelationIdentifier => J::Bool(
            input
                .get("value")
                .and_then(J::string)
                .is_some_and(|s| relation(&Data::string_units(s))),
        ),
        LegacyReferenceOperation::Urn => {
            let text = urn(
                &js_text(input.get("namespace")),
                &js_text(input.get("kind")),
                &js_text(input.get("value")),
            )?;
            Data::string_value(&text.0)
        }
        LegacyReferenceOperation::RepositoryUri => {
            let path = Data::string_units(path_string(input)?);
            let mut path = path
                .into_iter()
                .map(|c| if c == 92 { 47 } else { c })
                .collect::<Vec<_>>();
            if path.starts_with(&[46, 47]) {
                path.drain(..2);
            }
            let repository = if input.get("repository").is_some() {
                js_text(input.get("repository"))
            } else {
                "workspace".into()
            };
            let mut parts = Vec::new();
            for segment in path.split(|&c| c == 47) {
                parts.push(component(segment)?);
            }
            Data::string_value(
                &format!("repo://{}/{}", component(&repository.0)?, parts.join("/"))
                    .encode_utf16()
                    .collect::<Vec<_>>(),
            )
        }
        LegacyReferenceOperation::AmbiguousPath => {
            let path = Data::string_units(path_string(input)?);
            J::Bool(path.windows(4).any(|w| {
                whitespace(w[0])
                    && matches!(w[1], 79 | 111)
                    && matches!(w[2], 82 | 114)
                    && whitespace(w[3])
            }))
        }
        LegacyReferenceOperation::PathPattern => J::Bool(
            Data::string_units(path_string(input)?)
                .iter()
                .any(|c| matches!(c, 42 | 63 | 123 | 125 | 91 | 93)),
        ),
    };
    Data::json_raw(&result).map_err(|e| failure("Error", e.to_string()))
}
