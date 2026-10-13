use patamaps_contracts::{COMPATIBILITY_JSON_LIMITS, ContractError, LegacyPackJson, byte_digest};
use serde_json::Value;

#[test]
fn frozen_unchecked_digest_and_stable_bytes_match_original() {
    let raw = include_bytes!("../../../fixtures/parity/digest-controls.json");
    assert_eq!(
        byte_digest(raw),
        "sha256:b3738bc0f7c9816d6a4276e3eea40bb16d691889e9384facef62b55519a54b34"
    );
    let corpus: Value = serde_json::from_slice(raw).unwrap();
    assert_eq!(
        corpus["referenceEngine"],
        "399747a4ad05a37cd8db1cedd53048fad2175be4"
    );
    assert_eq!(corpus["originalCollation"]["locale"], "en-US");
    let cases = corpus["cases"].as_array().unwrap();
    assert_eq!(cases.len(), 40);
    for case in cases {
        let name = case["name"].as_str().unwrap();
        let mut text = case["text"].as_str().unwrap().to_owned();
        // This corpus observes the object API after JSON.parse. Executable
        // duplicate source text remains rejected by the existing strict parser.
        if name == "executable-last-version" {
            let value: Value = serde_json::from_str(&text).unwrap();
            text = serde_json::to_string(&value).unwrap();
        }
        let parsed = LegacyPackJson::parse(text.into_bytes(), COMPATIBILITY_JSON_LIMITS).unwrap();
        if name == "null-dispatch" {
            assert!(matches!(
                parsed.portable_digest_bytes(),
                Err(ContractError::LegacyDigestNull)
            ));
            continue;
        }
        let bytes = parsed.digest_bytes_for_locale("en-US").unwrap();
        assert_eq!(byte_digest(&bytes), case["expected"]["digest"], "{name}");
        if let Some(expected) = case["stableJson"].as_str() {
            assert_eq!(bytes, expected.as_bytes(), "{name}");
        }
    }
}

#[test]
fn unchecked_digest_preserves_source_and_never_supplies_native_admission() {
    let text = br#"{"Z":1,"a":2,"nonScalar":"\ud800"}"#;
    let parsed = LegacyPackJson::parse(text.to_vec(), COMPATIBILITY_JSON_LIMITS).unwrap();
    assert_eq!(parsed.source_bytes(), text);
    assert!(parsed.native_value().is_err());
    assert_eq!(
        parsed.digest_bytes_for_locale("en-US").unwrap(),
        br#"{"a":2,"nonScalar":"\ud800","Z":1}
"#
    );
}

#[test]
fn executable_digest_uses_jcs_and_ignores_legacy_locale() {
    let text = br#"{"schemaVersion":"2.0.0","3":1,"20":2,"Z":3,"a":4}"#;
    let parsed = LegacyPackJson::parse(text.to_vec(), COMPATIBILITY_JSON_LIMITS).unwrap();
    let bytes = parsed.digest_bytes_for_locale("invalid!locale").unwrap();
    assert_eq!(
        bytes,
        br#"{"20":2,"3":1,"Z":3,"a":4,"schemaVersion":"2.0.0"}"#
    );
    assert!(!bytes.ends_with(b"\n"));
}

#[test]
fn unknown_legacy_collation_does_not_fall_back_silently() {
    let parsed = LegacyPackJson::parse(b"{}".to_vec(), COMPATIBILITY_JSON_LIMITS).unwrap();
    assert!(matches!(
        parsed.digest_bytes_for_locale("invalid!locale"),
        Err(ContractError::LegacyCollation(_))
    ));
}

#[test]
fn every_unpaired_unit_and_mixed_context_matches_frozen_original_bytes() {
    let raw = include_bytes!("../../../fixtures/parity/digest-utf16-controls.json");
    assert_eq!(
        byte_digest(raw),
        "sha256:6fd875e4a72fe9fc2920d12ecc4fef701f2fb7554da238a5ed66abc11d659b3f"
    );
    let corpus: Value = serde_json::from_slice(raw).unwrap();
    assert_eq!(
        corpus["referenceEngine"],
        "399747a4ad05a37cd8db1cedd53048fad2175be4"
    );
    let cases = corpus["cases"].as_array().unwrap();
    assert_eq!(cases.len(), 65);
    for case in cases {
        let parsed = LegacyPackJson::parse(
            case["text"].as_str().unwrap().as_bytes().to_vec(),
            COMPATIBILITY_JSON_LIMITS,
        )
        .unwrap();
        let bytes = parsed.digest_bytes_for_locale("en-US").unwrap();
        assert_eq!(
            bytes,
            case["stableJson"].as_str().unwrap().as_bytes(),
            "{}",
            case["name"]
        );
        assert_eq!(
            byte_digest(&bytes),
            case["expected"]["digest"],
            "{}",
            case["name"]
        );
    }
}

#[test]
fn legacy_comparison_does_not_change_the_scalar_api_replacement_contract() {
    let collator = icu_collator::Collator::try_new(Default::default(), Default::default()).unwrap();
    assert_eq!(
        collator.compare_utf16(&[0xd800], &[0xdfff]),
        std::cmp::Ordering::Equal
    );
    assert_eq!(
        collator.compare_legacy_utf16(&[0xd800], &[0xdfff]),
        std::cmp::Ordering::Less
    );
    assert_eq!(
        collator.compare_legacy_utf16(&[0xd800], &[0xdb80, 0xdc00]),
        std::cmp::Ordering::Less
    );
}
