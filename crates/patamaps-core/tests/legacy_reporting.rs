use icu_collator::Collator;
use patamaps_contracts::{
    COMPATIBILITY_JSON_LIMITS, LegacyPackJson, LegacyReadOnlyJson, byte_digest,
};
use patamaps_core::{LegacyReportingAction, LegacyReportingRequest, legacy_reporting_request};
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
    action: LegacyReportingAction,
    expected: Box<RawValue>,
}
#[test]
fn all_frozen_original_diff_and_report_outputs_match() {
    let raw = include_bytes!("../package-inputs/fixtures/parity/reporting-controls.json");
    assert_eq!(
        byte_digest(raw),
        "sha256:6374b76bcd45d9e47dee7d4ae59547d4aaccb18a10a20736946c9b3578d97d0e"
    );
    let corpus: Corpus = serde_json::from_slice(raw).unwrap();
    assert_eq!(
        corpus.reference_engine,
        "399747a4ad05a37cd8db1cedd53048fad2175be4"
    );
    assert_eq!(corpus.cases.len(), 60);
    let col = Collator::try_new(Default::default(), Default::default()).unwrap();
    for case in corpus.cases {
        let response = legacy_reporting_request(LegacyReportingRequest {
            action: case.action,
            locale: "en-US".into(),
        })
        .unwrap();
        let actual = serde_json::to_string(&response).unwrap();
        let actual = LegacyReadOnlyJson::parse(&actual, COMPATIBILITY_JSON_LIMITS).unwrap();
        let expected =
            LegacyReadOnlyJson::parse(case.expected.get(), COMPATIBILITY_JSON_LIMITS).unwrap();
        // Normalize only result object member order; arrays and UTF-16 strings
        // remain exact. The standalone JS driver also uses deep strict equality.
        assert_eq!(
            LegacyReadOnlyJson::stable_bytes(actual.value(), &col).unwrap(),
            LegacyReadOnlyJson::stable_bytes(expected.value(), &col).unwrap(),
            "{}",
            case.name
        );
    }
}
#[test]
fn read_only_data_does_not_select_executable_pack_rules_or_admission() {
    let text = r#"{"schemaVersion":"2.0.0","id":"a","id":"b","label":"\ud800"}"#;
    let data = LegacyReadOnlyJson::parse(text, COMPATIBILITY_JSON_LIMITS).unwrap();
    assert_eq!(data.value().get("id").unwrap().string(), Some("b"));
    assert_eq!(
        LegacyReadOnlyJson::string_units(data.value().get("label").unwrap().string().unwrap()),
        vec![0xd800]
    );
    assert!(LegacyPackJson::parse(text.as_bytes().to_vec(), COMPATIBILITY_JSON_LIMITS).is_err());
}
#[test]
fn finite_transport_and_locale_bounds_refuse_explicitly() {
    for text in [
        "{",
        "[1e999]",
        &format!("{}0{}", "[".repeat(513), "]".repeat(513)),
    ] {
        assert!(LegacyReadOnlyJson::parse(text, COMPATIBILITY_JSON_LIMITS).is_err());
    }
    let input = r#"{"entities":[],"mappings":[],"authorities":[]}"#.to_owned();
    let failure = legacy_reporting_request(LegacyReportingRequest {
        action: LegacyReportingAction::Diff {
            before: input.clone(),
            after: input,
        },
        locale: "invalid!locale".into(),
    })
    .unwrap_err();
    assert_eq!(failure.code, "LEGACY_REPORTING_INPUT");
    assert_eq!(failure.message, "Invalid reporting locale");
}
#[test]
fn missing_required_collections_are_not_silently_empty() {
    let failure = legacy_reporting_request(LegacyReportingRequest {
        action: LegacyReportingAction::Diff {
            before: "{}".into(),
            after: "{}".into(),
        },
        locale: "en-US".into(),
    })
    .unwrap_err();
    assert_eq!(
        failure.message,
        "Read-only legacy entities requires an array"
    );
}
