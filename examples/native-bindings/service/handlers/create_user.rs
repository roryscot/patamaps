//! Port of the pinned consumer-owned service, after its input binding validates.
pub fn create_user(input: &str) -> String {
    let value: serde_json::Value =
        serde_json::from_str(input).expect("Consumer validated its input");
    serde_json::json!({"operation":"create-user","displayName":value["name"]}).to_string()
}
