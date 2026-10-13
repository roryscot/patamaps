use patamaps_contracts::{
    GraphDocument, MAX_INPUT_BYTES, MAX_JSON_DEPTH, canonical_bytes, canonical_digest, parse,
    parse_value,
};
use serde_json::{Value, json};

fn canonical(input: &str) -> String {
    String::from_utf8(canonical_bytes(&parse_value(input.as_bytes()).unwrap()).unwrap()).unwrap()
}

#[test]
fn nullable_budget_is_an_explicit_choice_and_absence_is_not_null() {
    use patamaps_contracts::ProjectionRequirements;
    assert!(parse::<ProjectionRequirements>(br#"{"consumer":"urn:consumer"}"#).is_err());
    assert!(
        parse::<ProjectionRequirements>(br#"{"consumer":"urn:consumer","budget":null}"#)
            .unwrap()
            .budget
            .is_none()
    );
    assert_eq!(
        parse::<ProjectionRequirements>(br#"{"consumer":"urn:consumer","budget":"urn:budget"}"#)
            .unwrap()
            .budget
            .as_deref(),
        Some("urn:budget")
    );
}

#[test]
fn normative_unicode_order_and_no_normalization() {
    let input = "{\"€\":1,\"\\r\":2,\"דּ\":3,\"1\":4,\"😀\":5,\"\\u0080\":6,\"ö\":7,\"a\":[3,2,1]}";
    assert_eq!(
        canonical(input),
        "{\"\\r\":2,\"1\":4,\"a\":[3,2,1],\"\u{0080}\":6,\"ö\":7,\"€\":1,\"😀\":5,\"דּ\":3}"
    );
    assert_ne!(canonical("\"é\""), canonical("\"e\\u0301\""));
}

#[test]
fn normative_binary64_numbers_and_hash_bytes() {
    assert_eq!(
        canonical("[333333333.33333329,1e30,4.5,2e-3,1e-27,-0]"),
        "[333333333.3333333,1e+30,4.5,0.002,1e-27,0]"
    );
    for (bits, expected) in [
        (0x0000000000000001, "5e-324"),
        (0x8000000000000001, "-5e-324"),
        (0x7fefffffffffffff, "1.7976931348623157e+308"),
        (0xffefffffffffffff, "-1.7976931348623157e+308"),
        (0x4340000000000000, "9007199254740992"),
        (0x4430000000000000, "295147905179352830000"),
        (0x44b52d02c7e14af5, "9.999999999999997e+22"),
        (0x44b52d02c7e14af6, "1e+23"),
        (0x44b52d02c7e14af7, "1.0000000000000001e+23"),
        (0x3eb0c6f7a0b5ed8c, "9.999999999999997e-7"),
        (0x3eb0c6f7a0b5ed8d, "0.000001"),
    ] {
        assert_eq!(
            String::from_utf8(canonical_bytes(&f64::from_bits(bits)).unwrap()).unwrap(),
            expected
        );
    }
    // SHA-256 of the exact UTF-8 bytes of {}, without a trailing newline.
    assert_eq!(
        canonical_digest(&json!({})).unwrap(),
        "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
    );
    assert_eq!(canonical("9007199254740993"), "9007199254740992");
}

#[test]
fn malformed_or_duplicate_json_never_reaches_typed_values() {
    for input in [
        "{\"a\":1,\"a\":2}",
        "{\"a\":1,\"\\u0061\":2}",
        "{\"a\":{\"x\":1,\"x\":2}}",
        "[1,]",
        "{} {}",
        "\"\\ud800\"",
        "\"\\udfff\"",
        "1e999",
        "NaN",
    ] {
        assert!(parse_value(input.as_bytes()).is_err(), "accepted {input}");
    }
    assert!(parse_value(b"\"\xff\"").is_err());
    assert_eq!(
        canonical("{\"__proto__\":{\"admin\":true}}"),
        "{\"__proto__\":{\"admin\":true}}"
    );
}

#[test]
fn parser_bounds_are_enforced_before_unlimited_recursion() {
    let deep = "[".repeat(MAX_JSON_DEPTH + 2) + "0" + &"]".repeat(MAX_JSON_DEPTH + 2);
    assert!(parse_value(deep.as_bytes()).is_err());
    assert!(parse_value(&vec![b' '; MAX_INPUT_BYTES + 1]).is_err());
}

#[test]
fn compatibility_nesting_preserves_the_reference_domain_without_weakening_strict_parsing() {
    use patamaps_contracts::{COMPATIBILITY_JSON_LIMITS, JsonLimits, parse_value_with_limits};
    for depth in [65, 128, 512] {
        let text = "[".repeat(depth) + "0" + &"]".repeat(depth);
        assert!(parse_value(text.as_bytes()).is_err());
        let parsed = parse_value_with_limits(text.as_bytes(), COMPATIBILITY_JSON_LIMITS).unwrap();
        assert_eq!(canonical_bytes(&parsed).unwrap(), text.as_bytes());
        assert_eq!(
            canonical_digest(&parsed).unwrap(),
            patamaps_contracts::byte_digest(text.as_bytes())
        );
    }
    let text = "[".repeat(513) + "0" + &"]".repeat(513);
    assert!(parse_value_with_limits(text.as_bytes(), COMPATIBILITY_JSON_LIMITS).is_err());
    let duplicate = "{\"child\":".repeat(511) + "{\"a\":1,\"\\u0061\":2}" + &"}".repeat(511);
    let error =
        parse_value_with_limits(duplicate.as_bytes(), COMPATIBILITY_JSON_LIMITS).unwrap_err();
    assert!(error.to_string().contains("DUPLICATE_JSON_KEY"));
    assert!(
        parse_value_with_limits(
            b"0",
            JsonLimits {
                max_depth: 513,
                ..COMPATIBILITY_JSON_LIMITS
            }
        )
        .is_err()
    );
}

#[test]
fn draft_wire_is_closed_and_absent_differs_from_null() {
    let value: Value =
        serde_json::from_slice(include_bytes!("../../../fixtures/routing/graph.json")).unwrap();
    assert!(parse::<GraphDocument>(&serde_json::to_vec(&value).unwrap()).is_ok());
    for (field, replacement) in [
        ("schemaVersion", json!("1.0.0")),
        ("label", Value::Null),
        ("unrecognized", json!(true)),
    ] {
        let mut input = value.clone();
        input[field] = replacement;
        assert!(parse::<GraphDocument>(&serde_json::to_vec(&input).unwrap()).is_err());
    }
}

#[test]
fn interoperable_integer_bounds_and_overflow_are_explicit() {
    use patamaps_contracts::{MAX_SAFE_INTEGER, SafeInteger};
    assert_eq!(
        parse::<SafeInteger>(b"9007199254740991").unwrap().get(),
        MAX_SAFE_INTEGER
    );
    for input in ["-1", "1.5", "9007199254740992", "9007199254740993", "\"1\""] {
        assert!(parse::<SafeInteger>(input.as_bytes()).is_err());
    }
    assert!(
        SafeInteger::new(MAX_SAFE_INTEGER)
            .unwrap()
            .checked_add(SafeInteger::new(1).unwrap())
            .is_none()
    );
}
