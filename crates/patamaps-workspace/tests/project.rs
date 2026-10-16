use patamaps_contracts::{SafeInteger, byte_digest, canonical_bytes, parse};
use patamaps_workspace::*;
use serde_json::json;
use std::{
    fs,
    path::PathBuf,
    sync::atomic::{AtomicU64, Ordering},
};
static SEQ: AtomicU64 = AtomicU64::new(0);
fn fixture() -> (PathBuf, ProjectProfile) {
    let root = std::env::temp_dir().join(format!(
        "patamaps-project-{}-{}",
        std::process::id(),
        SEQ.fetch_add(1, Ordering::Relaxed)
    ));
    fs::create_dir(&root).unwrap();
    fs::create_dir(root.join("frontend")).unwrap();
    fs::write(
        root.join("frontend/package.json"),
        b"{\"name\":\"real-layout\"}\n",
    )
    .unwrap();
    let profile = parse(&serde_json::to_vec(&json!({
        "profile": PROJECT_PROFILE, "id": "urn:project:test", "nonsecretInputs": true,
        "inputs": ["frontend/package.json"],
        "components": [{"id":"web","kind":"next-app","root":"frontend","entrypoints":["frontend/package.json"]}],
        "secretReferences": {"database":"PATAMAPS_TEST_SECRET_NEVER_RESOLVE"},
        "nonsecretConfiguration":{"port":8080}
    })).unwrap()).unwrap();
    eprintln!("Retained project fixture: {}", root.display());
    (root, profile)
}
#[test]
fn capture_replay_survives_absent_sources_and_preserves_bytes() {
    let (root, p) = fixture();
    let record = capture_project(&root, p.clone()).unwrap();
    assert_eq!(record.inputs[0].content, "{\"name\":\"real-layout\"}\n");
    assert_eq!(record.digest, capture_project(&root, p).unwrap().digest);
    fs::rename(root.join("frontend"), root.join("frontend-retained")).unwrap();
    let roundtrip: ProjectCapture = parse(&canonical_bytes(&record).unwrap()).unwrap();
    let report = verify_project_capture(&roundtrip).unwrap();
    assert_eq!(report["status"], "verified-project-input-bindings");
    assert_eq!(report["secretResolution"], "not-performed");
    assert_eq!(report["admission"], "not-performed");
}
#[test]
fn secret_paths_escapes_and_generated_dependency_trees_refuse() {
    for path in [
        "../private",
        "/absolute",
        "a/../b",
        "a\\b",
        ".env",
        "nested/.env.local",
        ".git/config",
        "target/key",
        "node_modules/pkg/a",
    ] {
        let (_, mut p) = fixture();
        p.inputs = vec![path.into()];
        assert!(p.validate().is_err(), "{path}");
    }
}
#[test]
fn duplicate_inputs_components_and_unselected_entrypoints_refuse() {
    let (_, p) = fixture();
    let mut bad = p.clone();
    bad.inputs.push(bad.inputs[0].clone());
    assert!(bad.validate().is_err());
    let mut bad = p.clone();
    bad.components.push(bad.components[0].clone());
    assert!(bad.validate().is_err());
    let mut bad = p.clone();
    bad.components[0].entrypoints = vec!["not-selected".into()];
    assert!(bad.validate().is_err());
    let mut bad = p;
    bad.components[0].root = "other".into();
    assert!(bad.validate().is_err());
}
#[test]
fn nonsecret_declaration_and_secret_reference_syntax_are_required() {
    let (_, p) = fixture();
    let mut bad = p.clone();
    bad.nonsecret_inputs = false;
    assert!(bad.validate().is_err());
    for name in ["", "9BAD", "TOKEN=value", "secret/file", "ENV\nVALUE"] {
        let mut bad = p.clone();
        bad.secret_references.insert("database".into(), name.into());
        assert!(bad.validate().is_err());
    }
    let mut bad = p;
    bad.nonsecret_configuration
        .insert("database".into(), json!("not-allowed"));
    assert!(bad.validate().is_err());
}
#[test]
fn tampered_content_profile_and_receipt_refuse_offline() {
    let (root, p) = fixture();
    let record = capture_project(&root, p).unwrap();
    let mut bad = record.clone();
    bad.inputs[0].content.push('!');
    assert!(verify_project_capture(&bad).is_err());
    let mut bad = record.clone();
    bad.inputs[0].receipt.digest = "sha256:wrong".into();
    assert!(verify_project_capture(&bad).is_err());
    let mut bad = record.clone();
    bad.definition.id = "urn:substitution".into();
    assert!(verify_project_capture(&bad).is_err());
    let mut bad = record;
    bad.profile = "wrong".into();
    assert!(verify_project_capture(&bad).is_err());
}
#[test]
fn unknown_fields_and_duplicate_json_keys_refuse() {
    let (_, p) = fixture();
    let mut v = serde_json::to_value(p).unwrap();
    v["execute"] = json!("arbitrary");
    assert!(parse::<ProjectProfile>(&serde_json::to_vec(&v).unwrap()).is_err());
    assert!(parse::<ProjectProfile>(br#"{"profile":"a","profile":"b"}"#).is_err());
}
#[cfg(unix)]
#[test]
fn file_and_directory_symlinks_and_fifo_refuse() {
    use std::os::unix::fs::symlink;
    let (root, p) = fixture();
    fs::rename(
        root.join("frontend/package.json"),
        root.join("retained.json"),
    )
    .unwrap();
    symlink(
        root.join("retained.json"),
        root.join("frontend/package.json"),
    )
    .unwrap();
    assert!(capture_project(&root, p).is_err());
    let (root, p) = fixture();
    fs::rename(root.join("frontend"), root.join("retained")).unwrap();
    symlink(root.join("retained"), root.join("frontend")).unwrap();
    assert!(capture_project(&root, p).is_err());
    let (root, p) = fixture();
    fs::rename(
        root.join("frontend/package.json"),
        root.join("retained.json"),
    )
    .unwrap();
    assert!(
        std::process::Command::new("/usr/bin/mkfifo")
            .arg(root.join("frontend/package.json"))
            .status()
            .unwrap()
            .success()
    );
    assert!(capture_project(&root, p).is_err());
}
#[test]
fn invalid_utf8_and_oversized_input_refuse() {
    let (root, p) = fixture();
    fs::write(root.join("frontend/package.json"), [0xff]).unwrap();
    assert!(capture_project(&root, p.clone()).is_err());
    fs::write(
        root.join("frontend/package.json"),
        vec![b'a'; patamaps_contracts::MAX_INPUT_BYTES + 1],
    )
    .unwrap();
    assert!(capture_project(&root, p).is_err());
}

#[cfg(unix)]
#[test]
fn staged_inputs_recapture_identically_after_sources_are_unavailable() {
    use std::os::unix::fs::PermissionsExt;
    let (root, mut profile) = fixture();
    fs::write(root.join("frontend/config.json"), "{\"label\":\"☃\"}\n").unwrap();
    profile.inputs.push("frontend/config.json".into());
    let record = capture_project(&root, profile.clone()).unwrap();
    fs::rename(root.join("frontend"), root.join("frontend-retained")).unwrap();
    let destination = root.join("candidate");
    let receipt = stage_project_capture(&record, &destination).unwrap();
    assert_eq!(receipt["status"], "staged-project-inputs");
    assert_eq!(receipt["digest"], record.digest);
    assert_eq!(receipt["selectionPublication"], "not-performed");
    assert_eq!(receipt["secretResolution"], "not-performed");
    assert_eq!(
        capture_project(&destination, profile).unwrap().digest,
        record.digest
    );
    for input in &record.inputs {
        let path = destination.join(&input.receipt.path);
        assert_eq!(fs::read(&path).unwrap(), input.content.as_bytes());
        assert_eq!(fs::metadata(path).unwrap().permissions().mode() & 0o177, 0);
    }
}
#[cfg(unix)]
#[test]
fn existing_destinations_and_symlink_parents_are_never_overwritten() {
    let (root, profile) = fixture();
    let record = capture_project(&root, profile).unwrap();
    let existing = root.join("occupied");
    fs::create_dir(&existing).unwrap();
    fs::write(existing.join("sentinel"), "preserve").unwrap();
    assert!(matches!(
        stage_project_capture(&record, &existing),
        Err(Error::Refused {
            code: "PROJECT_STAGE_DESTINATION_UNAVAILABLE",
            ..
        })
    ));
    let file = root.join("occupied-file");
    fs::write(&file, "preserve-file").unwrap();
    assert!(matches!(
        stage_project_capture(&record, &file),
        Err(Error::Refused {
            code: "PROJECT_STAGE_DESTINATION_UNAVAILABLE",
            ..
        })
    ));
    let alias = root.join("alias");
    std::os::unix::fs::symlink(&existing, &alias).unwrap();
    assert!(matches!(
        stage_project_capture(&record, &alias),
        Err(Error::Refused {
            code: "PROJECT_STAGE_DESTINATION_UNAVAILABLE",
            ..
        })
    ));
    assert!(matches!(
        stage_project_capture(&record, &alias.join("candidate")),
        Err(Error::Refused {
            code: "PROJECT_STAGE_PARENT_SYMLINK",
            ..
        })
    ));
    assert!(!existing.join("candidate").exists());
    assert_eq!(fs::read(existing.join("sentinel")).unwrap(), b"preserve");
    assert_eq!(fs::read(file).unwrap(), b"preserve-file");
    assert_eq!(fs::read_dir(&existing).unwrap().count(), 1);
}
#[cfg(unix)]
#[test]
fn invalid_records_and_prefix_collisions_refuse_before_any_destination_creation() {
    let (root, profile) = fixture();
    let mut record = capture_project(&root, profile).unwrap();
    record.inputs[0].content.push('!');
    let destination = root.join("tampered");
    assert!(stage_project_capture(&record, &destination).is_err());
    assert!(!destination.exists());
    record.definition.inputs = vec!["a".into(), "a-b".into(), "a/b".into()];
    record.definition.components[0].root = ".".into();
    record.definition.components[0].entrypoints = vec!["a".into()];
    record.inputs = record
        .definition
        .inputs
        .iter()
        .map(|p| SuppliedInput {
            receipt: InputReceipt {
                path: p.clone(),
                digest: byte_digest(b"data"),
                byte_length: SafeInteger::new(4).unwrap(),
            },
            content: "data".into(),
        })
        .collect();
    record.digest = patamaps_contracts::canonical_digest(
        &json!({"profile":PROJECT_PROFILE,"definition":record.definition,"inputs":record.inputs}),
    )
    .unwrap();
    verify_project_capture(&record).unwrap();
    let destination = root.join("conflicted");
    assert!(matches!(
        stage_project_capture(&record, &destination),
        Err(Error::Refused {
            code: "PROJECT_STAGE_PATH_CONFLICT",
            ..
        })
    ));
    assert!(!destination.exists());
}
