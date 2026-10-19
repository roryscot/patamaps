use patamaps_contracts::{
    COMPATIBILITY_JSON_LIMITS, ContractError, JsonLimits, LegacyPackJson, byte_digest, parse_value,
};

#[test]
fn legacy_decoding_preserves_utf16_units_and_private_use_scalar_collisions() {
    let raw =
        br#"{"schemaVersion":"1.0.0","description":"\ud800\udc00\ud800\udc01\udfff\ue000\ue001"}"#;
    let parsed = LegacyPackJson::parse(raw.to_vec(), COMPATIBILITY_JSON_LIMITS).unwrap();
    assert!(!parsed.executable());
    assert_eq!(parsed.decoded_text().as_bytes(), raw);
    assert_eq!(parsed.source_bytes(), raw);
    assert_eq!(parsed.source_byte_digest(), byte_digest(raw));
    assert_eq!(parsed.unpaired_paths(), ["/description"]);
    assert!(parsed.native_value().is_err());
    // Independent UTF-16 pairs and lone units, rather than the private schema
    // projection, must appear in the original stable bytes.
    let expected = "{\"description\":\"\u{10000}\u{10001}\\udfff\u{e000}\u{e001}\",\"schemaVersion\":\"1.0.0\"}\n";
    assert_eq!(parsed.portable_digest_bytes().unwrap(), expected.as_bytes());
    // A scalar marker sequence must not collide with a surrogate escape.
    let distinct = LegacyPackJson::parse(
        br#"{"schemaVersion":"1.0.0","values":["\ud800","\ue000\ue001","\ue000","\ue001"]}"#
            .to_vec(),
        COMPATIBILITY_JSON_LIMITS,
    )
    .unwrap();
    let values = distinct.schema_projection()["values"].as_array().unwrap();
    for i in 0..values.len() {
        for j in i + 1..values.len() {
            assert_ne!(values[i], values[j]);
        }
    }
}

#[test]
fn raw_last_version_selects_duplicate_and_unicode_rules_without_changing_strict_json() {
    let legacy = br#"{"schemaVersion":"2.0.0","\u0073chemaVersion":"1.0.0","description":"\ud800","description":"kept"}"#;
    let parsed = LegacyPackJson::parse(legacy.to_vec(), COMPATIBILITY_JSON_LIMITS).unwrap();
    assert!(!parsed.executable());
    assert_eq!(parsed.native_value().unwrap()["description"], "kept");
    assert!(parsed.unpaired_paths().is_empty());
    assert!(matches!(
        parse_value(legacy),
        Err(ContractError::DuplicateKey { .. })
    ));

    let executable =
        br#"{"schemaVersion":"1.0.0","description":"\ud800","\u0073chemaVersion":"2.0.0"}"#;
    let error = LegacyPackJson::parse(executable.to_vec(), COMPATIBILITY_JSON_LIMITS).unwrap_err();
    assert!(matches!(error, ContractError::DuplicateKey { .. }));
    assert_eq!(
        error.json_diagnostic(COMPATIBILITY_JSON_LIMITS).message,
        "Duplicate JSON property \"schemaVersion\""
    );
    let unicode = br#"{"schemaVersion":"2.0.0","description":"\ud800"}"#;
    let error = LegacyPackJson::parse(unicode.to_vec(), COMPATIBILITY_JSON_LIMITS).unwrap_err();
    assert_eq!(
        error.json_diagnostic(COMPATIBILITY_JSON_LIMITS).code,
        "INVALID_JSON_UNICODE"
    );
}

#[test]
fn file_decoding_retains_invalid_utf8_evidence_and_rejects_bom_and_source_limits() {
    let mut raw = b"{\"schemaVersion\":\"1.0.0\",\"description\":\"".to_vec();
    raw.extend([0xed, 0xa0, 0x80]);
    raw.extend(b"\"}");
    let parsed = LegacyPackJson::parse(raw.clone(), COMPATIBILITY_JSON_LIMITS).unwrap();
    assert!(parsed.utf8_replacement_occurred());
    assert_eq!(parsed.source_bytes(), raw);
    assert_eq!(
        parsed.native_value().unwrap()["description"],
        "\u{fffd}\u{fffd}\u{fffd}"
    );
    let mut bom = vec![0xef, 0xbb, 0xbf];
    bom.extend(b"{}");
    assert!(LegacyPackJson::parse(bom, COMPATIBILITY_JSON_LIMITS).is_err());
    let limits = JsonLimits {
        max_bytes: raw.len() - 1,
        ..COMPATIBILITY_JSON_LIMITS
    };
    assert!(matches!(
        LegacyPackJson::parse(raw, limits),
        Err(ContractError::ScopedInputLimit { .. })
    ));
    let projected = "{\"schemaVersion\":\"1.0.0\",\"description\":\"\u{e000}\"}"
        .as_bytes()
        .to_vec();
    let limits = JsonLimits {
        max_bytes: projected.len(),
        ..COMPATIBILITY_JSON_LIMITS
    };
    let parsed = LegacyPackJson::parse(projected, limits).unwrap();
    assert_eq!(parsed.native_value().unwrap()["description"], "\u{e000}");
}

#[test]
fn frozen_file_syntax_messages_preserve_original_findings_and_native_causes() {
    #[derive(serde::Deserialize)]
    struct Case {
        name: String,
        bytes: Vec<u8>,
        expected: serde_json::Value,
    }
    #[derive(serde::Deserialize)]
    #[serde(rename_all = "camelCase")]
    struct Corpus {
        reference_engine: String,
        cases: Vec<Case>,
    }
    let bytes = include_bytes!("../package-inputs/fixtures/parity/pack-file-syntax-controls.json");
    assert_eq!(
        patamaps_contracts::byte_digest(bytes),
        "sha256:eed27b7c48a08c346f7c86382ed244fc54aa43c949139ffdf1915e94d7ec9949"
    );
    let corpus: Corpus = serde_json::from_slice(bytes).unwrap();
    assert_eq!(
        corpus.reference_engine,
        "399747a4ad05a37cd8db1cedd53048fad2175be4"
    );
    assert_eq!(corpus.cases.len(), 10);
    for case in corpus.cases {
        let error = LegacyPackJson::parse(case.bytes, COMPATIBILITY_JSON_LIMITS).unwrap_err();
        let finding = error.json_diagnostic(COMPATIBILITY_JSON_LIMITS);
        assert_eq!(finding.code, "INVALID_JSON_SYNTAX", "{}", case.name);
        assert_eq!(
            finding.message,
            case.expected["error"]["message"].as_str().unwrap(),
            "{}",
            case.name
        );
        assert!(
            finding.native_message.starts_with("INVALID_JSON_SYNTAX: "),
            "{}",
            case.name
        );
    }
}
