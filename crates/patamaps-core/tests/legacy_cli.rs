use icu_collator::Collator;
use patamaps_contracts::{
    COMPATIBILITY_JSON_LIMITS, LegacyOrderedJson as J, LegacyReadOnlyJson as Data, byte_digest,
};
use patamaps_core::{LegacyWorkspaceRequest, legacy_cli_request};
use serde::Deserialize;
use serde_json::value::RawValue;

fn comparable(value: &J) -> Vec<u8> {
    let col = Collator::try_new(Default::default(), Default::default()).unwrap();
    Data::stable_bytes(value, &col).unwrap()
}

#[test]
fn frozen_catalog_values_and_uri_errors_match_original() {
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
    let bytes = include_bytes!("../package-inputs/fixtures/parity/migration-controls.json");
    assert_eq!(
        byte_digest(bytes),
        "sha256:84488b2e1c3f03a296051579067c43d50daa04f6e385062e342ce050cbb0fa51"
    );
    let corpus: Corpus = serde_json::from_slice(bytes).unwrap();
    assert_eq!(
        corpus.reference_engine,
        "399747a4ad05a37cd8db1cedd53048fad2175be4"
    );
    assert_eq!(corpus.cases.len(), 70);
    for case in corpus.cases {
        let expected = Data::parse(case.expected.get(), COMPATIBILITY_JSON_LIMITS).unwrap();
        match legacy_cli_request(case.action) {
            Ok(raw) => {
                assert_eq!(
                    expected.value().get("status").unwrap().string(),
                    Some("observed"),
                    "{}",
                    case.name
                );
                let actual = Data::parse(raw.get(), COMPATIBILITY_JSON_LIMITS).unwrap();
                let value = actual.value().get("value").unwrap_or(actual.value());
                assert_eq!(
                    comparable(value),
                    comparable(expected.value().get("value").unwrap()),
                    "{}",
                    case.name
                );
            }
            Err(error) => {
                assert_eq!(
                    expected.value().get("status").unwrap().string(),
                    Some("threw"),
                    "{}",
                    case.name
                );
                let finding = expected.value().get("error").unwrap();
                assert_eq!(
                    finding.get("name").unwrap().string(),
                    Some(error.name.as_str()),
                    "{}",
                    case.name
                );
                let message = Data::parse(error.message.get(), COMPATIBILITY_JSON_LIMITS).unwrap();
                assert_eq!(
                    comparable(message.value()),
                    comparable(finding.get("message").unwrap()),
                    "{}",
                    case.name
                );
            }
        }
    }
}

#[test]
fn frozen_cli_usage_and_argument_errors_match_original_streams() {
    #[derive(Deserialize)]
    struct Case {
        name: String,
        args: Vec<String>,
        expected: Box<RawValue>,
    }
    #[derive(Deserialize)]
    struct Corpus {
        cases: Vec<Case>,
    }
    let bytes = include_bytes!("../package-inputs/fixtures/parity/cli-controls.json");
    assert_eq!(
        byte_digest(bytes),
        "sha256:0296a5ea1a9dbd91b97a13f4dfea0dffa51d911882fcbc5131e8b1f494438f5a"
    );
    let corpus: Corpus = serde_json::from_slice(bytes).unwrap();
    assert_eq!(corpus.cases.len(), 76);
    // These first 21 frozen processes exit during argument parsing. Later cases
    // also perform filesystem/provider operations covered by the installed runner.
    for case in corpus.cases.into_iter().take(21) {
        let actual = match legacy_cli_request(LegacyWorkspaceRequest {
            operation: "plan".into(),
            input: serde_json::json!({"args":case.args}).to_string(),
            locale: "en-US".into(),
        }) {
            Ok(value) => value,
            Err(error) => legacy_cli_request(LegacyWorkspaceRequest {
                operation: "failure".into(),
                input: format!("{{\"message\":{}}}", error.message.get()),
                locale: "en-US".into(),
            })
            .unwrap(),
        };
        let actual = Data::parse(actual.get(), COMPATIBILITY_JSON_LIMITS).unwrap();
        let expected = Data::parse(case.expected.get(), COMPATIBILITY_JSON_LIMITS).unwrap();
        for field in ["exitCode", "stdout", "stderr"] {
            assert_eq!(
                comparable(actual.value().get(field).unwrap()),
                comparable(expected.value().get(field).unwrap()),
                "{} {field}",
                case.name
            );
        }
    }
}
