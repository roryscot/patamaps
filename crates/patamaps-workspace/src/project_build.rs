//! Retained local build selection. This never activates a deployment or trust state.
use crate::{Error, ProjectCommand, ProjectProfile, WorkspaceConfig};
use serde::{Deserialize, Serialize};

pub const PROJECT_BUILD_PROFILE: &str = "patamaps-project-build-1";
#[derive(Debug, Clone, Copy, Deserialize, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum ArtifactKind {
    File,
    Tree,
}
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ArtifactSelection {
    pub path: String,
    pub kind: ArtifactKind,
}
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ProjectBuildPlan {
    pub profile: String,
    pub project: ProjectProfile,
    pub workspace: WorkspaceConfig,
    pub build_steps: Vec<ProjectCommand>,
    pub verification_steps: Vec<ProjectCommand>,
    pub outputs: Vec<ArtifactSelection>,
}

#[cfg(unix)]
mod unix {
    use super::*;
    use crate::{
        InputReceipt, ProjectCapture, Source, SuppliedInput, WorkspaceBaseline, capture_project,
        execute_project_command, generate, relative_path, stage_project_capture, verify_baseline,
        verify_project_capture,
    };
    use patamaps_contracts::{
        MAX_INPUT_BYTES, SafeInteger, byte_digest, canonical_bytes, canonical_digest, parse,
    };
    use serde_json::{Value, json};
    use sha2::{Digest, Sha256};
    use std::{
        collections::{BTreeMap, BTreeSet},
        fs::{self, File, OpenOptions},
        io::{Read, Write},
        os::unix::fs::{DirBuilderExt, MetadataExt, OpenOptionsExt},
        path::Path,
        time::{Instant, SystemTime, UNIX_EPOCH},
    };

    fn refuse(code: &'static str) -> Error {
        Error::refused(code, "Retained project build refused")
    }
    fn write_new(path: &Path, value: &impl Serialize) -> Result<(), Error> {
        let bytes = canonical_bytes(value)?;
        if bytes.len() >= MAX_INPUT_BYTES {
            return Err(refuse("PROJECT_BUILD_RECORD_LIMIT"));
        }
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .open(path)?;
        file.write_all(&bytes)?;
        file.sync_all()?;
        Ok(())
    }
    fn read_bytes(root: &Path, name: &str) -> Result<Vec<u8>, Error> {
        let file = crate::project::open_project_file(&File::open(root)?, name)?;
        let mut bytes = Vec::new();
        file.take((MAX_INPUT_BYTES + 1) as u64)
            .read_to_end(&mut bytes)?;
        if bytes.len() >= MAX_INPUT_BYTES {
            return Err(refuse("PROJECT_BUILD_RECORD_LIMIT"));
        }
        Ok(bytes)
    }
    fn read<T: serde::de::DeserializeOwned>(root: &Path, name: &str) -> Result<T, Error> {
        Ok(parse(&read_bytes(root, name)?)?)
    }
    fn directory(path: &Path) -> Result<(), Error> {
        if !path.exists() {
            let mut builder = fs::DirBuilder::new();
            builder.mode(0o700);
            builder.create(path)?;
        }
        let meta = fs::symlink_metadata(path)?;
        if meta.file_type().is_symlink() || !meta.is_dir() {
            return Err(refuse("PROJECT_BUILD_DIRECTORY"));
        }
        Ok(())
    }
    fn validate(plan: &ProjectBuildPlan) -> Result<(), Error> {
        plan.project.validate()?;
        if plan.profile != PROJECT_BUILD_PROFILE
            || !(1..=32).contains(&plan.build_steps.len())
            || !(1..=32).contains(&plan.verification_steps.len())
            || !(1..=64).contains(&plan.outputs.len())
        {
            return Err(refuse("PROJECT_BUILD_PLAN"));
        }
        let mut paths = BTreeSet::new();
        for output in &plan.outputs {
            if !relative_path(&output.path) || !paths.insert(output.path.as_str()) {
                return Err(refuse("PROJECT_BUILD_OUTPUT_PATH"));
            }
        }
        if paths
            .iter()
            .any(|p| p.match_indices('/').any(|(i, _)| paths.contains(&p[..i])))
        {
            return Err(refuse("PROJECT_BUILD_OUTPUT_OVERLAP"));
        }
        Ok(())
    }
    fn tools(plan: &ProjectBuildPlan) -> Result<BTreeMap<String, Value>, Error> {
        let mut names = BTreeSet::new();
        for command in plan.build_steps.iter().chain(&plan.verification_steps) {
            names.insert(command.invocation.executable.clone());
        }
        for source in &plan.workspace.sources {
            if let Source::Process { invocation, .. } = source {
                names.insert(invocation.executable.clone());
            }
        }
        names
            .into_iter()
            .map(|name| {
                if !Path::new(&name).is_absolute() {
                    return Err(refuse("PROJECT_BUILD_EXECUTABLE"));
                }
                let resolved = Path::new(&name).canonicalize()?;
                if resolved.to_str().is_none() {
                    return Err(refuse("PROJECT_BUILD_EXECUTABLE"));
                }
                let digest = crate::hash_executable(&resolved)?;
                Ok((name, json!({"resolved":resolved,"digest":digest})))
            })
            .collect()
    }
    fn merged(
        source: &ProjectCapture,
        baseline: &WorkspaceBaseline,
    ) -> Result<(ProjectProfile, Vec<SuppliedInput>), Error> {
        let mut definition = source.definition.clone();
        let mut inputs = source.inputs.clone();
        let mut paths = definition.inputs.iter().cloned().collect::<BTreeSet<_>>();
        for (path, content) in &baseline.outputs {
            if !paths.insert(path.clone()) {
                return Err(refuse("PROJECT_BUILD_OUTPUT_SOURCE_COLLISION"));
            }
            definition.inputs.push(path.clone());
            inputs.push(SuppliedInput {
                receipt: InputReceipt {
                    path: path.clone(),
                    digest: byte_digest(content.as_bytes()),
                    byte_length: SafeInteger::new(content.len() as u64).expect("bounded output"),
                },
                content: content.clone(),
            });
        }
        definition.validate()?;
        inputs.sort_by(|a, b| a.receipt.path.cmp(&b.receipt.path));
        Ok((definition, inputs))
    }
    fn fingerprint_file(root: &File, path: &str, total: &mut u64) -> Result<Value, Error> {
        let mut file = crate::project::open_project_file(root, path)?;
        let before = file.metadata()?;
        if before.len() > 4 * 1024 * 1024 * 1024 {
            return Err(refuse("PROJECT_BUILD_ARTIFACT_LIMIT"));
        }
        let mut hash = Sha256::new();
        let mut buffer = [0u8; 65536];
        let mut count = 0u64;
        loop {
            let n = file.read(&mut buffer)?;
            if n == 0 {
                break;
            }
            count += n as u64;
            if count > 4 * 1024 * 1024 * 1024 {
                return Err(refuse("PROJECT_BUILD_ARTIFACT_LIMIT"));
            }
            hash.update(&buffer[..n]);
        }
        let after = file.metadata()?;
        if (
            before.dev(),
            before.ino(),
            before.len(),
            before.mtime(),
            before.mtime_nsec(),
            before.mode(),
        ) != (
            after.dev(),
            after.ino(),
            after.len(),
            after.mtime(),
            after.mtime_nsec(),
            after.mode(),
        ) || count != after.len()
        {
            return Err(refuse("PROJECT_BUILD_ARTIFACT_CHANGED"));
        }
        *total = total
            .checked_add(count)
            .ok_or_else(|| refuse("PROJECT_BUILD_ARTIFACT_LIMIT"))?;
        if *total > 16 * 1024 * 1024 * 1024 {
            return Err(refuse("PROJECT_BUILD_ARTIFACT_LIMIT"));
        }
        Ok(
            json!({"kind":"file","bytes":count,"mode":after.mode()&0o7777,"digest":format!("sha256:{:x}",hash.finalize())}),
        )
    }
    fn tree(
        root_path: &Path,
        root: &File,
        path: &str,
        depth: usize,
        entries: &mut BTreeMap<String, Value>,
        total: &mut u64,
    ) -> Result<(), Error> {
        if depth > 128 || entries.len() >= 32768 {
            return Err(refuse("PROJECT_BUILD_ARTIFACT_LIMIT"));
        }
        crate::project_command::directory(root_path, path)?;
        let meta = fs::symlink_metadata(root_path.join(path))?;
        entries.insert(
            path.into(),
            json!({"kind":"directory","mode":meta.mode()&0o7777}),
        );
        let mut children = fs::read_dir(root_path.join(path))?.collect::<Result<Vec<_>, _>>()?;
        children.sort_by_key(|a| a.file_name());
        for entry in children {
            let name = entry
                .file_name()
                .into_string()
                .map_err(|_| refuse("PROJECT_BUILD_OUTPUT_PATH"))?;
            let relative = format!("{path}/{name}");
            if !relative_path(&relative) || entries.len() >= 32768 {
                return Err(refuse("PROJECT_BUILD_ARTIFACT_LIMIT"));
            }
            let meta = fs::symlink_metadata(entry.path())?;
            if meta.file_type().is_symlink() {
                return Err(refuse("PROJECT_BUILD_OUTPUT_SYMLINK"));
            }
            if meta.is_dir() {
                tree(root_path, root, &relative, depth + 1, entries, total)?;
            } else {
                entries.insert(relative.clone(), fingerprint_file(root, &relative, total)?);
            }
        }
        Ok(())
    }
    fn artifacts(
        root_path: &Path,
        outputs: &[ArtifactSelection],
    ) -> Result<BTreeMap<String, Value>, Error> {
        let root = File::open(root_path)?;
        let mut entries = BTreeMap::new();
        let mut total = 0u64;
        for output in outputs {
            match output.kind {
                ArtifactKind::File => {
                    entries.insert(
                        output.path.clone(),
                        fingerprint_file(&root, &output.path, &mut total)?,
                    );
                }
                ArtifactKind::Tree => {
                    tree(root_path, &root, &output.path, 0, &mut entries, &mut total)?
                }
            }
        }
        if canonical_bytes(&entries)?.len() >= MAX_INPUT_BYTES {
            return Err(refuse("PROJECT_BUILD_RECORD_LIMIT"));
        }
        Ok(entries)
    }
    #[derive(Deserialize, Serialize)]
    #[serde(rename_all = "camelCase", deny_unknown_fields)]
    struct Selection {
        profile: String,
        input_key: String,
        attempt: String,
        receipt_digest: String,
        artifacts_digest: String,
        digest: String,
    }
    fn address(selection: &Selection) -> Result<String, Error> {
        let mut value = serde_json::to_value(selection).expect("typed selection");
        value.as_object_mut().unwrap().remove("digest");
        Ok(canonical_digest(&value)?)
    }
    fn selected_bytes(state: &Path) -> Result<Option<Vec<u8>>, Error> {
        match fs::symlink_metadata(state.join("selected.json")) {
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(None),
            Err(e) => Err(e.into()),
            Ok(_) => Ok(Some(read_bytes(state, "selected.json")?)),
        }
    }
    fn selection(raw: &[u8]) -> Result<Selection, Error> {
        let result: Selection = parse(raw)?;
        if result.profile != "patamaps-project-build-selection-1"
            || !relative_path(&result.attempt)
            || !result.attempt.starts_with("attempts/")
            || result.attempt.split('/').count() != 2
            || result.digest != address(&result)?
        {
            return Err(refuse("PROJECT_BUILD_SELECTION_BINDING"));
        }
        Ok(result)
    }
    pub fn verify_project_build_selection(state: &Path) -> Result<Value, Error> {
        if fs::symlink_metadata(state)?.file_type().is_symlink() {
            return Err(refuse("PROJECT_BUILD_DIRECTORY"));
        }
        let raw = selected_bytes(state)?.ok_or_else(|| refuse("PROJECT_BUILD_NO_SELECTION"))?;
        let selected = selection(&raw)?;
        crate::project_command::directory(state, &selected.attempt)?;
        let attempt = state.join(&selected.attempt);
        let receipt_raw = read_bytes(&attempt, "receipt.json")?;
        if byte_digest(&receipt_raw) != selected.receipt_digest {
            return Err(refuse("PROJECT_BUILD_SELECTION_BINDING"));
        }
        let receipt: Value = parse(&receipt_raw)?;
        let plan: ProjectBuildPlan = read(&attempt, "plan.json")?;
        validate(&plan)?;
        let source: ProjectCapture = read(&attempt, "source-capture.json")?;
        verify_project_capture(&source)?;
        let baseline: WorkspaceBaseline = read(&attempt, "workspace-baseline.json")?;
        verify_baseline(&baseline)?;
        let candidate: ProjectCapture = read(&attempt, "candidate-capture.json")?;
        verify_project_capture(&candidate)?;
        let (definition, inputs) = merged(&source, &baseline)?;
        if canonical_bytes(&definition)? != canonical_bytes(&candidate.definition)?
            || canonical_bytes(&inputs)? != canonical_bytes(&candidate.inputs)?
            || canonical_bytes(&source.definition)? != canonical_bytes(&plan.project)?
            || canonical_bytes(&baseline.config)? != canonical_bytes(&plan.workspace)?
            || baseline
                .captures
                .iter()
                .any(|c| c.result["status"] != "viable")
            || receipt["status"] != "verified-command-build"
            || receipt["inputKey"] != selected.input_key
            || receipt["planDigest"] != canonical_digest(&plan)?
            || receipt["workspaceDigest"] != baseline.digest
            || receipt["sourceCaptureDigest"] != source.digest
            || receipt["candidateCaptureDigest"] != candidate.digest
        {
            return Err(refuse("PROJECT_BUILD_SELECTION_BINDING"));
        }
        let tool_bindings: BTreeMap<String, Value> = read(&attempt, "tool-bindings.json")?;
        let key = canonical_digest(
            &json!({"profile":PROJECT_BUILD_PROFILE,"source":source.digest,"plan":canonical_digest(&plan)?,"tools":tool_bindings,"executor":crate::engine_id()}),
        )?;
        if key != selected.input_key {
            return Err(refuse("PROJECT_BUILD_SELECTION_BINDING"));
        }
        let summaries = receipt["commands"]
            .as_array()
            .ok_or_else(|| refuse("PROJECT_BUILD_SELECTION_BINDING"))?;
        let steps = plan
            .build_steps
            .iter()
            .map(|c| ("build", c))
            .chain(plan.verification_steps.iter().map(|c| ("verify", c)))
            .collect::<Vec<_>>();
        if summaries.len() != steps.len() {
            return Err(refuse("PROJECT_BUILD_SELECTION_BINDING"));
        }
        for (index, ((phase, command), summary)) in steps.iter().zip(summaries).enumerate() {
            let name = format!("{phase}-{index:03}.json");
            let bytes = read_bytes(&attempt, &name)?;
            let report: Value = parse(&bytes)?;
            let binding = tool_bindings
                .get(&command.invocation.executable)
                .ok_or_else(|| refuse("PROJECT_BUILD_SELECTION_BINDING"))?;
            if summary["file"] != name
                || summary["digest"] != byte_digest(&bytes)
                || report["status"] != "completed-project-command"
                || report["captureDigest"] != candidate.digest
                || report["commandDigest"] != canonical_digest(command)?
                || report["exitCode"].as_f64() != Some(0.0)
                || report["programSucceeded"] != true
                || report["executable"] != command.invocation.executable
                || report["resolvedExecutable"] != binding["resolved"]
                || !report["exitSignal"].is_null()
                || report["selectedInputsUnchanged"] != true
                || report["executableUnchanged"] != true
                || report["executableDigestBefore"] != binding["digest"]
                || report["executableDigestAfter"] != binding["digest"]
            {
                return Err(refuse("PROJECT_BUILD_SELECTION_BINDING"));
            }
        }
        let artifact_raw = read_bytes(&attempt, "artifacts.json")?;
        if byte_digest(&artifact_raw) != selected.artifacts_digest {
            return Err(refuse("PROJECT_BUILD_SELECTION_BINDING"));
        }
        let expected: BTreeMap<String, Value> = parse(&artifact_raw)?;
        let root = attempt.join("candidate");
        if capture_project(&root, candidate.definition)?.digest != candidate.digest
            || canonical_bytes(&artifacts(&root, &plan.outputs)?)? != canonical_bytes(&expected)?
        {
            return Err(refuse("PROJECT_BUILD_SELECTED_OUTPUT_CHANGED"));
        }
        Ok(
            json!({"status":"verified-selected-build-bindings","inputKey":key,"attempt":selected.attempt,
            "sourceRediscovery":"not-performed","toolExecution":"not-performed","runtime":"not-repeated",
            "authorizationNow":"not-evaluated","activation":"not-performed"}),
        )
    }
    fn build_inputs(
        source: &Path,
        plan: &ProjectBuildPlan,
    ) -> Result<(ProjectCapture, BTreeMap<String, Value>, String, String), Error> {
        validate(plan)?;
        let meta = fs::symlink_metadata(source)?;
        if meta.file_type().is_symlink() || !meta.is_dir() {
            return Err(refuse("PROJECT_BUILD_DIRECTORY"));
        }
        let original = capture_project(source, plan.project.clone())?;
        let bindings = tools(plan)?;
        let plan_digest = canonical_digest(plan)?;
        let key = canonical_digest(
            &json!({"profile":PROJECT_BUILD_PROFILE,"source":original.digest,"plan":plan_digest,"tools":bindings,"executor":crate::engine_id()}),
        )?;
        Ok((original, bindings, plan_digest, key))
    }

    /// Read declared inputs/tool identities without running commands or creating build state.
    /// This observation is not admission, readiness, or an atomic filesystem snapshot.
    pub fn project_build_input_key(source: &Path, plan: &ProjectBuildPlan) -> Result<Value, Error> {
        let (capture, bindings, plan_digest, key) = build_inputs(source, plan)?;
        Ok(
            json!({"status":"observed-project-build-inputs","inputKey":key,
            "sourceCaptureDigest":capture.digest,"planDigest":plan_digest,
            "tools":bindings,"executor":crate::engine_id(),
            "commandsExecuted":false,"admission":"not-performed","activation":"not-performed"}),
        )
    }

    pub fn build_project(
        source: &Path,
        state: &Path,
        plan: &ProjectBuildPlan,
        force: bool,
    ) -> Result<Value, Error> {
        validate(plan)?;
        let source_meta = fs::symlink_metadata(source)?;
        if source_meta.file_type().is_symlink() || !source_meta.is_dir() {
            return Err(refuse("PROJECT_BUILD_DIRECTORY"));
        }
        let source = source.canonicalize()?;
        let state = if state.exists() {
            if fs::symlink_metadata(state)?.file_type().is_symlink() {
                return Err(refuse("PROJECT_BUILD_DIRECTORY"));
            }
            state.canonicalize()?
        } else {
            let parent = state
                .parent()
                .filter(|p| !p.as_os_str().is_empty())
                .unwrap_or(Path::new("."))
                .canonicalize()?;
            parent.join(
                state
                    .file_name()
                    .ok_or_else(|| refuse("PROJECT_BUILD_DIRECTORY"))?,
            )
        };
        if state.starts_with(&source) || state.ancestors().any(|p| p.join("Cargo.toml").exists()) {
            return Err(refuse("PROJECT_BUILD_STATE_ISOLATION"));
        }
        directory(&state)?;
        let lock = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .mode(0o600)
            .custom_flags(rustix::fs::OFlags::NOFOLLOW.bits() as i32)
            .open(state.join("driver.lock"))?;
        lock.try_lock()
            .map_err(|_| refuse("PROJECT_BUILD_LOCK_UNAVAILABLE"))?;
        let (original, bindings, plan_digest, key) = build_inputs(&source, plan)?;
        let previous = selected_bytes(&state)?;
        if let Some(raw) = &previous {
            let selected = selection(raw)?;
            if !force && selected.input_key == key {
                verify_project_build_selection(&state)?;
                return Ok(
                    json!({"status":"unchanged-project-build","inputKey":key,"verification":"not-repeated","cacheHits":0,"activation":"not-performed"}),
                );
            }
        }
        directory(&state.join("attempts"))?;
        let id = format!(
            "{}-{}",
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map_err(|_| refuse("PROJECT_BUILD_CLOCK"))?
                .as_nanos(),
            std::process::id()
        );
        let relative = format!("attempts/{id}");
        let attempt = state.join(&relative);
        fs::DirBuilder::new().mode(0o700).create(&attempt)?;
        write_new(
            &attempt.join("started.json"),
            &json!({"status":"running","inputKey":key,"pid":std::process::id()}),
        )?;
        write_new(&attempt.join("plan.json"), plan)?;
        write_new(&attempt.join("source-capture.json"), &original)?;
        write_new(&attempt.join("tool-bindings.json"), &bindings)?;
        let began = Instant::now();
        let mut published = false;
        let result = (|| {
            stage_project_capture(&original, &attempt.join("source"))?;
            let baseline = generate(&attempt.join("source"), &plan.workspace, None)?.baseline;
            write_new(&attempt.join("workspace-baseline.json"), &baseline)?;
            verify_baseline(&baseline)?;
            if baseline
                .captures
                .iter()
                .any(|c| c.result["status"] != "viable")
            {
                return Err(refuse("PROJECT_BUILD_ADMISSION"));
            }
            let (definition, inputs) = merged(&original, &baseline)?;
            let candidate = attempt.join("candidate");
            crate::project::stage_selected_inputs(&inputs, &candidate)?;
            let captured = capture_project(&candidate, definition)?;
            write_new(&attempt.join("candidate-capture.json"), &captured)?;
            let mut summaries = Vec::new();
            let steps = plan
                .build_steps
                .iter()
                .map(|c| ("build", c))
                .chain(plan.verification_steps.iter().map(|c| ("verify", c)));
            let mut before_checks = None;
            for (index, (phase, command)) in steps.enumerate() {
                if phase == "verify" && before_checks.is_none() {
                    before_checks = Some(artifacts(&candidate, &plan.outputs)?);
                }
                write_new(
                    &attempt.join(format!("{phase}-{index:03}.started.json")),
                    &json!({"commandDigest":canonical_digest(command)?}),
                )?;
                let report = execute_project_command(&candidate, &captured, command)?;
                let name = format!("{phase}-{index:03}.json");
                write_new(&attempt.join(&name), &report)?;
                summaries
                    .push(json!({"file":name,"digest":byte_digest(&read_bytes(&attempt,&name)?)}));
                if report["status"] != "completed-project-command" {
                    return Err(refuse("PROJECT_BUILD_COMMAND"));
                }
            }
            let outputs = artifacts(&candidate, &plan.outputs)?;
            if before_checks.as_ref() != Some(&outputs) {
                return Err(refuse("PROJECT_BUILD_ARTIFACT_CHANGED"));
            }
            if capture_project(&source, plan.project.clone())?.digest != original.digest
                || tools(plan)? != bindings
            {
                return Err(refuse("PROJECT_BUILD_SOURCE_OR_TOOL_CHANGED"));
            }
            if capture_project(&candidate, captured.definition.clone())?.digest != captured.digest {
                return Err(refuse("PROJECT_BUILD_SOURCE_OR_TOOL_CHANGED"));
            }
            write_new(&attempt.join("artifacts.json"), &outputs)?;
            let receipt = json!({"status":"verified-command-build","inputKey":key,"planDigest":plan_digest,
                "sourceCaptureDigest":original.digest,"candidateCaptureDigest":captured.digest,"workspaceDigest":baseline.digest,
                "commands":summaries,"elapsedMs":began.elapsed().as_millis() as u64,
                "completeBuildContextEstablished":false,"completeExecutableDependencyClosureEstablished":false,
                "runtimeMeaning":"owner-declared-verification-commands; not inferred","activation":"not-performed"});
            write_new(&attempt.join("receipt.json"), &receipt)?;
            if selected_bytes(&state)? != previous {
                return Err(refuse("PROJECT_BUILD_SELECTION_RACE"));
            }
            if let Some(raw) = &previous {
                let mut history = OpenOptions::new()
                    .write(true)
                    .create_new(true)
                    .mode(0o600)
                    .open(attempt.join("previous-selection.json"))?;
                history.write_all(raw)?;
                history.sync_all()?;
            }
            let mut next = Selection {
                profile: "patamaps-project-build-selection-1".into(),
                input_key: key.clone(),
                attempt: relative.clone(),
                receipt_digest: byte_digest(&read_bytes(&attempt, "receipt.json")?),
                artifacts_digest: byte_digest(&read_bytes(&attempt, "artifacts.json")?),
                digest: String::new(),
            };
            next.digest = address(&next)?;
            write_new(&attempt.join("selection.candidate.json"), &next)?;
            if selected_bytes(&state)? != previous
                || artifacts(&candidate, &plan.outputs)? != outputs
                || capture_project(&source, plan.project.clone())?.digest != original.digest
                || tools(plan)? != bindings
            {
                return Err(refuse("PROJECT_BUILD_SELECTION_RACE"));
            }
            fs::rename(
                attempt.join("selection.candidate.json"),
                state.join("selected.json"),
            )?;
            published = true;
            File::open(&state)?.sync_all()?;
            Ok(
                json!({"status":"selected-project-build","inputKey":key,"attempt":relative,
                "verification":"commands-executed","cacheHits":0,"activation":"not-performed"}),
            )
        })();
        match result {
            Ok(value) => Ok(value),
            Err(error) => {
                let preserved = selected_bytes(&state).ok().flatten() == previous;
                write_new(
                    &attempt.join(if published {
                        "post-publication-error.json"
                    } else {
                        "failure.json"
                    }),
                    &json!({"status":"refused","reason":error.to_string(),"previousSelectionPreserved":preserved,"published":published}),
                )?;
                Ok(
                    json!({"status":if published {"selected-build-durability-unconfirmed"} else {"refused-project-build"},
                    "reason":error.to_string(),"attempt":relative,"previousSelectionPreserved":preserved,"activation":"not-performed"}),
                )
            }
        }
    }
}
#[cfg(unix)]
pub use unix::{build_project, project_build_input_key, verify_project_build_selection};

#[cfg(not(unix))]
pub fn build_project(
    _: &std::path::Path,
    _: &std::path::Path,
    _: &ProjectBuildPlan,
    _: bool,
) -> Result<serde_json::Value, Error> {
    Err(Error::refused(
        "PROJECT_BUILD_PLATFORM",
        "Retained builds require Unix",
    ))
}
#[cfg(not(unix))]
pub fn verify_project_build_selection(_: &std::path::Path) -> Result<serde_json::Value, Error> {
    Err(Error::refused(
        "PROJECT_BUILD_PLATFORM",
        "Retained builds require Unix",
    ))
}

#[cfg(not(unix))]
pub fn project_build_input_key(
    _: &std::path::Path,
    _: &ProjectBuildPlan,
) -> Result<serde_json::Value, Error> {
    Err(Error::refused(
        "PROJECT_BUILD_PLATFORM",
        "Retained builds require Unix",
    ))
}
