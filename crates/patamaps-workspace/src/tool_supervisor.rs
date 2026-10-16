//! Private CLI process guard. Each guard owns a group containing its ordinary
//! tool descendants and watches its actual parent, including after SIGKILL.
use crate::{Error, Invocation};
use patamaps_contracts::MAX_INPUT_BYTES;
use serde::{Deserialize, Serialize};
use std::{
    io::{BufRead, BufReader, Read, Write},
    path::{Path, PathBuf},
    sync::OnceLock,
};

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "kebab-case")]
pub(crate) enum ToolPurpose {
    #[default]
    Adapter,
    ProjectCommand,
}
impl ToolPurpose {
    pub(crate) fn maximum_elapsed_ms(self) -> u64 {
        match self {
            Self::Adapter => 60_000,
            Self::ProjectCommand => 86_400_000,
        }
    }
}
pub(crate) fn configured() -> bool {
    PROGRAM.get().is_some()
}

const HEADER_LIMIT: usize = MAX_INPUT_BYTES;
pub(crate) const TRANSPORT_LIMIT: usize = MAX_INPUT_BYTES + HEADER_LIMIT;
static PROGRAM: OnceLock<PathBuf> = OnceLock::new();

/// Configure the current CLI's private supervisor. Library embedders that do
/// not configure this retain bounded direct execution, without a parent-death
/// guarantee. This is process cleanup, not a sandbox against trusted tools.
pub fn configure_tool_supervisor(program: PathBuf) -> Result<(), Error> {
    let program = program.canonicalize()?;
    if let Some(existing) = PROGRAM.get() {
        if existing != &program {
            return Err(Error::refused(
                "ADAPTER_SUPERVISOR",
                "Supervisor is already configured",
            ));
        }
    } else {
        PROGRAM.set(program).map_err(|_| {
            Error::refused("ADAPTER_SUPERVISOR", "Concurrent supervisor configuration")
        })?;
    }
    Ok(())
}

#[derive(Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Request {
    version: String,
    #[serde(default)]
    purpose: ToolPurpose,
    parent_pid: u32,
    invocation: Invocation,
    executable: PathBuf,
    root: PathBuf,
    environment: Vec<(String, String)>,
    input_length: usize,
}

#[cfg(unix)]
pub(crate) fn invoke(
    invocation: &Invocation,
    executable: &Path,
    root: &Path,
    input: &[u8],
    environment: &[(&str, &str)],
) -> Result<(Vec<u8>, Vec<u8>), Error> {
    crate::process::validate_invocation(invocation)?;
    if input.len() > MAX_INPUT_BYTES {
        return Err(Error::refused(
            "ADAPTER_INPUT_LIMIT",
            "Request is too large",
        ));
    }
    let Some(program) = PROGRAM.get() else {
        return crate::process::invoke_direct(
            invocation,
            executable,
            root,
            input,
            environment,
            None,
            false,
        );
    };
    let request = Request {
        version: "patamaps-private-tool-guard-1".into(),
        purpose: ToolPurpose::Adapter,
        parent_pid: std::process::id(),
        invocation: invocation.clone(),
        executable: executable.to_owned(),
        root: root.to_owned(),
        environment: environment
            .iter()
            .map(|(k, v)| ((*k).to_owned(), (*v).to_owned()))
            .collect(),
        input_length: input.len(),
    };
    let mut bytes = serde_json::to_vec(&request)
        .map_err(|e| Error::refused("ADAPTER_SUPERVISOR", e.to_string()))?;
    if bytes.len() >= HEADER_LIMIT {
        return Err(Error::refused(
            "ADAPTER_SUPERVISOR",
            "Supervisor header bound exceeded",
        ));
    }
    bytes.push(b'\n');
    bytes.extend_from_slice(input);
    let guard = Invocation {
        executable: program.to_string_lossy().into_owned(),
        arguments: vec!["__tool-supervisor".into()],
        code_inputs: Vec::new(),
        bounds: invocation.bounds.clone(),
    };
    crate::process::invoke_direct(&guard, program, root, &bytes, &[], None, true)
}

#[cfg(unix)]
pub(crate) fn invoke_command(
    invocation: &Invocation,
    executable: &Path,
    root: &Path,
    environment: &[(&str, &str)],
) -> Result<crate::process::ToolOutput, Error> {
    crate::process::validate_invocation_for(invocation, ToolPurpose::ProjectCommand)?;
    let Some(program) = PROGRAM.get() else {
        return crate::process::invoke_direct_for(
            invocation,
            executable,
            root,
            &[],
            environment,
            crate::process::ExecutionContext {
                watched_parent: None,
                supervisor_exit_codes: false,
                purpose: ToolPurpose::ProjectCommand,
            },
        );
    };
    let request = Request {
        version: "patamaps-private-project-command-1".into(),
        purpose: ToolPurpose::ProjectCommand,
        parent_pid: std::process::id(),
        invocation: invocation.clone(),
        executable: executable.to_owned(),
        root: root.to_owned(),
        environment: environment
            .iter()
            .map(|(k, v)| ((*k).into(), (*v).into()))
            .collect(),
        input_length: 0,
    };
    let mut bytes = serde_json::to_vec(&request)
        .map_err(|e| Error::refused("ADAPTER_SUPERVISOR", e.to_string()))?;
    if bytes.len() >= HEADER_LIMIT {
        return Err(Error::refused(
            "ADAPTER_SUPERVISOR",
            "Supervisor header bound exceeded",
        ));
    }
    bytes.push(b'\n');
    let mut guard = invocation.clone();
    guard.executable = program.to_string_lossy().into_owned();
    guard.arguments = vec!["__tool-supervisor".into()];
    guard.code_inputs.clear();
    // serde's byte arrays take at most four bytes per byte plus commas. The
    // public command profile caps inner pipes so this envelope stays bounded.
    let envelope_limit = 5
        * (invocation.bounds.maximum_stdout_bytes.get()
            + invocation.bounds.maximum_stderr_bytes.get())
        + 4096;
    guard.bounds.maximum_stdout_bytes = patamaps_contracts::SafeInteger::new(envelope_limit)
        .ok_or_else(|| Error::refused("PROJECT_COMMAND_LIMITS", "Invalid envelope bound"))?;
    let output = crate::process::invoke_direct_for(
        &guard,
        program,
        root,
        &bytes,
        &[],
        crate::process::ExecutionContext {
            watched_parent: None,
            supervisor_exit_codes: true,
            purpose: ToolPurpose::ProjectCommand,
        },
    )?;
    serde_json::from_slice(&output.stdout)
        .map_err(|e| Error::refused("ADAPTER_SUPERVISOR", e.to_string()))
}

#[cfg(not(unix))]
pub(crate) fn invoke_command(
    _: &Invocation,
    _: &Path,
    _: &Path,
    _: &[(&str, &str)],
) -> Result<crate::process::ToolOutput, Error> {
    Err(Error::refused(
        "PROJECT_COMMAND_PLATFORM",
        "Project commands require Unix",
    ))
}

/// Entry for the CLI's hidden, versioned self-exec protocol. Its parent already
/// applies the ordinary process bounds. No project scripts run while reading it.
#[cfg(unix)]
pub fn supervise_tool_stdio() -> Result<(), Error> {
    let mut stdin = BufReader::new(std::io::stdin().lock());
    let mut header = Vec::new();
    stdin
        .by_ref()
        .take((HEADER_LIMIT + 1) as u64)
        .read_until(b'\n', &mut header)?;
    if header.len() > HEADER_LIMIT || header.last() != Some(&b'\n') {
        return Err(Error::refused(
            "ADAPTER_SUPERVISOR",
            "Supervisor header bound exceeded or unterminated",
        ));
    }
    header.pop();
    let request: Request = serde_json::from_slice(&header)
        .map_err(|e| Error::refused("ADAPTER_SUPERVISOR", e.to_string()))?;
    let actual_parent = rustix::process::getppid().map(|p| p.as_raw_nonzero().get() as u32);
    if request.version
        != match request.purpose {
            ToolPurpose::Adapter => "patamaps-private-tool-guard-1",
            ToolPurpose::ProjectCommand => "patamaps-private-project-command-1",
        }
        || request.input_length > MAX_INPUT_BYTES
        || actual_parent != Some(request.parent_pid)
        || rustix::process::getpgrp() != rustix::process::getpid()
        || !request.executable.is_absolute()
        || !request.root.is_absolute()
    {
        return Err(Error::refused(
            "ADAPTER_SUPERVISOR",
            "Invalid private supervisor context",
        ));
    }
    let parent = request.parent_pid;
    let owned_group = rustix::process::getpid();
    // Independent of the pipe-reader joins: a child may leave pipe holders
    // behind after failing. Parent death must still stop the whole owned group.
    let _ = std::thread::spawn(move || {
        loop {
            if rustix::process::getppid().map(|p| p.as_raw_nonzero().get() as u32) != Some(parent) {
                let _ =
                    rustix::process::kill_process_group(owned_group, rustix::process::Signal::KILL);
            }
            std::thread::sleep(std::time::Duration::from_millis(2));
        }
    });
    crate::process::validate_invocation_for(&request.invocation, request.purpose)?;
    let mut input = vec![0; request.input_length];
    stdin.read_exact(&mut input)?;
    let mut extra = [0];
    if stdin.read(&mut extra)? != 0 {
        return Err(Error::refused(
            "ADAPTER_SUPERVISOR",
            "Unexpected trailing input",
        ));
    }
    let environment: Vec<(&str, &str)> = request
        .environment
        .iter()
        .map(|(k, v)| (k.as_str(), v.as_str()))
        .collect();
    let result = crate::process::invoke_direct_for(
        &request.invocation,
        &request.executable,
        &request.root,
        &input,
        &environment,
        crate::process::ExecutionContext {
            watched_parent: Some(request.parent_pid),
            supervisor_exit_codes: false,
            purpose: request.purpose,
        },
    )?;
    if request.purpose == ToolPurpose::ProjectCommand {
        serde_json::to_writer(std::io::stdout().lock(), &result)
            .map_err(|e| Error::refused("ADAPTER_SUPERVISOR", e.to_string()))?;
    } else {
        std::io::stderr().write_all(&result.stderr)?;
        std::io::stdout().write_all(&result.stdout)?;
    }
    Ok(())
}

#[cfg(not(unix))]
pub fn supervise_tool_stdio() -> Result<(), Error> {
    Err(Error::refused(
        "ADAPTER_PLATFORM",
        "Tool supervision currently supports Linux and macOS",
    ))
}
