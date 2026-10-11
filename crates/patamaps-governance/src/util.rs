use patamaps_contracts::*;
use patamaps_core::{CheckError, Issue};
use serde::{Serialize, de::DeserializeOwned};
use serde_json::Value;

pub(crate) type Result<T> = std::result::Result<T, CheckError>;
pub(crate) fn fail<T>(code: &str, message: &str) -> Result<T> {
    Err(CheckError(vec![Issue::error(code, message, "governance")]))
}
pub(crate) fn text(value: &str) -> bool {
    !value.is_empty() && value.len() <= 1024 && !value.chars().any(char::is_control)
}
pub(crate) fn digest(value: &str) -> bool {
    value.len() == 71
        && value.starts_with("sha256:")
        && value[7..]
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}
pub(crate) fn normalized<T: Serialize + DeserializeOwned>(value: &T) -> Result<T> {
    Ok(parse(&canonical_bytes(value)?)?)
}
pub fn document_digest<T: Serialize>(value: &T) -> Result<String> {
    let mut value: Value = serde_json::to_value(value).map_err(ContractError::from)?;
    let Some(object) = value.as_object_mut() else {
        return fail("GOVERNANCE_INVALID_SHAPE", "Expected addressed object");
    };
    object.remove("id");
    object.remove("digest");
    Ok(canonical_digest(&value)?)
}
pub(crate) fn address(kind: &str, digest: &str) -> String {
    format!("urn:patamaps:{kind}:{}", &digest[7..])
}
pub(crate) fn check_address<T: Serialize>(
    value: &T,
    kind: &str,
    id: &str,
    hash: &str,
) -> Result<()> {
    if !digest(hash) || document_digest(value)? != hash || id != address(kind, hash) {
        return fail(
            "GOVERNANCE_CONTENT_MISMATCH",
            "Content address does not bind complete record",
        );
    }
    Ok(())
}
pub(crate) fn equal<A: Serialize, B: Serialize>(a: &A, b: &B) -> Result<bool> {
    Ok(canonical_bytes(a)? == canonical_bytes(b)?)
}
pub(crate) fn value_bounds(value: &Value) -> Result<()> {
    let mut queue = vec![(value, 0usize)];
    let (mut nodes, mut bytes) = (0usize, 0usize);
    while let Some((v, depth)) = queue.pop() {
        nodes += 1;
        bytes = bytes.saturating_add(1);
        if depth > MAX_JSON_DEPTH || nodes > MAX_JSON_VALUES || bytes > MAX_INPUT_BYTES {
            return fail(
                "GOVERNANCE_RESOURCE_LIMIT",
                "Untrusted output data exceeds JSON bounds",
            );
        }
        match v {
            Value::Object(o) => {
                for (k, v) in o {
                    bytes = bytes.saturating_add(k.len());
                    queue.push((v, depth + 1));
                }
            }
            Value::Array(a) => queue.extend(a.iter().map(|v| (v, depth + 1))),
            Value::String(s) => bytes = bytes.saturating_add(s.len()),
            _ => {}
        }
    }
    if bytes > MAX_INPUT_BYTES {
        return fail(
            "GOVERNANCE_RESOURCE_LIMIT",
            "Untrusted data exceeds byte bounds",
        );
    }
    Ok(())
}
