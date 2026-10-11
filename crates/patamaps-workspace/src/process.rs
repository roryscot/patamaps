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
fn stop(child: &mut std::process::Child) {
    // A configured provider is not sandboxed. Kill its ordinary process group,
    // including inherited pipe holders, before collecting reader threads.
    if let Some(pid) = rustix::process::Pid::from_raw(child.id() as i32) {
        let _ = rustix::process::kill_process_group(pid, rustix::process::Signal::KILL);
    }
    let _ = child.kill();
    let _ = child.wait();
}

#[cfg(unix)]
pub(crate) fn invoke(
    invocation: &Invocation,
    executable: &Path,
    root: &Path,
    request: &AdapterRequest,
) -> Result<AdapterResponse, Error> {
    use std::os::unix::process::CommandExt;
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
    let request_bytes = canonical_bytes(request)?;
    if request_bytes.len() > MAX_INPUT_BYTES {
        return Err(Error::refused(
            "ADAPTER_INPUT_LIMIT",
            "Request is too large",
        ));
    }
    let mut child = Command::new(executable)
        .args(&invocation.arguments)
        .env_clear()
        .current_dir(root)
        .process_group(0)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()?;
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
                        return Err(Error::refused(
                            "ADAPTER_EXIT",
                            "Provider exited unsuccessfully",
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
    stop(&mut child);
    let written = writer
        .join()
        .map_err(|_| Error::refused("ADAPTER_INPUT", "Input writer failed"));
    let _ = out.join();
    let _ = err.join();
    result?;
    written??;
    let response: AdapterResponse = parse(output.as_deref().expect("collected stdout"))?;
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
