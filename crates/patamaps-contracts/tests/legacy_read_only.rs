use patamaps_contracts::{COMPATIBILITY_JSON_LIMITS, LegacyReadOnlyJson as Data};
#[test]
fn generated_read_only_values_preserve_numeric_enumeration_and_utf16() {
    let input = r#"{"Z":1,"3":2,"20":3,"a":"\ud800","\ue000":"\ue000\ue001","Z":4}"#;
    let data = Data::parse(input, COMPATIBILITY_JSON_LIMITS).unwrap();
    let output = Data::json_raw(data.value()).unwrap();
    assert_eq!(
        output.get(),
        r#"{"3":2,"20":3,"Z":4,"a":"\ud800","":""}"#
    );
    let value = Data::string_value(&[0xe000, 0xe001, 0xd800, 0xdfff]);
    let raw = Data::json_raw(&value).unwrap();
    let reparsed = Data::parse(raw.get(), COMPATIBILITY_JSON_LIMITS).unwrap();
    assert_eq!(
        Data::string_units(reparsed.value().string().unwrap()),
        vec![0xe000, 0xe001, 0xd800, 0xdfff]
    );
}
#[test]
fn stable_pretty_json_preserves_node_enumeration_utf16_and_newline() {
    let data = Data::parse(
        r#"{"z":[],"3":{"b":"\ud800","a":"\ue000"},"20":[1,{}],"a":false}"#,
        COMPATIBILITY_JSON_LIMITS,
    )
    .unwrap();
    let col = icu_collator::Collator::try_new(Default::default(), Default::default()).unwrap();
    let expected = "{\n  \"3\": {\n    \"a\": \"\",\n    \"b\": \"\\ud800\"\n  },\n  \"20\": [\n    1,\n    {}\n  ],\n  \"a\": false,\n  \"z\": []\n}\n";
    assert_eq!(
        Data::stable_pretty_bytes(data.value(), &col).unwrap(),
        expected.as_bytes()
    );
    assert_eq!(
        Data::parse(expected, COMPATIBILITY_JSON_LIMITS)
            .unwrap()
            .value()
            .get("3")
            .unwrap()
            .get("b")
            .unwrap()
            .string()
            .map(Data::string_units),
        Some(vec![0xd800])
    );
}
#[test]
fn pretty_json_keeps_insertion_order_numeric_keys_utf16_and_newline() {
    let data = Data::parse(
        r#"{"z":[],"3":{"b":"\ud800","a":"\ue000"},"20":[1,{}],"a":false}"#,
        COMPATIBILITY_JSON_LIMITS,
    )
    .unwrap();
    let expected = "{\n  \"3\": {\n    \"b\": \"\\ud800\",\n    \"a\": \"\"\n  },\n  \"20\": [\n    1,\n    {}\n  ],\n  \"z\": [],\n  \"a\": false\n}\n";
    assert_eq!(
        Data::pretty_bytes(data.value()).unwrap(),
        expected.as_bytes()
    );
}
#[test]
fn first_and_subsequent_object_keys_keep_distinct_node_syntax_findings() {
    for (input, message) in [
        (
            "{bad",
            "Expected property name or '}' in JSON at position 1 (line 1 column 2)",
        ),
        (
            "{\"a\":1,bad",
            "Expected double-quoted property name in JSON at position 7 (line 1 column 8)",
        ),
        (
            "{\"nested\":{ bad",
            "Expected property name or '}' in JSON at position 12 (line 1 column 13)",
        ),
    ] {
        let error = patamaps_contracts::LegacyPackJson::parse(
            input.as_bytes().to_vec(),
            COMPATIBILITY_JSON_LIMITS,
        )
        .unwrap_err();
        assert_eq!(
            error.json_diagnostic(COMPATIBILITY_JSON_LIMITS).message,
            message
        );
    }
}
