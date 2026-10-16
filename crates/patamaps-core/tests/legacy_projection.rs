use icu_collator::Collator;
use patamaps_contracts::{COMPATIBILITY_JSON_LIMITS, LegacyReadOnlyJson as Data, byte_digest};
use patamaps_core::{LegacyWorkspaceRequest, legacy_viability_request};
use serde_json::{Value, json};

fn digest(v: &Value) -> String {
    let input = Data::parse(&v.to_string(), COMPATIBILITY_JSON_LIMITS).unwrap();
    let locale = Collator::try_new(
        icu_collator::CollatorPreferences::from_locale_strict(&"en-US".parse().unwrap()).unwrap(),
        Default::default(),
    )
    .unwrap();
    byte_digest(&Data::stable_bytes(input.value(), &locale).unwrap())
}
fn request(document: Value, spec: Value, active: Vec<String>) -> LegacyWorkspaceRequest {
    let mut generation = json!({"schemaVersion":"1.0.0","evaluatedAt":"2026-09-02T00:00:00.000Z",
        "graph":{"id":document["id"],"revision":"1","digest":digest(&document)},
        "policy":{"id":"urn:test:policy","digest":format!("sha256:{}","0".repeat(64))},
        "context":{},"activeMappings":active,"inactiveMappings":[],"evidence":[],"waiversApplied":[]});
    let address = digest(&generation);
    generation["digest"] = json!(address);
    generation["id"] = json!(format!(
        "urn:metamap:generation:{}",
        address.trim_start_matches("sha256:")
    ));
    LegacyWorkspaceRequest {
        operation: "projection-compile".into(),
        locale: "en-US".into(),
        input: json!({"document":document,"generation":generation,"spec":spec}).to_string(),
    }
}
fn document(entities: Vec<Value>, mappings: Vec<Value>) -> Value {
    json!({"schemaVersion":"2.0.0","id":"urn:test:projection:bounded-graph","namespace":"test","revision":"1",
    "entities":entities,"mappings":mappings,"authorities":[]})
}
fn spec(subjects: Vec<String>, slots: usize) -> Value {
    json!({"schemaVersion":"1.0.0","id":"urn:test:projection:bounded-spec","select":{"ids":subjects},
      "slots":(0..slots).map(|i|json!({"name":format!("slot{i}"),"relation":"core:contains","direction":"outgoing","cardinality":"many"})).collect::<Vec<_>>()})
}
#[test]
fn cartesian_projection_expansion_refuses_before_emission() {
    let entities = (0..1536)
        .map(|i| json!({"id":format!("urn:test:entity:{i}"),"kind":"test:item"}))
        .collect::<Vec<_>>();
    let subjects = entities
        .iter()
        .map(|e| e["id"].as_str().unwrap().to_owned())
        .collect();
    let result = legacy_viability_request(request(
        document(entities, vec![]),
        spec(subjects, 1536),
        vec![],
    ));
    let error = result.unwrap_err();
    assert_eq!(error.code.as_ref(), "LEGACY_PROJECTION_RESOURCE_LIMIT");
}
#[test]
fn repeated_large_target_metadata_is_bounded_before_output_cloning() {
    let entities = vec![
        json!({"id":"urn:test:subject","kind":"test:item"}),
        json!({"id":"urn:test:target","kind":"test:item","attributes":{"payload":"a".repeat(1024*1024)}}),
    ];
    let mapping = json!({"id":"urn:test:link","relation":"core:contains","sources":["urn:test:subject"],"targets":["urn:test:target"],
      "cardinality":"one-to-one","lossiness":"lossless","provenance":{"status":"declared","assertedBy":"test:owner"}});
    let result = legacy_viability_request(request(
        document(entities, vec![mapping]),
        spec(vec!["urn:test:subject".into()], 64),
        vec!["urn:test:link".into()],
    ));
    let error = result.unwrap_err();
    assert_eq!(error.code.as_ref(), "LEGACY_PROJECTION_RESOURCE_LIMIT");
}

#[derive(serde::Deserialize)]
#[serde(rename_all = "camelCase")]
struct FrozenCase {
    name: String,
    operation: String,
    input: String,
    expected_wire: Option<Box<serde_json::value::RawValue>>,
    expected_error: Option<Box<serde_json::value::RawValue>>,
}
#[derive(serde::Deserialize)]
#[serde(rename_all = "camelCase")]
struct FrozenCorpus {
    reference_lock_digest: String,
    cases: Vec<FrozenCase>,
}
#[test]
fn original_v1_projection_corpus_preserves_records_errors_and_numeric_transport() {
    let bytes = include_bytes!("../../../fixtures/parity/projection-controls.json");
    assert_eq!(
        byte_digest(bytes),
        "sha256:38d7d483f9cca50028765f91d8c11b141ceb9f64beedca9f8ebdb2bcc081e515"
    );
    let corpus: FrozenCorpus = serde_json::from_slice(bytes).unwrap();
    assert_eq!(
        format!("sha256:{}", corpus.reference_lock_digest),
        byte_digest(include_bytes!("../../../fixtures/parity/supplement.json"))
    );
    assert_eq!(corpus.cases.len(), 66);
    check_corpus(corpus);
}

#[test]
fn collation_equal_target_order_matches_original_repeatedly() {
    let bytes = include_bytes!("../../../fixtures/parity/projection-collation-controls.json");
    let corpus: FrozenCorpus = serde_json::from_slice(bytes).unwrap();
    assert_eq!(corpus.cases.len(), 2);
    for _ in 0..32 {
        check_corpus(serde_json::from_slice(bytes).unwrap());
    }
}

fn check_corpus(corpus: FrozenCorpus) {
    assert_eq!(
        format!("sha256:{}", corpus.reference_lock_digest),
        byte_digest(include_bytes!("../../../fixtures/parity/supplement.json"))
    );
    let locale = Collator::try_new(
        icu_collator::CollatorPreferences::from_locale_strict(&"en-US".parse().unwrap()).unwrap(),
        Default::default(),
    )
    .unwrap();
    let comparable =
        |v: &patamaps_contracts::LegacyOrderedJson| Data::stable_bytes(v, &locale).unwrap();
    for case in corpus.cases {
        let request = LegacyWorkspaceRequest {
            operation: case.operation,
            input: case.input,
            locale: "en-US".into(),
        };
        if let Some(wire) = case.expected_wire {
            let expected = Data::parse(wire.get(), COMPATIBILITY_JSON_LIMITS).unwrap();
            let actual = legacy_viability_request(request)
                .unwrap_or_else(|e| panic!("{}: {e:?}", case.name));
            let actual = Data::parse(actual.get(), COMPATIBILITY_JSON_LIMITS).unwrap();
            assert_eq!(
                comparable(actual.value().get("value").unwrap()),
                comparable(expected.value().get("value").unwrap()),
                "{} value",
                case.name
            );
            let empty = patamaps_contracts::LegacyOrderedJson::Array(vec![]);
            assert_eq!(
                comparable(actual.value().get("numbers").unwrap_or(&empty)),
                comparable(expected.value().get("numbers").unwrap()),
                "{} numeric facts",
                case.name
            );
        } else {
            let expected = Data::parse(
                case.expected_error.as_ref().unwrap().get(),
                COMPATIBILITY_JSON_LIMITS,
            )
            .unwrap();
            let actual = legacy_viability_request(request).unwrap_err();
            assert_eq!(
                Some(actual.name.as_str()),
                expected.value().get("name").and_then(|v| v.string()),
                "{}",
                case.name
            );
            let message = Data::parse(actual.message.get(), COMPATIBILITY_JSON_LIMITS).unwrap();
            assert_eq!(
                comparable(message.value()),
                comparable(expected.value().get("message").unwrap()),
                "{} error message",
                case.name
            );
        }
    }
}
