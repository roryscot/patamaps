use icu_collator::Collator;
use patamaps_contracts::{
    COMPATIBILITY_JSON_LIMITS, LegacyOrderedJson as J, LegacyReadOnlyJson as Data, byte_digest,
};
use patamaps_core::{LegacyWorkspaceRequest, legacy_viability_request};
use serde::Deserialize;
use serde_json::value::RawValue;

fn callback_corpus() -> serde_json::Value {
    let bytes = include_bytes!("../../../fixtures/parity/constraint-callback-controls.json");
    assert_eq!(
        byte_digest(bytes),
        "sha256:b2b0b824ecadc544de6bb5d6748f874707879112ce47435c8d537e5f46c232f7"
    );
    serde_json::from_slice(bytes).unwrap()
}

fn callback_request(operation: &str, input: serde_json::Value) -> serde_json::Value {
    let request = serde_json::from_value(
        serde_json::json!({"operation":operation,"input":input.to_string(),"locale":"en-US"}),
    )
    .unwrap();
    let result = legacy_viability_request(request).unwrap();
    serde_json::from_str(result.get()).unwrap()
}

#[test]
fn independently_frozen_original_builtin_constraint_evaluators() {
    let corpus = callback_corpus();
    let mut count = 0;
    for case in corpus["cases"].as_array().unwrap() {
        let action = &case["action"];
        if action["operation"] != "builtin" {
            continue;
        }
        let document = &corpus["document"];
        let mut constraint = serde_json::json!({"id":"urn:test:callback:builtin","kind":action["kind"],"subjects":[document["entities"][0]["id"]]});
        if let Some(parameters) = action.get("parameters") {
            constraint["parameters"] = parameters.clone();
        }
        let active = document["mappings"]
            .as_array()
            .unwrap()
            .iter()
            .map(|mapping| mapping["id"].clone())
            .collect::<Vec<_>>();
        let observed = callback_request(
            "constraint-evaluate",
            serde_json::json!({"kind":action["kind"],"constraint":constraint,"context":{"document":document,"activeMappings":active,"evidence":corpus["baseline"]["evidence"]}}),
        );
        assert_eq!(
            observed["value"], case["expected"]["value"]["value"],
            "{}",
            case["name"]
        );
        assert_eq!(
            observed["issueKeys"], case["expected"]["host"]["issueKeys"],
            "{}",
            case["name"]
        );
        count += 1;
    }
    assert_eq!(count, 24);
}

#[test]
fn original_callback_continuation_preserves_validation_and_hashes_live_inputs() {
    let corpus = callback_corpus();
    for mode in ["mutate-document-id", "mutate-mappings"] {
        let mut document = corpus["document"].clone();
        let mut policy = corpus["baseline"].clone();
        policy["constraints"] = serde_json::json!([{"id":"urn:test:callback:0","kind":"test:callback-0","subjects":[document["mappings"][0]["id"]],"parameters":{"mode":mode}}]);
        policy["evidence"] = serde_json::json!([]);
        for mapping in policy["mappings"].as_array_mut().unwrap() {
            mapping.as_object_mut().unwrap().remove("applicability");
        }
        let options = serde_json::json!({"context":{"environment":"production","maintenance":false},"evaluatedAt":"2026-09-02T00:00:00.000Z"});
        let prepared = callback_request(
            "compile-start",
            serde_json::json!({"document":document,"policy":policy,"options":options,"callbackPhase":true,"executablePackCount":0}),
        );
        let frame = &prepared["value"]["frame"];
        assert_eq!(prepared["value"]["status"], "constraints");
        if mode == "mutate-document-id" {
            document["id"] = serde_json::json!("urn:test:callback:mutated-document");
        } else {
            policy["mappings"] = serde_json::json!([]);
        }
        let observed = callback_request(
            "compile-finish",
            serde_json::json!({"document":document,"policy":policy,"options":options,"frame":frame,"activeMappings":frame["activeMappings"],"callbackIssues":[]}),
        );
        let name = format!("compile-{mode}");
        let expected = corpus["cases"]
            .as_array()
            .unwrap()
            .iter()
            .find(|case| case["name"] == name)
            .unwrap();
        assert_eq!(
            observed["value"], expected["expected"]["value"]["value"],
            "{name}"
        );
    }
}

#[test]
fn independently_frozen_original_v1_compiler_and_validation_observations() {
    verify_frozen_observations(
        include_bytes!("../../../fixtures/parity/viability-controls.json"),
        "sha256:df246fe562839235f187e2f61e21a329d01c3e4f2c20d90c03d37c8191a464fc",
        404,
        false,
    );
}

#[test]
fn independently_frozen_original_signed_zero_compiler_observations() {
    verify_frozen_observations(
        include_bytes!("../../../fixtures/parity/viability-signed-zero-controls.json"),
        "sha256:56f166b4418990175a91f512c5bc22ab90eaf6393932d9aa51bc2f80c3d88244",
        54,
        true,
    );
}

#[test]
fn independently_frozen_original_nonfinite_and_sparse_viability_observations() {
    verify_frozen_observations(
        include_bytes!("../../../fixtures/parity/viability-numeric-controls.json"),
        "sha256:eca5ec36bac010643489dc929f834b086b909e6772371bc3e091006556680361",
        400,
        true,
    );
}

fn numeric_wire_value(envelope: &J) -> J {
    let mut value = envelope.get("value").unwrap().clone();
    for fact in envelope.get("numbers").unwrap().array().unwrap() {
        if fact.get("kind").unwrap().string() == Some("negative-zero") {
            continue;
        }
        let mut slot = &mut value;
        for key in fact.get("path").unwrap().array().unwrap() {
            let key = key.string().unwrap();
            slot = match slot {
                J::Object(pairs) => &mut pairs.iter_mut().find(|(name, _)| name == key).unwrap().1,
                J::Array(values) => &mut values[key.parse::<usize>().unwrap()],
                _ => panic!("Frozen observation path must exist"),
            };
        }
        // JSON.stringify writes null for nonfinite numbers and array holes.
        // The SDK differential separately checks their preserved numeric facts
        // and caller identities; this assertion compares the actual JSON wire.
        *slot = J::Null;
    }
    value
}

fn verify_frozen_observations(bytes: &[u8], expected_digest: &str, count: usize, numeric: bool) {
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
    assert_eq!(byte_digest(bytes), expected_digest);
    let corpus: Corpus = serde_json::from_slice(bytes).unwrap();
    assert_eq!(
        corpus.reference_engine,
        "399747a4ad05a37cd8db1cedd53048fad2175be4"
    );
    assert_eq!(corpus.cases.len(), count);
    let collator = Collator::try_new(Default::default(), Default::default()).unwrap();
    let comparable = |value: &J| Data::stable_bytes(value, &collator).unwrap();
    for case in corpus.cases {
        let expected = Data::parse(case.expected.get(), COMPATIBILITY_JSON_LIMITS).unwrap();
        match legacy_viability_request(case.action) {
            Ok(actual) => {
                assert_eq!(
                    expected.value().get("status").and_then(J::string),
                    Some("observed"),
                    "{}",
                    case.name
                );
                let actual = Data::parse(actual.get(), COMPATIBILITY_JSON_LIMITS).unwrap();
                let expected_value = expected.value().get("value").unwrap();
                let expected_wire = if numeric {
                    numeric_wire_value(expected_value)
                } else {
                    expected_value.clone()
                };
                assert_eq!(
                    comparable(actual.value().get("value").unwrap()),
                    comparable(&expected_wire),
                    "{}",
                    case.name
                );
                let host = expected.value().get("host").unwrap();
                for (native, original) in [("issueKeys", "issueKeys"), ("graphKeys", "graphKeys")] {
                    if let Some(keys) = host.get(original) {
                        assert_eq!(
                            comparable(actual.value().get(native).unwrap()),
                            comparable(keys),
                            "{}: {native}",
                            case.name
                        );
                    }
                }
            }
            Err(actual) => {
                assert_eq!(
                    expected.value().get("status").and_then(J::string),
                    Some("threw"),
                    "{}: {:?}",
                    case.name,
                    actual
                );
                let error = expected.value().get("error").unwrap();
                assert_eq!(
                    error.get("name").and_then(J::string),
                    Some(actual.name.as_str()),
                    "{}",
                    case.name
                );
                assert_eq!(
                    comparable(
                        Data::parse(actual.message.get(), COMPATIBILITY_JSON_LIMITS)
                            .unwrap()
                            .value()
                    ),
                    comparable(error.get("message").unwrap()),
                    "{}",
                    case.name
                );
            }
        }
    }
}
