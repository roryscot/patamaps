use clap::{Args, Parser, Subcommand, ValueEnum};
use patamaps_contracts::{
    CompositionRequest, ContractError, GraphDocument, JsonObject, MAX_INPUT_BYTES, PolicyDocument,
    ProjectionSpec, RelationPack, canonical_bytes, parse, parse_value,
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
    /// Source-preserving scientific syntax/profile operations; imports stay unadmitted.
    Sssom {
        #[command(subcommand)]
        command: ScientificCommand,
    },
    /// Describe installed source identities; this does not authenticate a binary.
    Engine,
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
        spec: Option<PathBuf>,
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
enum ScientificCommand {
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
    let mut bytes = Vec::new();
    File::open(path)?
        .take((MAX_INPUT_BYTES + 1) as u64)
        .read_to_end(&mut bytes)?;
    if bytes.len() > MAX_INPUT_BYTES {
        return Err(ContractError::InputLimit.into());
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
    if bytes.len().saturating_add(usize::from(newline)) > MAX_INPUT_BYTES {
        return Err(ContractError::InputLimit.into());
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
fn stdout_json<T: Serialize>(value: &T) -> Result<(), Failure> {
    json(
        &Output {
            output: None,
            overwrite: false,
        },
        value,
    )
}
fn run(command: Command) -> Result<(), Failure> {
    match command {
        Command::Sssom { command } => match command {
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
                    &serde_json::json!({"status":"verified", "profile":"urn:patamaps:scientific-crate:draft:1", "engine":patamaps_scientific::scientific_engine_id(), "files":verified.record().files.len(), "scientificTruth":"not-established", "authorization":"not-evaluated", "activation":"not-evaluated"}),
                )
            }
            ScientificCommand::Import {
                input,
                source_config,
                metadata,
                output,
            } => {
                let options: patamaps_scientific::ImportOptions = read(&source_config)?;
                let raw = bytes(&input)?;
                let external = metadata.as_ref().map(|p| bytes(p)).transpose()?;
                let checked = patamaps_scientific::parse_tsv(&raw, external.as_deref())
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
                json(
                    &output,
                    &serde_json::json!({"schemaVersion":"0.1.0","documentType":"scientific-import","profile":"patamaps-scientific-draft-1","sourceOptions":options,"status":"source-imported","scientificTruth":"not-established","document":checked.document(),"interpretation":checked.interpretation(),"graph":graph,"pack":patamaps_scientific::scientific_pack(),"sources":sources}),
                )
            }
            ScientificCommand::Export {
                document,
                condense,
                output,
            } => {
                let document: patamaps_scientific::SssomDocument = read(&document)?;
                let checked = patamaps_scientific::check_document(&document)
                    .map_err(|e| Failure::Operational(e.to_string()))?;
                let exported = patamaps_scientific::export_tsv(&checked, condense)
                    .map_err(|e| Failure::Operational(e.to_string()))?;
                json(&output, &exported)
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
        Command::Canonical { input, output } => {
            write(&output, &canonical_bytes(&parse_value(&bytes(&input)?)?)?)
        }
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
                graph: read(&input.graph)?,
                packs: packs(&input.packs)?,
                policy: read(&policy)?,
                context: options.context,
                evaluated_at: options.evaluated_at,
                projection_spec: spec.as_ref().map(|p| read(p)).transpose()?,
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
