//! Explicit trusted development commands. Execution is not selection or activation.
use crate::{
    Error, Invocation, ProjectCapture, capture_project, relative_path, verify_project_capture,
};
use patamaps_contracts::{byte_digest, canonical_digest};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{
    collections::{BTreeMap, BTreeSet},
    path::{Path, PathBuf},
    time::Instant,
};

pub const PROJECT_COMMAND_PROFILE: &str = "patamaps-project-command-1";

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ProjectCommand {
    pub profile: String,
    pub invocation: Invocation,
    /// "." or a normalized relative directory beneath the supplied owner root.
    pub working_directory: String,
    /// Environment names refer only to captured nonsecretConfiguration string keys.
    pub environment_references: BTreeMap<String, String>,
}

fn refuse(code: &'static str) -> Error {
    Error::refused(code, "Explicit project command contract refused")
}

fn directory(root: &Path, relative: &str) -> Result<PathBuf, Error> {
    if relative != "." && !relative_path(relative) {
        return Err(refuse("PROJECT_COMMAND_DIRECTORY"));
    }
    let mut path = root.to_owned();
    if relative != "." {
        for part in relative.split('/') {
            path.push(part);
            let metadata = std::fs::symlink_metadata(&path)?;
            if metadata.file_type().is_symlink() || !metadata.is_dir() {
                return Err(refuse("PROJECT_COMMAND_DIRECTORY"));
            }
        }
    }
    Ok(path)
}

fn captured_bytes(bytes: &[u8]) -> Value {
    let text = std::str::from_utf8(bytes).ok();
    let hex = text
        .is_none()
        .then(|| bytes.iter().map(|b| format!("{b:02x}")).collect::<String>());
    json!({"digest":byte_digest(bytes), "byteLength":bytes.len(), "text":text, "hex":hex})
}

/// Execute an explicit command against a caller-selected retained root. Programs
/// are trusted and are not sandboxed. Only declared selected bytes are bound.
pub fn execute_project_command(
    root: &Path,
    capture: &ProjectCapture,
    command: &ProjectCommand,
) -> Result<Value, Error> {
    verify_project_capture(capture)?;
    if command.profile != PROJECT_COMMAND_PROFILE
        || command.invocation.bounds.maximum_stdout_bytes.get() > 1_048_576
        || command.environment_references.len() > 64
    {
        return Err(refuse("PROJECT_COMMAND_LIMITS"));
    }
    crate::process::validate_invocation_for(
        &command.invocation,
        crate::tool_supervisor::ToolPurpose::ProjectCommand,
    )?;
    let selected = capture
        .inputs
        .iter()
        .map(|v| v.receipt.path.as_str())
        .collect::<BTreeSet<_>>();
    let code = command
        .invocation
        .code_inputs
        .iter()
        .map(String::as_str)
        .collect::<BTreeSet<_>>();
    if code.len() != command.invocation.code_inputs.len()
        || code.len() > 128
        || code.iter().any(|p| !selected.contains(p))
    {
        return Err(refuse("PROJECT_COMMAND_CODE_INPUTS"));
    }
    let mut environment = Vec::new();
    for (name, key) in &command.environment_references {
        if name.is_empty()
            || name.len() > 128
            || !name
                .bytes()
                .enumerate()
                .all(|(i, b)| b == b'_' || b.is_ascii_uppercase() || (i > 0 && b.is_ascii_digit()))
        {
            return Err(refuse("PROJECT_COMMAND_ENVIRONMENT"));
        }
        let value = capture
            .definition
            .nonsecret_configuration
            .get(key)
            .and_then(Value::as_str)
            .ok_or_else(|| refuse("PROJECT_COMMAND_ENVIRONMENT"))?;
        if value.len() > 4096 || value.contains('\0') {
            return Err(refuse("PROJECT_COMMAND_ENVIRONMENT"));
        }
        environment.push((name.as_str(), value));
    }
    let configured = Path::new(&command.invocation.executable);
    if !configured.is_absolute() {
        return Err(refuse("PROJECT_COMMAND_EXECUTABLE"));
    }
    let executable = configured.canonicalize()?;
    if executable.to_str().is_none() {
        return Err(refuse("PROJECT_COMMAND_EXECUTABLE"));
    }
    let before_tool = crate::hash_executable(&executable)?;
    if !std::fs::metadata(root)?.is_dir()
        || std::fs::symlink_metadata(root)?.file_type().is_symlink()
    {
        return Err(refuse("PROJECT_COMMAND_DIRECTORY"));
    }
    let owner = root.canonicalize()?;
    let cwd = directory(&owner, &command.working_directory)?;
    if capture_project(&owner, capture.definition.clone())?.digest != capture.digest {
        return Err(refuse("PROJECT_COMMAND_INPUTS_CHANGED"));
    }
    let began = Instant::now();
    let output = crate::tool_supervisor::invoke_command(
        &command.invocation,
        configured,
        &cwd,
        &environment,
    )?;
    let elapsed = began.elapsed().as_millis() as u64;
    let after_tool = crate::hash_executable(&executable).ok();
    let tool_unchanged = after_tool.as_ref() == Some(&before_tool)
        && configured.canonicalize().ok().as_deref() == Some(executable.as_path());
    let inputs_unchanged = capture_project(&owner, capture.definition.clone())
        .is_ok_and(|r| r.digest == capture.digest);
    let completed = output.success && tool_unchanged && inputs_unchanged;
    Ok(json!({
        "status":if completed {"completed-project-command"} else {"refused-project-command"},
        "profile":PROJECT_COMMAND_PROFILE, "captureDigest":capture.digest,
        "commandDigest":canonical_digest(&serde_json::to_value(command).expect("finite typed command"))?,
        "executable":command.invocation.executable, "resolvedExecutable":executable, "executableDigestBefore":before_tool, "executableDigestAfter":after_tool,
        "executableUnchanged":tool_unchanged, "selectedInputsUnchanged":inputs_unchanged,
        "workingDirectory":command.working_directory, "environmentReferences":command.environment_references,
        "environmentResolution":"captured-nonsecretConfiguration-only", "ambientEnvironment":"not-inherited",
        "exitCode":output.exit_code, "exitSignal":output.exit_signal, "programSucceeded":output.success, "elapsedMs":elapsed,
        "stdout":captured_bytes(&output.stdout), "stderr":captured_bytes(&output.stderr),
        "parentDeathCleanup":if crate::tool_supervisor::configured() {"private-supervisor-configured"} else {"not-established"},
        "completeExecutableDependencyClosureEstablished":false,
        "completeBuildContextEstablished":false, "selectionPublication":"not-performed",
        "authorizationNow":"not-evaluated", "activation":"not-performed"
    }))
}
