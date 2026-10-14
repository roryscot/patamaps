use patamaps_contracts::byte_digest;
use patamaps_core::{LegacyWorkspaceRequest, legacy_viability_request};
use serde_json::{Value, json};

#[test]
fn independently_frozen_original_semantic_shape_bindings_and_parser_diagnostics() {
    let bytes = include_bytes!("../../../fixtures/parity/semantic-validation-controls.json");
    assert_eq!(
        byte_digest(bytes),
        "sha256:f8b33a4c6666d454220bddd015b488846ffd8b4347c860d4bfa8b6dfe7e452ee"
    );
    let corpus: Value = serde_json::from_slice(bytes).unwrap();
    assert_eq!(corpus["cases"].as_array().unwrap().len(), 467);
    let mut observed = 0;
    for case in corpus["cases"].as_array().unwrap() {
        let action = &case["action"];
        let operation = action["operation"].as_str().unwrap();
        if ![
            "validate-policy",
            "parse-policy",
            "validate-generation",
            "parse-generation",
        ]
        .contains(&operation)
        {
            continue;
        }
        let Some(text) = action["text"].as_str() else {
            continue;
        };
        let value: Value = serde_json::from_str(text).unwrap();
        let request:LegacyWorkspaceRequest=serde_json::from_value(json!({"operation":format!("semantic-{operation}"),"input":json!({"value":value}).to_string(),"locale":"en-US"})).unwrap();
        match legacy_viability_request(request) {
            Ok(result) => {
                assert_eq!(case["expected"]["status"], "observed", "{}", case["name"]);
                let result: Value = serde_json::from_str(result.get()).unwrap();
                assert_eq!(
                    result["value"], case["expected"]["value"],
                    "{}",
                    case["name"]
                );
                if !case["expected"]["host"]["issueKeys"].is_null() {
                    assert_eq!(
                        result["issueKeys"], case["expected"]["host"]["issueKeys"],
                        "{}",
                        case["name"]
                    );
                }
            }
            Err(result) => {
                assert_eq!(case["expected"]["status"], "threw", "{}", case["name"]);
                assert_eq!(
                    result.name,
                    case["expected"]["error"]["name"].as_str().unwrap(),
                    "{}",
                    case["name"]
                );
                let message: Value = serde_json::from_str(result.message.get()).unwrap();
                assert_eq!(
                    message, case["expected"]["error"]["message"],
                    "{}",
                    case["name"]
                );
            }
        }
        observed += 1;
    }
    assert_eq!(observed, 380);
}
