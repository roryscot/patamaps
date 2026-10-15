// Generated from sha256:b8164dd6cc718a37f1553e717e97d44bd1f1d3545d42103eec229fbec99612d3; regenerate after correspondence changes.
pub const PROJECTION_JSON: &str = "{\"digest\":\"sha256:b8164dd6cc718a37f1553e717e97d44bd1f1d3545d42103eec229fbec99612d3\",\"documentType\":\"projection\",\"entries\":[{\"slots\":[{\"cardinality\":\"exactly-one\",\"direction\":\"outgoing\",\"mappings\":[\"urn:example:operation:create-item:mapping:endpoint\"],\"name\":\"endpoint\",\"relation\":\"routing:exposed_as\",\"targets\":[{\"attributes\":{\"http\":{\"method\":\"POST\",\"path\":\"/items\",\"successStatus\":201}},\"id\":\"urn:example:operation:create-item:endpoint\",\"kind\":\"routing:endpoint\"}]},{\"cardinality\":\"exactly-one\",\"direction\":\"outgoing\",\"mappings\":[\"urn:example:operation:create-item:mapping:handler\"],\"name\":\"handler\",\"relation\":\"routing:handled_by\",\"targets\":[{\"attributes\":{\"http\":{\"errorType\":\"OperationError\",\"errors\":[{\"code\":\"invalid-name\",\"status\":400,\"variant\":\"InvalidName\"},{\"code\":\"backend-failure\",\"status\":500,\"variant\":\"BackendFailure\"}],\"modulePath\":\"handlers/create_item.rs\",\"profile\":\"patamaps-http-object-strings-1\",\"requestType\":\"CreateItemRequest\",\"responseSchema\":{\"$schema\":\"https://json-schema.org/draft/2020-12/schema\",\"additionalProperties\":false,\"properties\":{\"id\":{\"type\":\"string\"},\"name\":{\"type\":\"string\"}},\"required\":[\"id\",\"name\"],\"type\":\"object\"},\"responseType\":\"CreateItemResponse\"}},\"id\":\"urn:example:operation:create-item:handler\",\"kind\":\"routing:handler\",\"locators\":[{\"digest\":\"sha256:1e04089800d93b65af6823c1be25653244b70252723e6f9df4005e80a2eea962\",\"uri\":\"rust:crate::catalog::create_item\"}]}]},{\"cardinality\":\"exactly-one\",\"direction\":\"outgoing\",\"mappings\":[\"urn:example:operation:create-item:mapping:input\"],\"name\":\"input\",\"relation\":\"routing:accepts\",\"targets\":[{\"attributes\":{\"jsonSchema\":{\"$schema\":\"https://json-schema.org/draft/2020-12/schema\",\"additionalProperties\":false,\"properties\":{\"name\":{\"maxLength\":80,\"minLength\":1,\"type\":\"string\"}},\"required\":[\"name\"],\"type\":\"object\"}},\"id\":\"urn:example:operation:create-item:input\",\"kind\":\"routing:schema\",\"locators\":[{\"digest\":\"sha256:e814007c18146f82674e36f5dc6fb1affe8e871f828c8ddff117f244e2ddfe95\",\"uri\":\"json-schema:contracts/create-item.request.schema.json\"}]}]}],\"subject\":{\"attributes\":{\"http\":{\"method\":\"POST\",\"path\":\"/api/items\"}},\"id\":\"urn:example:operation:create-item\",\"kind\":\"routing:command\"}}],\"generation\":{\"digest\":\"sha256:9393b98b4f5b16009240d5a6bf56ed847213163b78d837ef9cfed4e553f3ffc4\",\"id\":\"urn:patamaps:generation:9393b98b4f5b16009240d5a6bf56ed847213163b78d837ef9cfed4e553f3ffc4\"},\"graph\":{\"digest\":\"sha256:a8ddf1dc83cd107dfc00d09a64c4ba9e4f66507d7db1d6c470cd7d22418da992\",\"id\":\"urn:example:cross-stack:http\",\"revision\":\"1\"},\"id\":\"urn:patamaps:projection:b8164dd6cc718a37f1553e717e97d44bd1f1d3545d42103eec229fbec99612d3\",\"profile\":\"patamaps-routing-draft-1\",\"schemaVersion\":\"0.1.0\",\"spec\":{\"digest\":\"sha256:fd6159348fb5cb7216f8be30a546d956bee3ab6a04e677fe6f62e3d289e51c22\",\"id\":\"urn:example:cross-stack:http-projection\"}}";
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SemanticId(&'static str);
impl SemanticId {
    pub fn as_str(self) -> &'static str {
        self.0
    }
    pub fn parse(id: &str) -> Option<Self> {
        match id {
            "urn:example:operation:create-item" => Some(Self("urn:example:operation:create-item")),
            _ => None,
        }
    }
}
// HTTP profile patamaps-http-object-strings-1; projection sha256:b8164dd6cc718a37f1553e717e97d44bd1f1d3545d42103eec229fbec99612d3.
#[rustfmt::skip]
#[path = "handlers/create_item.rs"]
pub mod catalog;
pub const OPERATIONS: &[(&str, &str, &str)] =
    &[("urn:example:operation:create-item", "POST", "/items")];
fn request_0(value: &serde_json::Value) -> bool {
    let Some(object) = value.as_object() else {
        return false;
    };
    if object.len() != 1 {
        return false;
    }
    let Some(text) = object.get("name").and_then(serde_json::Value::as_str) else {
        return false;
    };
    let length = text.chars().count();
    if length < 1 {
        return false;
    }
    if length > 80 {
        return false;
    }
    true
}
fn response_0(value: &serde_json::Value) -> bool {
    let Some(object) = value.as_object() else {
        return false;
    };
    if object.len() != 2 {
        return false;
    }
    let Some(text) = object.get("id").and_then(serde_json::Value::as_str) else {
        return false;
    };
    let _ = text;
    let Some(text) = object.get("name").and_then(serde_json::Value::as_str) else {
        return false;
    };
    let _ = text;
    true
}
pub fn dispatch(method: &str, path: &str, raw: &[u8]) -> Option<(u16, serde_json::Value)> {
    match (method, path) {
        ("POST", "/items") => {
            if raw.len() > 8192 {
                return Some((413, serde_json::json!({"error":"input-limit"})));
            }
            let parsed: serde_json::Value = match serde_json::from_slice(raw) {
                Ok(v) => v,
                Err(_) => return Some((400, serde_json::json!({"error":"invalid-request"}))),
            };
            if !request_0(&parsed) {
                return Some((400, serde_json::json!({"error":"invalid-request"})));
            }
            let input: catalog::CreateItemRequest = match serde_json::from_value(parsed) {
                Ok(v) => v,
                Err(_) => return Some((400, serde_json::json!({"error":"invalid-request"}))),
            };
            let handler: fn(
                catalog::CreateItemRequest,
            )
                -> Result<catalog::CreateItemResponse, catalog::OperationError> =
                catalog::create_item;
            Some(match handler(input) {
                Ok(value) => match serde_json::to_value(value) {
                    Ok(value) if response_0(&value) => (201, value),
                    _ => (500, serde_json::json!({"error":"invalid-response"})),
                },
                Err(catalog::OperationError::InvalidName) => {
                    (400, serde_json::json!({"error":"invalid-name"}))
                }
                Err(catalog::OperationError::BackendFailure) => {
                    (500, serde_json::json!({"error":"backend-failure"}))
                }
            })
        }
        _ => None,
    }
}
