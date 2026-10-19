use icu_collator::Collator;
use patamaps_contracts::{
    COMPATIBILITY_JSON_LIMITS, LegacyOrderedJson as J, LegacyReadOnlyJson as Data, byte_digest,
};
use patamaps_core::{LegacyWorkspaceRequest, legacy_evaluation_request};
use serde::Deserialize;
use serde_json::value::RawValue;

#[test]
fn independent_original_context_selector_and_impact_values() {
    #[derive(Deserialize)]
    struct Case {
        name: String,
        action: LegacyWorkspaceRequest,
        expected: Box<RawValue>,
    }
    #[derive(Deserialize)]
    #[serde(rename_all = "camelCase")]
    struct Corpus {
        reference_engine: String,
        cases: Vec<Case>,
    }
    let bytes = include_bytes!("../package-inputs/fixtures/parity/evaluation-controls.json");
    assert_eq!(
        byte_digest(bytes),
        "sha256:e7f5814db4c87eeedbd225c15ff3ae98ce90ced48cfa0f0aee53e72d71eebb01"
    );
    let corpus: Corpus = serde_json::from_slice(bytes).unwrap();
    assert_eq!(
        corpus.reference_engine,
        "399747a4ad05a37cd8db1cedd53048fad2175be4"
    );
    assert_eq!(corpus.cases.len(), 855);
    let col = Collator::try_new(Default::default(), Default::default()).unwrap();
    let comparable = |value: &J| Data::stable_bytes(value, &col).unwrap();
    let mut checked = 0;
    for mut case in corpus.cases {
        // Host object parsing is exercised by the installed JS observer. The
        // native parser receives type facts, never caller-owned object handles.
        if case.action.operation == "parse-context" {
            continue;
        }
        if case.action.operation == "impact" && case.action.input.contains("\"packs\"") {
            let mut envelope: serde_json::Value = serde_json::from_str(&case.action.input).unwrap();
            if let Some(packs) = envelope["value"].get("packs").cloned() {
                envelope["value"]["registry"] = serde_json::json!({"definitions":packs.as_array().unwrap().iter().flat_map(|p| p["relations"].as_array().unwrap()).map(|r| serde_json::json!({"key":r["id"],"value":r})).collect::<Vec<_>>()});
                envelope["value"].as_object_mut().unwrap().remove("packs");
                case.action.input = envelope.to_string();
            }
        }
        let expected = Data::parse(case.expected.get(), COMPATIBILITY_JSON_LIMITS).unwrap();
        assert_eq!(
            expected.value().get("status").and_then(J::string),
            Some("observed"),
            "{}",
            case.name
        );
        let actual = legacy_evaluation_request(case.action)
            .unwrap_or_else(|e| panic!("{}: {:?}", case.name, e));
        let actual = Data::parse(actual.get(), COMPATIBILITY_JSON_LIMITS).unwrap();
        assert_eq!(
            comparable(actual.value()),
            comparable(expected.value().get("value").unwrap()),
            "{}",
            case.name
        );
        checked += 1;
    }
    assert_eq!(checked, 826);
}

#[test]
fn numeric_observation_facts_cannot_forge_paths_or_canonical_values() {
    for numbers in [
        serde_json::json!([{"path":[],"kind":"nan"}]),
        serde_json::json!([{"path":["absent"],"kind":"nan"}]),
        serde_json::json!([{"path":["n"],"kind":"nan"}]),
        serde_json::json!([{"path":["zero"],"kind":"unsupported"}]),
        serde_json::json!([{"path":["zero"],"kind":"nan"},{"path":["zero"],"kind":"nan"}]),
    ] {
        let envelope = serde_json::json!({"value":{"zero":0,"n":1},"numbers":numbers});
        let error = legacy_evaluation_request(LegacyWorkspaceRequest {
            operation: "evaluate".into(),
            input: envelope.to_string(),
            locale: "en-US".into(),
        })
        .unwrap_err();
        assert_eq!(error.name, "TypeError");
    }
}
