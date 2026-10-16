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

fn readdress(baseline: &mut WorkspaceBaseline) {
    let mut value = serde_json::to_value(&*baseline).unwrap();
    value.as_object_mut().unwrap().remove("digest");
    baseline.digest = patamaps_contracts::canonical_digest(&value).unwrap();
}
fn recapture(baseline: &mut WorkspaceBaseline) {
    for record in &mut baseline.captures {
        *record =
            patamaps_projection::capture(record.inputs.clone(), record.sources.clone()).unwrap();
    }
    readdress(baseline);
}
fn refusal(baseline: &WorkspaceBaseline, code: &str) {
    match verify_baseline(baseline).unwrap_err() {
        Error::Refused { code: actual, .. } => assert_eq!(actual, code),
        error => panic!("Unexpected refusal: {error}"),
    }
}

#[test]
fn offline_lineage_reconstructs_without_live_source_files() {
    let root = Temp::new();
    let config = fixture(&root);
    let baseline = generate(&root.0, &config, None).unwrap().baseline;
    let saved = canonical_bytes(&baseline).unwrap();
    let original = fs::read(root.0.join("graph.json")).unwrap();
    fs::rename(
        root.0.join("graph.json"),
        root.0.join("graph.retained.json"),
    )
    .unwrap();
    let checked = verify_baseline(&baseline).unwrap();
    assert_eq!(checked.record().digest, baseline.digest);
    assert_eq!(canonical_bytes(&baseline).unwrap(), saved);
    assert_eq!(
        fs::read(root.0.join("graph.retained.json")).unwrap(),
        original
    );
    assert!(generate(&root.0, &config, None).is_err());
}

#[test]
fn rehashed_discovery_inventory_cannot_replace_recorded_composition() {
    let root = Temp::new();
    let mut config = fixture(&root);
    let mut empty: GraphDocument = parse(&fs::read(root.0.join("graph.json")).unwrap()).unwrap();
    empty.id = "urn:patamaps:shard:second".into();
    empty.entities.clear();
    empty.mappings.clear();
    empty.authorities.clear();
    fs::write(root.0.join("second.json"), canonical_bytes(&empty).unwrap()).unwrap();
    config.sources.push(Source::PortableShard {
        id: "urn:patamaps:source:second".into(),
        path: "second.json".into(),
    });
    let baseline = generate(&root.0, &config, None).unwrap().baseline;
    verify_baseline(&baseline).unwrap();
    for change in 0..4 {
        let mut forged = baseline.clone();
        match change {
            0 => forged.discovery[0].source_id = "urn:patamaps:forged-source".into(),
            1 => forged.discovery.reverse(),
            2 => {
                forged.discovery.pop();
            }
            _ => forged.discovery.push(forged.discovery[0].clone()),
        }
        readdress(&mut forged);
        refusal(&forged, "WORKSPACE_SOURCE_INVENTORY");
    }
    // Inconsistent historical lineage refuses before any current root access.
    let mut forged = baseline.clone();
    forged.discovery[0].source_id = "urn:patamaps:forged-source".into();
    readdress(&mut forged);
    assert!(matches!(
        check(&root.0.join("never-created"), &config, &forged, None),
        Err(Error::Refused {
            code: "WORKSPACE_SOURCE_INVENTORY",
            ..
        })
    ));
}

#[test]
fn individually_verified_capture_and_rehashed_output_substitutions_refuse() {
    let root = Temp::new();
    let config = fixture(&root);
    let baseline = generate(&root.0, &config, None).unwrap().baseline;
    let mut forged = baseline.clone();
    forged.captures[0].inputs.graph.entities[0].label = Some("different candidate".into());
    recapture(&mut forged);
    patamaps_projection::replay(&forged.captures[0]).unwrap();
    refusal(&forged, "WORKSPACE_COMPOSITION_BINDING");
    let mut forged = baseline.clone();
    forged
        .outputs
        .insert("bindings.rs".into(), "// substituted output".into());
    readdress(&mut forged);
    refusal(&forged, "WORKSPACE_COMPOSITION_BINDING");
    let mut forged = baseline.clone();
    forged.captures[0].inputs.evaluated_at = "2026-10-10T12:00:01Z".into();
    recapture(&mut forged);
    patamaps_projection::replay(&forged.captures[0]).unwrap();
    refusal(&forged, "WORKSPACE_COMPOSITION_BINDING");
}

#[test]
fn raw_receipts_and_configured_requests_cannot_be_swapped_after_rehashing() {
    let root = Temp::new();
    let config = fixture(&root);
    let baseline = generate(&root.0, &config, None).unwrap().baseline;
    let mut forged = baseline.clone();
    forged.config.sources[0] = Source::PortableShard {
        id: config.sources[0].id().into(),
        path: "different.json".into(),
    };
    forged.config_digest = patamaps_contracts::canonical_digest(&forged.config).unwrap();
    readdress(&mut forged);
    refusal(&forged, "WORKSPACE_SOURCE_INVENTORY");
    let mut forged = baseline.clone();
    forged.discovery[0].request_digest = format!("sha256:{}", "0".repeat(64));
    readdress(&mut forged);
    refusal(&forged, "WORKSPACE_DISCOVERY_BINDING");
    let mut forged = baseline.clone();
    for record in &mut forged.captures {
        let raw = record
            .sources
            .iter_mut()
            .find(|s| s.id.ends_with(":graph.json"))
            .unwrap();
        let content = raw.content.as_mut().unwrap();
        content.push(' ');
        raw.digest = patamaps_contracts::byte_digest(content.as_bytes());
        raw.byte_length = patamaps_contracts::SafeInteger::new(content.len() as u64).unwrap();
    }
    recapture(&mut forged);
    // Parsed source values are identical, but exact raw request bytes changed.
    refusal(&forged, "WORKSPACE_DISCOVERY_BINDING");
    let mut forged = baseline.clone();
    for record in &mut forged.captures {
        let raw = record
            .sources
            .iter_mut()
            .find(|s| s.id.ends_with(":pack.json"))
            .unwrap();
        let mut pack: serde_json::Value =
            serde_json::from_str(raw.content.as_ref().unwrap()).unwrap();
        pack["description"] = serde_json::json!("changed declared pack");
        let content = serde_json::to_string(&pack).unwrap();
        raw.digest = patamaps_contracts::byte_digest(content.as_bytes());
        raw.byte_length = patamaps_contracts::SafeInteger::new(content.len() as u64).unwrap();
        raw.content = Some(content);
    }
    recapture(&mut forged);
    refusal(&forged, "WORKSPACE_COMPOSITION_BINDING");
    let mut forged = baseline.clone();
    for record in &mut forged.captures {
        record
            .sources
            .iter_mut()
            .find(|s| s.id.ends_with(":graph.json"))
            .unwrap()
            .content = None;
    }
    recapture(&mut forged);
    assert_eq!(
        patamaps_projection::replay(&forged.captures[0])
            .unwrap()
            .missing_sources()
            .len(),
        1
    );
    refusal(&forged, "WORKSPACE_SOURCE_UNAVAILABLE");
    let mut forged = baseline.clone();
    for record in &mut forged.captures {
        let mut extra = record.sources[0].clone();
        extra.id = "urn:patamaps:unconfigured-input".into();
        record.sources.push(extra);
    }
    recapture(&mut forged);
    refusal(&forged, "WORKSPACE_COMPOSITION_BINDING");
}

#[test]
fn offline_lineage_preserves_rejected_evaluation_without_creating_outputs() {
    let root = Temp::new();
    let config = fixture(&root);
    let mut graph: GraphDocument = parse(&fs::read(root.0.join("graph.json")).unwrap()).unwrap();
    graph.mappings[0].targets = vec!["urn:missing:handler".into()];
    fs::write(root.0.join("graph.json"), canonical_bytes(&graph).unwrap()).unwrap();
    let baseline = generate(&root.0, &config, None).unwrap().baseline;
    let checked = verify_baseline(&baseline).unwrap();
    assert_eq!(checked.record().captures[0].result["status"], "rejected");
    assert!(checked.record().outputs.is_empty());
}

#[cfg(unix)]
#[test]
fn offline_process_records_bind_code_and_requests_without_executing_the_provider() {
    let root = Temp::new();
    let mut config = fixture(&root);
    let raw = fs::read(root.0.join("graph.json")).unwrap();
    let response = AdapterResponse {
        schema_version: ProtocolVersion::Draft1,
        document_type: ResponseType::Record,
        profile: PROFILE.into(),
        source_id: config.sources[0].id().into(),
        adapter_version: "offline-process-control-1".into(),
        request_digest: "sha256:REPLACE_REQUEST".into(),
        inputs: vec![InputReceipt {
            path: "graph.json".into(),
            digest: patamaps_contracts::byte_digest(&raw),
            byte_length: patamaps_contracts::SafeInteger::new(raw.len() as u64).unwrap(),
        }],
        shard: parse(&raw).unwrap(),
        diagnostics: Vec::new(),
    };
    fs::write(
        root.0.join("response.json"),
        canonical_bytes(&response).unwrap(),
    )
    .unwrap();
    fs::write(root.0.join("provider.sh"), "printf 'ran\\n' >> provider-runs; request=$(/bin/cat); digest=$(printf '%s' \"$request\" | /usr/bin/sed -n 's/.*\"requestDigest\":\"\\([^\"]*\\)\".*/\\1/p'); /usr/bin/sed \"s/sha256:REPLACE_REQUEST/$digest/\" response.json\n").unwrap();
    config.sources = vec![Source::Process {
        id: response.source_id,
        invocation: Invocation {
            executable: "/bin/sh".into(),
            arguments: vec!["provider.sh".into()],
            code_inputs: vec!["provider.sh".into(), "response.json".into()],
            bounds: ProcessBounds {
                maximum_elapsed_ms: patamaps_contracts::SafeInteger::new(1000).unwrap(),
                maximum_stdout_bytes: patamaps_contracts::SafeInteger::new(65536).unwrap(),
                maximum_stderr_bytes: patamaps_contracts::SafeInteger::new(4096).unwrap(),
            },
        },
        inputs: vec!["graph.json".into()],
        config: Default::default(),
    }];
    let baseline = generate(&root.0, &config, None).unwrap().baseline;
    assert!(baseline.discovery[0].executable_digest.is_some());
    let ran = fs::read(root.0.join("provider-runs")).unwrap();
    assert_eq!(ran, b"ran\n");
    fs::rename(
        root.0.join("provider.sh"),
        root.0.join("provider.retained.sh"),
    )
    .unwrap();
    fs::rename(
        root.0.join("graph.json"),
        root.0.join("graph.retained.json"),
    )
    .unwrap();
    verify_baseline(&baseline).unwrap();
    assert_eq!(fs::read(root.0.join("provider-runs")).unwrap(), ran);
    for change in 0..3 {
        let mut forged = baseline.clone();
        match change {
            0 => forged.discovery[0].executable_digest = Some(format!("sha256:{}", "0".repeat(64))),
            1 => {
                if let Source::Process { invocation, .. } = &mut forged.config.sources[0] {
                    invocation.arguments = vec!["different.sh".into()];
                }
            }
            _ => forged.discovery[0].request_digest = format!("sha256:{}", "0".repeat(64)),
        }
        forged.config_digest = patamaps_contracts::canonical_digest(&forged.config).unwrap();
        readdress(&mut forged);
        refusal(&forged, "WORKSPACE_DISCOVERY_BINDING");
    }
    assert_eq!(fs::read(root.0.join("provider-runs")).unwrap(), ran);
    for change in 0..2 {
        let mut forged = baseline.clone();
        match change {
            0 => forged.discovery[0].adapter_version = "different-provider-version".into(),
            _ => {
                forged.discovery[0].shard.revision = Some("different-source-revision".into());
                forged.discovery[0].shard_digest =
                    patamaps_contracts::canonical_digest(&forged.discovery[0].shard).unwrap();
            }
        }
        readdress(&mut forged);
        refusal(&forged, "WORKSPACE_COMPOSITION_BINDING");
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

#[cfg(unix)]
#[test]
fn failed_process_names_its_source_and_captured_inputs_without_pipe_payloads() {
    let root = Temp::new();
    let mut config = fixture(&root);
    config.sources = vec![
        serde_json::from_value(serde_json::json!({
            "adapter": "process",
            "id": "urn:patamaps:source:failing-provider",
            "invocation": {
                "executable": "/usr/bin/false",
                "arguments": [],
                "codeInputs": [],
                "bounds": {
                    "maximumElapsedMs": 1000,
                    "maximumStdoutBytes": 1024,
                    "maximumStderrBytes": 1024
                }
            },
            "inputs": ["graph.json"],
            "config": {}
        }))
        .unwrap(),
    ];
    match generate(&root.0, &config, None).unwrap_err() {
        Error::Refused { code, message } => {
            assert_eq!(code, "ADAPTER_EXIT");
            assert!(message.contains("urn:patamaps:source:failing-provider"));
            assert!(message.contains("graph.json"));
        }
        error => panic!("Unexpected provider refusal: {error}"),
    }
}

#[test]
#[cfg(unix)]
fn workspace_output_staging_is_offline_and_never_overwrites() {
    use std::os::unix::fs::PermissionsExt;
    let root = Temp::new();
    let config = fixture(&root);
    let baseline = generate(&root.0, &config, None).unwrap().baseline;
    for name in ["graph.json", "pack.json", "policy.json", "projection.json"] {
        fs::rename(root.0.join(name), root.0.join(format!("retained-{name}"))).unwrap();
    }
    let destination = root.0.join("outputs");
    let report = stage_workspace_outputs(&baseline, &destination).unwrap();
    assert_eq!(report["status"], "staged-workspace-outputs");
    assert_eq!(report["baselineDigest"], baseline.digest);
    let file = destination.join("bindings.rs");
    assert_eq!(
        fs::read_to_string(&file).unwrap(),
        baseline.outputs["bindings.rs"]
    );
    assert_eq!(
        fs::metadata(&file).unwrap().permissions().mode() & 0o777,
        0o600
    );
    assert_eq!(
        fs::metadata(&destination).unwrap().permissions().mode() & 0o777,
        0o700
    );
    assert!(stage_workspace_outputs(&baseline, &destination).is_err());
    assert_eq!(
        fs::read_to_string(&file).unwrap(),
        baseline.outputs["bindings.rs"]
    );
    let alias = root.0.join("alias");
    std::os::unix::fs::symlink(&destination, &alias).unwrap();
    assert!(stage_workspace_outputs(&baseline, &alias).is_err());
    assert_eq!(
        fs::read_to_string(&file).unwrap(),
        baseline.outputs["bindings.rs"]
    );
}

#[test]
fn workspace_output_staging_refuses_tampering_and_prefix_conflicts_before_creation() {
    let root = Temp::new();
    let mut config = fixture(&root);
    let baseline = generate(&root.0, &config, None).unwrap().baseline;
    let mut forged = baseline.clone();
    forged
        .outputs
        .insert("bindings.rs".into(), "// altered".into());
    readdress(&mut forged);
    let destination = root.0.join("tampered");
    assert!(matches!(
        stage_workspace_outputs(&forged, &destination),
        Err(Error::Refused {
            code: "WORKSPACE_COMPOSITION_BINDING",
            ..
        })
    ));
    assert!(!destination.exists());
    config.projections[0].emissions[0].path = "out".into();
    let mut nested = config.projections[0].emissions[0].clone();
    nested.path = "out/nested.rs".into();
    config.projections[0].emissions.push(nested);
    let conflict = generate(&root.0, &config, None).unwrap().baseline;
    let destination = root.0.join("conflict");
    assert!(matches!(
        stage_workspace_outputs(&conflict, &destination),
        Err(Error::Refused {
            code: "PROJECT_STAGE_PATH_CONFLICT",
            ..
        })
    ));
    assert!(!destination.exists());
}
