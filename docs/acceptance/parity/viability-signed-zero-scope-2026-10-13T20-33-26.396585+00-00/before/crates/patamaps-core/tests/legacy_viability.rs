use icu_collator::Collator;
use patamaps_contracts::{
    COMPATIBILITY_JSON_LIMITS, LegacyOrderedJson as J, LegacyReadOnlyJson as Data, byte_digest,
};
use patamaps_core::{LegacyWorkspaceRequest, legacy_viability_request};
use serde::Deserialize;
use serde_json::value::RawValue;

#[test]
fn independently_frozen_original_v1_compiler_and_validation_observations() {
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
    let bytes = include_bytes!("../../../fixtures/parity/viability-controls.json");
    assert_eq!(
        byte_digest(bytes),
        "sha256:df246fe562839235f187e2f61e21a329d01c3e4f2c20d90c03d37c8191a464fc"
    );
    let corpus: Corpus = serde_json::from_slice(bytes).unwrap();
    assert_eq!(
        corpus.reference_engine,
        "399747a4ad05a37cd8db1cedd53048fad2175be4"
    );
    assert_eq!(corpus.cases.len(), 404);
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
                assert_eq!(
                    comparable(actual.value().get("value").unwrap()),
                    comparable(expected.value().get("value").unwrap()),
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
