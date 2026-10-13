use base64::{Engine as _, engine::general_purpose::STANDARD};
use clap::{Args, Parser, Subcommand, ValueEnum};
use patamaps_contracts::{
    COMPATIBILITY_JSON_LIMITS, CompositionRequest, ContractError, GraphDocument, JsonObject,
    MAX_INPUT_BYTES, PolicyDocument, ProjectionSpec, RelationPack, canonical_bytes,
    canonical_digest, parse, parse_value, parse_value_with_limits,
};
use patamaps_core::{
    CheckError, CheckedGraph, DerivationStatus, Direction, EvaluationOptions, Issue, admit,
    compose, derive,
};
use patamaps_governance::{
    ApprovalOptions, ApprovalPayload, ArtifactEmission, DeploymentIntent, GovernedBaseline,
    GovernedCandidate, PreparedCandidate, ProposalOptions, SignedApproval, TrustedConsumer,
    VerificationContext, approval_signing_bytes, attach_signature, check_prepared,
    create_approval_payload, create_proposal, verify_approval,
};
use patamaps_projection::{
    CaptureInputs, CaptureRecord, SourceReceipt, capture, compare, compile_path_tree, emit_rust,
    emit_typescript, hydrate, project, replay,
};
use serde::{Serialize, de::DeserializeOwned};
use std::{
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    path::{Path, PathBuf},
    sync::atomic::{AtomicU64, Ordering},
};

#[derive(Parser)]
#[command(
    name = "patamaps",
    version,
    about = "Compile checked semantic correspondences into native bindings"
)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Args)]
struct GraphInput {
    graph: PathBuf,
    #[arg(long = "relation-pack")]
    packs: Vec<PathBuf>,
}
#[derive(Args)]
struct Evaluation {
    /// Explicit logical evaluation time, in RFC 3339 format.
    #[arg(long = "as-of")]
    evaluated_at: String,
    #[arg(long)]
    context: Option<PathBuf>,
}
#[derive(Args)]
struct Output {
    #[arg(short, long)]
    output: Option<PathBuf>,
    #[arg(long, requires = "output")]
    overwrite: bool,
}
#[derive(Clone, Copy, ValueEnum)]
enum Format {
    Json,
    Rust,
    Typescript,
}
#[derive(Clone, Copy, ValueEnum)]
enum JsonOperation {
    Canonical,
    Digest,
    Parse,
}

#[derive(Clone, Copy, ValueEnum)]
enum LegacyJsonOperation {
    Validate,
    Shape,
}
#[derive(Clone, Copy, ValueEnum)]
enum LegacyPackOperation {
    Parse,
    Import,
    Digest,
}
#[derive(Clone, Copy, ValueEnum)]
enum TraceDirection {
    Forward,
    Reverse,
    Both,
}
#[derive(Clone, Copy, ValueEnum)]
enum Intent {
    Deploy,
    Rollback,
}
#[derive(Subcommand)]
enum Command {
    /// Read-only legacy data validation; reports confer no admission or authorization.
    Legacy {
        #[command(subcommand)]
        command: LegacyCommand,
    },
    /// Source-preserving scientific syntax/profile operations; imports stay unadmitted.
    Sssom {
        #[command(subcommand)]
        command: ScientificCommand,
    },
    /// Describe installed source identities; this does not authenticate a binary.
    Engine,
    /// JSON SDK transport: bounded stdin, Rust canonicalization and diagnostics.
    Json {
        #[arg(value_enum)]
        operation: JsonOperation,
    },
    /// Discover explicitly selected sources and return a captured native bundle.
    Generate {
        config: PathBuf,
        #[arg(long)]
        root: PathBuf,
        #[arg(long)]
        cache: Option<PathBuf>,
        #[command(flatten)]
        output: Output,
    },
    /// Recompute current sources and report drift without replacing the baseline.
    Check {
        config: PathBuf,
        baseline: PathBuf,
        #[arg(long)]
        root: PathBuf,
        #[arg(long)]
        cache: Option<PathBuf>,
        #[command(flatten)]
        output: Output,
    },
    /// Search only explicitly supplied edits; no changes are written or applied.
    Repair {
        request: PathBuf,
        #[arg(long)]
        cancel_after_ms: Option<u64>,
        #[command(flatten)]
        output: Output,
    },
    /// Inspect verified captured inputs and results as JSON or offline HTML.
    Inspect {
        capture: PathBuf,
        #[arg(long)]
        before: Option<PathBuf>,
        #[arg(long)]
        subject: String,
        #[arg(long)]
        mapping: bool,
        #[arg(long)]
        html: bool,
        #[arg(long, default_value_t = 128)]
        maximum_subjects: usize,
        #[arg(long, default_value_t = 256)]
        maximum_mappings: usize,
        #[command(flatten)]
        output: Output,
    },
    /// Prepare exact recomputed files and an unapproved change proposal.
    Propose {
        #[arg(required = true)]
        captures: Vec<PathBuf>,
        #[arg(long)]
        trust: PathBuf,
        #[arg(long)]
        baseline: Option<PathBuf>,
        #[arg(long)]
        consumer: String,
        #[arg(long)]
        environment: String,
        #[arg(long)]
        proposer: String,
        #[arg(long, value_enum, default_value = "deploy")]
        intent: Intent,
        #[arg(long)]
        emissions: Option<PathBuf>,
        #[command(flatten)]
        output: Output,
    },
    /// Produce the exact canonical bytes for an external signer.
    ApprovalPayload {
        prepared: PathBuf,
        #[arg(long)]
        principal: String,
        #[arg(long)]
        key: String,
        #[arg(long = "grant", required = true)]
        grants: Vec<String>,
        #[arg(long)]
        issued_at: String,
        #[arg(long)]
        expires_at: String,
        #[command(flatten)]
        output: Output,
    },
    /// Attach canonical base64 signature data without granting authorization.
    AttachSignature {
        payload: PathBuf,
        signature: PathBuf,
        #[command(flatten)]
        output: Output,
    },
    /// Verify under separately supplied trust/base/time; performs no activation.
    VerifyApproval {
        prepared: PathBuf,
        approval: PathBuf,
        #[arg(long)]
        trust: PathBuf,
        #[arg(long)]
        baseline: Option<PathBuf>,
        #[arg(long)]
        now: String,
        #[command(flatten)]
        output: Output,
    },
    PathTree {
        #[command(flatten)]
        input: GraphInput,
        policy: PathBuf,
        spec: PathBuf,
        #[command(flatten)]
        evaluation: Evaluation,
        #[arg(long)]
        parameters: Option<PathBuf>,
        #[command(flatten)]
        output: Output,
    },
    /// Propose one explicitly requested law application without graph writes.
    Derive {
        #[command(flatten)]
        input: GraphInput,
        request: PathBuf,
        #[command(flatten)]
        output: Output,
    },
    Validate {
        #[command(flatten)]
        input: GraphInput,
    },
    Compose {
        #[arg(required = true)]
        shards: Vec<PathBuf>,
        #[arg(long)]
        id: String,
        #[arg(long)]
        namespace: String,
        #[arg(long = "relation-pack")]
        packs: Vec<PathBuf>,
        #[command(flatten)]
        output: Output,
    },
    Authority {
        #[command(flatten)]
        input: GraphInput,
        concept: String,
        fact: String,
    },
    Trace {
        #[command(flatten)]
        input: GraphInput,
        subject: String,
        #[arg(long, value_enum, default_value = "both")]
        direction: TraceDirection,
        #[arg(long, default_value_t = 3)]
        depth: usize,
        #[arg(long = "relation")]
        relations: Vec<String>,
    },
    Compile {
        #[command(flatten)]
        input: GraphInput,
        policy: PathBuf,
        #[command(flatten)]
        evaluation: Evaluation,
        #[command(flatten)]
        output: Output,
    },
    Link {
        #[command(flatten)]
        input: GraphInput,
        policy: PathBuf,
        spec: PathBuf,
        #[command(flatten)]
        evaluation: Evaluation,
        /// Saved records are always compared with a fresh evaluation.
        #[arg(long)]
        generation: Option<PathBuf>,
        #[arg(long, value_enum, default_value = "json")]
        format: Format,
        #[arg(long, default_value = "bindings")]
        export: String,
        #[arg(long)]
        binding_slot: Option<String>,
        #[command(flatten)]
        output: Output,
    },
    Capture {
        #[command(flatten)]
        input: GraphInput,
        policy: PathBuf,
        #[arg(long)]
        spec: Vec<PathBuf>,
        #[arg(long)]
        source_receipts: Option<PathBuf>,
        #[command(flatten)]
        evaluation: Evaluation,
        #[command(flatten)]
        output: Output,
    },
    Replay {
        input: PathBuf,
    },
    Compare {
        before: PathBuf,
        after: PathBuf,
        #[command(flatten)]
        output: Output,
    },
    Diff {
        before: PathBuf,
        after: PathBuf,
        #[command(flatten)]
        output: Output,
    },
    Canonical {
        input: PathBuf,
        #[command(flatten)]
        output: Output,
    },
}

#[derive(Subcommand)]
enum LegacyCommand {
    /// JSON request with document and optional native or legacy registered packs.
    Json {
        #[arg(value_enum)]
        operation: LegacyJsonOperation,
    },
    /// Versioned portable pack data over stdin; its original address is preserved.
    Pack {
        #[arg(value_enum)]
        operation: LegacyPackOperation,
        /// Observed host locale for unchecked legacy stable digests.
        #[arg(long, default_value = "en-US")]
        locale: String,
    },
    /// Read a portable pack file with its original version-specific JSON rules.
    PackFile {
        #[arg(value_enum)]
        operation: LegacyPackOperation,
        path: PathBuf,
    },
    /// Ordered legacy registry operations over current host-owned snapshots.
    Registry {
        #[arg(value_enum)]
        operation: LegacyRegistryTransport,
    },
    /// Indexed graph observations over retained host-owned data and keys.
    Graph {
        #[arg(value_enum)]
        operation: LegacyRegistryTransport,
    },
    /// Compose legacy shards without validating their cross-shard references.
    Compose {
        #[arg(value_enum)]
        operation: LegacyRegistryTransport,
    },
    /// Read-only legacy diffs and Markdown reports, retaining UTF-16 output.
    Reporting {
        #[arg(value_enum)]
        operation: LegacyRegistryTransport,
    },
    /// Materialize legacy correspondence declarations and observe drift.
    Correspondence {
        #[arg(value_enum)]
        operation: LegacyRegistryTransport,
    },
    /// Original workspace assembly, cache, baseline and output observations.
    Workspace {
        #[arg(value_enum)]
        operation: LegacyRegistryTransport,
    },
    /// Validate the original workspace config without admission or defaults.
    Config {
        #[arg(value_enum)]
        operation: LegacyRegistryTransport,
    },
    /// Load an original workspace config and resolve repository paths.
    ConfigFile { path: PathBuf },
    /// Observe legacy reference identifiers, URI encoding and path predicates.
    References {
        #[arg(value_enum)]
        operation: LegacyRegistryTransport,
    },
}

#[derive(Clone, Copy, ValueEnum)]
enum LegacyRegistryTransport {
    Json,
}

#[derive(Subcommand)]
enum ScientificCommand {
    /// SDK operations over stdin; all scientific interpretation executes here.
    Json {
        operation: ScientificJsonOperation,
        #[arg(long)]
        condense: bool,
    },
    /// Regenerate a bounded scientific RO-Crate from viable captured source bytes.
    Crate {
        capture: PathBuf,
        options: PathBuf,
        #[command(flatten)]
        output: Output,
    },
    /// Verify all metadata, files, source receipts and native outputs afresh.
    VerifyCrate {
        input: PathBuf,
        #[command(flatten)]
        output: Output,
    },
    /// Parse the pinned entity TSV profile and emit raw unadmitted observations.
    Import {
        input: PathBuf,
        #[arg(long)]
        source_config: PathBuf,
        #[arg(long)]
        metadata: Option<PathBuf>,
        #[command(flatten)]
        output: Output,
    },
    /// Return TSV text and a verified preservation/normalization report.
    Export {
        document: PathBuf,
        #[arg(long)]
        condense: bool,
        #[command(flatten)]
        output: Output,
    },
}

#[derive(Clone, Copy, ValueEnum)]
enum ScientificJsonOperation {
    Parse,
    SourceConfig,
    Profile,
    Document,
    Interpret,
    Export,
    Expand,
}

fn scientific_operation(
    operation: ScientificJsonOperation,
    condense: bool,
) -> patamaps_scientific::Result<serde_json::Value> {
    use patamaps_scientific::*;
    let error = |code, message: String| Error { code, message };
    if condense && !matches!(operation, ScientificJsonOperation::Export) {
        return Err(error(
            "SSSOM_EXPORT_OPTIONS",
            "condense applies only to export".into(),
        ));
    }
    let mut input = Vec::new();
    std::io::stdin()
        .take((SSSOM_TRANSPORT_LIMITS.max_bytes + 1) as u64)
        .read_to_end(&mut input)
        .map_err(|e| error("SSSOM_TRANSPORT", e.to_string()))?;
    if matches!(operation, ScientificJsonOperation::SourceConfig) {
        return serde_json::to_value(parse_sssom_source_config(&input)?)
            .map_err(|e| error("SSSOM_TRANSPORT", e.to_string()));
    }
    let value = parse_value_with_limits(&input, SSSOM_TRANSPORT_LIMITS)?;
    match operation {
        ScientificJsonOperation::Profile => {
            if value != serde_json::json!({}) {
                return Err(error(
                    "SSSOM_TRANSPORT",
                    "Profile expects an empty request object".into(),
                ));
            }
            Ok(
                serde_json::json!({"prefixes": builtin_prefixes(), "propagatableSlots": propagatable_slots()}),
            )
        }
        ScientificJsonOperation::SourceConfig => unreachable!(),
        ScientificJsonOperation::Parse => {
            #[derive(serde::Deserialize)]
            #[serde(deny_unknown_fields)]
            struct Request {
                input: String,
                metadata: Option<String>,
            }
            let request: Request = serde_json::from_value(value)
                .map_err(|e| error("SSSOM_DOCUMENT", e.to_string()))?;
            let decode = |v: &str| {
                if v.len() > SSSOM_MAX_BYTES.div_ceil(3) * 4 {
                    return Err(error(
                        "SSSOM_SIZE_LIMIT",
                        "SSSOM input exceeds 64 MiB".into(),
                    ));
                }
                let bytes = STANDARD
                    .decode(v)
                    .map_err(|e| error("SSSOM_TRANSPORT", e.to_string()))?;
                if bytes.len() > SSSOM_MAX_BYTES {
                    return Err(error(
                        "SSSOM_SIZE_LIMIT",
                        "SSSOM input exceeds 64 MiB".into(),
                    ));
                }
                Ok(bytes)
            };
            let source = decode(&request.input)?;
            let metadata = request.metadata.as_deref().map(decode).transpose()?;
            let checked = parse_tsv_compatible(&source, metadata.as_deref())?;
            serde_json::to_value(checked.document())
                .map_err(|e| error("SSSOM_TRANSPORT", e.to_string()))
        }
        ScientificJsonOperation::Expand => {
            #[derive(serde::Deserialize)]
            #[serde(deny_unknown_fields)]
            struct Request {
                value: String,
                prefixes: std::collections::BTreeMap<String, String>,
            }
            let request: Request = serde_json::from_value(value)
                .map_err(|e| error("SSSOM_IDENTIFIER", e.to_string()))?;
            Ok(serde_json::Value::String(expand_curie(
                &request.value,
                &request.prefixes,
            )?))
        }
        _ => {
            let document: SssomDocument = serde_json::from_value(value)
                .map_err(|e| error("SSSOM_DOCUMENT", e.to_string()))?;
            let checked = check_document_compatible(&document)?;
            match operation {
                ScientificJsonOperation::Document => serde_json::to_value(checked.document()),
                ScientificJsonOperation::Interpret => {
                    serde_json::to_value(checked.interpretation())
                }
                ScientificJsonOperation::Export => {
                    serde_json::to_value(export_tsv(&checked, condense)?)
                }
                _ => unreachable!(),
            }
            .map_err(|e| error("SSSOM_TRANSPORT", e.to_string()))
        }
    }
}
enum Failure {
    Rejected(CheckError),
    ReportedRejection,
    Operational(String),
}
impl From<CheckError> for Failure {
    fn from(e: CheckError) -> Self {
        Self::Rejected(e)
    }
}
impl From<ContractError> for Failure {
    fn from(e: ContractError) -> Self {
        Self::Rejected(CheckError::from(e))
    }
}
impl From<std::io::Error> for Failure {
    fn from(e: std::io::Error) -> Self {
        Self::Operational(e.to_string())
    }
}
impl From<serde_json::Error> for Failure {
    fn from(e: serde_json::Error) -> Self {
        Self::Operational(e.to_string())
    }
}

fn bytes(path: &Path) -> Result<Vec<u8>, Failure> {
    bytes_with_limit(path, MAX_INPUT_BYTES)
}
fn bytes_with_limit(path: &Path, maximum: usize) -> Result<Vec<u8>, Failure> {
    let mut bytes = Vec::new();
    File::open(path)?
        .take((maximum + 1) as u64)
        .read_to_end(&mut bytes)?;
    if bytes.len() > maximum {
        if maximum == MAX_INPUT_BYTES {
            return Err(ContractError::InputLimit.into());
        }
        return Err(ContractError::ScopedInputLimit { max_bytes: maximum }.into());
    }
    Ok(bytes)
}
fn read<T: DeserializeOwned>(path: &Path) -> Result<T, Failure> {
    Ok(parse(&bytes(path)?)?)
}
fn packs(paths: &[PathBuf]) -> Result<Vec<RelationPack>, Failure> {
    let mut packs = paths
        .iter()
        .map(|p| read::<RelationPack>(p))
        .collect::<Result<Vec<_>, _>>()?;
    let core: RelationPack = parse(include_bytes!("../../../relation-packs/core.json"))?;
    if !packs.iter().any(|p| p.id == core.id) {
        packs.push(core);
    }
    Ok(packs)
}
fn graph(input: &GraphInput) -> Result<CheckedGraph, Failure> {
    Ok(CheckedGraph::check(
        read(&input.graph)?,
        packs(&input.packs)?,
    )?)
}
fn options(e: &Evaluation) -> Result<EvaluationOptions, Failure> {
    let context: JsonObject = e
        .context
        .as_ref()
        .map(|p| read(p))
        .transpose()?
        .unwrap_or_default();
    Ok(EvaluationOptions {
        context,
        evaluated_at: e.evaluated_at.clone(),
    })
}
static TEMP_ID: AtomicU64 = AtomicU64::new(0);
fn write(output: &Output, bytes: &[u8]) -> Result<(), Failure> {
    write_bytes(output, bytes, true)
}
fn write_bytes(output: &Output, bytes: &[u8], newline: bool) -> Result<(), Failure> {
    write_bytes_with_limit(output, bytes, newline, MAX_INPUT_BYTES)
}
fn write_bytes_with_limit(
    output: &Output,
    bytes: &[u8],
    newline: bool,
    maximum: usize,
) -> Result<(), Failure> {
    if bytes.len().saturating_add(usize::from(newline)) > maximum {
        if maximum == MAX_INPUT_BYTES {
            return Err(ContractError::InputLimit.into());
        }
        return Err(ContractError::ScopedInputLimit { max_bytes: maximum }.into());
    }
    let Some(path) = &output.output else {
        let mut stdout = std::io::stdout().lock();
        stdout.write_all(bytes)?;
        if newline {
            stdout.write_all(b"\n")?;
        }
        return Ok(());
    };
    let parent = path
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or(Path::new("."));
    let name = path
        .file_name()
        .ok_or_else(|| Failure::Operational("Output needs a file name".into()))?
        .to_string_lossy();
    let temporary = parent.join(format!(
        ".{name}.{}.{}.tmp",
        std::process::id(),
        TEMP_ID.fetch_add(1, Ordering::Relaxed)
    ));
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&temporary)?;
    let result = (|| -> Result<(), std::io::Error> {
        file.write_all(bytes)?;
        if newline {
            file.write_all(b"\n")?;
        }
        file.sync_all()?;
        drop(file);
        if output.overwrite {
            fs::rename(&temporary, path)?;
        } else {
            fs::hard_link(&temporary, path)?;
            fs::remove_file(&temporary)?;
        }
        Ok(())
    })();
    if result.is_err() {
        let _ = fs::remove_file(&temporary);
    }
    result.map_err(Into::into)
}
fn json<T: Serialize>(output: &Output, value: &T) -> Result<(), Failure> {
    write(output, &serde_json::to_vec_pretty(value)?)
}
fn scientific_json<T: Serialize>(output: &Output, value: &T) -> Result<(), Failure> {
    let bytes = canonical_bytes(value)?;
    parse_value_with_limits(&bytes, patamaps_scientific::SSSOM_TRANSPORT_LIMITS)?;
    write_bytes_with_limit(
        output,
        &bytes,
        true,
        patamaps_scientific::SSSOM_TRANSPORT_LIMITS.max_bytes,
    )
}
fn stdout_json<T: Serialize>(value: &T) -> Result<(), Failure> {
    json(
        &Output {
            output: None,
            overwrite: false,
        },
        value,
    )
}

fn legacy_pack_output(
    operation: LegacyPackOperation,
    input: Vec<u8>,
    locale: &str,
) -> Result<(), Failure> {
    // The original digest export dispatches by version without shape parsing.
    // In particular, a caller can address an invalid executable definition
    // before asking registration to reject it. Digesting grants no validity.
    if matches!(operation, LegacyPackOperation::Digest) {
        let digest = patamaps_contracts::LegacyPackJson::parse(input, COMPATIBILITY_JSON_LIMITS)
            .and_then(|json| json.digest_bytes_for_locale(locale))
            .map(|bytes| patamaps_contracts::byte_digest(&bytes));
        return match digest {
            Ok(digest) => stdout_json(&digest),
            Err(error) => {
                stdout_json(
                    &serde_json::json!({"status":"refused","error":error.json_diagnostic(COMPATIBILITY_JSON_LIMITS)}),
                )?;
                Err(Failure::ReportedRejection)
            }
        };
    }
    let result = patamaps_core::ParsedLegacyRelationPack::parse(input);
    let parsed = match result {
        Ok(parsed) => parsed,
        Err(error) => {
            stdout_json(&serde_json::json!({"status":"refused","error":error}))?;
            return Err(Failure::ReportedRejection);
        }
    };
    match operation {
        // Preserve the original text for the host JSON.parse transport. A
        // scalar-Unicode serializer would reject valid legacy UTF-16 escapes.
        LegacyPackOperation::Parse => write_bytes_with_limit(
            &Output {
                output: None,
                overwrite: false,
            },
            parsed.document_json().as_bytes(),
            true,
            MAX_INPUT_BYTES + 1,
        ),
        LegacyPackOperation::Digest => unreachable!("digest dispatch precedes shape validation"),
        LegacyPackOperation::Import => match parsed.import_native_view() {
            Ok(imported) => stdout_json(imported.report()),
            Err(error) => {
                stdout_json(&serde_json::json!({"status":"refused","error":error}))?;
                Err(Failure::ReportedRejection)
            }
        },
    }
}

fn legacy_pack_file(operation: LegacyPackOperation, path: &Path) -> Result<(), Failure> {
    let read = || -> std::io::Result<Vec<u8>> {
        let mut bytes = Vec::new();
        File::open(path)?
            .take((MAX_INPUT_BYTES + 1) as u64)
            .read_to_end(&mut bytes)?;
        Ok(bytes)
    };
    match read() {
        Ok(bytes) => legacy_pack_output(operation, bytes, "en-US"),
        Err(error) => legacy_file_error(error, path),
    }
}

fn legacy_file_error(error: std::io::Error, path: &Path) -> Result<(), Failure> {
    use std::io::ErrorKind;
    let code = match error.kind() {
        ErrorKind::NotFound => "ENOENT",
        ErrorKind::PermissionDenied => "EACCES",
        ErrorKind::NotADirectory => "ENOTDIR",
        ErrorKind::IsADirectory => "EISDIR",
        _ if error.raw_os_error() == Some(rustix::io::Errno::LOOP.raw_os_error()) => "ELOOP",
        _ => "LEGACY_PACK_IO",
    };
    let description = match code {
        "ENOENT" => "no such file or directory",
        "EACCES" => "permission denied",
        "ENOTDIR" => "not a directory",
        "EISDIR" => "illegal operation on a directory",
        "ELOOP" => "too many symbolic links encountered",
        _ => "unmapped native filesystem error",
    };
    let syscall = if code == "EISDIR" { "read" } else { "open" };
    let message = if code == "EISDIR" {
        format!("{code}: {description}, {syscall}")
    } else {
        format!("{code}: {description}, {syscall} '{}'", path.display())
    };
    let mut report = serde_json::json!({"status":"refused","error":{
        "code":code, "message":message, "path":path,
        "errno":error.raw_os_error().map(|errno| -errno),
        "syscall":syscall, "nativeMessage":error.to_string()
    }});
    if code == "EISDIR" {
        report["error"].as_object_mut().unwrap().remove("path");
    }
    stdout_json(&report)?;
    Err(Failure::ReportedRejection)
}

#[derive(Serialize)]
struct LegacyConfigRefusal {
    status: &'static str,
    error: patamaps_scientific::LegacyConfigError,
}

fn run(command: Command) -> Result<(), Failure> {
    match command {
        Command::Legacy {
            command: LegacyCommand::Pack { operation, locale },
        } => {
            let mut input = Vec::new();
            std::io::stdin()
                .take((MAX_INPUT_BYTES + 1) as u64)
                .read_to_end(&mut input)?;
            legacy_pack_output(operation, input, &locale)
        }
        Command::Legacy {
            command: LegacyCommand::PackFile { operation, path },
        } => legacy_pack_file(operation, &path),
        Command::Legacy {
            command: LegacyCommand::Workspace { .. },
        } => {
            let mut input = Vec::new();
            std::io::stdin()
                .take((MAX_INPUT_BYTES + 1) as u64)
                .read_to_end(&mut input)?;
            let result = parse_value_with_limits(&input, COMPATIBILITY_JSON_LIMITS)
                .and_then(|v| serde_json::from_value(v).map_err(Into::into));
            let request = match result {
                Ok(v) => v,
                Err(e) => {
                    stdout_json(
                        &serde_json::json!({"status":"refused","error":{"code":"LEGACY_WORKSPACE_INPUT","name":"Error","message":e.to_string()}}),
                    )?;
                    return Err(Failure::ReportedRejection);
                }
            };
            match patamaps_workspace::legacy_workspace_request(request) {
                Ok(response) => stdout_json(&response),
                Err(error) => {
                    #[derive(Serialize)]
                    struct Refusal {
                        status: &'static str,
                        error: patamaps_core::LegacyWorkspaceError,
                    }
                    stdout_json(&Refusal {
                        status: "refused",
                        error,
                    })?;
                    Err(Failure::ReportedRejection)
                }
            }
        }
        Command::Legacy {
            command: LegacyCommand::Config { .. },
        } => {
            let mut input = Vec::new();
            std::io::stdin()
                .take((MAX_INPUT_BYTES + 1) as u64)
                .read_to_end(&mut input)?;
            let result = parse_value_with_limits(&input, COMPATIBILITY_JSON_LIMITS)
                .and_then(|v| serde_json::from_value(v).map_err(Into::into));
            let request = match result {
                Ok(v) => v,
                Err(e) => {
                    stdout_json(
                        &serde_json::json!({"status":"refused","error":{"code":"LEGACY_CONFIG_INPUT","name":"Error","message":e.to_string()}}),
                    )?;
                    return Err(Failure::ReportedRejection);
                }
            };
            match patamaps_scientific::legacy_config_request(request) {
                Ok(response) => stdout_json(&response),
                Err(error) => {
                    stdout_json(&LegacyConfigRefusal {
                        status: "refused",
                        error,
                    })?;
                    Err(Failure::ReportedRejection)
                }
            }
        }
        Command::Legacy {
            command: LegacyCommand::ConfigFile { path },
        } => {
            let path = patamaps_scientific::resolve_legacy_config_path(&path)?;
            let mut bytes = Vec::new();
            let read = File::open(&path)
                .and_then(|f| f.take((MAX_INPUT_BYTES + 1) as u64).read_to_end(&mut bytes));
            match read {
                Err(error) => legacy_file_error(error, &path),
                Ok(_) => match patamaps_scientific::load_legacy_metamap_config_bytes(&bytes, &path)
                {
                    Ok(response) => stdout_json(&response),
                    Err(error) => {
                        stdout_json(&LegacyConfigRefusal {
                            status: "refused",
                            error,
                        })?;
                        Err(Failure::ReportedRejection)
                    }
                },
            }
        }
        Command::Legacy {
            command: LegacyCommand::Registry { .. },
        } => {
            let mut input = Vec::new();
            std::io::stdin()
                .take((MAX_INPUT_BYTES + 1) as u64)
                .read_to_end(&mut input)?;
            let result = parse_value_with_limits(&input, COMPATIBILITY_JSON_LIMITS)
                .map_err(|error| patamaps_core::LegacyRegistryError {
                    code: "LEGACY_REGISTRY_INPUT".into(),
                    message: error.to_string(),
                })
                .and_then(|value| {
                    serde_json::from_value(value).map_err(|error| {
                        patamaps_core::LegacyRegistryError {
                            code: "LEGACY_REGISTRY_INPUT".into(),
                            message: error.to_string(),
                        }
                    })
                })
                .and_then(patamaps_core::legacy_registry_request);
            match result {
                Ok(response) => stdout_json(&response),
                Err(error) => {
                    stdout_json(&serde_json::json!({"status":"refused","error":error}))?;
                    Err(Failure::ReportedRejection)
                }
            }
        }
        Command::Legacy {
            command: LegacyCommand::Graph { .. },
        } => {
            let mut input = Vec::new();
            std::io::stdin()
                .take((MAX_INPUT_BYTES + 1) as u64)
                .read_to_end(&mut input)?;
            let result = parse_value_with_limits(&input, COMPATIBILITY_JSON_LIMITS)
                .map_err(|error| patamaps_core::LegacyGraphError {
                    code: "LEGACY_GRAPH_INPUT".into(),
                    name: "Error".into(),
                    message: error.to_string(),
                })
                .and_then(|value| {
                    serde_json::from_value(value).map_err(|error| patamaps_core::LegacyGraphError {
                        code: "LEGACY_GRAPH_INPUT".into(),
                        name: "Error".into(),
                        message: error.to_string(),
                    })
                })
                .and_then(patamaps_core::legacy_graph_request);
            match result {
                Ok(response) => stdout_json(&response),
                Err(error) => {
                    stdout_json(&serde_json::json!({"status":"refused","error":error}))?;
                    Err(Failure::ReportedRejection)
                }
            }
        }
        Command::Legacy {
            command: LegacyCommand::Correspondence { .. },
        } => {
            let mut input = Vec::new();
            std::io::stdin()
                .take((MAX_INPUT_BYTES + 1) as u64)
                .read_to_end(&mut input)?;
            let result = parse_value_with_limits(&input, COMPATIBILITY_JSON_LIMITS)
                .map_err(|e| patamaps_core::LegacyCorrespondenceError {
                    code: "LEGACY_CORRESPONDENCE_INPUT".into(),
                    name: "Error".into(),
                    message: e.to_string(),
                })
                .and_then(|v| {
                    serde_json::from_value(v).map_err(|e| {
                        patamaps_core::LegacyCorrespondenceError {
                            code: "LEGACY_CORRESPONDENCE_INPUT".into(),
                            name: "Error".into(),
                            message: e.to_string(),
                        }
                    })
                })
                .and_then(patamaps_core::legacy_correspondence_request);
            match result {
                Ok(response) => stdout_json(&response),
                Err(error) => {
                    stdout_json(&serde_json::json!({"status":"refused","error":error}))?;
                    Err(Failure::ReportedRejection)
                }
            }
        }
        Command::Legacy {
            command: LegacyCommand::References { .. },
        } => {
            let mut input = Vec::new();
            std::io::stdin()
                .take((MAX_INPUT_BYTES + 1) as u64)
                .read_to_end(&mut input)?;
            let result = parse_value_with_limits(&input, COMPATIBILITY_JSON_LIMITS)
                .map_err(|e| patamaps_core::LegacyReferenceError {
                    code: "LEGACY_REFERENCE_INPUT".into(),
                    name: "Error".into(),
                    message: e.to_string(),
                })
                .and_then(|v| {
                    serde_json::from_value(v).map_err(|e| patamaps_core::LegacyReferenceError {
                        code: "LEGACY_REFERENCE_INPUT".into(),
                        name: "Error".into(),
                        message: e.to_string(),
                    })
                })
                .and_then(patamaps_core::legacy_reference_request);
            match result {
                Ok(response) => stdout_json(&response),
                Err(error) => {
                    stdout_json(&serde_json::json!({"status":"refused","error":error}))?;
                    Err(Failure::ReportedRejection)
                }
            }
        }
        Command::Legacy {
            command: LegacyCommand::Reporting { .. },
        } => {
            let mut input = Vec::new();
            std::io::stdin()
                .take((MAX_INPUT_BYTES + 1) as u64)
                .read_to_end(&mut input)?;
            let result = parse_value_with_limits(&input, COMPATIBILITY_JSON_LIMITS)
                .map_err(|e| patamaps_core::LegacyReportingError {
                    code: "LEGACY_REPORTING_INPUT".into(),
                    name: "Error".into(),
                    message: e.to_string(),
                })
                .and_then(|v| {
                    serde_json::from_value(v).map_err(|e| patamaps_core::LegacyReportingError {
                        code: "LEGACY_REPORTING_INPUT".into(),
                        name: "Error".into(),
                        message: e.to_string(),
                    })
                })
                .and_then(patamaps_core::legacy_reporting_request);
            match result {
                Ok(response) => {
                    // This read-only response carries JSON-escaped UTF-16 code
                    // units. Converting through scalar Value would lose them.
                    let bytes = serde_json::to_vec(&response)?;
                    write_bytes(
                        &Output {
                            output: None,
                            overwrite: false,
                        },
                        &bytes,
                        true,
                    )
                }
                Err(error) => {
                    stdout_json(&serde_json::json!({"status":"refused","error":error}))?;
                    Err(Failure::ReportedRejection)
                }
            }
        }
        Command::Legacy {
            command: LegacyCommand::Compose { .. },
        } => {
            let mut input = Vec::new();
            std::io::stdin()
                .take((MAX_INPUT_BYTES + 1) as u64)
                .read_to_end(&mut input)?;
            let result = parse_value_with_limits(&input, COMPATIBILITY_JSON_LIMITS)
                .map_err(|e| patamaps_core::LegacyCompositionError {
                    code: "LEGACY_COMPOSITION_INPUT".into(),
                    name: "Error".into(),
                    message: e.to_string(),
                    identifier: None,
                })
                .and_then(|v| {
                    serde_json::from_value(v).map_err(|e| patamaps_core::LegacyCompositionError {
                        code: "LEGACY_COMPOSITION_INPUT".into(),
                        name: "Error".into(),
                        message: e.to_string(),
                        identifier: None,
                    })
                })
                .and_then(patamaps_core::compose_legacy_documents);
            match result {
                Ok(response) => stdout_json(&response),
                Err(error) => {
                    stdout_json(&serde_json::json!({"status":"refused","error":error}))?;
                    Err(Failure::ReportedRejection)
                }
            }
        }
        Command::Legacy {
            command: LegacyCommand::Json { operation },
        } => {
            let mut input = Vec::new();
            std::io::stdin()
                .take((MAX_INPUT_BYTES + 1) as u64)
                .read_to_end(&mut input)?;
            let request = match parse_value_with_limits(&input, COMPATIBILITY_JSON_LIMITS) {
                Ok(value) => value,
                Err(error) => {
                    stdout_json(
                        &serde_json::json!({"status":"refused","error":error.json_diagnostic(COMPATIBILITY_JSON_LIMITS)}),
                    )?;
                    return Err(Failure::ReportedRejection);
                }
            };
            if !request.is_object()
                || request
                    .as_object()
                    .unwrap()
                    .keys()
                    .any(|key| key != "document" && key != "packs" && key != "legacyPacks")
                || request.get("document").is_none()
                || (request.get("packs").is_some() && request.get("legacyPacks").is_some())
            {
                stdout_json(
                    &serde_json::json!({"status":"refused","error":{"code":"LEGACY_REQUEST","message":"Expected a document and either native draft packs or portable legacy packs"}}),
                )?;
                return Err(Failure::ReportedRejection);
            }
            if matches!(operation, LegacyJsonOperation::Shape) {
                return stdout_json(&patamaps_core::validate_legacy_document_shape(
                    &request["document"],
                ));
            }
            let registry = if let Some(packs) = request.get("packs") {
                match serde_json::from_value::<Vec<RelationPack>>(packs.clone()) {
                    Ok(packs) => patamaps_core::RelationRegistry::new(packs),
                    Err(error) => {
                        stdout_json(
                            &serde_json::json!({"status":"refused","error":{"code":"LEGACY_REGISTRY_INPUT","message":error.to_string()}}),
                        )?;
                        return Err(Failure::ReportedRejection);
                    }
                }
            } else if let Some(packs) = request.get("legacyPacks") {
                let Some(packs) = packs.as_array() else {
                    stdout_json(
                        &serde_json::json!({"status":"refused","error":{"code":"LEGACY_REGISTRY_INPUT","message":"Legacy packs must be an array"}}),
                    )?;
                    return Err(Failure::ReportedRejection);
                };
                patamaps_core::RelationRegistry::from_legacy_packs(packs.iter().cloned())
            } else {
                patamaps_core::RelationRegistry::with_legacy_core()
            };
            match registry {
                Ok(registry) => stdout_json(&patamaps_core::validate_legacy_document(
                    &request["document"],
                    &registry,
                )),
                Err(error) => {
                    stdout_json(&serde_json::json!({"status":"refused","issues":error.0}))?;
                    Err(Failure::ReportedRejection)
                }
            }
        }
        Command::Json { operation } => {
            let mut input = Vec::new();
            std::io::stdin()
                .take((MAX_INPUT_BYTES + 1) as u64)
                .read_to_end(&mut input)?;
            let value = match parse_value_with_limits(&input, COMPATIBILITY_JSON_LIMITS) {
                Ok(value) => value,
                Err(error) => {
                    stdout_json(
                        &serde_json::json!({"status":"refused","error":error.json_diagnostic(COMPATIBILITY_JSON_LIMITS)}),
                    )?;
                    return Err(Failure::ReportedRejection);
                }
            };
            match operation {
                JsonOperation::Canonical | JsonOperation::Parse => write(
                    &Output {
                        output: None,
                        overwrite: false,
                    },
                    &canonical_bytes(&value)?,
                ),
                JsonOperation::Digest => stdout_json(&canonical_digest(&value)?),
            }
        }
        Command::Sssom { command } => match command {
            ScientificCommand::Json {
                operation,
                condense,
            } => {
                let output = Output {
                    output: None,
                    overwrite: false,
                };
                match scientific_operation(operation, condense) {
                    Ok(value) => scientific_json(&output, &value),
                    Err(error) => {
                        stdout_json(
                            &serde_json::json!({"status":"refused","error":{"code":error.code,"message":error.message}}),
                        )?;
                        Err(Failure::ReportedRejection)
                    }
                }
            }
            ScientificCommand::Crate {
                capture,
                options,
                output,
            } => {
                let capture = read::<CaptureRecord>(&capture)?;
                let options = read::<patamaps_scientific::CrateOptions>(&options)?;
                let result = patamaps_scientific::create_crate(&capture, &options)
                    .map_err(|e| Failure::Operational(e.to_string()))?;
                json(&output, &result)
            }
            ScientificCommand::VerifyCrate { input, output } => {
                let input = read::<patamaps_scientific::ScientificCrate>(&input)?;
                let verified = patamaps_scientific::verify_crate(&input)
                    .map_err(|e| Failure::Operational(e.to_string()))?;
                json(
                    &output,
                    &serde_json::json!({"status":"verified", "profile":"urn:patamaps:scientific-crate:draft:1", "engine":patamaps_scientific::scientific_engine_id(), "files":verified.record().files.len(), "externalRawInputs":verified.external_raw_inputs(), "scientificTruth":"not-established", "authorization":"not-evaluated", "activation":"not-evaluated"}),
                )
            }
            ScientificCommand::Import {
                input,
                source_config,
                metadata,
                output,
            } => {
                let options: patamaps_scientific::ImportOptions = read(&source_config)?;
                let raw = bytes_with_limit(&input, patamaps_scientific::SSSOM_MAX_BYTES)?;
                let external = metadata
                    .as_ref()
                    .map(|p| bytes_with_limit(p, patamaps_scientific::SSSOM_MAX_BYTES))
                    .transpose()?;
                let checked = patamaps_scientific::parse_tsv_compatible(&raw, external.as_deref())
                    .map_err(|e| Failure::Operational(e.to_string()))?;
                let graph = patamaps_scientific::import_graph(&checked, &options)
                    .map_err(|e| Failure::Operational(e.to_string()))?;
                let mut sources = Vec::new();
                for (kind, raw) in std::iter::once(("tsv", raw.as_slice()))
                    .chain(external.as_deref().map(|v| ("metadata", v)))
                {
                    sources.push(SourceReceipt {
                        id: format!("{}:{kind}", options.id),
                        locator: format!("urn:patamaps:provided-source:{kind}"),
                        digest: patamaps_contracts::byte_digest(raw),
                        byte_length: patamaps_contracts::SafeInteger::new(raw.len() as u64)
                            .expect("bounded input bytes"),
                        content: Some(
                            String::from_utf8(raw.to_vec())
                                .expect("scientific parser checked UTF-8"),
                        ),
                    });
                }
                scientific_json(
                    &output,
                    &serde_json::json!({"schemaVersion":"0.1.0","documentType":"scientific-import","profile":"patamaps-scientific-draft-1","sourceOptions":options,"status":"source-imported","scientificTruth":"not-established","document":checked.document(),"interpretation":checked.interpretation(),"graph":graph,"pack":patamaps_scientific::scientific_pack(),"sources":sources}),
                )
            }
            ScientificCommand::Export {
                document,
                condense,
                output,
            } => {
                let document: patamaps_scientific::SssomDocument =
                    patamaps_contracts::parse_with_limits(
                        &bytes_with_limit(&document, patamaps_scientific::SSSOM_MAX_BYTES)?,
                        patamaps_scientific::SSSOM_COMPATIBILITY_LIMITS,
                    )?;
                let checked = patamaps_scientific::check_document_compatible(&document)
                    .map_err(|e| Failure::Operational(e.to_string()))?;
                let exported = patamaps_scientific::export_tsv(&checked, condense)
                    .map_err(|e| Failure::Operational(e.to_string()))?;
                scientific_json(&output, &exported)
            }
        },
        Command::Engine => stdout_json(
            &serde_json::json!({"schemaVersion":"0.1.0","documentType":"executor-description","compiler":patamaps_projection::executor_id(),"governance":patamaps_governance::governance_executor_id(),"workspace":patamaps_workspace::engine_id(),"scientific":patamaps_scientific::scientific_engine_id()}),
        ),
        Command::Generate {
            config,
            root,
            cache,
            output,
        } => {
            let config = read::<patamaps_workspace::WorkspaceConfig>(&config)?;
            let result = patamaps_workspace::generate(&root, &config, cache.as_deref())
                .map_err(|error| Failure::Operational(error.to_string()))?;
            json(&output, &result)?;
            if result.baseline.captures.iter().any(|c| {
                c.result.get("status").and_then(serde_json::Value::as_str) != Some("viable")
            }) {
                return Err(Failure::Operational(
                    "WORKSPACE_REJECTED: captured evaluation rejected".into(),
                ));
            }
            Ok(())
        }
        Command::Check {
            config,
            baseline,
            root,
            cache,
            output,
        } => {
            let config = read::<patamaps_workspace::WorkspaceConfig>(&config)?;
            let baseline = read::<patamaps_workspace::WorkspaceBaseline>(&baseline)?;
            let report = patamaps_workspace::check(&root, &config, &baseline, cache.as_deref())
                .map_err(|error| Failure::Operational(error.to_string()))?;
            json(&output, &report)?;
            if report.status != "unchanged" {
                return Err(Failure::Operational(format!(
                    "WORKSPACE_{}",
                    report.status.to_uppercase()
                )));
            }
            Ok(())
        }
        Command::Repair {
            request,
            cancel_after_ms,
            output,
        } => {
            let token = patamaps_core::CancellationToken::default();
            if let Some(milliseconds) = cancel_after_ms {
                let signal = token.clone();
                std::thread::spawn(move || {
                    std::thread::sleep(std::time::Duration::from_millis(milliseconds));
                    signal.cancel();
                });
            }
            json(
                &output,
                &patamaps_inspect::search_repairs(&read(&request)?, token)?,
            )
        }
        Command::Inspect {
            capture,
            before,
            subject,
            mapping,
            html,
            maximum_subjects,
            maximum_mappings,
            output,
        } => {
            let capture: CaptureRecord = read(&capture)?;
            let before: Option<CaptureRecord> = before.as_ref().map(|p| read(p)).transpose()?;
            let report = patamaps_inspect::explain(
                &capture,
                before.as_ref(),
                patamaps_inspect::InspectionSelection {
                    kind: if mapping {
                        patamaps_inspect::SelectionKind::Mapping
                    } else {
                        patamaps_inspect::SelectionKind::Entity
                    },
                    id: subject,
                },
                maximum_subjects,
                maximum_mappings,
            )?;
            if html {
                write(
                    &output,
                    patamaps_inspect::render_debugger(&report)?.as_bytes(),
                )
            } else {
                json(&output, &report)
            }
        }
        Command::Propose {
            captures,
            trust,
            baseline,
            consumer,
            environment,
            proposer,
            intent,
            emissions,
            output,
        } => {
            let trust: TrustedConsumer = read(&trust)?;
            let baseline = baseline
                .as_ref()
                .map(|p| read::<GovernedBaseline>(p))
                .transpose()?;
            let candidate = GovernedCandidate {
                captures: captures
                    .iter()
                    .map(|p| read::<CaptureRecord>(p))
                    .collect::<Result<Vec<_>, _>>()?,
                emissions: emissions
                    .as_ref()
                    .map(|p| read::<Vec<ArtifactEmission>>(p))
                    .transpose()?
                    .unwrap_or_default(),
            };
            let proposal = create_proposal(
                &candidate,
                ProposalOptions {
                    consumer: &consumer,
                    environment: &environment,
                    proposer: &proposer,
                    intent: match intent {
                        Intent::Deploy => DeploymentIntent::Deploy,
                        Intent::Rollback => DeploymentIntent::Rollback,
                    },
                    trust: &trust,
                    baseline: baseline.as_ref(),
                },
            )?;
            write(&output, &canonical_bytes(&proposal.prepared())?)
        }
        Command::ApprovalPayload {
            prepared,
            principal,
            key,
            grants,
            issued_at,
            expires_at,
            output,
        } => {
            let prepared: PreparedCandidate = read(&prepared)?;
            let proposal = check_prepared(&prepared)?;
            let payload = create_approval_payload(
                &proposal,
                ApprovalOptions {
                    principal: &principal,
                    key: &key,
                    grants: &grants,
                    issued_at: &issued_at,
                    expires_at: &expires_at,
                },
            )?;
            write_bytes(&output, &approval_signing_bytes(&payload)?, false)
        }
        Command::AttachSignature {
            payload,
            signature,
            output,
        } => {
            let payload: ApprovalPayload = read(&payload)?;
            let signature: String = read(&signature)?;
            let approval = attach_signature(payload, &signature)?;
            write(&output, &canonical_bytes(&approval)?)
        }
        Command::VerifyApproval {
            prepared,
            approval,
            trust,
            baseline,
            now,
            output,
        } => {
            let prepared: PreparedCandidate = read(&prepared)?;
            let proposal = check_prepared(&prepared)?;
            let approval: SignedApproval = read(&approval)?;
            let trust: TrustedConsumer = read(&trust)?;
            let baseline = baseline
                .as_ref()
                .map(|p| read::<GovernedBaseline>(p))
                .transpose()?;
            let authorized = verify_approval(
                &proposal,
                &approval,
                VerificationContext {
                    trust: &trust,
                    baseline: baseline.as_ref(),
                    now: &now,
                },
            )?;
            write(&output, &canonical_bytes(authorized.record())?)
        }
        Command::PathTree {
            input,
            policy,
            spec,
            evaluation,
            parameters,
            output,
        } => {
            let graph = graph(&input)?;
            let policy: PolicyDocument = read(&policy)?;
            let spec: ProjectionSpec = read(&spec)?;
            let generation = admit(&graph, &policy, options(&evaluation)?)?;
            let projection = project(&generation, &spec)?;
            let tree = compile_path_tree(&projection, &spec)?;
            match parameters {
                Some(path) => json(&output, &hydrate(&tree, read(&path)?)?),
                None => json(&output, tree.record()),
            }
        }
        Command::Derive {
            input,
            request,
            output,
        } => {
            let outcome = derive(&graph(&input)?, &read::<CompositionRequest>(&request)?);
            json(&output, &outcome)?;
            if outcome.status == DerivationStatus::Proposed {
                Ok(())
            } else {
                Err(Failure::ReportedRejection)
            }
        }
        Command::Validate { input } => {
            let graph = graph(&input)?;
            stdout_json(
                &serde_json::json!({"status":"valid","graph":graph.digest(),"issues":graph.issues()}),
            )
        }
        Command::Compose {
            shards,
            id,
            namespace,
            packs: paths,
            output,
        } => {
            let shards = shards
                .iter()
                .map(|p| read::<GraphDocument>(p))
                .collect::<Result<Vec<_>, _>>()?;
            let checked = CheckedGraph::check(compose(&shards, id, namespace)?, packs(&paths)?)?;
            json(&output, checked.document())
        }
        Command::Authority {
            input,
            concept,
            fact,
        } => stdout_json(&graph(&input)?.resolve_authority(&concept, &fact)),
        Command::Trace {
            input,
            subject,
            direction,
            depth,
            relations,
        } => {
            let direction = match direction {
                TraceDirection::Forward => Direction::Outgoing,
                TraceDirection::Reverse => Direction::Incoming,
                TraceDirection::Both => Direction::Both,
            };
            stdout_json(&graph(&input)?.trace(&subject, direction, depth, &relations)?)
        }
        Command::Compile {
            input,
            policy,
            evaluation,
            output,
        } => {
            let graph = graph(&input)?;
            let policy: PolicyDocument = read(&policy)?;
            let generation = admit(&graph, &policy, options(&evaluation)?)?;
            json(&output, generation.record())
        }
        Command::Link {
            input,
            policy,
            spec,
            evaluation,
            generation,
            format,
            export,
            binding_slot,
            output,
        } => {
            let graph = graph(&input)?;
            let policy: PolicyDocument = read(&policy)?;
            let spec: ProjectionSpec = read(&spec)?;
            let admitted = admit(&graph, &policy, options(&evaluation)?)?;
            if let Some(path) = generation {
                let supplied = parse_value(&bytes(&path)?)?;
                if canonical_bytes(&supplied)? != canonical_bytes(admitted.record())? {
                    return Err(CheckError(vec![Issue::error(
                        "PROJECTION_GENERATION_RECHECK_FAILED",
                        "Saved generation differs from fresh evaluation",
                        path.to_string_lossy(),
                    )])
                    .into());
                }
            }
            let projection = project(&admitted, &spec)?;
            match format {
                Format::Json => json(&output, projection.record()),
                Format::Rust => write(
                    &output,
                    emit_rust(&projection, binding_slot.as_deref())?.as_bytes(),
                ),
                Format::Typescript => write(
                    &output,
                    emit_typescript(&projection, &export, binding_slot.as_deref())?.as_bytes(),
                ),
            }
        }
        Command::Canonical { input, output } => write(
            &output,
            &canonical_bytes(&parse_value_with_limits(
                &bytes(&input)?,
                COMPATIBILITY_JSON_LIMITS,
            )?)?,
        ),
        Command::Capture {
            input,
            policy,
            spec,
            source_receipts,
            evaluation,
            output,
        } => {
            let options = options(&evaluation)?;
            let inputs = CaptureInputs {
                projection_specs: if spec.len() > 1 {
                    spec.iter().map(|p| read(p)).collect::<Result<_, _>>()?
                } else {
                    vec![]
                },
                graph: read(&input.graph)?,
                packs: packs(&input.packs)?,
                policy: read(&policy)?,
                context: options.context,
                evaluated_at: options.evaluated_at,
                projection_spec: if spec.len() == 1 {
                    Some(read(&spec[0])?)
                } else {
                    None
                },
            };
            let sources: Vec<SourceReceipt> = source_receipts
                .as_ref()
                .map(|p| read(p))
                .transpose()?
                .unwrap_or_default();
            json(&output, &capture(inputs, sources)?)
        }
        Command::Replay { input } => {
            let record: CaptureRecord = read(&input)?;
            let verified = replay(&record)?;
            stdout_json(
                &serde_json::json!({"status":"verified","capture":record.digest,"result":verified.result(),"missingSources":verified.missing_sources()}),
            )
        }
        Command::Compare {
            before,
            after,
            output,
        } => {
            let before: CaptureRecord = read(&before)?;
            let after: CaptureRecord = read(&after)?;
            json(&output, &compare(&replay(&before)?, &replay(&after)?)?)
        }
        Command::Diff {
            before,
            after,
            output,
        } => json(
            &output,
            &patamaps_core::diff(&read(&before)?, &read(&after)?)?,
        ),
    }
}
fn main() {
    let code = match run(Cli::parse().command) {
        Ok(()) => 0,
        Err(Failure::Rejected(error)) => {
            if stdout_json(&serde_json::json!({"status":"rejected","issues":error.0})).is_err() {
                eprintln!("Could not write rejection report");
            }
            1
        }
        Err(Failure::Operational(message)) => {
            eprintln!("patamaps: {message}");
            2
        }
        Err(Failure::ReportedRejection) => 1,
    };
    std::process::exit(code);
}
