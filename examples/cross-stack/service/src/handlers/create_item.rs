use serde::{Deserialize, Serialize};
#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct CreateItemRequest {
    pub name: String,
}
#[derive(Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct CreateItemResponse {
    pub id: String,
    pub name: String,
}
#[derive(Debug, PartialEq)]
pub enum OperationError {
    InvalidName,
    BackendFailure,
}
pub fn create_item(input: CreateItemRequest) -> Result<CreateItemResponse, OperationError> {
    if input.name.is_empty() || input.name.chars().count() > 80 {
        return Err(OperationError::InvalidName);
    }
    if input.name == "fail" {
        return Err(OperationError::BackendFailure);
    }
    Ok(CreateItemResponse {
        id: format!("item:{}", input.name.to_lowercase()),
        name: input.name,
    })
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn contract_and_failure() {
        let result = create_item(serde_json::from_str(r#"{"name":"Widget"}"#).unwrap()).unwrap();
        assert_eq!(
            serde_json::to_value(result).unwrap(),
            serde_json::json!({"id":"item:widget","name":"Widget"})
        );
        assert!(serde_json::from_str::<CreateItemRequest>(r#"{"name":"ok","extra":1}"#).is_err());
        assert!(serde_json::from_str::<CreateItemRequest>(r#"{"name":2}"#).is_err());
        assert_eq!(
            create_item(CreateItemRequest { name: "".into() }).unwrap_err(),
            OperationError::InvalidName
        );
        assert_eq!(
            create_item(CreateItemRequest {
                name: "fail".into()
            })
            .unwrap_err(),
            OperationError::BackendFailure
        );
    }
}
