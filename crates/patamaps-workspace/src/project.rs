//! Explicit nonsecret project inputs. Capture is not discovery, admission or activation.
use crate::{Error, InputReceipt, SuppliedInput, relative_path};
use patamaps_contracts::{
    MAX_INPUT_BYTES, SafeInteger, byte_digest, canonical_bytes, canonical_digest,
};
use serde::{Deserialize, Serialize};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs::File,
    io::Read,
    path::Path,
};

pub const PROJECT_PROFILE: &str = "patamaps-project-inputs-1";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ProjectProfile {
    pub profile: String,
    pub id: String,
    pub nonsecret_inputs: bool,
    pub inputs: Vec<String>,
    pub components: Vec<ProjectComponent>,
    /// Only owner-declared nonsecret values. This never redacts other inputs.
    #[serde(default)]
    pub nonsecret_configuration: BTreeMap<String, serde_json::Value>,
    /// Logical names mapped to environment variable names; values are never resolved.
    #[serde(default)]
    pub secret_references: BTreeMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ProjectComponentKind {
    NextApp,
    CargoPackage,
    Configuration,
    Contracts,
    Deployment,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ProjectComponent {
    pub id: String,
    pub kind: ProjectComponentKind,
    /// "." or a normalized owner-relative directory.
    pub root: String,
    /// Explicit selected inputs relative to the project root, never globs.
    pub entrypoints: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ProjectCapture {
    pub profile: String,
    pub definition: ProjectProfile,
    pub inputs: Vec<SuppliedInput>,
    pub digest: String,
}

fn refuse(code: &'static str) -> Error {
    Error::refused(
        code,
        "Project input contract refused; no tools or secret references were evaluated",
    )
}

fn label(s: &str) -> bool {
    !s.is_empty() && s.len() <= 256 && !s.chars().any(char::is_control)
}

fn allowed_input(path: &str) -> bool {
    relative_path(path)
        && path.split('/').all(|part| {
            part != ".git"
                && part != ".env"
                && !part.starts_with(".env.")
                && !matches!(part, "node_modules" | "target" | ".next")
        })
}

impl ProjectProfile {
    pub fn validate(&self) -> Result<(), Error> {
        if self.profile != PROJECT_PROFILE || !label(&self.id) || !self.nonsecret_inputs {
            return Err(refuse("PROJECT_PROFILE"));
        }
        if !(1..=1024).contains(&self.inputs.len())
            || !(1..=128).contains(&self.components.len())
            || self.secret_references.len() > 128
            || self.nonsecret_configuration.len() > 128
        {
            return Err(refuse("PROJECT_LIMIT"));
        }
        let mut paths = BTreeSet::new();
        for path in &self.inputs {
            if !allowed_input(path) || !paths.insert(path) {
                return Err(refuse("PROJECT_INPUT_PATH"));
            }
        }
        let mut ids = BTreeSet::new();
        for c in &self.components {
            if !label(&c.id)
                || !ids.insert(&c.id)
                || (c.root != "." && !relative_path(&c.root))
                || c.entrypoints.is_empty()
                || c.entrypoints.len() > 1024
            {
                return Err(refuse("PROJECT_COMPONENT"));
            }
            let mut entries = BTreeSet::new();
            for p in &c.entrypoints {
                if !paths.contains(p)
                    || !entries.insert(p)
                    || (c.root != "." && !p.starts_with(&(c.root.clone() + "/")))
                {
                    return Err(refuse("PROJECT_COMPONENT_INPUT"));
                }
            }
        }
        for (key, name) in &self.secret_references {
            if !label(key)
                || name.is_empty()
                || name.len() > 256
                || !name.bytes().enumerate().all(|(i, b)| {
                    b == b'_' || b.is_ascii_alphabetic() || (i > 0 && b.is_ascii_digit())
                })
                || self.nonsecret_configuration.contains_key(key)
            {
                return Err(refuse("PROJECT_SECRET_REFERENCE"));
            }
        }
        if self.nonsecret_configuration.keys().any(|k| !label(k))
            || canonical_bytes(self)?.len() > 262144
        {
            return Err(refuse("PROJECT_PROFILE_LIMIT"));
        }
        Ok(())
    }
}

/// Open each path component relative to a held directory with NOFOLLOW.
/// No project code is executed; this is not an OS snapshot or a malicious-host sandbox.
#[cfg(unix)]
pub(crate) fn open_project_file(root: &File, path: &str) -> Result<File, Error> {
    use rustix::fs::{Mode, OFlags, openat};
    if !relative_path(path) {
        return Err(refuse("PROJECT_INPUT_PATH"));
    }
    let mut directory = root.try_clone()?;
    let parts = path.split('/').collect::<Vec<_>>();
    for (i, part) in parts.iter().enumerate() {
        let last = i + 1 == parts.len();
        let flags = OFlags::RDONLY
            | OFlags::CLOEXEC
            | OFlags::NOFOLLOW
            | if last {
                OFlags::NONBLOCK
            } else {
                OFlags::DIRECTORY
            };
        let fd = openat(&directory, *part, flags, Mode::empty())
            .map_err(|_| refuse("PROJECT_INPUT_UNAVAILABLE"))?;
        let file = File::from(fd);
        if last {
            if !file.metadata()?.is_file() {
                return Err(refuse("PROJECT_INPUT_NOT_REGULAR"));
            }
            return Ok(file);
        }
        directory = file;
    }
    Err(refuse("PROJECT_INPUT_PATH"))
}

#[cfg(unix)]
fn read_input(root: &File, path: &str, remaining: usize) -> Result<Vec<u8>, Error> {
    let file = open_project_file(root, path)?;
    let mut raw = Vec::new();
    file.take((remaining + 1) as u64).read_to_end(&mut raw)?;
    if raw.len() > remaining {
        return Err(refuse("PROJECT_INPUT_LIMIT"));
    }
    Ok(raw)
}

#[cfg(not(unix))]
fn read_input(_: &File, _: &str, _: usize) -> Result<Vec<u8>, Error> {
    Err(refuse("PROJECT_PLATFORM_UNAVAILABLE"))
}

fn record_digest(definition: &ProjectProfile, inputs: &[SuppliedInput]) -> Result<String, Error> {
    Ok(canonical_digest(&serde_json::json!({
        "profile": PROJECT_PROFILE, "definition": definition, "inputs": inputs
    }))?)
}

pub fn capture_project(root: &Path, definition: ProjectProfile) -> Result<ProjectCapture, Error> {
    definition.validate()?;
    if std::fs::symlink_metadata(root)?.file_type().is_symlink() {
        return Err(refuse("PROJECT_ROOT_SYMLINK"));
    }
    let directory = File::open(root)?;
    if !directory.metadata()?.is_dir() {
        return Err(refuse("PROJECT_ROOT_NOT_DIRECTORY"));
    }
    let mut total = 0;
    let mut inputs = Vec::new();
    let mut paths = definition.inputs.clone();
    paths.sort();
    for path in &paths {
        let raw = read_input(&directory, path, MAX_INPUT_BYTES.saturating_sub(total))?;
        total += raw.len();
        let receipt = InputReceipt {
            path: path.clone(),
            digest: byte_digest(&raw),
            byte_length: SafeInteger::new(raw.len() as u64).expect("bounded"),
        };
        let content = String::from_utf8(raw).map_err(|_| refuse("PROJECT_INPUT_UTF8"))?;
        inputs.push(SuppliedInput { receipt, content });
    }
    // Recheck selected paths after capture. Sequential reads do not promise an atomic FS snapshot.
    for input in &inputs {
        let raw = read_input(&directory, &input.receipt.path, MAX_INPUT_BYTES)?;
        if byte_digest(&raw) != input.receipt.digest {
            return Err(refuse("PROJECT_INPUT_CHANGED"));
        }
    }
    let digest = record_digest(&definition, &inputs)?;
    let record = ProjectCapture {
        profile: PROJECT_PROFILE.into(),
        definition,
        inputs,
        digest,
    };
    // Escaping and record metadata also count against the normal CLI input limit.
    if canonical_bytes(&record)?.len() >= MAX_INPUT_BYTES {
        return Err(refuse("PROJECT_RECORD_LIMIT"));
    }
    Ok(record)
}

pub fn verify_project_capture(record: &ProjectCapture) -> Result<serde_json::Value, Error> {
    record.definition.validate()?;
    if record.profile != PROJECT_PROFILE || record.inputs.len() != record.definition.inputs.len() {
        return Err(refuse("PROJECT_RECORD_PROFILE"));
    }
    let mut paths = record.definition.inputs.clone();
    paths.sort();
    let mut total: usize = 0;
    for (input, path) in record.inputs.iter().zip(paths) {
        let raw = input.content.as_bytes();
        total = total.saturating_add(raw.len());
        if input.receipt.path != path
            || input.receipt.digest != byte_digest(raw)
            || input.receipt.byte_length != SafeInteger::new(raw.len() as u64).expect("addressable")
            || total > MAX_INPUT_BYTES
        {
            return Err(refuse("PROJECT_RECORD_INPUT"));
        }
    }
    if record.digest != record_digest(&record.definition, &record.inputs)?
        || canonical_bytes(record)?.len() >= MAX_INPUT_BYTES
    {
        return Err(refuse("PROJECT_RECORD_DIGEST"));
    }
    Ok(serde_json::json!({
        "status": "verified-project-input-bindings",
        "profile": PROJECT_PROFILE, "digest": record.digest,
        "project": record.definition.id, "inputCount": record.inputs.len(),
        "inputBytes": total, "sourceRediscovery": "not-performed",
        "secretResolution": "not-performed", "toolExecution": "not-performed",
        "admission": "not-performed", "authorizationNow": "not-evaluated",
        "activation": "not-performed"
    }))
}

/// Materialize only verified selected bytes into a new retained directory.
/// Partial failures are preserved; this never publishes a selection or runs tools.
pub fn stage_project_capture(
    record: &ProjectCapture,
    destination: &Path,
) -> Result<serde_json::Value, Error> {
    let verification = verify_project_capture(record)?;
    stage_selected_inputs(&record.inputs, destination)?;
    Ok(serde_json::json!({
        "status":"staged-project-inputs", "profile":PROJECT_PROFILE,
        "digest":record.digest, "project":record.definition.id,
        "inputs":record.inputs.iter().map(|v| &v.receipt).collect::<Vec<_>>(),
        "inputCount":verification["inputCount"], "inputBytes":verification["inputBytes"],
        "selectedBytesRechecked":true, "permissions":"user-only-non-executable-files",
        "completeBuildContext":"not-established", "sourceRediscovery":"not-performed",
        "secretResolution":"not-performed", "toolExecution":"not-performed",
        "admission":"not-performed", "selectionPublication":"not-performed",
        "authorizationNow":"not-evaluated", "activation":"not-performed"
    }))
}

pub(crate) fn stage_selected_inputs(
    inputs: &[SuppliedInput],
    destination: &Path,
) -> Result<(), Error> {
    let paths = inputs
        .iter()
        .map(|v| v.receipt.path.as_str())
        .collect::<BTreeSet<_>>();
    if paths.len() != inputs.len()
        || inputs.iter().any(|v| {
            !relative_path(&v.receipt.path)
                || v.receipt
                    .path
                    .match_indices('/')
                    .any(|(i, _)| paths.contains(&v.receipt.path[..i]))
        })
    {
        return Err(refuse("PROJECT_STAGE_PATH_CONFLICT"));
    }
    stage_inputs(inputs, destination)
}

#[cfg(unix)]
fn stage_inputs(inputs: &[SuppliedInput], destination: &Path) -> Result<(), Error> {
    use rustix::fs::{Mode, OFlags, mkdirat, openat};
    use std::{
        fs::OpenOptions,
        io::Write,
        os::unix::fs::{MetadataExt, OpenOptionsExt},
    };
    let leaf = destination
        .file_name()
        .and_then(|v| v.to_str())
        .filter(|v| relative_path(v) && !v.contains('/'))
        .ok_or_else(|| refuse("PROJECT_STAGE_DESTINATION"))?;
    let parent = destination
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or(Path::new("."));
    if std::fs::symlink_metadata(parent)?.file_type().is_symlink() {
        return Err(refuse("PROJECT_STAGE_PARENT_SYMLINK"));
    }
    let directory_flags = OFlags::RDONLY | OFlags::DIRECTORY | OFlags::NOFOLLOW | OFlags::CLOEXEC;
    let parent = OpenOptions::new()
        .read(true)
        .custom_flags(directory_flags.bits() as i32)
        .open(parent)?;
    mkdirat(&parent, leaf, Mode::from_bits_truncate(0o700))
        .map_err(|_| refuse("PROJECT_STAGE_DESTINATION_UNAVAILABLE"))?;
    let directory = File::from(
        openat(&parent, leaf, directory_flags, Mode::empty())
            .map_err(|_| refuse("PROJECT_STAGE_DIRECTORY_UNAVAILABLE"))?,
    );
    for input in inputs {
        let mut current = directory.try_clone()?;
        let parts = input.receipt.path.split('/').collect::<Vec<_>>();
        for part in &parts[..parts.len() - 1] {
            match mkdirat(&current, *part, Mode::from_bits_truncate(0o700)) {
                Ok(()) => {}
                Err(rustix::io::Errno::EXIST) => {}
                Err(_) => return Err(refuse("PROJECT_STAGE_DIRECTORY_UNAVAILABLE")),
            }
            current = File::from(
                openat(&current, *part, directory_flags, Mode::empty())
                    .map_err(|_| refuse("PROJECT_STAGE_DIRECTORY_UNAVAILABLE"))?,
            );
        }
        let mut file = File::from(
            openat(
                &current,
                *parts.last().expect("validated nonempty input"),
                OFlags::WRONLY | OFlags::CREATE | OFlags::EXCL | OFlags::NOFOLLOW | OFlags::CLOEXEC,
                Mode::from_bits_truncate(0o600),
            )
            .map_err(|_| refuse("PROJECT_STAGE_INPUT_UNAVAILABLE"))?,
        );
        file.write_all(input.content.as_bytes())?;
    }
    let metadata = directory.metadata()?;
    let visible = File::from(
        openat(&parent, leaf, directory_flags, Mode::empty())
            .map_err(|_| refuse("PROJECT_STAGE_DIRECTORY_CHANGED"))?,
    );
    let visible_metadata = visible.metadata()?;
    if (metadata.dev(), metadata.ino()) != (visible_metadata.dev(), visible_metadata.ino()) {
        return Err(refuse("PROJECT_STAGE_DIRECTORY_CHANGED"));
    }
    for input in inputs {
        if read_input(&visible, &input.receipt.path, MAX_INPUT_BYTES)? != input.content.as_bytes() {
            return Err(refuse("PROJECT_STAGE_INPUT_CHANGED"));
        }
    }
    let path_view = OpenOptions::new()
        .read(true)
        .custom_flags(directory_flags.bits() as i32)
        .open(destination)?;
    let path_metadata = path_view.metadata()?;
    if (metadata.dev(), metadata.ino()) != (path_metadata.dev(), path_metadata.ino()) {
        return Err(refuse("PROJECT_STAGE_DIRECTORY_CHANGED"));
    }
    Ok(())
}

#[cfg(not(unix))]
fn stage_inputs(_: &[SuppliedInput], _: &Path) -> Result<(), Error> {
    Err(refuse("PROJECT_PLATFORM_UNAVAILABLE"))
}
