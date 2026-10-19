use patamaps_contracts::{COMPATIBILITY_JSON_LIMITS, LegacyReadOnlyJson as Data, byte_digest};
use patamaps_scientific::{
    LegacyConfigRequest, legacy_config_request, load_legacy_metamap_config_bytes,
};
use serde::Deserialize;
use serde_json::value::RawValue;
#[derive(Deserialize)]
struct Corpus {
    cases: Vec<Case>,
}
#[derive(Deserialize)]
struct Case {
    name: String,
    action: LegacyConfigRequest,
    expected: Box<RawValue>,
}
#[test]
fn frozen_original_config_contracts() {
    let bytes = include_bytes!("../package-inputs/fixtures/parity/config-controls.json");
    assert_eq!(
        byte_digest(bytes),
        "sha256:8e8679fa88f457687ab06614a2e6b98d778cbd17af6257474a7682bafde30aed"
    );
    // The corpus action has an observation-only operation tag, omitted here.
    #[derive(Deserialize)]
    struct InputCorpus {
        cases: Vec<InputCase>,
    }
    #[derive(Deserialize)]
    struct InputCase {
        name: String,
        action: InputAction,
        expected: Box<RawValue>,
    }
    #[derive(Deserialize)]
    struct InputAction {
        input: String,
    }
    let input: InputCorpus = serde_json::from_slice(bytes).unwrap();
    let corpus = Corpus {
        cases: input
            .cases
            .into_iter()
            .map(|c| Case {
                name: c.name,
                action: LegacyConfigRequest {
                    input: c.action.input,
                },
                expected: c.expected,
            })
            .collect(),
    };
    assert_eq!(corpus.cases.len(), 213);
    for case in corpus.cases {
        let expected = Data::parse(case.expected.get(), COMPATIBILITY_JSON_LIMITS)
            .unwrap()
            .schema_projection()
            .unwrap();
        match legacy_config_request(case.action) {
            Ok(raw) => {
                assert_eq!(expected["status"], "observed", "{}", case.name);
                let actual = Data::parse(raw.get(), COMPATIBILITY_JSON_LIMITS)
                    .unwrap()
                    .schema_projection()
                    .unwrap();
                assert_eq!(actual, expected["value"], "{}", case.name);
            }
            Err(error) => {
                assert_eq!(expected["status"], "threw", "{}", case.name);
                let text = serde_json::to_string(&error).unwrap();
                let actual = Data::parse(&text, COMPATIBILITY_JSON_LIMITS)
                    .unwrap()
                    .schema_projection()
                    .unwrap();
                for field in ["name", "message"] {
                    assert_eq!(
                        actual[field], expected["error"][field],
                        "{}:{field}",
                        case.name
                    );
                }
                if !expected["error"]["code"].is_null() {
                    assert_eq!(actual["code"], expected["error"]["code"], "{}", case.name);
                }
            }
        }
    }
}
#[test]
fn loaded_paths_are_lexical_and_preserve_unpaired_repository_units() {
    let input = r#"{"schemaVersion":"1.0.0","id":"i","namespace":"n","repository":"r","repositoryRoot":"../\udfff/./x/..","sources":[{"id":"db","adapter":"prisma","path":"s"}],"correspondences":[],"outputs":{"graph":"g","snapshot":"s","report":"r","documentation":"d"}}"#;
    let result = load_legacy_metamap_config_bytes(
        input.as_bytes(),
        std::path::Path::new("/fixture/project/config.json"),
    )
    .unwrap();
    assert_eq!(result.config_directory, "/fixture/project");
    assert_eq!(result.repository_root.get(), r#""/fixture/\udfff""#);
    let duplicate = input.replace(
        "\"schemaVersion\":\"1.0.0\"",
        "\"schemaVersion\":\"2.0.0\",\"schemaVersion\":\"1.0.0\"",
    );
    assert!(patamaps_scientific::parse_legacy_metamap_config(duplicate.as_bytes()).is_ok());
}
