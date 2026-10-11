//! Port of the pinned consumer-owned validator; ECMAScript trim semantics.
fn js_space(c: char) -> bool {
    matches!(c,'\u{0009}'..='\u{000d}'|'\u{0020}'|'\u{00a0}'|'\u{1680}'|'\u{2000}'..='\u{200a}'|'\u{2028}'|'\u{2029}'|'\u{202f}'|'\u{205f}'|'\u{3000}'|'\u{feff}')
}
pub fn validate_create_user(input: &str) -> String {
    let value = serde_json::from_str::<serde_json::Value>(input).ok();
    let name = value
        .as_ref()
        .and_then(|v| v.as_object())
        .and_then(|o| o.get("name"))
        .and_then(|v| v.as_str())
        .map(|s| s.trim_matches(js_space));
    match name {
        Some(n) if !n.is_empty() => serde_json::json!({"name":n}).to_string(),
        _ => serde_json::json!({"error":"INVALID_CREATE_USER_INPUT"}).to_string(),
    }
}
