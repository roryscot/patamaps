use super::*;
use crate::SuppliedInput;
use patamaps_contracts::canonical_bytes;

fn request(raw: &str) -> AdapterRequest {
    let mut request:AdapterRequest=serde_json::from_value(json!({
        "schemaVersion":"0.1.0","documentType":"adapter-request","profile":PROFILE,
        "sourceId":"toml-test","namespace":"native-observation-tests",
        "config":{"provider":"toml","nonsecretInputs":true,"files":[{"path":"input.toml","fields":[[]]}]},
        "inputs":[{"receipt":{"path":"input.toml","digest":byte_digest(raw.as_bytes()),"byteLength":raw.len()},"content":raw}],
        "invocationDigest":format!("sha256:{}","0".repeat(64)),"requestDigest":""
    })).unwrap();
    rehash(&mut request);
    request
}
fn rehash(request: &mut AdapterRequest) {
    request.request_digest.clear();
    request.request_digest = canonical_digest(request).unwrap();
}
fn response(raw: &str) -> Value {
    // Exercise the actual canonical wire representation, not serde's internal
    // distinction between equivalent integral and floating-point JSON numbers.
    let value = discover_native(&request(raw), Path::new("/not-a-live-owner-root")).unwrap();
    serde_json::from_slice(&canonical_bytes(&value).unwrap()).unwrap()
}

fn observation(response: &Value, key: Value) -> &Value {
    &response["shard"]["entities"]
        .as_array()
        .unwrap()
        .iter()
        .find(|e| e["attributes"]["observation"]["key"] == key)
        .unwrap()["attributes"]["observation"]
}
#[test]
fn integers_dates_and_special_floats_are_lossless_tagged_values() {
    let result = response(
        "large = 9007199254740993\nlargest = 9223372036854775807\nwhen = 1979-05-27T07:32:00Z\nnan = nan\ninfinite = +inf\nnegative_zero = -0.0\n",
    );
    assert_eq!(
        observation(&result, json!(["large"]))["value"],
        json!({"type":"integer","decimal":"9007199254740993"})
    );
    assert_eq!(
        observation(&result, json!(["largest"]))["value"]["decimal"],
        "9223372036854775807"
    );
    assert_eq!(
        observation(&result, json!(["when"]))["value"]["type"],
        "datetime"
    );
    assert_eq!(
        observation(&result, json!(["when"]))["lexeme"],
        "1979-05-27T07:32:00Z"
    );
    assert_eq!(observation(&result, json!(["nan"]))["lexeme"], "nan");
    let bits = u64::from_str_radix(
        observation(&result, json!(["nan"]))["value"]["ieee754Bits"]
            .as_str()
            .unwrap(),
        16,
    )
    .unwrap();
    assert!(f64::from_bits(bits).is_nan());
    assert_eq!(observation(&result, json!(["infinite"]))["lexeme"], "+inf");
    assert_eq!(
        observation(&result, json!(["negative_zero"]))["value"]["ieee754Bits"],
        "8000000000000000"
    );
}
#[test]
fn key_and_value_spans_are_utf8_byte_offsets() {
    let result = response("name = \"é\"\n");
    let item = observation(&result, json!(["name"]));
    assert_eq!(item["keySpan"], json!([0, 4]));
    assert_eq!(item["valueSpan"], json!([7, 11]));
    assert_eq!(item["lexeme"], "\"é\"");
    assert_eq!(item["value"], json!({"type":"string","value":"é"}));
}
#[test]
fn quoted_and_dotted_keys_do_not_collapse() {
    let result = response("\"a.b\" = 3\na.b = 4\n");
    assert_eq!(
        observation(&result, json!(["a.b"]))["value"]["decimal"],
        "3"
    );
    assert_eq!(
        observation(&result, json!(["a", "b"]))["value"]["decimal"],
        "4"
    );
    let ids = result["shard"]["entities"]
        .as_array()
        .unwrap()
        .iter()
        .map(|v| v["id"].as_str().unwrap())
        .collect::<BTreeSet<_>>();
    assert_eq!(
        ids.len(),
        result["shard"]["entities"].as_array().unwrap().len()
    );
}
#[test]
fn compounds_empty_containers_and_array_tables_are_observed() {
    let result = response(
        "a = [true, {x=1}, []]\n[empty]\n[[servers]]\nname = \"one\"\n[[servers]]\nname = \"two\"\n",
    );
    assert_eq!(
        observation(&result, json!(["a", 0]))["value"]["value"],
        true
    );
    assert_eq!(
        observation(&result, json!(["a", 1, "x"]))["value"]["decimal"],
        "1"
    );
    assert_eq!(
        observation(&result, json!(["a", 2]))["value"],
        json!({"type":"array","length":0})
    );
    assert_eq!(
        observation(&result, json!(["empty"]))["value"]["type"],
        "table"
    );
    assert_eq!(
        observation(&result, json!(["servers"]))["value"]["type"],
        "array-of-tables"
    );
    assert_eq!(
        observation(&result, json!(["servers", 1, "name"]))["value"]["value"],
        "two"
    );
}
#[test]
fn duplicate_keys_malformed_values_and_out_of_range_integers_refuse() {
    for raw in ["a=1\na=2\n", "a = [", "a = 9223372036854775808"] {
        assert!(matches!(
            discover_native(&request(raw), Path::new("/unused")),
            Err(Error::Refused {
                code: "NATIVE_TOML_SYNTAX",
                ..
            })
        ));
    }
}
#[test]
fn explicit_fields_exclude_unselected_values_and_missing_fields_refuse() {
    let mut req =
        request("[http]\nlisten=\"127.0.0.1:1\"\n[unrelated]\nvalue=\"synthetic-not-selected\"\n");
    req.config.insert(
        "files".into(),
        json!([{"path":"input.toml","fields":[["http","listen"]]}]),
    );
    rehash(&mut req);
    let result = discover_native(&req, Path::new("/unused")).unwrap();
    assert_eq!(result.shard.entities.len(), 1);
    assert!(
        !String::from_utf8(canonical_bytes(&result).unwrap())
            .unwrap()
            .contains("synthetic-not-selected")
    );
    req.config.insert(
        "files".into(),
        json!([{"path":"input.toml","fields":[["http","absent"]]}]),
    );
    rehash(&mut req);
    assert!(matches!(
        discover_native(&req, Path::new("/unused")),
        Err(Error::Refused {
            code: "NATIVE_TOML_FIELD",
            ..
        })
    ));
}
#[test]
fn request_and_each_captured_input_bind_exact_bytes() {
    let mut req = request("a=1\n");
    req.inputs[0].content = "a=2\n".into();
    assert!(matches!(
        discover_native(&req, Path::new("/unused")),
        Err(Error::Refused {
            code: "NATIVE_DISCOVERY_REQUEST",
            ..
        })
    ));
    rehash(&mut req);
    assert!(matches!(
        discover_native(&req, Path::new("/unused")),
        Err(Error::Refused {
            code: "NATIVE_DISCOVERY_INPUT",
            ..
        })
    ));
    let mut req = request("a=1\n");
    req.inputs[0].receipt.path = "../escape.toml".into();
    rehash(&mut req);
    assert!(matches!(
        discover_native(&req, Path::new("/unused")),
        Err(Error::Refused {
            code: "NATIVE_DISCOVERY_INPUT",
            ..
        })
    ));
    let mut req = request("a=1\n");
    let duplicate: SuppliedInput = req.inputs[0].clone();
    req.inputs.push(duplicate);
    rehash(&mut req);
    assert!(matches!(
        discover_native(&req, Path::new("/unused")),
        Err(Error::Refused {
            code: "NATIVE_DISCOVERY_INPUT",
            ..
        })
    ));
}
#[test]
fn undeclared_secrets_unknown_configuration_and_excessive_nodes_refuse() {
    let mut req = request("a=1\n");
    req.config.insert("nonsecretInputs".into(), json!(false));
    rehash(&mut req);
    assert!(matches!(
        discover_native(&req, Path::new("/unused")),
        Err(Error::Refused {
            code: "NATIVE_SECRET_INPUT",
            ..
        })
    ));
    let mut req = request("a=1\n");
    req.config.insert("unimplemented".into(), json!(true));
    rehash(&mut req);
    assert!(matches!(
        discover_native(&req, Path::new("/unused")),
        Err(Error::Refused {
            code: "NATIVE_DISCOVERY_CONFIG",
            ..
        })
    ));
    let raw = (0..10_001)
        .map(|i| format!("key{i}=1\n"))
        .collect::<String>();
    assert!(matches!(
        discover_native(&request(&raw), Path::new("/unused")),
        Err(Error::Refused {
            code: "NATIVE_TOML_LIMIT",
            ..
        })
    ));
}
#[test]
fn toml_observations_are_offline_and_owner_root_independent() {
    let req = request("a=1\n");
    let a = discover_native(&req, Path::new("/missing-first-checkout")).unwrap();
    let b = discover_native(&req, Path::new("/different-missing-checkout")).unwrap();
    assert_eq!(canonical_bytes(&a).unwrap(), canonical_bytes(&b).unwrap());
    assert_eq!(
        a.inputs,
        req.inputs
            .iter()
            .map(|v| v.receipt.clone())
            .collect::<Vec<_>>()
    );
}

#[test]
fn repeated_long_key_paths_cannot_amplify_the_observation_budget() {
    let key = "k".repeat(16_384);
    let mut raw = format!("[\"{key}\"]\n");
    for i in 0..1000 {
        raw.push_str(&format!("field{i}=1\n"));
    }
    assert!(matches!(
        discover_native(&request(&raw), Path::new("/unused")),
        Err(Error::Refused {
            code: "NATIVE_TOML_LIMIT",
            ..
        })
    ));
}
