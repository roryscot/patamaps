use patamaps_contracts::{
    COMPATIBILITY_JSON_LIMITS, LegacyOrderedJson as J, LegacyReadOnlyJson, byte_digest,
};
use patamaps_core::{LegacyWorkspaceRequest, legacy_viability_request};
use serde_json::{Value, json};

#[test]
fn original_uncertainty_and_budget_controls_run_in_the_native_library() {
    let corpora: [&[u8]; 2] = [
        include_bytes!("../../../fixtures/parity/uncertainty-risk-controls.json"),
        include_bytes!("../../../fixtures/parity/uncertainty-risk-assessment-controls.json"),
    ];
    let mut checked = 0;
    for (index, bytes) in corpora.into_iter().enumerate() {
        if index == 0 {
            assert_eq!(
                byte_digest(bytes),
                "sha256:8475785f4a8b75c5d209e76bb264951dfa02d866e3338fbf06aca3feecdbdc10"
            );
        } else {
            assert_eq!(
                byte_digest(bytes),
                "sha256:2f17db893503b01aed39a9d8b8ea802b1498217b7eb53f6b5dfa0626a271ed55"
            );
        }
        let corpus: Value = serde_json::from_slice(bytes).unwrap();
        for case in corpus["cases"].as_array().unwrap() {
            let action = &case["action"];
            if !action["kind"].is_null() || case["expected"]["status"] != "observed" {
                continue;
            }
            let operation = match action["operation"].as_str().unwrap() {
                "validate" => "uncertainty-shape",
                "unknown" => "uncertainty-unknown",
                "combine" => "uncertainty-combine",
                "mapping" => "uncertainty-mapping",
                "graph" => "uncertainty-graph",
                "summary" => "uncertainty-summary",
                "requirements" => "uncertainty-requirements",
                "budgets" => "risk-budgets",
                _ => continue,
            };
            let input = action["input"].to_string();
            let request = |operation: &str| {
                serde_json::from_value::<LegacyWorkspaceRequest>(
                    json!({"operation":operation,"input":input,"locale":"en-US"}),
                )
                .unwrap()
            };
            let mut response = legacy_viability_request(request(operation)).unwrap();
            if action["operation"] == "validate" {
                let value: Value = serde_json::from_str(response.get()).unwrap();
                if value["value"].as_array().unwrap().is_empty() {
                    response = legacy_viability_request(request("uncertainty-validate")).unwrap();
                }
            }
            let value: Value = serde_json::from_str(response.get()).unwrap();
            assert_eq!(
                value["value"], case["expected"]["value"]["value"],
                "{}",
                case["name"]
            );
            let ordered =
                LegacyReadOnlyJson::parse(response.get(), COMPATIBILITY_JSON_LIMITS).unwrap();
            if let Some(expected) = case["expected"]["host"]["itemKeys"].as_array() {
                let keys = ordered
                    .value()
                    .get("value")
                    .unwrap()
                    .array()
                    .unwrap()
                    .iter()
                    .map(|item| match item {
                        J::Object(fields) => {
                            json!(fields.iter().map(|(name, _)| name).collect::<Vec<_>>())
                        }
                        _ => Value::Null,
                    })
                    .collect::<Vec<_>>();
                assert_eq!(&keys, expected, "{}", case["name"]);
            }
            checked += 1;
        }
    }
    assert!(
        checked > 900,
        "Expected comprehensive frozen native uncertainty/budget controls; checked {checked}"
    );
}
