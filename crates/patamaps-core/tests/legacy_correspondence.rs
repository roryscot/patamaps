use icu_collator::Collator;
use patamaps_contracts::{COMPATIBILITY_JSON_LIMITS, LegacyReadOnlyJson as Data, byte_digest};
use patamaps_core::{
    LegacyCorrespondenceRequest, LegacyReferenceRequest, legacy_correspondence_request,
    legacy_reference_request,
};
use serde::Deserialize;
use serde_json::value::RawValue;
#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Corpus<T> {
    reference_engine: String,
    cases: Vec<Case<T>>,
}
#[derive(Deserialize)]
struct Case<T> {
    name: String,
    action: T,
    expected: Box<RawValue>,
}
fn comparable(raw: &str) -> Vec<u8> {
    let data = Data::parse(raw, COMPATIBILITY_JSON_LIMITS).unwrap();
    let col = Collator::try_new(Default::default(), Default::default()).unwrap();
    Data::stable_bytes(data.value(), &col).unwrap()
}
#[test]
fn complete_frozen_correspondence_values_match_original() {
    let raw = include_bytes!("../package-inputs/fixtures/parity/correspondence-controls.json");
    assert_eq!(
        byte_digest(raw),
        "sha256:3061410d68ab3fb14a4de5aaaa13088cf187302c5e1876c09c709303fe8df860"
    );
    let corpus: Corpus<LegacyCorrespondenceRequest> = serde_json::from_slice(raw).unwrap();
    assert_eq!(
        corpus.reference_engine,
        "399747a4ad05a37cd8db1cedd53048fad2175be4"
    );
    assert_eq!(corpus.cases.len(), 63);
    let col = Collator::try_new(Default::default(), Default::default()).unwrap();
    for case in corpus.cases {
        let expected = Data::parse(case.expected.get(), COMPATIBILITY_JSON_LIMITS).unwrap();
        match legacy_correspondence_request(case.action) {
            Ok(raw) => {
                assert_eq!(
                    expected.value().get("status").unwrap().string(),
                    Some("observed"),
                    "{}",
                    case.name
                );
                let actual = Data::parse(raw.get(), COMPATIBILITY_JSON_LIMITS).unwrap();
                for field in ["document", "issues", "configuredStructureIds"] {
                    assert_eq!(
                        Data::stable_bytes(actual.value().get(field).unwrap(), &col).unwrap(),
                        Data::stable_bytes(
                            expected.value().get("value").unwrap().get(field).unwrap(),
                            &col
                        )
                        .unwrap(),
                        "{}:{field}",
                        case.name
                    );
                }
            }
            Err(error) => {
                assert_eq!(
                    expected.value().get("status").unwrap().string(),
                    Some("threw"),
                    "{}",
                    case.name
                );
                let e = expected.value().get("error").unwrap();
                assert_eq!(
                    e.get("name").unwrap().string(),
                    Some(error.name.as_str()),
                    "{}",
                    case.name
                );
                assert_eq!(
                    e.get("message").unwrap().string(),
                    Some(error.message.as_str()),
                    "{}",
                    case.name
                );
            }
        }
    }
}
#[test]
fn complete_frozen_reference_values_and_refusals_match_original() {
    let raw = include_bytes!("../package-inputs/fixtures/parity/reference-controls.json");
    assert_eq!(
        byte_digest(raw),
        "sha256:44bf09feb2bf64a9162116630c511d16446e6a24621c1f7b57a1cf00481c5a37"
    );
    let corpus: Corpus<LegacyReferenceRequest> = serde_json::from_slice(raw).unwrap();
    assert_eq!(
        corpus.reference_engine,
        "399747a4ad05a37cd8db1cedd53048fad2175be4"
    );
    assert_eq!(corpus.cases.len(), 253);
    for case in corpus.cases {
        let actual=match legacy_reference_request(case.action){Ok(value)=>format!("{{\"status\":\"observed\",\"value\":{}}}",value.get()),Err(error)=>serde_json::to_string(&serde_json::json!({"status":"threw","error":{"name":error.name,"message":error.message}})).unwrap()};
        assert_eq!(
            comparable(&actual),
            comparable(case.expected.get()),
            "{}",
            case.name
        );
    }
}
#[test]
fn every_unpaired_uri_unit_refuses_without_scalar_replacement() {
    for unit in 0xd800..=0xdfff {
        let input = format!(
            "{{\"namespace\":\"n\",\"kind\":\"entity\",\"value\":{}}}",
            Data::string_json(&[unit]).get()
        );
        let request =
            serde_json::from_value(serde_json::json!({"operation":"urn","input":input})).unwrap();
        let error = legacy_reference_request(request).unwrap_err();
        assert_eq!(error.name, "URIError");
        assert_eq!(error.message, "URI malformed");
    }
}
