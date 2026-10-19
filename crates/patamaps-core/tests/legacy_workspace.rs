use icu_collator::Collator;
use patamaps_contracts::{
    COMPATIBILITY_JSON_LIMITS, LegacyOrderedJson as J, LegacyReadOnlyJson as Data, byte_digest,
};
use patamaps_core::{LegacyWorkspaceRequest, legacy_workspace_request};
use serde::Deserialize;
use serde_json::value::RawValue;
#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Corpus {
    reference_engine: String,
    cases: Vec<Case>,
}
#[derive(Deserialize)]
struct Case {
    name: String,
    action: LegacyWorkspaceRequest,
    expected: Box<RawValue>,
}
fn comparable(value: &J) -> Vec<u8> {
    let col = Collator::try_new(Default::default(), Default::default()).unwrap();
    Data::stable_bytes(value, &col).unwrap()
}
#[test]
fn all_frozen_workspace_values_and_errors_match_original() {
    let bytes = include_bytes!("../package-inputs/fixtures/parity/workspace-controls.json");
    assert_eq!(
        byte_digest(bytes),
        "sha256:7180988e57237db46577c1f8220ceaaf3fc38f5917642c983eec02586cd9c1cd"
    );
    let corpus: Corpus = serde_json::from_slice(bytes).unwrap();
    assert_eq!(
        corpus.reference_engine,
        "399747a4ad05a37cd8db1cedd53048fad2175be4"
    );
    assert_eq!(corpus.cases.len(), 59);
    for mut case in corpus.cases {
        let data = Data::parse(&case.action.input, COMPATIBILITY_JSON_LIMITS).unwrap();
        if case.action.operation == "assemble" {
            let mut packs = vec![
                Data::parse(
                    include_str!("../src/legacy_core.json"),
                    COMPATIBILITY_JSON_LIMITS,
                )
                .unwrap()
                .value()
                .clone(),
            ];
            if let Some(incoming) = data.value().get("registeredPacks") {
                packs.extend_from_slice(incoming.array().unwrap());
            }
            let versions = packs
                .iter()
                .map(|p| {
                    J::Object(vec![
                        ("key".into(), p.get("id").unwrap().clone()),
                        ("version".into(), p.get("version").unwrap().clone()),
                    ])
                })
                .collect();
            let definitions = packs
                .iter()
                .flat_map(|p| p.get("relations").unwrap().array().unwrap().iter())
                .map(|r| {
                    J::Object(vec![
                        ("key".into(), r.get("id").unwrap().clone()),
                        ("value".into(), r.clone()),
                    ])
                })
                .collect();
            let mut input = data.value().clone();
            let J::Object(fields) = &mut input else {
                panic!("object fixture")
            };
            fields.push((
                "registry".into(),
                J::Object(vec![
                    ("packs".into(), J::Array(versions)),
                    ("definitions".into(), J::Array(definitions)),
                ]),
            ));
            case.action.input = Data::json_raw(&input).unwrap().get().to_owned();
        }
        let expected = Data::parse(case.expected.get(), COMPATIBILITY_JSON_LIMITS).unwrap();
        match legacy_workspace_request(case.action) {
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
            Err(e) => {
                assert_eq!(
                    expected.value().get("status").unwrap().string(),
                    Some("threw"),
                    "{}",
                    case.name
                );
                let error = expected.value().get("error").unwrap();
                assert_eq!(
                    error.get("name").unwrap().string(),
                    Some(e.name.as_str()),
                    "{}",
                    case.name
                );
                let message = Data::parse(e.message.get(), COMPATIBILITY_JSON_LIMITS).unwrap();
                assert_eq!(
                    comparable(message.value()),
                    comparable(error.get("message").unwrap()),
                    "{}",
                    case.name
                );
                if let Some(id) = e.identifier {
                    assert_eq!(
                        comparable(
                            Data::parse(id.get(), COMPATIBILITY_JSON_LIMITS)
                                .unwrap()
                                .value()
                        ),
                        comparable(error.get("identifier").unwrap()),
                        "{}",
                        case.name
                    );
                }
            }
        }
    }
}
