use crate::{AdapterRequest, AdapterResponse, Error, Invocation, PROFILE};
use patamaps_contracts::{MAX_INPUT_BYTES, canonical_bytes, parse};
use std::{
    io::{Read, Write},
    path::Path,
    process::{Command, Stdio},
    sync::mpsc,
    thread,
    time::{Duration, Instant},
};

#[cfg(unix)]
fn stop(child: &mut std::process::Child, owned_group: bool) {
    // A configured provider is not sandboxed. Kill its ordinary process group,
    // including inherited pipe holders, before collecting reader threads.
    if owned_group && let Some(pid) = rustix::process::Pid::from_raw(child.id() as i32) {
        let _ = rustix::process::kill_process_group(pid, rustix::process::Signal::KILL);
    }
    let _ = child.kill();
    let _ = child.wait();
}

pub(crate) fn validate_invocation(invocation: &Invocation) -> Result<(), Error> {
    let limits = &invocation.bounds;
    if !(1..=60_000).contains(&limits.maximum_elapsed_ms.get())
        || !(1..=MAX_INPUT_BYTES as u64).contains(&limits.maximum_stdout_bytes.get())
        || !(1..=65_536).contains(&limits.maximum_stderr_bytes.get())
        || invocation.arguments.len() > 128
        || invocation
            .arguments
            .iter()
            .any(|s| s.len() > 4096 || s.contains('\0'))
    {
        return Err(Error::refused(
            "ADAPTER_LIMITS",
            "Invalid process bounds or argument vector",
        ));
    }
    Ok(())
}

#[cfg(unix)]
pub(crate) fn invoke_tool(
    invocation: &Invocation,
    executable: &Path,
    root: &Path,
    input: &[u8],
    environment: &[(&str, &str)],
) -> Result<(Vec<u8>, Vec<u8>), Error> {
    crate::tool_supervisor::invoke(invocation, executable, root, input, environment)
}

#[cfg(unix)]
pub(crate) fn invoke_direct(
    invocation: &Invocation,
    executable: &Path,
    root: &Path,
    input: &[u8],
    environment: &[(&str, &str)],
    watched_parent: Option<u32>,
    supervisor_exit_codes: bool,
) -> Result<(Vec<u8>, Vec<u8>), Error> {
    use std::os::unix::process::CommandExt;
    validate_invocation(invocation)?;
    let limits = &invocation.bounds;
    let request_bytes = input.to_vec();
    if request_bytes.len() > crate::tool_supervisor::TRANSPORT_LIMIT {
        return Err(Error::refused(
            "ADAPTER_INPUT_LIMIT",
            "Request is too large",
        ));
    }
    let mut command = Command::new(executable);
    command
        .args(&invocation.arguments)
        .env_clear()
        .envs(environment.iter().copied())
        .current_dir(root)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    if watched_parent.is_none() {
        command.process_group(0);
    }
    let mut child = command.spawn()?;
    let mut stdin = child.stdin.take().expect("piped stdin");
    let stdout = child.stdout.take().expect("piped stdout");
    let stderr = child.stderr.take().expect("piped stderr");
    let writer = thread::spawn(move || stdin.write_all(&request_bytes));
    let (tx, rx) = mpsc::channel();
    let out_limit = limits.maximum_stdout_bytes.get() as usize;
    let err_limit = limits.maximum_stderr_bytes.get() as usize;
    let out_tx = tx.clone();
    let out = thread::spawn(move || {
        let mut bytes = Vec::new();
        let result = stdout.take((out_limit + 1) as u64).read_to_end(&mut bytes);
        let _ = out_tx.send((true, result, bytes));
    });
    let err = thread::spawn(move || {
        let mut bytes = Vec::new();
        let result = stderr.take((err_limit + 1) as u64).read_to_end(&mut bytes);
        let _ = tx.send((false, result, bytes));
    });
    let start = Instant::now();
    let mut output = None;
    let mut diagnostics = None;
    let result = (|| {
        let mut status = None;
        loop {
            if let Some(parent) = watched_parent
                && rustix::process::getppid().map(|p| p.as_raw_nonzero().get() as u32)
                    != Some(parent)
            {
                // Only the validated private helper uses this mode. Its own
                // process group contains the tool and ordinary pipe holders.
                let group = rustix::process::getpgrp();
                if group == rustix::process::getpid() {
                    let _ =
                        rustix::process::kill_process_group(group, rustix::process::Signal::KILL);
                }
                return Err(Error::refused(
                    "ADAPTER_PARENT_EXIT",
                    "The invoking parent exited",
                ));
            }
            while let Ok((is_stdout, result, bytes)) = rx.try_recv() {
                result?;
                let limit = if is_stdout { out_limit } else { err_limit };
                if bytes.len() > limit {
                    return Err(Error::refused(
                        "ADAPTER_OUTPUT_LIMIT",
                        "Provider exceeded a pipe bound",
                    ));
                }
                if is_stdout {
                    output = Some(bytes);
                } else {
                    diagnostics = Some(bytes);
                }
            }
            if status.is_none() {
                status = child.try_wait()?;
            }
            if let Some(status) = status {
                // A provider may leave children holding pipes open. They cannot
                // prolong the protocol beyond the configured deadline.
                if output.is_some() && diagnostics.is_some() {
                    if !status.success() {
                        let code = if supervisor_exit_codes {
                            match status.code() {
                                Some(71) => "ADAPTER_TIMEOUT",
                                Some(72) => "ADAPTER_OUTPUT_LIMIT",
                                Some(73) => "ADAPTER_INPUT_LIMIT",
                                Some(74) => "ADAPTER_EXIT",
                                _ => "ADAPTER_SUPERVISOR",
                            }
                        } else {
                            "ADAPTER_EXIT"
                        };
                        return Err(Error::refused(
                            code,
                            "Provider or its private supervisor exited unsuccessfully",
                        ));
                    }
                    break;
                }
            }
            if start.elapsed() >= Duration::from_millis(limits.maximum_elapsed_ms.get()) {
                return Err(Error::refused(
                    "ADAPTER_TIMEOUT",
                    "Provider did not complete within its deadline",
                ));
            }
            thread::sleep(Duration::from_millis(2));
        }
        Ok(())
    })();
    stop(&mut child, watched_parent.is_none());
    let failure = match (watched_parent.is_some(), result.err()) {
        // The private helper exits immediately with the refusal class. Its
        // caller owns the group and kills remaining ordinary pipe holders.
        // Joining those holders here could delay cleanup indefinitely.
        (true, Some(error)) => return Err(error),
        (_, failure) => failure,
    };
    let written = writer
        .join()
        .map_err(|_| Error::refused("ADAPTER_INPUT", "Input writer failed"));
    let _ = out.join();
    let _ = err.join();
    if let Some(error) = failure {
        return Err(error);
    }
    written??;
    Ok((
        output.expect("collected stdout"),
        diagnostics.expect("collected stderr"),
    ))
}

#[cfg(unix)]
pub(crate) fn invoke(
    invocation: &Invocation,
    executable: &Path,
    root: &Path,
    request: &AdapterRequest,
) -> Result<AdapterResponse, Error> {
    let (output, _) = invoke_tool(
        invocation,
        executable,
        root,
        &canonical_bytes(request)?,
        &[],
    )
    .map_err(|error| match error {
        Error::Refused { code, message } => {
            let inputs = request
                .inputs
                .iter()
                .take(8)
                .map(|input| input.receipt.path.as_str())
                .collect::<Vec<_>>()
                .join(", ");
            Error::refused(
                code,
                format!(
                    "Source {} (first captured inputs: {}): {}",
                    request.source_id, inputs, message
                ),
            )
        }
        other => other,
    })?;
    let response: AdapterResponse = parse(&output)?;
    if response.profile != PROFILE
        || response.source_id != request.source_id
        || response.request_digest != request.request_digest
        || response.adapter_version.is_empty()
        || response.adapter_version.len() > 128
        || response.inputs
            != request
                .inputs
                .iter()
                .map(|i| i.receipt.clone())
                .collect::<Vec<_>>()
        || response.diagnostics.len() > 1024
    {
        return Err(Error::refused(
            "ADAPTER_BINDING",
            "Response does not bind the exact supplied request and inputs",
        ));
    }
    if response
        .diagnostics
        .iter()
        .any(|d| matches!(d.severity, crate::DiagnosticSeverity::Error))
    {
        return Err(Error::refused(
            "ADAPTER_DIAGNOSTIC",
            "Provider reported discovery errors",
        ));
    }
    Ok(response)
}

#[cfg(not(unix))]
pub(crate) fn invoke(
    _: &Invocation,
    _: &Path,
    _: &Path,
    _: &AdapterRequest,
) -> Result<AdapterResponse, Error> {
    Err(Error::refused(
        "ADAPTER_PLATFORM",
        "Process discovery currently supports Linux and macOS",
    ))
}

#[cfg(not(unix))]
pub(crate) fn invoke_tool(
    _: &Invocation,
    _: &Path,
    _: &Path,
    _: &[u8],
    _: &[(&str, &str)],
) -> Result<(Vec<u8>, Vec<u8>), Error> {
    Err(Error::refused(
        "ADAPTER_PLATFORM",
        "Native tool observations currently support Linux and macOS",
    ))
}
