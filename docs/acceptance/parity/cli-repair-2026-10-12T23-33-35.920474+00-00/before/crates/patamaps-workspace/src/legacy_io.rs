//! Filesystem transport for the legacy workspace observation workflow.
//! This writes explicitly requested cache/output files and never removes files.
use patamaps_contracts::{
    COMPATIBILITY_JSON_LIMITS, LegacyPackJson, LegacyReadOnlyJson as Data, MAX_INPUT_BYTES,
};
use patamaps_core::{LegacyWorkspaceError, LegacyWorkspaceRequest};
use serde_json::value::RawValue;
use std::{
    fs::{self, File},
    io::Read,
    path::{Path, PathBuf},
};
fn error(code: &str, name: &str, message: &str) -> LegacyWorkspaceError {
    LegacyWorkspaceError {
        code: code.into(),
        name: name.into(),
        message: Data::string_json(&message.encode_utf16().collect::<Vec<_>>()),
        identifier: None,
        path: None,
        errno: None,
        syscall: None,
    }
}
fn io_error(error: std::io::Error, path: &Path) -> LegacyWorkspaceError {
    use std::io::ErrorKind;
    let code = match error.kind() {
        ErrorKind::NotFound => "ENOENT",
        ErrorKind::PermissionDenied => "EACCES",
        ErrorKind::NotADirectory => "ENOTDIR",
        ErrorKind::IsADirectory => "EISDIR",
        _ if error.raw_os_error() == Some(rustix::io::Errno::LOOP.raw_os_error()) => "ELOOP",
        _ => "LEGACY_WORKSPACE_IO",
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
    error_with_io(error, code, &message, path, syscall)
}
fn error_with_io(
    io: std::io::Error,
    code: &str,
    message: &str,
    path: &Path,
    syscall: &str,
) -> LegacyWorkspaceError {
    let mut value = error(code, "Error", message);
    value.errno = io.raw_os_error().map(|errno| -errno);
    value.syscall = Some(syscall.into());
    if code != "EISDIR" {
        value.path = Some(path.to_string_lossy().into_owned().into_boxed_str())
    }
    value
}

fn resolve(root: &[u16], value: &[u16]) -> Vec<u16> {
    let mut parts = Vec::new();
    let mut absolute = Vec::new();
    if value.first() == Some(&47) {
        absolute.extend_from_slice(value)
    } else {
        if root.first() == Some(&47) {
            absolute.extend_from_slice(root)
        } else {
            absolute.extend(
                std::env::current_dir()
                    .expect("workspace current directory")
                    .to_string_lossy()
                    .encode_utf16(),
            );
            absolute.push(47);
            absolute.extend_from_slice(root)
        }
        absolute.push(47);
        absolute.extend_from_slice(value)
    }
    for part in absolute.split(|unit| *unit == 47) {
        if part.is_empty() || part == [46] {
            continue;
        }
        if part == [46, 46] {
            parts.pop();
        } else {
            parts.push(part)
        }
    }
    let mut result = vec![47];
    for (index, part) in parts.iter().enumerate() {
        if index != 0 {
            result.push(47);
        }
        result.extend_from_slice(part);
    }
    result
}
pub fn legacy_workspace_request(
    request: LegacyWorkspaceRequest,
) -> Result<Box<RawValue>, LegacyWorkspaceError> {
    if !matches!(
        request.operation.as_str(),
        "resolve" | "read-json" | "write-file"
    ) {
        return patamaps_core::legacy_workspace_request(request);
    }
    let input = Data::parse(&request.input, COMPATIBILITY_JSON_LIMITS)
        .map_err(|e| error("LEGACY_WORKSPACE_INPUT", "Error", &e.to_string()))?;
    let required = |key: &str| {
        input
            .value()
            .get(key)
            .and_then(patamaps_contracts::LegacyOrderedJson::string)
            .map(Data::string_units)
            .ok_or_else(|| {
                error(
                    "LEGACY_WORKSPACE_INPUT",
                    "TypeError",
                    &format!("Workspace {key} requires a string"),
                )
            })
    };
    if request.operation == "resolve" {
        return Ok(Data::string_json(&resolve(
            &required("root")?,
            &required("path")?,
        )));
    }
    let path = PathBuf::from(String::from_utf16_lossy(&required("path")?));
    if request.operation == "write-file" {
        let content = String::from_utf16_lossy(&required("content")?);
        fs::create_dir_all(path.parent().unwrap_or_else(|| Path::new(".")))
            .map_err(|e| io_error(e, &path))?;
        fs::write(&path, content).map_err(|e| io_error(e, &path))?;
        return Ok(RawValue::from_string("null".into()).expect("null JSON"));
    }
    let mut bytes = Vec::new();
    let read = File::open(&path).and_then(|file| {
        file.take((MAX_INPUT_BYTES + 1) as u64)
            .read_to_end(&mut bytes)
    });
    match read {
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
            Ok(RawValue::from_string(r#"{"present":false}"#.into()).expect("missing JSON result"))
        }
        Err(e) => Err(io_error(e, &path)),
        Ok(_) => {
            let text = String::from_utf8_lossy(&bytes);
            let parsed = Data::parse(&text, COMPATIBILITY_JSON_LIMITS).map_err(|e| {
                let diagnostic = LegacyPackJson::parse(bytes, COMPATIBILITY_JSON_LIMITS)
                    .err()
                    .unwrap_or(e)
                    .json_diagnostic(COMPATIBILITY_JSON_LIMITS);
                error(
                    diagnostic.code,
                    if diagnostic.code == "INVALID_JSON_SYNTAX" {
                        "SyntaxError"
                    } else {
                        "Error"
                    },
                    &diagnostic.message,
                )
            })?;
            let raw = Data::json_raw(parsed.value())
                .map_err(|e| error("LEGACY_WORKSPACE_INPUT", "Error", &e.to_string()))?;
            RawValue::from_string(format!(r#"{{"present":true,"value":{}}}"#, raw.get()))
                .map_err(|e| error("LEGACY_WORKSPACE_INPUT", "Error", &e.to_string()))
        }
    }
}
