use icu_collator::Collator;
use patamaps_contracts::{
    COMPATIBILITY_JSON_LIMITS, LegacyOrderedJson as J, LegacyReadOnlyJson as Data, byte_digest,
};
use patamaps_core::{LegacyWorkspaceRequest, legacy_viability_request};
use serde::Deserialize;
use serde_json::value::RawValue;

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
