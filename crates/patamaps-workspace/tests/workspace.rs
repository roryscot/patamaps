use patamaps_contracts::{
    GraphDocument, JsonObject, PolicyDocument, ProtocolVersion, canonical_bytes, parse,
};
use patamaps_workspace::*;
use std::{
    fs,
    path::PathBuf,
    sync::atomic::{AtomicU64, Ordering},
};
static SEQUENCE: AtomicU64 = AtomicU64::new(0);
struct Temp(PathBuf);
impl Temp {
    fn new() -> Self {
        let path = std::env::temp_dir().join(format!(
            "patamaps-workspace-test-{}-{}",
            std::process::id(),
            SEQUENCE.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&path).unwrap();
        Self(path)
    }
}
impl Drop for Temp {
    fn drop(&mut self) {
        eprintln!("Retained workspace-test fixture: {}", self.0.display());
    }
}
fn fixture(root: &Temp) -> WorkspaceConfig {
    let mut graph: GraphDocument =
        parse(include_bytes!("../../../fixtures/routing/graph.json")).unwrap();
    graph
        .entities
        .iter_mut()
        .find(|e| e.kind == "routing:handler")
        .unwrap()
        .locators
        .as_mut()
        .unwrap()
        .push(patamaps_contracts::Locator {
            uri: "rust:crate::service::greet".into(),
            media_type: None,
            revision: None,
            digest: None,
        });
    fs::write(root.0.join("graph.json"), canonical_bytes(&graph).unwrap()).unwrap();
    fs::write(
        root.0.join("pack.json"),
        include_bytes!("../../../relation-packs/routing.json"),
    )
    .unwrap();
    fs::write(
        root.0.join("projection.json"),
        include_bytes!("../../../fixtures/routing/projection-spec.json"),
    )
    .unwrap();
    let mut policy: PolicyDocument =
        parse(include_bytes!("../../../fixtures/routing/policy.json")).unwrap();
    policy.graph.id = "urn:patamaps:workspace:test".into();
    policy.graph.revision = Some("1".into());
    policy.graph.digest = None;
    fs::write(
        root.0.join("policy.json"),
        canonical_bytes(&policy).unwrap(),
    )
    .unwrap();
    WorkspaceConfig {
        schema_version: ProtocolVersion::Draft1,
        document_type: WorkspaceType::Record,
        id: policy.graph.id,
        namespace: "workspace-test".into(),
        revision: "1".into(),
        sources: vec![Source::PortableShard {
            id: "urn:patamaps:source:test".into(),
            path: "graph.json".into(),
        }],
        packs: vec!["pack.json".into()],
        policy: "policy.json".into(),
        projections: vec![SelectedProjection {
            path: "projection.json".into(),
            emissions: vec![Emission {
                path: "bindings.rs".into(),
                language: OutputLanguage::Rust,
                binding_slot: Some("handler".into()),
            }],
        }],
        context: JsonObject::from([("environment".into(), serde_json::json!("production"))]),
        evaluated_at: "2026-10-10T12:00:00Z".into(),
    }
}

#[test]
fn current_bytes_cache_equivalence_and_untrusted_cache_refusal() {
    let root = Temp::new();
    let cache = Temp::new();
    let config = fixture(&root);
    let plain = generate(&root.0, &config, None).unwrap();
    assert_eq!(
        plain.baseline.captures[0].result["status"], "viable",
        "{}",
        plain.baseline.captures[0].result
    );
    assert!(plain.baseline.outputs["bindings.rs"].contains("pub fn dispatch"));
    let first = generate(&root.0, &config, Some(&cache.0)).unwrap();
    let second = generate(&root.0, &config, Some(&cache.0)).unwrap();
    assert_eq!(first.cache_misses, 1);
    assert_eq!(second.cache_hits, 1);
    assert_eq!(
        canonical_bytes(&plain.baseline).unwrap(),
        canonical_bytes(&second.baseline).unwrap()
    );
    let path = fs::read_dir(&cache.0)
        .unwrap()
        .next()
        .unwrap()
        .unwrap()
        .path();
    let mut forged: GraphDocument = parse(&fs::read(&path).unwrap()).unwrap();
    forged.entities[0].label = Some("forged".into());
    fs::write(&path, canonical_bytes(&forged).unwrap()).unwrap();
    let rechecked = generate(&root.0, &config, Some(&cache.0)).unwrap();
    assert_eq!(rechecked.cache_hits, 0);
    assert_eq!(plain.baseline.digest, rechecked.baseline.digest);
    assert_eq!(
        check(&root.0, &config, &plain.baseline, None)
            .unwrap()
            .status,
        "unchanged"
    );
}

#[test]
fn drift_check_preserves_baseline_and_captures_actual_changed_source() {
    let root = Temp::new();
    let config = fixture(&root);
    let baseline = generate(&root.0, &config, None).unwrap().baseline;
    let bytes = canonical_bytes(&baseline).unwrap();
    let mut graph: GraphDocument = parse(&fs::read(root.0.join("graph.json")).unwrap()).unwrap();
    graph.entities[0].label = Some("changed independently".into());
    fs::write(root.0.join("graph.json"), canonical_bytes(&graph).unwrap()).unwrap();
    let report = check(&root.0, &config, &baseline, None).unwrap();
    assert_eq!(report.status, "drift");
    assert!(report.changes.contains(&"discovery"));
    assert_eq!(bytes, canonical_bytes(&baseline).unwrap());
    let mut invalid = baseline.clone();
    invalid
        .outputs
        .insert("bindings.rs".into(), "forged".into());
    assert!(check(&root.0, &config, &invalid, None).is_err());
}

#[test]
fn malformed_config_shards_duplicate_outputs_and_rejected_capture_remain_explicit() {
    let root = Temp::new();
    let mut config = fixture(&root);
    let duplicate = config.projections[0].emissions[0].clone();
    config.projections[0].emissions.push(duplicate);
    assert!(generate(&root.0, &config, None).is_err());
    config.projections[0].emissions.pop();
    fs::write(root.0.join("graph.json"), b"{\"id\":1,\"id\":2}").unwrap();
    assert!(generate(&root.0, &config, None).is_err());
    let config = fixture(&root);
    let mut graph: GraphDocument = parse(&fs::read(root.0.join("graph.json")).unwrap()).unwrap();
    graph.mappings[0].targets = vec!["urn:missing:handler".into()];
    fs::write(root.0.join("graph.json"), canonical_bytes(&graph).unwrap()).unwrap();
    let rejected = generate(&root.0, &config, None).unwrap();
    assert_eq!(rejected.baseline.captures[0].result["status"], "rejected");
    assert!(rejected.baseline.outputs.is_empty());
}

#[cfg(unix)]
#[test]
fn source_symlink_escape_and_absolute_locator_paths_refuse() {
    use std::os::unix::fs::symlink;
    let root = Temp::new();
    let outside = Temp::new();
    let mut config = fixture(&root);
    fs::write(
        outside.0.join("outside.json"),
        include_bytes!("../../../fixtures/routing/graph.json"),
    )
    .unwrap();
    symlink(outside.0.join("outside.json"), root.0.join("escape.json")).unwrap();
    config.sources = vec![Source::PortableShard {
        id: "urn:patamaps:source:test".into(),
        path: "escape.json".into(),
    }];
    assert!(
        generate(&root.0, &config, None)
            .unwrap_err()
            .to_string()
            .contains("SOURCE_ESCAPE")
    );
    for path in ["../outside.json", "/outside.json", "a//b", "a\\b", "a/./b"] {
        assert!(!relative_path(path));
    }
}

#[cfg(unix)]
#[test]
fn large_provider_code_inventory_is_captured_and_bounded() {
    use patamaps_contracts::{MAX_INPUT_BYTES, SafeInteger, canonical_digest};

    let root = Temp::new();
    let mut config = fixture(&root);
    let raw = fs::read(root.0.join("graph.json")).unwrap();
    let response = AdapterResponse {
        schema_version: ProtocolVersion::Draft1,
        document_type: ResponseType::Record,
        profile: PROFILE.into(),
        source_id: config.sources[0].id().into(),
        adapter_version: "inventory-fixture-1".into(),
        request_digest: "sha256:REPLACE_REQUEST".into(),
        inputs: vec![InputReceipt {
            path: "graph.json".into(),
            digest: patamaps_contracts::byte_digest(&raw),
            byte_length: SafeInteger::new(raw.len() as u64).unwrap(),
        }],
        shard: parse(&raw).unwrap(),
        diagnostics: Vec::new(),
    };
    fs::write(
        root.0.join("response.json"),
        canonical_bytes(&response).unwrap(),
    )
    .unwrap();
    let mut code_inputs = vec!["response.json".into()];
    for index in 0..511 {
        let name = format!("dependency-{index}.txt");
        fs::write(root.0.join(&name), format!("dependency {index}\n")).unwrap();
        code_inputs.push(name);
    }
    config.sources = vec![Source::Process {
        id: response.source_id,
        invocation: Invocation {
            executable: "/bin/sh".into(),
            arguments: vec![
                "-c".into(),
                "request=$(/bin/cat); digest=$(printf '%s' \"$request\" | /usr/bin/sed -n 's/.*\"requestDigest\":\"\\([^\"]*\\)\".*/\\1/p'); /usr/bin/sed \"s/sha256:REPLACE_REQUEST/$digest/\" response.json".into(),
            ],
            code_inputs,
            bounds: ProcessBounds {
                maximum_elapsed_ms: SafeInteger::new(1000).unwrap(),
                maximum_stdout_bytes: SafeInteger::new(65536).unwrap(),
                maximum_stderr_bytes: SafeInteger::new(4096).unwrap(),
            },
        },
        inputs: vec!["graph.json".into()],
        config: Default::default(),
    }];
    let first = generate(&root.0, &config, None).unwrap();
    assert_eq!(first.baseline.captures[0].result["status"], "viable");
    assert_eq!(first.baseline.captures[0].sources.len(), 516);
    let first_digest = canonical_digest(&first.baseline).unwrap();
    fs::write(root.0.join("dependency-510.txt"), b"changed dependency\n").unwrap();
    let changed = generate(&root.0, &config, None).unwrap();
    assert_ne!(first_digest, canonical_digest(&changed.baseline).unwrap());
    assert!(
        check(&root.0, &config, &first.baseline, None)
            .unwrap()
            .changes
            .contains(&"discovery")
    );

    let Source::Process { invocation, .. } = &mut config.sources[0] else {
        unreachable!()
    };
    invocation.code_inputs.push("over-limit.txt".into());
    assert!(
        generate(&root.0, &config, None)
            .unwrap_err()
            .to_string()
            .contains("ADAPTER_INPUT_LIMIT")
    );
    let Source::Process { invocation, .. } = &mut config.sources[0] else {
        unreachable!()
    };
    invocation.code_inputs.pop();
    fs::write(root.0.join("dependency-0.txt"), vec![b'x'; MAX_INPUT_BYTES]).unwrap();
    assert!(
        generate(&root.0, &config, None)
            .unwrap_err()
            .to_string()
            .contains("WORKSPACE_SOURCE_LIMIT")
    );
}
