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

#[test]
fn captured_file_receipts_bind_utf8_bytes_without_live_io() {
    let mut req = request("label=\"é\"\n");
    req.config =
        serde_json::from_value(json!({"provider":"files","nonsecretInputs":true})).unwrap();
    rehash(&mut req);
    let a = discover_native(&req, Path::new("/unavailable-owner")).unwrap();
    let b = discover_native(&req, Path::new("/relocated-unavailable-owner")).unwrap();
    assert_eq!(canonical_bytes(&a).unwrap(), canonical_bytes(&b).unwrap());
    assert_eq!(a.shard.entities.len(), 1);
    let value = serde_json::to_value(&a.shard.entities[0]).unwrap();
    assert_eq!(value["kind"], "build:input");
    assert_eq!(
        value["attributes"]["digest"],
        byte_digest(req.inputs[0].content.as_bytes())
    );
    assert_eq!(
        canonical_bytes(&value["attributes"]["byteLength"]).unwrap(),
        canonical_bytes(&json!(req.inputs[0].content.len())).unwrap()
    );
    assert_eq!(value["attributes"]["compilationEstablished"], false);
}
#[test]
fn file_receipts_require_nonsecret_consent_and_correct_input_digest() {
    let mut req = request("a=1\n");
    req.config =
        serde_json::from_value(json!({"provider":"files","nonsecretInputs":false})).unwrap();
    rehash(&mut req);
    assert!(matches!(
        discover_native(&req, Path::new("/unused")),
        Err(Error::Refused {
            code: "NATIVE_SECRET_INPUT",
            ..
        })
    ));
    req.config.insert("nonsecretInputs".into(), json!(true));
    req.inputs[0].content.push('x');
    rehash(&mut req);
    assert!(discover_native(&req, Path::new("/unused")).is_err());
}

#[test]
fn standalone_cargo_root_is_explicit_and_does_not_read_ancestor_values() {
    use std::sync::atomic::{AtomicU64, Ordering};
    static SEQ: AtomicU64 = AtomicU64::new(0);
    let root = std::env::temp_dir().join(format!(
        "patamaps-standalone-{}-{}",
        std::process::id(),
        SEQ.fetch_add(1, Ordering::Relaxed)
    ));
    fs::create_dir(&root).unwrap();
    let package_dir = root.join("package");
    fs::create_dir(&package_dir).unwrap();
    let manifest = package_dir.join("Cargo.toml");
    let document = parse_toml(
        "Cargo.toml",
        "[package]\nname='standalone'\nversion='0.1.0'\n",
    )
    .unwrap();
    fs::write(&manifest, "[package]\nname='standalone'\nversion='0.1.0'\n").unwrap();
    assert!(
        validate_cargo_root(
            CargoRootMode::StandalonePackage,
            &manifest,
            &manifest,
            &document
        )
        .is_ok()
    );
    assert!(
        validate_cargo_root(
            CargoRootMode::ExplicitWorkspace,
            &manifest,
            &manifest,
            &document
        )
        .is_err()
    );
    assert!(
        validate_cargo_root(
            CargoRootMode::StandalonePackage,
            &root.join("other.toml"),
            &manifest,
            &document
        )
        .is_err()
    );
    let workspace = parse_toml("Cargo.toml", "[workspace]\nmembers=[]\n").unwrap();
    assert!(
        validate_cargo_root(
            CargoRootMode::StandalonePackage,
            &manifest,
            &manifest,
            &workspace
        )
        .is_err()
    );
    assert!(
        validate_cargo_root(
            CargoRootMode::ExplicitWorkspace,
            &manifest,
            &manifest,
            &workspace
        )
        .is_ok()
    );
    let inherited = parse_toml(
        "Cargo.toml",
        "[package]\nname='standalone'\nversion='0.1.0'\nworkspace='..'\n",
    )
    .unwrap();
    assert!(
        validate_cargo_root(
            CargoRootMode::StandalonePackage,
            &manifest,
            &manifest,
            &inherited
        )
        .is_err()
    );
    // Invalid UTF-8 would fail TOML/source parsing if read. Existence alone must refuse.
    fs::write(root.join("Cargo.toml"), [0xff, 0xfe]).unwrap();
    let error = validate_cargo_root(
        CargoRootMode::StandalonePackage,
        &manifest,
        &manifest,
        &document,
    )
    .unwrap_err();
    assert!(
        error
            .to_string()
            .starts_with("NATIVE_CARGO_ROOT_ISOLATION:")
    );
    assert_eq!(fs::read(root.join("Cargo.toml")).unwrap(), [0xff, 0xfe]);
    eprintln!("Retained standalone root fixture: {}", root.display());
}

#[test]
fn bounded_member_expansion_requires_captured_ordinary_manifests() {
    use std::sync::atomic::{AtomicU64, Ordering};
    static SEQ: AtomicU64 = AtomicU64::new(0);
    let root = std::env::temp_dir().join(format!(
        "patamaps-members-{}-{}",
        std::process::id(),
        SEQ.fetch_add(1, Ordering::Relaxed)
    ));
    fs::create_dir(&root).unwrap();
    let root = fs::canonicalize(root).unwrap();
    fs::create_dir(root.join("crates")).unwrap();
    for name in ["b", "a"] {
        fs::create_dir(root.join("crates").join(name)).unwrap();
        fs::write(
            root.join("crates").join(name).join("Cargo.toml"),
            [0xff, 0xfe],
        )
        .unwrap();
    }
    let inputs = Inputs::from([
        ("crates/a/Cargo.toml", "captured-a"),
        ("crates/b/Cargo.toml", "captured-b"),
    ]);
    assert_eq!(
        expand_member(&root, &root, "crates/*", &inputs).unwrap(),
        vec!["crates/a/Cargo.toml", "crates/b/Cargo.toml"]
    );
    // On-disk bytes are intentionally invalid UTF-8: expansion reads names and
    // file kinds only; source-byte matching belongs to same_sources separately.
    let missing = Inputs::from([("crates/a/Cargo.toml", "captured-a")]);
    assert!(matches!(
        expand_member(&root, &root, "crates/*", &missing),
        Err(Error::Refused {
            code: "NATIVE_CARGO_MANIFEST_INPUT",
            ..
        })
    ));
    for pattern in [
        "crates/**",
        "crates/a*",
        "crates/?",
        "crates/[ab]",
        "../*",
        "/crates/*",
        "crates/*/*",
        "crates///*",
    ] {
        assert!(
            expand_member(&root, &root, pattern, &inputs).is_err(),
            "{pattern}"
        );
    }
    fs::create_dir(root.join("empty")).unwrap();
    assert!(expand_member(&root, &root, "empty/*", &inputs).is_err());
    fs::create_dir(root.join("large")).unwrap();
    for n in 0..1025 {
        fs::create_dir(root.join("large").join(n.to_string())).unwrap();
    }
    assert!(matches!(
        expand_member(&root, &root, "large/*", &inputs),
        Err(Error::Refused {
            code: "NATIVE_CARGO_MEMBERS",
            ..
        })
    ));
    #[cfg(unix)]
    {
        std::os::unix::fs::symlink(root.join("crates/a"), root.join("alias")).unwrap();
        assert!(expand_member(&root, &root, "alias/*", &inputs).is_err());
        std::os::unix::fs::symlink(root.join("crates/a"), root.join("crates/alias")).unwrap();
        assert!(expand_member(&root, &root, "crates/*", &inputs).is_err());
    }
    eprintln!("Retained member expansion fixture: {}", root.display());
}
