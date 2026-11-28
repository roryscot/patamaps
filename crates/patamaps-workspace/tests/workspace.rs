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

#[cfg(unix)]
fn build_fixture() -> (Temp, Temp, ProjectBuildPlan) {
    use patamaps_contracts::SafeInteger;
    let root = Temp::new();
    let source = Temp(root.0.join("owner"));
    fs::create_dir(&source.0).unwrap();
    let workspace = fixture(&source);
    fs::write(source.0.join("input.txt"), "selected original\n").unwrap();
    let project: ProjectProfile = serde_json::from_value(serde_json::json!({
        "profile":"patamaps-project-inputs-1","id":"urn:test:retained-build","nonsecretInputs":true,
        "inputs":["graph.json","pack.json","policy.json","projection.json","input.txt"],
        "components":[{"id":"sources","kind":"contracts","root":".","entrypoints":["graph.json"]}],
        "nonsecretConfiguration":{},"secretReferences":{}
    }))
    .unwrap();
    let command = |body: &str| ProjectCommand {
        profile: PROJECT_COMMAND_PROFILE.into(),
        working_directory: ".".into(),
        environment_references: Default::default(),
        invocation: Invocation {
            executable: "/bin/sh".into(),
            arguments: vec!["-c".into(), body.into()],
            code_inputs: vec![],
            bounds: ProcessBounds {
                maximum_elapsed_ms: SafeInteger::new(5000).unwrap(),
                maximum_stdout_bytes: SafeInteger::new(65536).unwrap(),
                maximum_stderr_bytes: SafeInteger::new(4096).unwrap(),
            },
        },
    };
    let plan = ProjectBuildPlan {
        maximum_retained_attempts: SafeInteger::new(8).unwrap(),
        profile: PROJECT_BUILD_PROFILE.into(),
        project,
        workspace,
        build_steps: vec![command(
            "/bin/mkdir -p bundle/nested; printf artifact > bundle/nested/app; printf executed > execution-marker",
        )],
        verification_steps: vec![command("test \"$(/bin/cat bundle/nested/app)\" = artifact")],
        outputs: vec![ArtifactSelection {
            path: "bundle".into(),
            kind: ArtifactKind::Tree,
        }],
    };
    (root, source, plan)
}

#[test]
#[cfg(unix)]
fn retained_build_selects_coherent_artifacts_and_reports_noop_without_reexecution() {
    let (root, source, plan) = build_fixture();
    let state = root.0.join("state");
    let selected = build_project(&source.0, &state, &plan, false).unwrap();
    assert_eq!(selected["status"], "selected-project-build");
    let pointer = fs::read(state.join("selected.json")).unwrap();
    let candidate = state
        .join(selected["attempt"].as_str().unwrap())
        .join("candidate");
    assert_eq!(
        fs::read_to_string(candidate.join("bundle/nested/app")).unwrap(),
        "artifact"
    );
    assert!(candidate.join("bindings.rs").is_file());
    assert!(!source.0.join("bindings.rs").exists());
    assert_eq!(
        verify_project_build_selection(&state).unwrap()["status"],
        "verified-selected-build-bindings"
    );
    let noop = build_project(&source.0, &state, &plan, false).unwrap();
    assert_eq!(noop["status"], "unchanged-project-build");
    assert_eq!(noop["verification"], "not-repeated");
    assert_eq!(noop["cacheHits"], 0);
    assert_eq!(fs::read(state.join("selected.json")).unwrap(), pointer);
    assert_eq!(fs::read_dir(state.join("attempts")).unwrap().count(), 1);
}

#[test]
#[cfg(unix)]
fn failed_mutating_and_raced_builds_preserve_the_previous_selection() {
    let (root, source, plan) = build_fixture();
    let state = root.0.join("state");
    assert_eq!(
        build_project(&source.0, &state, &plan, false).unwrap()["status"],
        "selected-project-build"
    );
    let previous = fs::read(state.join("selected.json")).unwrap();
    let mut failing = plan.clone();
    failing.build_steps[0].invocation.arguments =
        vec!["-c".into(), "printf failed >&2; exit 9".into()];
    let failure = build_project(&source.0, &state, &failing, false).unwrap();
    assert_eq!(failure["status"], "refused-project-build");
    assert_eq!(failure["previousSelectionPreserved"], true);
    assert_eq!(fs::read(state.join("selected.json")).unwrap(), previous);
    let mut changing = plan.clone();
    changing.verification_steps[0].invocation.arguments =
        vec!["-c".into(), "printf altered > bundle/nested/app".into()];
    let result = build_project(&source.0, &state, &changing, false).unwrap();
    assert_eq!(result["status"], "refused-project-build");
    assert_eq!(result["previousSelectionPreserved"], true);
    assert!(
        result["reason"]
            .as_str()
            .unwrap()
            .contains("PROJECT_BUILD_ARTIFACT_CHANGED")
    );
    assert_eq!(fs::read(state.join("selected.json")).unwrap(), previous);
    let mut raced = plan.clone();
    raced.build_steps[0].invocation.arguments = vec![
        "-c".into(),
        "/bin/mkdir -p bundle/nested; printf artifact > bundle/nested/app; printf changed > \"$1\""
            .into(),
        "source-race".into(),
        source.0.join("input.txt").to_str().unwrap().into(),
    ];
    let result = build_project(&source.0, &state, &raced, false).unwrap();
    assert_eq!(result["status"], "refused-project-build");
    assert_eq!(result["previousSelectionPreserved"], true);
    assert!(
        result["reason"]
            .as_str()
            .unwrap()
            .contains("PROJECT_BUILD_SOURCE_OR_TOOL_CHANGED")
    );
    assert_eq!(fs::read(state.join("selected.json")).unwrap(), previous);
    verify_project_build_selection(&state).unwrap();
}

#[test]
#[cfg(unix)]
fn retained_build_refuses_unsafe_state_before_creating_it() {
    let (root, source, plan) = build_fixture();
    let inside = source.0.join("state");
    assert!(matches!(
        build_project(&source.0, &inside, &plan, false),
        Err(Error::Refused {
            code: "PROJECT_BUILD_STATE_ISOLATION",
            ..
        })
    ));
    assert!(!inside.exists());
    let cargo = root.0.join("cargo-parent");
    fs::create_dir(&cargo).unwrap();
    fs::write(cargo.join("Cargo.toml"), "[workspace]\n").unwrap();
    let nested = cargo.join("state");
    assert!(matches!(
        build_project(&source.0, &nested, &plan, false),
        Err(Error::Refused {
            code: "PROJECT_BUILD_STATE_ISOLATION",
            ..
        })
    ));
    assert!(!nested.exists());
}

#[test]
#[cfg(unix)]
fn selected_artifact_tampering_refuses_noop_and_force_retains_history() {
    let (root, source, plan) = build_fixture();
    let state = root.0.join("state");
    let first = build_project(&source.0, &state, &plan, false).unwrap();
    let previous = fs::read(state.join("selected.json")).unwrap();
    let old = state
        .join(first["attempt"].as_str().unwrap())
        .join("candidate/bundle/nested/app");
    fs::write(&old, "poisoned").unwrap();
    assert!(verify_project_build_selection(&state).is_err());
    assert!(build_project(&source.0, &state, &plan, false).is_err());
    assert_eq!(fs::read(state.join("selected.json")).unwrap(), previous);
    let forced = build_project(&source.0, &state, &plan, true).unwrap();
    assert_eq!(forced["status"], "selected-project-build");
    let history = state
        .join(forced["attempt"].as_str().unwrap())
        .join("previous-selection.json");
    assert_eq!(fs::read(history).unwrap(), previous);
    assert_eq!(fs::read_to_string(old).unwrap(), "poisoned");
    verify_project_build_selection(&state).unwrap();
}

#[test]
#[cfg(unix)]
fn retained_build_bindings_replay_without_original_source_or_tool_path() {
    use std::os::unix::fs::PermissionsExt;
    let (root, source, mut plan) = build_fixture();
    let state = root.0.join("state");
    let tools = root.0.join("tools");
    fs::create_dir(&tools).unwrap();
    let executable = tools.join("build.sh");
    fs::write(
        &executable,
        "#!/bin/sh\n/bin/mkdir -p bundle/nested\nprintf artifact > bundle/nested/app\n",
    )
    .unwrap();
    fs::set_permissions(&executable, fs::Permissions::from_mode(0o700)).unwrap();
    plan.build_steps[0].invocation.executable = executable.to_str().unwrap().into();
    plan.build_steps[0].invocation.arguments.clear();
    assert_eq!(
        build_project(&source.0, &state, &plan, false).unwrap()["status"],
        "selected-project-build"
    );
    fs::rename(&source.0, root.0.join("owner.retained")).unwrap();
    fs::rename(&tools, root.0.join("tools.retained")).unwrap();
    assert_eq!(
        verify_project_build_selection(&state).unwrap()["status"],
        "verified-selected-build-bindings"
    );
}

#[test]
#[cfg(unix)]
fn rehashed_contradictory_command_evidence_cannot_validate_a_selection() {
    use patamaps_contracts::{byte_digest, canonical_digest};
    let (root, source, plan) = build_fixture();
    let state = root.0.join("state");
    let selected = build_project(&source.0, &state, &plan, false).unwrap();
    let attempt = state.join(selected["attempt"].as_str().unwrap());
    let pointer_path = state.join("selected.json");
    let mut pointer: serde_json::Value =
        serde_json::from_slice(&fs::read(&pointer_path).unwrap()).unwrap();
    let receipt_path = attempt.join("receipt.json");
    let mut receipt: serde_json::Value =
        serde_json::from_slice(&fs::read(&receipt_path).unwrap()).unwrap();
    let command_path = attempt.join("verify-001.json");
    fs::copy(
        &command_path,
        attempt.join("verify-001.valid-before-mutation.json"),
    )
    .unwrap();
    fs::copy(
        &receipt_path,
        attempt.join("receipt.valid-before-mutation.json"),
    )
    .unwrap();
    fs::copy(
        &pointer_path,
        state.join("selected.valid-before-mutation.json"),
    )
    .unwrap();
    let mut command: serde_json::Value =
        serde_json::from_slice(&fs::read(&command_path).unwrap()).unwrap();
    command["programSucceeded"] = serde_json::json!(false);
    let bytes = canonical_bytes(&command).unwrap();
    fs::write(&command_path, &bytes).unwrap();
    receipt["commands"][1]["digest"] = serde_json::json!(byte_digest(&bytes));
    let bytes = canonical_bytes(&receipt).unwrap();
    fs::write(&receipt_path, &bytes).unwrap();
    pointer["receiptDigest"] = serde_json::json!(byte_digest(&bytes));
    pointer.as_object_mut().unwrap().remove("digest");
    let digest = canonical_digest(&pointer).unwrap();
    pointer["digest"] = serde_json::json!(digest);
    fs::write(&pointer_path, canonical_bytes(&pointer).unwrap()).unwrap();
    assert!(matches!(
        verify_project_build_selection(&state),
        Err(Error::Refused {
            code: "PROJECT_BUILD_SELECTION_BINDING",
            ..
        })
    ));
}

#[test]
#[cfg(unix)]
fn changing_an_earlier_tool_during_verification_preserves_selection() {
    use std::os::unix::fs::PermissionsExt;
    let (root, source, plan) = build_fixture();
    let state = root.0.join("state");
    assert_eq!(
        build_project(&source.0, &state, &plan, false).unwrap()["status"],
        "selected-project-build"
    );
    let previous = fs::read(state.join("selected.json")).unwrap();
    let executable = root.0.join("builder.sh");
    fs::write(
        &executable,
        "#!/bin/sh\n/bin/mkdir -p bundle/nested\nprintf artifact > bundle/nested/app\n",
    )
    .unwrap();
    fs::set_permissions(&executable, fs::Permissions::from_mode(0o700)).unwrap();
    fs::copy(&executable, root.0.join("builder.valid-before-mutation.sh")).unwrap();
    let mut changed = plan.clone();
    changed.build_steps[0].invocation.executable = executable.to_str().unwrap().into();
    changed.build_steps[0].invocation.arguments.clear();
    changed.verification_steps[0].invocation.arguments = vec![
        "-c".into(),
        "printf '# changed\\n' >> \"$1\"".into(),
        "tool-change".into(),
        executable.to_str().unwrap().into(),
    ];
    let result = build_project(&source.0, &state, &changed, false).unwrap();
    assert_eq!(result["status"], "refused-project-build");
    assert_eq!(result["previousSelectionPreserved"], true);
    assert!(
        result["reason"]
            .as_str()
            .unwrap()
            .contains("PROJECT_BUILD_SOURCE_OR_TOOL_CHANGED")
    );
    assert_eq!(fs::read(state.join("selected.json")).unwrap(), previous);
    verify_project_build_selection(&state).unwrap();
}

#[test]
#[cfg(unix)]
fn build_input_observation_is_readonly_and_matches_selection() {
    let (root, source, mut plan) = build_fixture();
    let state = root.0.join("state");
    let before = capture_project(&source.0, plan.project.clone()).unwrap();
    let observed = project_build_input_key(&source.0, &plan).unwrap();
    assert_eq!(observed["commandsExecuted"], false);
    assert!(!state.exists());
    assert!(!source.0.join("execution-marker").exists());
    assert_eq!(
        capture_project(&source.0, plan.project.clone())
            .unwrap()
            .digest,
        before.digest
    );
    let selected = build_project(&source.0, &state, &plan, false).unwrap();
    assert_eq!(selected["inputKey"], observed["inputKey"]);
    fs::write(source.0.join("not-selected.txt"), "ignored").unwrap();
    assert_eq!(
        project_build_input_key(&source.0, &plan).unwrap()["inputKey"],
        observed["inputKey"]
    );
    fs::write(source.0.join("input.txt"), "changed").unwrap();
    assert_ne!(
        project_build_input_key(&source.0, &plan).unwrap()["inputKey"],
        observed["inputKey"]
    );
    fs::write(source.0.join("input.txt"), "selected original\n").unwrap();
    plan.verification_steps[0]
        .invocation
        .arguments
        .push("plan-change".into());
    assert_ne!(
        project_build_input_key(&source.0, &plan).unwrap()["inputKey"],
        observed["inputKey"]
    );
    plan.build_steps[0].invocation.executable =
        root.0.join("unavailable-tool").to_str().unwrap().into();
    assert!(project_build_input_key(&source.0, &plan).is_err());
}

#[cfg(unix)]
fn context_build_fixture() -> (Temp, Temp, ProjectBuildPlan, ProjectBuildContext) {
    use std::os::unix::fs::{PermissionsExt, symlink};
    let (root, source, mut plan) = build_fixture();
    let owner = root.0.join("context-owner");
    fs::create_dir_all(owner.join("node_modules/pkg")).unwrap();
    fs::create_dir(owner.join("empty")).unwrap();
    fs::write(owner.join("node_modules/pkg/tool.bin"), [0, 255, 128, 0, 1]).unwrap();
    fs::set_permissions(
        owner.join("node_modules/pkg/tool.bin"),
        fs::Permissions::from_mode(0o751),
    )
    .unwrap();
    fs::write(
        owner.join("input.txt"),
        "old context
",
    )
    .unwrap();
    symlink("node_modules/pkg/tool.bin", owner.join("dep-link")).unwrap();
    let definition:ProjectContextDefinition=serde_json::from_value(serde_json::json!({
        "profile":CONTEXT_PROFILE,"id":"urn:test:native-build-context","nonsecretInputs":true,
        "paths":["node_modules/pkg/tool.bin","dep-link","empty","input.txt"],"symlinks":"internal-closed"
    })).unwrap();
    let snapshot = root.0.join("snapshot");
    let captured = capture_project_context(&owner, &snapshot, &definition).unwrap();
    let binding = ProjectBuildContext {
        profile: "patamaps-project-build-context-1".into(),
        snapshot: snapshot.to_str().unwrap().into(),
        digest: captured["digest"].as_str().unwrap().into(),
        overlays: std::collections::BTreeMap::from([(
            "input.txt".into(),
            patamaps_contracts::byte_digest(
                b"old context
",
            ),
        )]),
        writable_paths: vec!["bundle".into(), "execution-marker".into()],
    };
    plan.build_steps[0].invocation.arguments[1]
        .push_str("; /bin/cp dep-link bundle/nested/dependency");
    (root, source, plan, binding)
}

#[cfg(unix)]
#[test]
fn contextual_build_materializes_binary_inputs_overlays_and_replays_without_snapshot_or_source() {
    use std::os::unix::fs::PermissionsExt;
    let (root, source, plan, binding) = context_build_fixture();
    let state = root.0.join("state");
    let observed = project_build_input_key_with_context(&source.0, &plan, Some(&binding)).unwrap();
    assert_eq!(
        observed["contextReference"]["bytesVerification"],
        "not-performed"
    );
    assert_ne!(
        observed["inputKey"],
        project_build_input_key(&source.0, &plan).unwrap()["inputKey"]
    );
    let selected =
        build_project_with_context(&source.0, &state, &plan, Some(&binding), false).unwrap();
    assert_eq!(selected["status"], "selected-project-build", "{selected}");
    assert_eq!(selected["inputKey"], observed["inputKey"]);
    let pointer = fs::read(state.join("selected.json")).unwrap();
    let candidate = state
        .join(selected["attempt"].as_str().unwrap())
        .join("candidate");
    assert_eq!(
        fs::read(candidate.join("bundle/nested/dependency")).unwrap(),
        [0, 255, 128, 0, 1]
    );
    assert_eq!(
        fs::metadata(candidate.join("node_modules/pkg/tool.bin"))
            .unwrap()
            .permissions()
            .mode()
            & 0o777,
        0o751
    );
    assert_eq!(
        fs::read_link(candidate.join("dep-link")).unwrap(),
        PathBuf::from("node_modules/pkg/tool.bin")
    );
    assert_eq!(
        fs::read_to_string(candidate.join("input.txt")).unwrap(),
        "selected original
"
    );
    assert!(candidate.join("empty").is_dir() && candidate.join("bindings.rs").is_file());
    assert_eq!(
        build_project_with_context(&source.0, &state, &plan, Some(&binding), false).unwrap()["status"],
        "unchanged-project-build"
    );
    assert_eq!(fs::read(state.join("selected.json")).unwrap(), pointer);
    let binary = candidate.join("node_modules/pkg/tool.bin");
    fs::write(&binary, b"tamper before no-op").unwrap();
    assert!(build_project_with_context(&source.0, &state, &plan, Some(&binding), false).is_err());
    assert_eq!(fs::read(state.join("selected.json")).unwrap(), pointer);
    fs::write(&binary, [0, 255, 128, 0, 1]).unwrap();
    verify_project_build_selection(&state).unwrap();
    fs::rename(&source.0, root.0.join("source-retained-offline")).unwrap();
    fs::rename(&binding.snapshot, root.0.join("snapshot-retained-offline")).unwrap();
    assert_eq!(
        verify_project_build_selection(&state).unwrap()["status"],
        "verified-selected-build-bindings"
    );
    fs::write(
        candidate.join("node_modules/pkg/tool.bin"),
        b"corrupt binary context",
    )
    .unwrap();
    assert!(verify_project_build_selection(&state).is_err());
    assert_eq!(fs::read(state.join("selected.json")).unwrap(), pointer);
}

#[cfg(unix)]
#[test]
fn contextual_build_refusals_preserve_selection_for_bad_overlays_dependency_mutation_and_extra_writes()
 {
    let (root, source, plan, binding) = context_build_fixture();
    let state = root.0.join("state");
    assert_eq!(
        build_project_with_context(&source.0, &state, &plan, Some(&binding), false).unwrap()["status"],
        "selected-project-build"
    );
    let pointer = fs::read(state.join("selected.json")).unwrap();
    let mut wrong = binding.clone();
    wrong.overlays.insert(
        "input.txt".into(),
        patamaps_contracts::byte_digest(b"wrong preimage"),
    );
    let mut mutable = binding.clone();
    mutable.writable_paths.push("node_modules".into());
    let mut wrong_digest = binding.clone();
    wrong_digest.digest = patamaps_contracts::byte_digest(b"wrong sealed context");
    for bad in [wrong, mutable, wrong_digest] {
        let result =
            build_project_with_context(&source.0, &state, &plan, Some(&bad), true).unwrap();
        assert_eq!(result["status"], "refused-project-build", "{result}");
        assert_eq!(result["previousSelectionPreserved"], true);
        assert_eq!(fs::read(state.join("selected.json")).unwrap(), pointer);
    }
    for suffix in [
        "; printf changed > node_modules/pkg/tool.bin",
        "; printf unexpected > stray-file",
        "; exit 9",
    ] {
        let mut changed = plan.clone();
        changed.build_steps[0].invocation.arguments[1].push_str(suffix);
        let result =
            build_project_with_context(&source.0, &state, &changed, Some(&binding), true).unwrap();
        assert_eq!(result["status"], "refused-project-build", "{result}");
        assert_eq!(result["previousSelectionPreserved"], true);
        assert_eq!(fs::read(state.join("selected.json")).unwrap(), pointer);
        verify_project_build_selection(&state).unwrap();
    }
    fs::write(
        PathBuf::from(&binding.snapshot).join("data/node_modules/pkg/tool.bin"),
        b"corrupt retained blob",
    )
    .unwrap();
    let result =
        build_project_with_context(&source.0, &state, &plan, Some(&binding), true).unwrap();
    assert_eq!(result["status"], "refused-project-build");
    assert_eq!(fs::read(state.join("selected.json")).unwrap(), pointer);
    verify_project_build_selection(&state).unwrap();
}

#[test]
#[cfg(unix)]
fn retained_build_ceiling_preserves_selection_and_allows_noop_at_capacity() {
    let (root, source, mut plan) = build_fixture();
    plan.maximum_retained_attempts = patamaps_contracts::SafeInteger::new(2).unwrap();
    let state = root.0.join("state");
    build_project(&source.0, &state, &plan, false).unwrap();
    build_project(&source.0, &state, &plan, true).unwrap();
    let previous = fs::read(state.join("selected.json")).unwrap();
    assert_eq!(
        build_project(&source.0, &state, &plan, false).unwrap()["status"],
        "unchanged-project-build"
    );
    assert!(matches!(
        build_project(&source.0, &state, &plan, true),
        Err(Error::Refused {
            code: "PROJECT_BUILD_RETENTION_REVIEW_REQUIRED",
            ..
        })
    ));
    assert_eq!(fs::read_dir(state.join("attempts")).unwrap().count(), 2);
    assert_eq!(fs::read(state.join("selected.json")).unwrap(), previous);
    verify_project_build_selection(&state).unwrap();
}

#[test]
#[cfg(unix)]
fn failed_attempts_count_toward_retention_and_invalid_limits_create_no_state() {
    let (root, source, mut plan) = build_fixture();
    let state = root.0.join("state");
    plan.maximum_retained_attempts = patamaps_contracts::SafeInteger::new(0).unwrap();
    assert!(build_project(&source.0, &state, &plan, false).is_err());
    assert!(!state.exists());
    plan.maximum_retained_attempts = patamaps_contracts::SafeInteger::new(65).unwrap();
    assert!(build_project(&source.0, &state, &plan, false).is_err());
    assert!(!state.exists());
    plan.maximum_retained_attempts = patamaps_contracts::SafeInteger::new(1).unwrap();
    plan.build_steps[0].invocation.arguments = vec!["-c".into(), "exit 9".into()];
    assert_eq!(
        build_project(&source.0, &state, &plan, false).unwrap()["status"],
        "refused-project-build"
    );
    assert!(matches!(
        build_project(&source.0, &state, &plan, true),
        Err(Error::Refused {
            code: "PROJECT_BUILD_RETENTION_REVIEW_REQUIRED",
            ..
        })
    ));
    assert_eq!(fs::read_dir(state.join("attempts")).unwrap().count(), 1);
}

#[test]
#[cfg(unix)]
fn omitted_retention_limit_keeps_legacy_plan_serialization() {
    let (_, _, plan) = build_fixture();
    let raw = serde_json::to_value(&plan).unwrap();
    assert!(raw.get("maximumRetainedAttempts").is_none());
    let decoded: ProjectBuildPlan = serde_json::from_value(raw).unwrap();
    assert_eq!(decoded.maximum_retained_attempts.get(), 8);
}

#[cfg(unix)]
fn closed_build_fixture() -> (Temp, Temp, ProjectBuildPlan) {
    let (root, source, mut plan) = build_fixture();
    plan.outputs[0].kind = ArtifactKind::ClosedTree;
    plan.build_steps[0].invocation.arguments = vec![
        "-c".into(),
        "/bin/mkdir -p bundle/nested; printf artifact > bundle/nested/app; \
         /bin/cp bundle/nested/app bundle/nested/twin; \
         /bin/ln -s nested/app bundle/file-link; /bin/ln -s nested bundle/dir-link; \
         /bin/ln -s file-link bundle/chained-link"
            .into(),
    ];
    plan.verification_steps[0].invocation.arguments = vec![
        "-c".into(),
        "test \"$(/bin/cat bundle/file-link)\" = artifact && \
         test \"$(/bin/cat bundle/dir-link/app)\" = artifact && \
         test \"$(/bin/cat bundle/chained-link)\" = artifact"
            .into(),
    ];
    (root, source, plan)
}

#[test]
#[cfg(unix)]
fn closed_tree_selects_links_and_replays_without_original_source_or_build_tools() {
    use std::os::unix::fs::symlink;
    let (root, source, mut plan) = closed_build_fixture();
    let tools = root.0.join("configured-tools");
    fs::create_dir(&tools).unwrap();
    let configured = tools.join("shell");
    symlink("/bin/sh", &configured).unwrap();
    for command in plan
        .build_steps
        .iter_mut()
        .chain(&mut plan.verification_steps)
    {
        command.invocation.executable = configured.to_str().unwrap().into();
    }
    let state = root.0.join("state");
    let selected = build_project(&source.0, &state, &plan, false).unwrap();
    assert_eq!(selected["status"], "selected-project-build");
    let attempt = state.join(selected["attempt"].as_str().unwrap());
    let artifacts: serde_json::Value =
        serde_json::from_slice(&fs::read(attempt.join("artifacts.json")).unwrap()).unwrap();
    for (name, target) in [
        ("file-link", "nested/app"),
        ("dir-link", "nested"),
        ("chained-link", "file-link"),
    ] {
        let record = &artifacts[format!("bundle/{name}")];
        assert_eq!(record["kind"], "symlink");
        assert_eq!(record["target"], target);
        assert!(record["mode"].is_number());
    }
    let pointer = fs::read(state.join("selected.json")).unwrap();
    let noop = build_project(&source.0, &state, &plan, false).unwrap();
    assert_eq!(noop["status"], "unchanged-project-build");
    assert_eq!(noop["verification"], "not-repeated");
    fs::rename(&source.0, root.0.join("owner.offline-retained")).unwrap();
    fs::rename(&tools, root.0.join("tools.offline-retained")).unwrap();
    assert_eq!(
        verify_project_build_selection(&state).unwrap()["status"],
        "verified-selected-build-bindings"
    );
    let mut runtime = plan.verification_steps[0].clone();
    runtime.invocation.executable = "/bin/sh".into();
    let executed = execute_selected_project_command(&state, &runtime).unwrap();
    assert_eq!(executed["status"], "completed-selected-project-command");
    assert_eq!(executed["postExecutionSelectionVerified"], true);
    assert_eq!(executed["selectionPointerUnchanged"], true);
    assert_eq!(fs::read(state.join("selected.json")).unwrap(), pointer);
}

#[test]
#[cfg(unix)]
fn closed_tree_refuses_unsafe_targets_without_replacing_previous_selection() {
    for (name, body, ordinary) in [
        ("ordinary", "/bin/ln -s nested/app bundle/link", true),
        (
            "absolute",
            "/bin/ln -s /unselected-outside bundle/link",
            false,
        ),
        (
            "escape",
            "printf artifact > outside; /bin/ln -s ../outside bundle/link",
            false,
        ),
        ("missing", "/bin/ln -s missing bundle/link", false),
        ("self-cycle", "/bin/ln -s link bundle/link", false),
        (
            "chain-cycle",
            "/bin/ln -s other bundle/link; /bin/ln -s link bundle/other",
            false,
        ),
        (
            "other-output",
            "printf artifact > outside; /bin/ln -s ../outside bundle/link",
            false,
        ),
    ] {
        let (root, source, original) = build_fixture();
        let state = root.0.join("state");
        assert_eq!(
            build_project(&source.0, &state, &original, false).unwrap()["status"],
            "selected-project-build"
        );
        let pointer = fs::read(state.join("selected.json")).unwrap();
        let mut plan = original.clone();
        if !ordinary {
            plan.outputs[0].kind = ArtifactKind::ClosedTree;
        }
        if name == "other-output" {
            plan.outputs.push(ArtifactSelection {
                path: "outside".into(),
                kind: ArtifactKind::File,
            });
        }
        plan.build_steps[0].invocation.arguments = vec![
            "-c".into(),
            format!("/bin/mkdir -p bundle/nested; printf artifact > bundle/nested/app; {body}"),
        ];
        plan.verification_steps[0].invocation.arguments =
            vec!["-c".into(), "printf invoked > forbidden.marker".into()];
        let refused = build_project(&source.0, &state, &plan, false).unwrap();
        assert_eq!(
            refused["status"], "refused-project-build",
            "{name}: {refused}"
        );
        let expected = if ordinary {
            "PROJECT_BUILD_OUTPUT_SYMLINK"
        } else {
            "PROJECT_BUILD_OUTPUT_LINK_CLOSURE"
        };
        assert!(
            refused["reason"].as_str().unwrap().contains(expected),
            "{name}: {refused}"
        );
        assert_eq!(refused["previousSelectionPreserved"], true);
        assert!(
            !state
                .join(refused["attempt"].as_str().unwrap())
                .join("candidate/forbidden.marker")
                .exists()
        );
        assert_eq!(fs::read(state.join("selected.json")).unwrap(), pointer);
        verify_project_build_selection(&state).unwrap();
    }
}

#[test]
#[cfg(unix)]
fn closed_tree_member_and_link_changes_refuse_before_selected_command_effects() {
    use std::os::unix::fs::{PermissionsExt, symlink};
    for kind in [
        "identical-external-link",
        "identical-internal-link",
        "missing-target",
        "extra-member",
        "file-mode",
        "directory-mode",
        "file-bytes",
    ] {
        let (root, source, plan) = closed_build_fixture();
        let state = root.0.join("state");
        let selected = build_project(&source.0, &state, &plan, false).unwrap();
        assert_eq!(selected["status"], "selected-project-build");
        let candidate = state
            .join(selected["attempt"].as_str().unwrap())
            .join("candidate");
        let pointer = fs::read(state.join("selected.json")).unwrap();
        let mut moved = None;
        let mut changed_mode = None;
        match kind {
            "identical-external-link" | "identical-internal-link" => {
                let path = candidate.join("bundle/file-link");
                let backup = root.0.join("original-link.retained");
                fs::rename(&path, &backup).unwrap();
                if kind == "identical-external-link" {
                    let outside = root.0.join("outside-identical");
                    fs::write(&outside, "artifact").unwrap();
                    symlink(&outside, &path).unwrap();
                } else {
                    symlink("nested/twin", &path).unwrap();
                }
                moved = Some((path, backup));
            }
            "missing-target" | "file-bytes" => {
                let path = candidate.join("bundle/nested/app");
                let backup = root.0.join("original-member.retained");
                fs::rename(&path, &backup).unwrap();
                if kind == "file-bytes" {
                    fs::write(&path, "changed artifact").unwrap();
                }
                moved = Some((path, backup));
            }
            "extra-member" => {
                fs::write(candidate.join("bundle/extra"), "unselected").unwrap();
            }
            "file-mode" | "directory-mode" => {
                let path = candidate.join(if kind == "file-mode" {
                    "bundle/nested/app"
                } else {
                    "bundle/nested"
                });
                let mode = fs::metadata(&path).unwrap().permissions().mode();
                fs::set_permissions(&path, fs::Permissions::from_mode(mode ^ 0o010)).unwrap();
                changed_mode = Some((path, mode));
            }
            _ => unreachable!(),
        }
        let mut command = plan.verification_steps[0].clone();
        command.invocation.arguments =
            vec!["-c".into(), "printf invoked > forbidden.marker".into()];
        assert!(
            execute_selected_project_command(&state, &command).is_err(),
            "{kind}"
        );
        assert!(!candidate.join("forbidden.marker").exists(), "{kind}");
        assert_eq!(fs::read(state.join("selected.json")).unwrap(), pointer);
        if let Some((path, backup)) = moved {
            if fs::symlink_metadata(&path).is_ok() {
                fs::rename(&path, root.0.join("changed-member.retained")).unwrap();
            }
            fs::rename(&backup, &path).unwrap();
        }
        if kind == "extra-member" {
            fs::rename(
                candidate.join("bundle/extra"),
                root.0.join("extra-member.retained"),
            )
            .unwrap();
        }
        if let Some((path, mode)) = changed_mode {
            fs::set_permissions(path, fs::Permissions::from_mode(mode)).unwrap();
        }
        verify_project_build_selection(&state).unwrap();
    }
}

#[test]
#[cfg(unix)]
fn closed_tree_successful_command_link_mutation_is_refused_after_execution() {
    let (root, source, plan) = closed_build_fixture();
    let state = root.0.join("state");
    let selected = build_project(&source.0, &state, &plan, false).unwrap();
    assert_eq!(selected["status"], "selected-project-build");
    let candidate = state
        .join(selected["attempt"].as_str().unwrap())
        .join("candidate");
    let pointer = fs::read(state.join("selected.json")).unwrap();
    let mut command = plan.verification_steps[0].clone();
    command.invocation.arguments = vec![
        "-c".into(),
        "/bin/mv bundle/file-link original-link.retained; /bin/ln -s nested/twin bundle/file-link"
            .into(),
    ];
    let result = execute_selected_project_command(&state, &command).unwrap();
    assert_eq!(result["command"]["programSucceeded"], true);
    assert_eq!(result["status"], "refused-selected-project-command");
    assert_eq!(result["postExecutionSelectionVerified"], false);
    assert_eq!(result["selectionPointerUnchanged"], true);
    assert_eq!(fs::read(state.join("selected.json")).unwrap(), pointer);
    fs::rename(
        candidate.join("bundle/file-link"),
        root.0.join("changed-link.retained"),
    )
    .unwrap();
    fs::rename(
        candidate.join("original-link.retained"),
        candidate.join("bundle/file-link"),
    )
    .unwrap();
    verify_project_build_selection(&state).unwrap();
}
