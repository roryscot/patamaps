//! Local I/O orchestration. All semantic decisions use the checked Rust kernel.
#![forbid(unsafe_code)]
mod elf_target;
pub use elf_target::check_elf_target;
mod legacy_io;
mod model;
mod native_discovery;
mod native_docker;
mod native_next;
pub use native_discovery::discover_native;
mod source_evaluation;
pub use legacy_io::legacy_workspace_request;
pub use source_evaluation::*;
mod project;
#[cfg(unix)]
mod project_fs;
pub use project::*;
mod project_command;
pub use project_command::*;
mod project_build;
mod project_context;
pub use project_build::*;
pub use project_context::*;
mod process;
mod tool_supervisor;
pub use tool_supervisor::{configure_tool_supervisor, supervise_tool_stdio};
#[cfg(all(test, unix))]
mod process_tests;
pub use model::*;
use patamaps_contracts::*;
use patamaps_core::{CheckError, CheckedGraph, EvaluationOptions, admit, compose};
use patamaps_projection::{
    CaptureInputs, SourceReceipt, capture, emit_axum_witness, emit_http_client, emit_rust,
    emit_typescript, executor_id, project, replay,
};
use serde_json::json;
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    path::{Path, PathBuf},
};

pub const PROFILE: &str = "patamaps-workspace-draft-1";
pub fn engine_id() -> String {
    canonical_digest(&json!({"profile":PROFILE,"compiler":executor_id(),"manifest":include_str!("../Cargo.toml"),"model":include_str!("model.rs"),"process":include_str!("process.rs"),"toolSupervisor":include_str!("tool_supervisor.rs"),"workspace":include_str!("lib.rs"),"elfTarget":include_str!("elf_target.rs"),"legacyIO":include_str!("legacy_io.rs"),"sourceEvaluation":include_str!("source_evaluation.rs"),"nativeDiscovery":include_str!("native_discovery.rs"),"nativeDocker":include_str!("native_docker.rs"),"nativeNext":include_str!("native_next.rs"),"project":include_str!("project.rs"),"projectFilesystem":include_str!("project_fs.rs"),"projectCommand":include_str!("project_command.rs"),"projectBuild":include_str!("project_build.rs"),"projectContext":include_str!("project_context.rs")})).expect("finite embedded source")
}
#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("{code}: {message}")]
    Refused { code: &'static str, message: String },
    #[error(transparent)]
    Contract(#[from] ContractError),
    #[error(transparent)]
    Check(#[from] CheckError),
    #[error(transparent)]
    Io(#[from] std::io::Error),
}
impl Error {
    pub(crate) fn refused(code: &'static str, message: impl Into<String>) -> Self {
        Self::Refused {
            code,
            message: message.into(),
        }
    }
}

pub fn relative_path(path: &str) -> bool {
    !path.is_empty()
        && path.len() <= 1024
        && !path.contains(['\\', '\0'])
        && path.split('/').all(|s| {
            !s.is_empty()
                && s != "."
                && s != ".."
                && !s.contains(':')
                && !s.chars().any(char::is_control)
        })
}
fn bytes(path: &Path) -> Result<Vec<u8>, Error> {
    let mut bytes = Vec::new();
    File::open(path)?
        .take((MAX_INPUT_BYTES + 1) as u64)
        .read_to_end(&mut bytes)?;
    if bytes.len() > MAX_INPUT_BYTES {
        return Err(ContractError::InputLimit.into());
    }
    Ok(bytes)
}
fn source_path(root: &Path, path: &str) -> Result<PathBuf, Error> {
    if !relative_path(path) {
        return Err(Error::refused(
            "SOURCE_PATH",
            "Source must be a normalized relative path",
        ));
    }
    let resolved = fs::canonicalize(root.join(path))?;
    if !resolved.starts_with(root) || !resolved.is_file() {
        return Err(Error::refused(
            "SOURCE_ESCAPE",
            "Source resolves outside the selected workspace or is not a file",
        ));
    }
    Ok(resolved)
}
fn supplied(root: &Path, path: &str, total: &mut usize) -> Result<SuppliedInput, Error> {
    let mut raw = Vec::new();
    let available = MAX_INPUT_BYTES.saturating_sub(*total);
    File::open(source_path(root, path)?)?
        .take((available + 1) as u64)
        .read_to_end(&mut raw)?;
    if raw.len() > available {
        return Err(Error::refused(
            "WORKSPACE_SOURCE_LIMIT",
            "Captured source inventory exceeds its byte limit",
        ));
    }
    *total += raw.len();
    let receipt = InputReceipt {
        path: path.into(),
        digest: byte_digest(&raw),
        byte_length: SafeInteger::new(raw.len() as u64).expect("bounded source bytes"),
    };
    let content = String::from_utf8(raw)
        .map_err(|_| Error::refused("SOURCE_UTF8", "Source must be strict UTF-8"))?;
    Ok(SuppliedInput { receipt, content })
}
fn receipt(id: &str, input: &SuppliedInput) -> SourceReceipt {
    SourceReceipt {
        id: format!("{id}:{}", input.receipt.path),
        locator: format!("workspace:{}", input.receipt.path),
        digest: input.receipt.digest.clone(),
        byte_length: input.receipt.byte_length,
        content: Some(input.content.clone()),
    }
}
fn recorded_input(sources: &[SourceReceipt], id: &str, path: &str) -> Result<SuppliedInput, Error> {
    if !relative_path(path) {
        return Err(Error::refused(
            "SOURCE_PATH",
            "Invalid recorded source path",
        ));
    }
    let source_id = format!("{id}:{path}");
    let source = sources
        .iter()
        .find(|s| s.id == source_id)
        .ok_or_else(|| Error::refused("WORKSPACE_SOURCE_INVENTORY", "Required source absent"))?;
    let content = source.content.as_ref().ok_or_else(|| {
        Error::refused(
            "WORKSPACE_SOURCE_UNAVAILABLE",
            "Raw recorded input is unavailable",
        )
    })?;
    if source.locator != format!("workspace:{path}")
        || content.len() > MAX_INPUT_BYTES
        || source.byte_length.get() != content.len() as u64
        || source.digest != byte_digest(content.as_bytes())
    {
        return Err(Error::refused(
            "WORKSPACE_SOURCE_BINDING",
            "Recorded raw input binding differs",
        ));
    }
    Ok(SuppliedInput {
        receipt: InputReceipt {
            path: path.into(),
            digest: source.digest.clone(),
            byte_length: source.byte_length,
        },
        content: content.clone(),
    })
}
fn hash_executable(path: &Path) -> Result<String, Error> {
    let file = File::open(path)?;
    if !file.metadata()?.is_file() || file.metadata()?.len() > 256 * 1024 * 1024 {
        return Err(Error::refused(
            "ADAPTER_EXECUTABLE",
            "Executable must be a bounded regular file",
        ));
    }
    let mut hash = Sha256::new();
    let mut reader = file.take(256 * 1024 * 1024 + 1);
    let mut buffer = [0u8; 65536];
    let mut count = 0usize;
    loop {
        let n = reader.read(&mut buffer)?;
        if n == 0 {
            break;
        }
        count += n;
        if count > 256 * 1024 * 1024 {
            return Err(Error::refused(
                "ADAPTER_EXECUTABLE",
                "Executable grew beyond its limit",
            ));
        }
        hash.update(&buffer[..n]);
    }
    Ok(format!("sha256:{:x}", hash.finalize()))
}
fn validate_config(config: &WorkspaceConfig) -> Result<(), Error> {
    if !patamaps_core::valid_identifier(&config.id)
        || config.namespace.is_empty()
        || config.revision.is_empty()
        || config.revision.len() > 4096
        || !(1..=64).contains(&config.sources.len())
        || config.packs.len() > 64
        || !(1..=16).contains(&config.projections.len())
        || config
            .projections
            .iter()
            .map(|p| p.emissions.len())
            .sum::<usize>()
            > 32
    {
        return Err(Error::refused(
            "WORKSPACE_CONFIG",
            "Invalid identities or workspace bounds",
        ));
    }
    let mut ids = BTreeSet::new();
    let mut outputs = BTreeSet::new();
    for source in &config.sources {
        if !patamaps_core::valid_identifier(source.id()) || !ids.insert(source.id()) {
            return Err(Error::refused(
                "WORKSPACE_SOURCE_ID",
                "Sources require unique valid IDs",
            ));
        }
        if let Source::Process { config, .. } = source {
            patamaps_core::check_metadata_bounds(
                [(config, 1)],
                source.id(),
                "WORKSPACE_CONFIG_LIMIT",
            )?;
        }
    }
    for p in &config.projections {
        for e in &p.emissions {
            if matches!(
                e.language,
                OutputLanguage::HttpClient | OutputLanguage::AxumWitness
            ) && e.binding_slot.is_some()
            {
                return Err(Error::refused(
                    "WORKSPACE_HTTP_BINDING_SLOT",
                    "HTTP emissions use declared profile slots; bindingSlot overrides are unsupported",
                ));
            }
            if !relative_path(&e.path) || !outputs.insert(&e.path) {
                return Err(Error::refused(
                    "WORKSPACE_OUTPUT_PATH",
                    "Outputs require unique normalized relative paths",
                ));
            }
        }
    }
    patamaps_core::check_metadata_bounds(
        [(&config.context, 1)],
        &config.id,
        "WORKSPACE_CONFIG_LIMIT",
    )?;
    parse_value(&canonical_bytes(config)?)?;
    Ok(())
}

/// A host-selected cache is only an optimization of portable parsing. Every
/// entry is compared with the current decoded source before it is counted as a hit.
pub fn generate(
    root: &Path,
    config: &WorkspaceConfig,
    cache: Option<&Path>,
) -> Result<Generation, Error> {
    validate_config(config)?;
    let root = fs::canonicalize(root)?;
    let config_digest = canonical_digest(config)?;
    let mut sources = Vec::new();
    let mut discovery = Vec::new();
    let mut hits = 0;
    let mut misses = 0;
    let mut total_source_bytes = 0usize;
    let mut total_shard_bytes = 0usize;
    for source in &config.sources {
        let (shard, adapter, version, request_digest, executable_digest, diagnostics) = match source
        {
            Source::PortableShard { id, path } => {
                let input = supplied(&root, path, &mut total_source_bytes)?;
                let shard: GraphDocument = parse(input.content.as_bytes())?;
                let key = canonical_digest(
                    &json!({"profile":PROFILE,"executor":executor_id(),"workspaceExecutor":engine_id(),"config":config_digest,"source":source,"input":input.receipt}),
                )?;
                let canonical = canonical_bytes(&shard)?;
                let mut hit = false;
                if let Some(cache) = cache {
                    let path = cache.join(format!("{}.json", &key[7..]));
                    if let Ok(raw) = bytes(&path)
                        && let Ok(cached) = parse::<GraphDocument>(&raw)
                    {
                        hit = canonical_bytes(&cached)? == canonical;
                    }
                    if !hit {
                        fs::create_dir_all(cache)?;
                        if let Ok(mut file) =
                            OpenOptions::new().write(true).create_new(true).open(path)
                        {
                            file.write_all(&canonical)?;
                            file.sync_all()?;
                        }
                    }
                }
                if hit {
                    hits += 1;
                } else {
                    misses += 1;
                }
                sources.push(receipt(id, &input));
                (
                    shard,
                    "portable-shard".into(),
                    "0.1.0".into(),
                    key,
                    None,
                    Vec::new(),
                )
            }
            Source::Process {
                id,
                invocation,
                inputs,
                config: adapter_config,
            } => {
                if !(1..=1024).contains(&inputs.len()) || invocation.code_inputs.len() > 512 {
                    return Err(Error::refused(
                        "ADAPTER_INPUT_LIMIT",
                        "Provider input inventory is out of bounds",
                    ));
                }
                let executable = Path::new(&invocation.executable);
                if !executable.is_absolute() {
                    return Err(Error::refused(
                        "ADAPTER_EXECUTABLE",
                        "Configure an absolute executable path; PATH lookup is disabled",
                    ));
                }
                let executable = fs::canonicalize(executable)?;
                let mut paths = BTreeSet::new();
                let inputs = inputs
                    .iter()
                    .map(|p| {
                        if !paths.insert(p) {
                            return Err(Error::refused(
                                "ADAPTER_DUPLICATE_INPUT",
                                "Repeated source path",
                            ));
                        }
                        supplied(&root, p, &mut total_source_bytes)
                    })
                    .collect::<Result<Vec<_>, _>>()?;
                let code = invocation
                    .code_inputs
                    .iter()
                    .map(|p| {
                        if !paths.insert(p) {
                            return Err(Error::refused(
                                "ADAPTER_DUPLICATE_INPUT",
                                "Code and source inventories must be disjoint and unique",
                            ));
                        }
                        supplied(&root, p, &mut total_source_bytes)
                    })
                    .collect::<Result<Vec<_>, _>>()?;
                let executable_digest = hash_executable(&executable)?;
                let invocation_digest = canonical_digest(
                    &json!({"invocation":invocation,"executableDigest":executable_digest,"codeInputs":code.iter().map(|i| &i.receipt).collect::<Vec<_>>()}),
                )?;
                let mut request = AdapterRequest {
                    schema_version: ProtocolVersion::Draft1,
                    document_type: RequestType::Record,
                    profile: PROFILE.into(),
                    source_id: id.clone(),
                    namespace: config.namespace.clone(),
                    config: adapter_config.clone(),
                    inputs,
                    invocation_digest,
                    request_digest: String::new(),
                };
                request.request_digest = canonical_digest(&request)?;
                let response = process::invoke(invocation, &executable, &root, &request)?;
                for input in request.inputs.iter().chain(&code) {
                    sources.push(receipt(id, input));
                }
                (
                    response.shard,
                    "process".into(),
                    response.adapter_version,
                    request.request_digest,
                    Some(executable_digest),
                    response.diagnostics,
                )
            }
        };
        if total_source_bytes > MAX_INPUT_BYTES {
            return Err(Error::refused(
                "WORKSPACE_SOURCE_LIMIT",
                "Captured sources exceed the workspace byte bound",
            ));
        }
        // Closed wire parsing is required even for provider structs and cache hits.
        parse::<GraphDocument>(&canonical_bytes(&shard)?)?;
        total_shard_bytes = total_shard_bytes.saturating_add(canonical_bytes(&shard)?.len());
        if total_shard_bytes > MAX_INPUT_BYTES {
            return Err(Error::refused(
                "WORKSPACE_SHARD_LIMIT",
                "Combined discovery shards exceed their byte limit",
            ));
        }
        discovery.push(DiscoveryReceipt {
            source_id: source.id().into(),
            adapter,
            adapter_version: version,
            request_digest,
            executable_digest,
            shard_digest: canonical_digest(&shard)?,
            shard: shard.clone(),
            diagnostics,
        });
    }
    // Capture authored policy, pack and projection bytes alongside discovery.
    let mut additional = BTreeSet::new();
    for p in std::iter::once(&config.policy)
        .chain(&config.packs)
        .chain(config.projections.iter().map(|p| &p.path))
    {
        if additional.insert(p) {
            let input = supplied(&root, p, &mut total_source_bytes)?;
            sources.push(receipt("urn:patamaps:workspace:authored", &input));
        }
    }
    Ok(Generation {
        baseline: assemble(config, discovery, sources)?,
        cache_hits: hits,
        cache_misses: misses,
    })
}

// Pure assembly is shared by live generation and offline reconstruction.
fn assemble(
    config: &WorkspaceConfig,
    discovery: Vec<DiscoveryReceipt>,
    sources: Vec<SourceReceipt>,
) -> Result<WorkspaceBaseline, Error> {
    let config_digest = canonical_digest(config)?;
    let shards = discovery
        .iter()
        .map(|d| d.shard.clone())
        .collect::<Vec<_>>();
    let mut graph = compose(&shards, config.id.clone(), config.namespace.clone())?;
    // Composition revision is explicitly authored; policies are never rebound
    // automatically when sources or their correspondence meanings change.
    graph.revision = Some(config.revision.clone());
    // Bind recorded provider versions, shard revisions and request/code
    // identities into the evaluated graph, including metadata-only changes.
    // This proves record consistency; it does not authenticate a provider.
    graph.metadata.as_mut().expect("composition metadata").insert(
        "workspaceLineageDigest".into(),
        json!(canonical_digest(&json!({"profile":PROFILE,"workspaceExecutor":engine_id(),"configDigest":config_digest,"discovery":discovery}))?),
    );
    let load = |path: &String| -> Result<String, Error> {
        Ok(recorded_input(&sources, "urn:patamaps:workspace:authored", path)?.content)
    };
    let policy: PolicyDocument = parse(load(&config.policy)?.as_bytes())?;
    let mut packs = config
        .packs
        .iter()
        .map(|p| parse::<RelationPack>(load(p)?.as_bytes()).map_err(Error::from))
        .collect::<Result<Vec<_>, _>>()?;
    let core: RelationPack = parse(include_bytes!("../../../relation-packs/core.json"))?;
    if !packs.iter().any(|p| p.id == core.id) {
        packs.push(core);
    }
    let mut captures = Vec::new();
    let mut outputs = BTreeMap::new();
    let mut projection_ids = BTreeSet::new();
    let mut capture_bytes = 0usize;
    let mut output_bytes = 0usize;
    for selection in &config.projections {
        let spec: ProjectionSpec = parse(load(&selection.path)?.as_bytes())?;
        if !projection_ids.insert(spec.id.clone()) {
            return Err(Error::refused(
                "WORKSPACE_PROJECTION_ID",
                "Repeated projection ID",
            ));
        }
        let record = capture(
            CaptureInputs {
                projection_specs: vec![],
                graph: graph.clone(),
                packs: packs.clone(),
                policy: policy.clone(),
                context: config.context.clone(),
                evaluated_at: config.evaluated_at.clone(),
                projection_spec: Some(spec.clone()),
            },
            sources.clone(),
        )?;
        capture_bytes = capture_bytes.saturating_add(canonical_bytes(&record)?.len());
        if capture_bytes > MAX_INPUT_BYTES {
            return Err(Error::refused(
                "WORKSPACE_CAPTURE_LIMIT",
                "Combined captures exceed their byte limit",
            ));
        }
        if record
            .result
            .get("status")
            .and_then(serde_json::Value::as_str)
            == Some("viable")
        {
            let checked = CheckedGraph::check(graph.clone(), packs.clone())?;
            let admitted = admit(
                &checked,
                &policy,
                EvaluationOptions {
                    context: config.context.clone(),
                    evaluated_at: config.evaluated_at.clone(),
                },
            )?;
            let projection = project(&admitted, &spec)?;
            for e in &selection.emissions {
                let content = match e.language {
                    OutputLanguage::Json => {
                        String::from_utf8(canonical_bytes(projection.record())?)
                            .expect("canonical UTF-8")
                    }
                    OutputLanguage::Rust => emit_rust(&projection, e.binding_slot.as_deref())?,
                    OutputLanguage::HttpClient => emit_http_client(&projection)?,
                    OutputLanguage::AxumWitness => emit_axum_witness(&projection)?,
                    OutputLanguage::Typescript => {
                        emit_typescript(&projection, "bindings", e.binding_slot.as_deref())?
                    }
                };
                output_bytes = output_bytes.saturating_add(content.len());
                if output_bytes > MAX_INPUT_BYTES {
                    return Err(Error::refused(
                        "WORKSPACE_OUTPUT_LIMIT",
                        "Combined outputs exceed their byte limit",
                    ));
                }
                outputs.insert(e.path.clone(), content);
            }
        }
        captures.push(record);
    }
    let mut baseline = WorkspaceBaseline {
        schema_version: ProtocolVersion::Draft1,
        document_type: BaselineType::Record,
        profile: PROFILE.into(),
        executor: executor_id().into(),
        workspace_executor: engine_id(),
        config_digest,
        config: config.clone(),
        discovery,
        captures,
        outputs,
        digest: String::new(),
    };
    baseline.digest = baseline_digest(&baseline)?;
    parse_value(&canonical_bytes(&baseline)?)?;
    Ok(baseline)
}
fn baseline_digest(baseline: &WorkspaceBaseline) -> Result<String, Error> {
    let mut value = serde_json::to_value(baseline).map_err(ContractError::from)?;
    value
        .as_object_mut()
        .expect("baseline object")
        .remove("digest");
    Ok(canonical_digest(&value)?)
}

/// Checked historical record bindings. This is not authentication, current
/// source rediscovery, authorization or activation. It cannot deserialize.
///
/// ```compile_fail
/// use patamaps_workspace::{VerifiedWorkspace, WorkspaceBaseline};
/// fn forge(baseline: &WorkspaceBaseline) -> VerifiedWorkspace<'_> {
///     VerifiedWorkspace { baseline }
/// }
/// ```
#[derive(Debug)]
pub struct VerifiedWorkspace<'a> {
    baseline: &'a WorkspaceBaseline,
}
impl VerifiedWorkspace<'_> {
    pub fn record(&self) -> &WorkspaceBaseline {
        self.baseline
    }
}

/// Reconstruct recorded source composition and output bytes without filesystem
/// access or executing a recorded provider. The workspace executor must match.
pub fn verify_baseline(baseline: &WorkspaceBaseline) -> Result<VerifiedWorkspace<'_>, Error> {
    validate_config(&baseline.config)?;
    if baseline.captures.is_empty()
        || baseline.captures.len() > 16
        || baseline.outputs.len() > 32
        || baseline.discovery.len() > 64
    {
        return Err(Error::refused(
            "WORKSPACE_BASELINE_LIMIT",
            "Baseline inventory is out of bounds",
        ));
    }
    for captured in &baseline.captures {
        replay(captured)?;
    }
    for discovered in &baseline.discovery {
        patamaps_core::check_input_bounds(
            &discovered.shard,
            &[],
            &baseline.captures[0].inputs.policy,
            &baseline.config.context,
        )?;
        if canonical_digest(&discovered.shard)? != discovered.shard_digest {
            return Err(Error::refused(
                "WORKSPACE_SHARD_BINDING",
                "Retained discovery shard differs from its receipt",
            ));
        }
    }
    parse_value(&canonical_bytes(baseline)?)?;
    if baseline.profile != PROFILE
        || baseline.executor != executor_id()
        || baseline.workspace_executor != engine_id()
        || canonical_digest(&baseline.config)? != baseline.config_digest
        || baseline_digest(baseline)? != baseline.digest
        || baseline.captures.is_empty()
        || baseline.captures.len() > 16
    {
        return Err(Error::refused(
            "WORKSPACE_BASELINE",
            "Baseline address or executor is invalid",
        ));
    }
    if baseline.discovery.len() != baseline.config.sources.len()
        || baseline.captures.len() != baseline.config.projections.len()
    {
        return Err(Error::refused(
            "WORKSPACE_SOURCE_INVENTORY",
            "Recorded inventory differs",
        ));
    }
    let raw_sources = &baseline.captures[0].sources;
    let mut expected_sources = Vec::new();
    for (source, discovered) in baseline.config.sources.iter().zip(&baseline.discovery) {
        if discovered.source_id != source.id() {
            return Err(Error::refused(
                "WORKSPACE_SOURCE_INVENTORY",
                "Source order or identity differs",
            ));
        }
        match source {
            Source::PortableShard { id, path } => {
                let input = recorded_input(raw_sources, id, path)?;
                let key = canonical_digest(
                    &json!({"profile":PROFILE,"executor":executor_id(),"workspaceExecutor":engine_id(),"config":baseline.config_digest,"source":source,"input":input.receipt}),
                )?;
                let shard: GraphDocument = parse(input.content.as_bytes())?;
                if discovered.adapter != "portable-shard"
                    || discovered.adapter_version != "0.1.0"
                    || discovered.executable_digest.is_some()
                    || !discovered.diagnostics.is_empty()
                    || discovered.request_digest != key
                    || canonical_bytes(&shard)? != canonical_bytes(&discovered.shard)?
                {
                    return Err(Error::refused(
                        "WORKSPACE_DISCOVERY_BINDING",
                        "Portable discovery differs from its source",
                    ));
                }
                expected_sources.push(receipt(id, &input));
            }
            Source::Process {
                id,
                invocation,
                inputs,
                config,
            } => {
                process::validate_invocation(invocation)?;
                if !(1..=1024).contains(&inputs.len()) || invocation.code_inputs.len() > 512 {
                    return Err(Error::refused(
                        "ADAPTER_INPUT_LIMIT",
                        "Recorded input inventory exceeds its bound",
                    ));
                }
                let executable_digest =
                    discovered.executable_digest.as_deref().ok_or_else(|| {
                        Error::refused(
                            "WORKSPACE_DISCOVERY_BINDING",
                            "Recorded executable digest absent",
                        )
                    })?;
                if !Path::new(&invocation.executable).is_absolute()
                    || executable_digest.len() != 71
                    || !executable_digest.starts_with("sha256:")
                    || !executable_digest[7..]
                        .bytes()
                        .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
                {
                    return Err(Error::refused(
                        "WORKSPACE_DISCOVERY_BINDING",
                        "Invalid recorded executable binding",
                    ));
                }
                let mut paths = BTreeSet::new();
                let mut load = |path: &String| {
                    if !paths.insert(path.clone()) {
                        return Err(Error::refused(
                            "ADAPTER_DUPLICATE_INPUT",
                            "Repeated recorded input",
                        ));
                    }
                    let input = recorded_input(raw_sources, id, path)?;
                    expected_sources.push(receipt(id, &input));
                    Ok(input)
                };
                let inputs = inputs
                    .iter()
                    .map(&mut load)
                    .collect::<Result<Vec<_>, _>>()?;
                let code = invocation
                    .code_inputs
                    .iter()
                    .map(&mut load)
                    .collect::<Result<Vec<_>, _>>()?;
                let invocation_digest = canonical_digest(
                    &json!({"invocation":invocation,"executableDigest":executable_digest,"codeInputs":code.iter().map(|i| &i.receipt).collect::<Vec<_>>()}),
                )?;
                let request = AdapterRequest {
                    schema_version: ProtocolVersion::Draft1,
                    document_type: RequestType::Record,
                    profile: PROFILE.into(),
                    source_id: id.clone(),
                    namespace: baseline.config.namespace.clone(),
                    config: config.clone(),
                    inputs,
                    invocation_digest,
                    request_digest: String::new(),
                };
                if discovered.adapter != "process"
                    || discovered.adapter_version.is_empty()
                    || discovered.adapter_version.len() > 128
                    || discovered.diagnostics.len() > 1024
                    || discovered
                        .diagnostics
                        .iter()
                        .any(|d| matches!(d.severity, DiagnosticSeverity::Error))
                    || discovered.request_digest != canonical_digest(&request)?
                {
                    return Err(Error::refused(
                        "WORKSPACE_DISCOVERY_BINDING",
                        "Process discovery request differs",
                    ));
                }
            }
        }
    }
    let mut authored = BTreeSet::new();
    for path in std::iter::once(&baseline.config.policy)
        .chain(&baseline.config.packs)
        .chain(baseline.config.projections.iter().map(|p| &p.path))
    {
        if authored.insert(path) {
            let input = recorded_input(raw_sources, "urn:patamaps:workspace:authored", path)?;
            expected_sources.push(receipt("urn:patamaps:workspace:authored", &input));
        }
    }
    let rebuilt = assemble(
        &baseline.config,
        baseline.discovery.clone(),
        expected_sources,
    )?;
    if canonical_bytes(&rebuilt)? != canonical_bytes(baseline)? {
        return Err(Error::refused(
            "WORKSPACE_COMPOSITION_BINDING",
            "Recorded composition, captures or emitted bytes differ",
        ));
    }
    Ok(VerifiedWorkspace { baseline })
}

/// Rebuild from actual current sources after verifying the historical baseline;
/// never writes or accepts drift.
pub fn check(
    root: &Path,
    config: &WorkspaceConfig,
    baseline: &WorkspaceBaseline,
    cache: Option<&Path>,
) -> Result<DriftReport, Error> {
    verify_baseline(baseline)?;
    let current = generate(root, config, cache)?.baseline;
    let mut changes = Vec::new();
    if baseline.config_digest != current.config_digest {
        changes.push("configuration");
    }
    if canonical_bytes(&baseline.discovery)? != canonical_bytes(&current.discovery)? {
        changes.push("discovery");
    }
    if canonical_bytes(&baseline.captures)? != canonical_bytes(&current.captures)? {
        changes.push("captures");
    }
    if baseline.outputs != current.outputs {
        changes.push("native-output");
    }
    let viable = current
        .captures
        .iter()
        .all(|c| c.result.get("status").and_then(serde_json::Value::as_str) == Some("viable"));
    Ok(DriftReport {
        status: if !viable {
            "rejected"
        } else if changes.is_empty() {
            "unchanged"
        } else {
            "drift"
        },
        baseline_digest: baseline.digest.clone(),
        current_digest: current.digest,
        changes,
    })
}

/// Reconstruct verified output bytes in a fresh retained directory, without tools.
/// This does not copy source inputs, execute a build, or publish a selection.
pub fn stage_workspace_outputs(
    baseline: &WorkspaceBaseline,
    destination: &Path,
) -> Result<serde_json::Value, Error> {
    let checked = verify_baseline(baseline)?;
    let inputs = checked
        .record()
        .outputs
        .iter()
        .map(|(path, content)| {
            Ok(SuppliedInput {
                receipt: InputReceipt {
                    path: path.clone(),
                    digest: byte_digest(content.as_bytes()),
                    byte_length: SafeInteger::new(content.len() as u64).ok_or_else(|| {
                        Error::refused(
                            "WORKSPACE_OUTPUT_LIMIT",
                            "Output length exceeds safe integers",
                        )
                    })?,
                },
                content: content.clone(),
            })
        })
        .collect::<Result<Vec<_>, Error>>()?;
    project::stage_selected_inputs(&inputs, destination)?;
    Ok(json!({
        "status": "staged-workspace-outputs", "profile": PROFILE,
        "baselineDigest": baseline.digest, "workspace": baseline.config.id,
        "outputs": inputs.iter().map(|v| &v.receipt).collect::<Vec<_>>(),
        "outputCount": inputs.len(), "outputBytesRechecked": true,
        "permissions": "user-only-non-executable-files",
        "sourceInputs": "not-copied", "toolExecution": "not-performed",
        "compilation": "not-performed", "selectionPublication": "not-performed",
        "authorizationNow": "not-evaluated", "activation": "not-performed"
    }))
}
