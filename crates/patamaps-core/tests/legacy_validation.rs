use patamaps_contracts::RelationPack;
use patamaps_core::{RelationRegistry, validate_legacy_document, validate_legacy_document_shape};
use serde_json::Value;

#[test]
fn frozen_independent_legacy_diagnostics_preserve_every_field_and_order() {
    let corpus: Value = serde_json::from_str(include_str!(
        "../package-inputs/fixtures/parity/legacy-validation-controls.json"
    ))
    .unwrap();
    assert_eq!(
        corpus["referenceEngine"],
        "399747a4ad05a37cd8db1cedd53048fad2175be4"
    );
    let cases = corpus["cases"].as_array().unwrap();
    assert!(cases.len() >= 450);
    for case in cases {
        let registry = if let Some(packs) = case.get("nativePacks") {
            RelationRegistry::new(
                serde_json::from_value::<Vec<RelationPack>>(packs.clone()).unwrap(),
            )
            .unwrap()
        } else {
            RelationRegistry::with_legacy_core().unwrap()
        };
        let original = case["document"].clone();
        assert_eq!(
            serde_json::to_value(validate_legacy_document_shape(&case["document"])).unwrap(),
            case["expectedShape"],
            "shape {}",
            case["name"]
        );
        assert_eq!(
            serde_json::to_value(validate_legacy_document(&case["document"], &registry)).unwrap(),
            case["expectedValidation"],
            "semantics {}",
            case["name"]
        );
        assert_eq!(case["document"], original, "caller data must remain intact");
    }
}
