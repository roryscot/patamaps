use patamaps_contracts::{COMPATIBILITY_JSON_LIMITS, LegacyReadOnlyJson as Data};
use patamaps_core::LegacyWorkspaceRequest;
use patamaps_workspace::legacy_workspace_request;
use std::{
    fs,
    sync::atomic::{AtomicU64, Ordering},
};
static SEQUENCE: AtomicU64 = AtomicU64::new(0);
fn request(operation: &str, input: String) -> Box<serde_json::value::RawValue> {
    legacy_workspace_request(LegacyWorkspaceRequest {
        operation: operation.into(),
        input,
        locale: "en-US".into(),
    })
    .unwrap()
}
#[test]
fn lexical_resolution_retains_original_utf16_and_normalizes_dot_segments() {
    let value = request(
        "resolve",
        r#"{"root":"/a/\ud800","path":"../b/./\udfff"}"#.into(),
    );
    assert_eq!(value.get(), r#""/a/b/\udfff""#);
    assert_eq!(
        request("resolve", r#"{"root":"/a","path":"/x/../../"}"#.into()).get(),
        "\"/\""
    );
}
#[test]
fn written_utf16_and_read_only_json_keep_node_file_semantics() {
    let root = std::env::temp_dir().join(format!(
        "patamaps-legacy-io-{}-{}",
        std::process::id(),
        SEQUENCE.fetch_add(1, Ordering::Relaxed)
    ));
    fs::create_dir(&root).unwrap();
    let path = root.join("nested/�-value.json");
    let path_units = root
        .join("nested")
        .to_string_lossy()
        .encode_utf16()
        .chain([47, 0xd800])
        .chain("-value.json".encode_utf16())
        .collect::<Vec<_>>();
    let input = format!(
        "{{\"path\":{},\"content\":\"{{\\\"text\\\":\\\"\\ud800\\\"}}\"}}",
        Data::string_json(&path_units).get()
    );
    request("write-file", input);
    assert_eq!(fs::read(&path).unwrap(), "{\"text\":\"�\"}".as_bytes());
    let input = serde_json::json!({"path":path}).to_string();
    let read = request("read-json", input.clone());
    assert_eq!(read.get(), "{\"present\":true,\"value\":{\"text\":\"�\"}}");
    fs::write(&path, r#"{"3":"\ud800","3":"\udfff"}"#).unwrap();
    let read = request("read-json", input.clone());
    assert_eq!(read.get(), r#"{"present":true,"value":{"3":"\udfff"}}"#);
    fs::write(&path, "{bad").unwrap();
    let e = legacy_workspace_request(LegacyWorkspaceRequest {
        operation: "read-json".into(),
        input,
        locale: "en-US".into(),
    })
    .unwrap_err();
    assert_eq!(e.name, "SyntaxError");
    assert_eq!(
        Data::parse(e.message.get(), COMPATIBILITY_JSON_LIMITS)
            .unwrap()
            .value()
            .string(),
        Some("Expected property name or '}' in JSON at position 1 (line 1 column 2)")
    );
    assert_eq!(
        request(
            "read-json",
            serde_json::json!({"path":root.join("absent")}).to_string()
        )
        .get(),
        r#"{"present":false}"#
    );
    eprintln!("Retained legacy workspace I/O fixture: {}", root.display());
}

#[test]
fn mandatory_reads_and_direct_writes_preserve_missing_path_failures() {
    let root = std::env::temp_dir().join(format!(
        "patamaps-legacy-io-{}-{}",
        std::process::id(),
        SEQUENCE.fetch_add(1, Ordering::Relaxed)
    ));
    fs::create_dir(&root).unwrap();
    let absent = root.join("absent/value.json");
    for (operation, input) in [
        (
            "read-json",
            serde_json::json!({"path":absent,"optional":false}),
        ),
        (
            "write-file",
            serde_json::json!({"path":absent,"content":"value","createParents":false}),
        ),
    ] {
        let error = legacy_workspace_request(LegacyWorkspaceRequest {
            operation: operation.into(),
            input: input.to_string(),
            locale: "en-US".into(),
        })
        .unwrap_err();
        assert_eq!(error.name, "Error");
        let message = Data::parse(error.message.get(), COMPATIBILITY_JSON_LIMITS).unwrap();
        assert!(message.value().string().unwrap().starts_with("ENOENT:"));
        assert!(!root.join("absent").exists());
    }
    let path = root.join("direct.txt");
    request(
        "write-file",
        serde_json::json!({"path":path,"content":"value","createParents":false}).to_string(),
    );
    assert_eq!(fs::read(path).unwrap(), b"value");
    eprintln!("Retained mandatory legacy I/O fixture: {}", root.display());
}
