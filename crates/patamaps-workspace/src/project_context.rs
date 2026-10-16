//! Explicit retained opaque inputs. No discovery, tools, secret resolution or activation.
use crate::Error;
use patamaps_contracts::{
    JsonLimits, MAX_INPUT_BYTES, MAX_JSON_DEPTH, MAX_JSON_VALUES, SafeInteger, canonical_bytes,
    canonical_digest, parse_with_limits,
};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
const MAX_CONTEXT_RECORD_BYTES: usize = 64 * 1024 * 1024;
pub const CONTEXT_PROFILE: &str = "patamaps-project-context-selection-1";
pub const CONTEXT_RECORD: &str = "patamaps-project-context-1";
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum ContextSymlinks {
    #[default]
    Refuse,
    InternalClosed,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ProjectContextDefinition {
    pub profile: String,
    pub id: String,
    pub nonsecret_inputs: bool,
    pub paths: Vec<String>,
    #[serde(default)]
    pub symlinks: ContextSymlinks,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(
    tag = "kind",
    rename_all = "kebab-case",
    rename_all_fields = "camelCase",
    deny_unknown_fields
)]
pub enum ProjectContextEntry {
    File {
        digest: String,
        byte_length: SafeInteger,
        mode: SafeInteger,
    },
    Directory {
        mode: SafeInteger,
    },
    Symlink {
        target: String,
    },
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ProjectContextManifest {
    pub profile: String,
    pub definition_digest: String,
    pub entries: BTreeMap<String, ProjectContextEntry>,
    pub digest: String,
}
fn refuse() -> Error {
    Error::refused(
        "PROJECT_CONTEXT",
        "Explicit retained context refused; partial outputs retained",
    )
}
fn allowed(path: &str) -> bool {
    crate::relative_path(path)
        && path.len() <= 4096
        && path.split('/').count() <= 128
        && path.split('/').all(|p| {
            p != ".git"
                && !p.starts_with(".env")
                && p != ".npmrc"
                && ![
                    "target",
                    ".next",
                    "id_rsa",
                    "id_ed25519",
                    "server-reference-manifest.json",
                ]
                .contains(&p)
        })
}
fn selected(def: &ProjectContextDefinition) -> Result<BTreeSet<String>, Error> {
    if def.profile != CONTEXT_PROFILE
        || !def.nonsecret_inputs
        || def.id.is_empty()
        || def.id.len() > 256
        || def.id.chars().any(char::is_control)
        || def.paths.is_empty()
        || def.paths.len() > 262144
        || canonical_bytes(def)?.len() >= MAX_INPUT_BYTES
    {
        return Err(refuse());
    }
    let mut result = BTreeSet::new();
    let mut originals = BTreeSet::new();
    for path in &def.paths {
        if !allowed(path) || !originals.insert(path) {
            return Err(refuse());
        }
        result.insert(path.clone());
        for (index, _) in path.match_indices('/') {
            result.insert(path[..index].into());
            if result.len() > 262144 {
                return Err(refuse());
            }
        }
    }
    Ok(result)
}
fn address(manifest: &ProjectContextManifest) -> Result<String, Error> {
    #[derive(Serialize)]
    #[serde(rename_all = "camelCase")]
    struct Unsigned<'a> {
        profile: &'a str,
        definition_digest: &'a str,
        entries: &'a BTreeMap<String, ProjectContextEntry>,
    }
    Ok(canonical_digest(&Unsigned {
        profile: &manifest.profile,
        definition_digest: &manifest.definition_digest,
        entries: &manifest.entries,
    })?)
}
fn closure(entries: &BTreeMap<String, ProjectContextEntry>) -> Result<(), Error> {
    use std::collections::VecDeque;
    for (path, entry) in entries {
        for (i, _) in path.match_indices('/') {
            if !matches!(
                entries.get(&path[..i]),
                Some(ProjectContextEntry::Directory { .. })
            ) {
                return Err(refuse());
            }
        }
        let ProjectContextEntry::Symlink { target } = entry else {
            continue;
        };
        let mut resolved = path.split('/').map(str::to_owned).collect::<Vec<_>>();
        resolved.pop();
        let mut pending = VecDeque::new();
        let mut links = 0;
        let mut steps = 0;
        let push_target = |pending: &mut VecDeque<String>, target: &str| -> Result<(), Error> {
            if target.is_empty()
                || target.len() > 4096
                || target.starts_with('/')
                || target.contains(['\\', '\0'])
            {
                return Err(refuse());
            }
            for part in target.split('/').rev() {
                pending.push_front(part.to_owned());
            }
            if pending.len() > 8192 {
                return Err(refuse());
            }
            Ok(())
        };
        push_target(&mut pending, target)?;
        while let Some(part) = pending.pop_front() {
            steps += 1;
            if steps > 8192 {
                return Err(refuse());
            }
            match part.as_str() {
                "" | "." => continue,
                ".." => {
                    if resolved.pop().is_none() {
                        return Err(refuse());
                    }
                    continue;
                }
                _ => {}
            }
            let candidate = resolved
                .iter()
                .map(String::as_str)
                .chain(std::iter::once(part.as_str()))
                .collect::<Vec<_>>()
                .join("/");
            match entries.get(&candidate) {
                Some(ProjectContextEntry::Directory { .. }) => resolved.push(part),
                Some(ProjectContextEntry::File { .. }) => {
                    if !pending.is_empty() {
                        return Err(refuse());
                    }
                    resolved.push(part);
                }
                Some(ProjectContextEntry::Symlink { target }) => {
                    links += 1;
                    if links > 128 {
                        return Err(refuse());
                    }
                    push_target(&mut pending, target)?;
                }
                None => return Err(refuse()),
            }
        }
    }
    Ok(())
}
fn validate(
    def: &ProjectContextDefinition,
    manifest: &ProjectContextManifest,
) -> Result<(), Error> {
    if manifest.profile != CONTEXT_RECORD
        || manifest.definition_digest != canonical_digest(def)?
        || manifest.digest != address(manifest)?
        || selected(def)? != manifest.entries.keys().cloned().collect()
        || canonical_bytes(manifest)?.len() >= MAX_CONTEXT_RECORD_BYTES
    {
        return Err(refuse());
    }
    let mut total = 0u64;
    for entry in manifest.entries.values() {
        match entry {
            ProjectContextEntry::File {
                digest,
                byte_length,
                mode,
            } => {
                let hex = digest.strip_prefix("sha256:").ok_or_else(refuse)?;
                if hex.len() != 64
                    || !hex
                        .bytes()
                        .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
                    || byte_length.get() > 1024 * 1024 * 1024
                    || mode.get() > 0o777
                    || mode.get() & 0o400 == 0
                {
                    return Err(refuse());
                }
                total = total.checked_add(byte_length.get()).ok_or_else(refuse)?;
            }
            ProjectContextEntry::Directory { mode } => {
                if mode.get() > 0o777 || mode.get() & 0o500 != 0o500 {
                    return Err(refuse());
                }
            }
            ProjectContextEntry::Symlink { .. } => {
                if def.symlinks != ContextSymlinks::InternalClosed {
                    return Err(refuse());
                }
            }
        }
    }
    if total > 16 * 1024 * 1024 * 1024 {
        return Err(refuse());
    }
    closure(&manifest.entries)
}
#[cfg(unix)]
mod unix {
    use super::*;
    use crate::project_fs::{self, StageRoot};
    use rustix::fs::{AtFlags, Dir, FileType, Mode, readlinkat, statat};
    use sha2::{Digest, Sha256};
    use std::{
        fs::File,
        io::{Read, Write},
        os::unix::fs::MetadataExt,
        path::Path,
    };
    fn integer(v: u64) -> SafeInteger {
        SafeInteger::new(v).expect("bounded metadata")
    }
    fn mode(file: &File) -> Result<SafeInteger, Error> {
        let value = file.metadata()?.mode() & 0o7777;
        if value > 0o777 {
            return Err(refuse());
        }
        Ok(integer(u64::from(value)))
    }
    fn describe(root: &File, path: &str) -> Result<ProjectContextEntry, Error> {
        let (parent, leaf) = project_fs::parent(root, path, false)?;
        let metadata = statat(&parent, leaf.as_str(), AtFlags::SYMLINK_NOFOLLOW)
            .map_err(std::io::Error::from)?;
        match FileType::from_raw_mode(metadata.st_mode) {
            FileType::RegularFile => {
                let file = crate::project::open_project_file(root, path)?;
                let size = file.metadata()?.len();
                if size > 1024 * 1024 * 1024 {
                    return Err(refuse());
                }
                let permissions = mode(&file)?;
                if permissions.get() & 0o400 == 0 {
                    return Err(refuse());
                }
                Ok(ProjectContextEntry::File {
                    digest: String::new(),
                    byte_length: integer(size),
                    mode: permissions,
                })
            }
            FileType::Directory => {
                let permissions = mode(&project_fs::directory(root, path)?)?;
                if permissions.get() & 0o500 != 0o500 {
                    return Err(refuse());
                }
                Ok(ProjectContextEntry::Directory { mode: permissions })
            }
            FileType::Symlink => {
                let value =
                    readlinkat(&parent, leaf.as_str(), Vec::new()).map_err(std::io::Error::from)?;
                Ok(ProjectContextEntry::Symlink {
                    target: value.into_string().map_err(|_| refuse())?,
                })
            }
            _ => Err(refuse()),
        }
    }
    fn bytes(mut source: File, mut destination: Option<&mut File>) -> Result<(String, u64), Error> {
        let before = source.metadata()?;
        let mut hash = Sha256::new();
        let mut length = 0u64;
        let mut buffer = [0u8; 65536];
        loop {
            let n = source.read(&mut buffer)?;
            if n == 0 {
                break;
            }
            length += n as u64;
            if length > 1024 * 1024 * 1024 {
                return Err(refuse());
            }
            hash.update(&buffer[..n]);
            if let Some(out) = destination.as_mut() {
                out.write_all(&buffer[..n])?
            }
        }
        let after = source.metadata()?;
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
        ) || length != before.len()
        {
            return Err(refuse());
        }
        Ok((format!("sha256:{:x}", hash.finalize()), length))
    }
    fn write_json(stage: &StageRoot, path: &str, value: &impl Serialize) -> Result<(), Error> {
        let raw = canonical_bytes(value)?;
        if raw.len() >= MAX_CONTEXT_RECORD_BYTES {
            return Err(refuse());
        }
        let mut file = stage.file(path)?;
        file.write_all(&raw)?;
        file.sync_all()?;
        Ok(())
    }
    fn read_json<T: serde::de::DeserializeOwned>(root: &File, path: &str) -> Result<T, Error> {
        let mut raw = Vec::new();
        crate::project::open_project_file(root, path)?
            .take((MAX_CONTEXT_RECORD_BYTES + 1) as u64)
            .read_to_end(&mut raw)?;
        if raw.len() >= MAX_CONTEXT_RECORD_BYTES {
            return Err(refuse());
        }
        Ok(parse_with_limits(
            &raw,
            JsonLimits {
                max_bytes: MAX_CONTEXT_RECORD_BYTES,
                max_depth: MAX_JSON_DEPTH,
                max_values: MAX_JSON_VALUES,
            },
        )?)
    }
    fn tree(
        root: &File,
        prefix: &str,
        found: &mut BTreeMap<String, u8>,
        links: bool,
    ) -> Result<(), Error> {
        if found.len() > 262144 || prefix.split('/').count() > 128 {
            return Err(refuse());
        }
        let dir = project_fs::directory(root, prefix)?;
        for entry in Dir::read_from(&dir).map_err(std::io::Error::from)? {
            let entry = entry.map_err(std::io::Error::from)?;
            let name = entry.file_name().to_str().map_err(|_| refuse())?;
            if name == "." || name == ".." {
                continue;
            }
            if found.len() >= 262144 {
                return Err(refuse());
            }
            let path = if prefix.is_empty() {
                name.to_owned()
            } else {
                format!("{prefix}/{name}")
            };
            if !allowed(&path) {
                return Err(refuse());
            }
            let metadata =
                statat(&dir, name, AtFlags::SYMLINK_NOFOLLOW).map_err(std::io::Error::from)?;
            match FileType::from_raw_mode(metadata.st_mode) {
                FileType::Directory => {
                    found.insert(path.clone(), 1);
                    tree(root, &path, found, links)?;
                }
                FileType::RegularFile => {
                    found.insert(path, 0);
                }
                FileType::Symlink if links => {
                    found.insert(path, 2);
                }
                _ => return Err(refuse()),
            }
        }
        Ok(())
    }
    fn root_identity(path: &Path, held: &File) -> Result<(), Error> {
        let expected = held.metadata()?;
        let visible = project_fs::root(path)?.metadata()?;
        if (expected.dev(), expected.ino()) != (visible.dev(), visible.ino()) {
            return Err(refuse());
        }
        Ok(())
    }
    fn isolated_destination(source: &Path, destination: &Path) -> Result<(), Error> {
        let owner = source.canonicalize()?;
        let parent = destination
            .parent()
            .filter(|p| !p.as_os_str().is_empty())
            .unwrap_or(Path::new("."))
            .canonicalize()?;
        let leaf = destination.file_name().ok_or_else(refuse)?;
        if parent.join(leaf).starts_with(owner) {
            return Err(refuse());
        }
        Ok(())
    }
    fn load(
        snapshot: &Path,
    ) -> Result<(File, ProjectContextDefinition, ProjectContextManifest), Error> {
        let root = project_fs::root(snapshot)?;
        let names = Dir::read_from(&root)
            .map_err(std::io::Error::from)?
            .map(|v| {
                v.map_err(std::io::Error::from).and_then(|v| {
                    v.file_name()
                        .to_str()
                        .map(str::to_owned)
                        .map_err(|_| std::io::Error::other("non-UTF8 context member"))
                })
            })
            .collect::<Result<BTreeSet<_>, _>>()?;
        if names
            .into_iter()
            .filter(|v| v != "." && v != "..")
            .collect::<BTreeSet<_>>()
            != BTreeSet::from([
                "selection.json".to_owned(),
                "manifest.json".to_owned(),
                "data".to_owned(),
            ])
        {
            return Err(refuse());
        }
        let definition = read_json(&root, "selection.json")?;
        let manifest: ProjectContextManifest = read_json(&root, "manifest.json")?;
        validate(&definition, &manifest)?;
        let data = project_fs::directory(&root, "data")?;
        let mut found = BTreeMap::new();
        tree(&data, "", &mut found, false)?;
        let expected = manifest
            .entries
            .iter()
            .filter_map(|(p, e)| match e {
                ProjectContextEntry::Directory { .. } => Some((p.clone(), 1)),
                ProjectContextEntry::File { .. } => Some((p.clone(), 0)),
                _ => None,
            })
            .collect::<BTreeMap<_, _>>();
        if found != expected {
            return Err(refuse());
        }
        for (path, entry) in &manifest.entries {
            if let ProjectContextEntry::File {
                digest,
                byte_length,
                ..
            } = entry
            {
                let actual = bytes(crate::project::open_project_file(&data, path)?, None)?;
                if actual != (digest.clone(), byte_length.get()) {
                    return Err(refuse());
                }
            }
        }
        root_identity(snapshot, &root)?;
        Ok((root, definition, manifest))
    }
    pub fn capture_project_context(
        source: &Path,
        snapshot: &Path,
        definition: &ProjectContextDefinition,
    ) -> Result<serde_json::Value, Error> {
        let paths = selected(definition)?;
        let original = project_fs::root(source)?;
        let mut entries = paths
            .into_iter()
            .map(|p| describe(&original, &p).map(|v| (p, v)))
            .collect::<Result<BTreeMap<_, _>, _>>()?;
        closure(&entries)?;
        if definition.symlinks == ContextSymlinks::Refuse
            && entries
                .values()
                .any(|v| matches!(v, ProjectContextEntry::Symlink { .. }))
        {
            return Err(refuse());
        }
        let total = entries
            .values()
            .filter_map(|v| match v {
                ProjectContextEntry::File { byte_length, .. } => Some(byte_length.get()),
                _ => None,
            })
            .sum::<u64>();
        if total > 16 * 1024 * 1024 * 1024 {
            return Err(refuse());
        }
        // Input validation precedes every destination creation.
        isolated_destination(source, snapshot)?;
        let stage = StageRoot::create(snapshot)?;
        let data = StageRoot::create(&snapshot.join("data"))?;
        for (path, entry) in &mut entries {
            match entry {
                ProjectContextEntry::Directory { .. } => {
                    data.mkdir(path)?;
                }
                ProjectContextEntry::File {
                    digest,
                    byte_length,
                    ..
                } => {
                    let mut output = data.file(path)?;
                    let (hash, length) = bytes(
                        crate::project::open_project_file(&original, path)?,
                        Some(&mut output),
                    )?;
                    if length != byte_length.get() {
                        return Err(refuse());
                    }
                    *digest = hash;
                }
                ProjectContextEntry::Symlink { .. } => {}
            }
        }
        let mut manifest = ProjectContextManifest {
            profile: CONTEXT_RECORD.into(),
            definition_digest: canonical_digest(definition)?,
            entries,
            digest: String::new(),
        };
        manifest.digest = address(&manifest)?;
        validate(definition, &manifest)?;
        for (path, entry) in &manifest.entries {
            match (entry, describe(&original, path)?) {
                (
                    ProjectContextEntry::File {
                        digest,
                        byte_length,
                        mode,
                    },
                    ProjectContextEntry::File { mode: now, .. },
                ) => {
                    if *mode != now
                        || bytes(crate::project::open_project_file(&original, path)?, None)?
                            != (digest.clone(), byte_length.get())
                    {
                        return Err(refuse());
                    }
                }
                (
                    ProjectContextEntry::Directory { mode },
                    ProjectContextEntry::Directory { mode: now },
                ) => {
                    if *mode != now {
                        return Err(refuse());
                    }
                }
                (
                    ProjectContextEntry::Symlink { target },
                    ProjectContextEntry::Symlink { target: now },
                ) => {
                    if *target != now {
                        return Err(refuse());
                    }
                }
                _ => return Err(refuse()),
            }
        }
        root_identity(source, &original)?;
        data.verify_identity()?;
        write_json(&stage, "selection.json", definition)?;
        write_json(&stage, "manifest.json", &manifest)?;
        stage.verify_identity()?;
        Ok(
            serde_json::json!({"status":"captured-project-context","digest":manifest.digest,"entries":manifest.entries.len(),
            "fileBytes":total,"completeBuildContextEstablished":false,"activation":"not-performed","durability":"not-attested"}),
        )
    }
    pub fn verify_project_context(snapshot: &Path) -> Result<serde_json::Value, Error> {
        let (_, _, manifest) = load(snapshot)?;
        Ok(
            serde_json::json!({"status":"verified-project-context","digest":manifest.digest,"entries":manifest.entries.len(),
            "originalSourceAccess":"not-required","toolExecution":"not-performed","activation":"not-performed"}),
        )
    }
    pub fn stage_project_context(
        snapshot: &Path,
        destination: &Path,
    ) -> Result<serde_json::Value, Error> {
        isolated_destination(snapshot, destination)?;
        let (root, _, manifest) = load(snapshot)?;
        let data = project_fs::directory(&root, "data")?;
        let stage = StageRoot::create(destination)?;
        for (path, entry) in &manifest.entries {
            match entry {
                ProjectContextEntry::Directory { .. } => {
                    stage.mkdir(path)?;
                }
                ProjectContextEntry::File {
                    digest,
                    byte_length,
                    mode,
                } => {
                    let mut out = stage.file(path)?;
                    if bytes(
                        crate::project::open_project_file(&data, path)?,
                        Some(&mut out),
                    )? != (digest.clone(), byte_length.get())
                    {
                        return Err(refuse());
                    }
                    rustix::fs::fchmod(
                        &out,
                        Mode::from_bits_truncate(mode.get().try_into().map_err(|_| refuse())?),
                    )
                    .map_err(std::io::Error::from)?;
                }
                ProjectContextEntry::Symlink { target } => stage.symlink(path, target)?,
            }
        }
        let mut directories = manifest
            .entries
            .iter()
            .filter_map(|(p, e)| {
                if let ProjectContextEntry::Directory { mode } = e {
                    Some((p, mode))
                } else {
                    None
                }
            })
            .collect::<Vec<_>>();
        directories.sort_by_key(|(p, _)| std::cmp::Reverse(p.split('/').count()));
        for (path, mode) in directories {
            rustix::fs::fchmod(
                project_fs::directory(&stage.directory, path)?,
                Mode::from_bits_truncate(mode.get().try_into().map_err(|_| refuse())?),
            )
            .map_err(std::io::Error::from)?;
        }
        for (path, entry) in &manifest.entries {
            match (entry, describe(&stage.directory, path)?) {
                (
                    ProjectContextEntry::File {
                        digest,
                        byte_length,
                        mode,
                    },
                    ProjectContextEntry::File { mode: now, .. },
                ) => {
                    if *mode != now
                        || bytes(
                            crate::project::open_project_file(&stage.directory, path)?,
                            None,
                        )? != (digest.clone(), byte_length.get())
                    {
                        return Err(refuse());
                    }
                }
                (
                    ProjectContextEntry::Directory { mode },
                    ProjectContextEntry::Directory { mode: now },
                ) => {
                    if *mode != now {
                        return Err(refuse());
                    }
                }
                (
                    ProjectContextEntry::Symlink { target },
                    ProjectContextEntry::Symlink { target: now },
                ) => {
                    if *target != now {
                        return Err(refuse());
                    }
                }
                _ => return Err(refuse()),
            }
        }
        let mut staged = BTreeMap::new();
        tree(&stage.directory, "", &mut staged, true)?;
        let expected = manifest
            .entries
            .iter()
            .map(|(p, e)| {
                (
                    p.clone(),
                    match e {
                        ProjectContextEntry::File { .. } => 0,
                        ProjectContextEntry::Directory { .. } => 1,
                        ProjectContextEntry::Symlink { .. } => 2,
                    },
                )
            })
            .collect::<BTreeMap<_, _>>();
        if staged != expected {
            return Err(refuse());
        }
        stage.verify_identity()?;
        root_identity(snapshot, &root)?;
        Ok(
            serde_json::json!({"status":"staged-project-context","digest":manifest.digest,"entries":manifest.entries.len(),
            "destination":destination,"completeBuildContextEstablished":false,"activation":"not-performed","durability":"not-attested"}),
        )
    }
}
#[cfg(unix)]
pub use unix::{capture_project_context, stage_project_context, verify_project_context};
#[cfg(not(unix))]
pub fn capture_project_context(
    _: &std::path::Path,
    _: &std::path::Path,
    _: &ProjectContextDefinition,
) -> Result<serde_json::Value, Error> {
    Err(refuse())
}
#[cfg(not(unix))]
pub fn verify_project_context(_: &std::path::Path) -> Result<serde_json::Value, Error> {
    Err(refuse())
}
#[cfg(not(unix))]
pub fn stage_project_context(
    _: &std::path::Path,
    _: &std::path::Path,
) -> Result<serde_json::Value, Error> {
    Err(refuse())
}

#[cfg(all(test, unix))]
mod tests {
    use super::*;
    use std::{
        fs,
        os::unix::fs::{PermissionsExt, symlink},
        path::PathBuf,
        sync::atomic::{AtomicU64, Ordering},
    };
    static SEQUENCE: AtomicU64 = AtomicU64::new(0);
    struct Temp(PathBuf);
    impl Temp {
        fn new() -> Self {
            let path = std::env::temp_dir().join(format!(
                "patamaps-context-{}-{}",
                std::process::id(),
                SEQUENCE.fetch_add(1, Ordering::Relaxed)
            ));
            fs::create_dir(&path).unwrap();
            Self(path)
        }
    }
    impl Drop for Temp {
        fn drop(&mut self) {
            eprintln!("Retained context fixture: {}", self.0.display());
        }
    }
    fn fixture() -> (Temp, PathBuf, ProjectContextDefinition) {
        let tmp = Temp::new();
        let source = tmp.0.join("owner");
        fs::create_dir(&source).unwrap();
        fs::create_dir(source.join("tools")).unwrap();
        fs::create_dir(source.join("empty")).unwrap();
        fs::write(source.join("tools/program"), [0, 255, 128, 1, 0]).unwrap();
        fs::set_permissions(
            source.join("tools/program"),
            fs::Permissions::from_mode(0o751),
        )
        .unwrap();
        symlink("tools/program", source.join("alias")).unwrap();
        let definition = ProjectContextDefinition {
            profile: CONTEXT_PROFILE.into(),
            id: "urn:test:binary-context".into(),
            nonsecret_inputs: true,
            paths: vec!["tools/program".into(), "empty".into(), "alias".into()],
            symlinks: ContextSymlinks::InternalClosed,
        };
        (tmp, source, definition)
    }
    #[test]
    fn binary_modes_empty_directories_and_internal_links_reconstruct_without_source() {
        let (tmp, source, definition) = fixture();
        let snapshot = tmp.0.join("snapshot");
        let captured = capture_project_context(&source, &snapshot, &definition).unwrap();
        fs::rename(&source, tmp.0.join("owner.retained-offline")).unwrap();
        assert_eq!(
            verify_project_context(&snapshot).unwrap()["digest"],
            captured["digest"]
        );
        let dest = tmp.0.join("staged");
        stage_project_context(&snapshot, &dest).unwrap();
        assert_eq!(
            fs::read(dest.join("tools/program")).unwrap(),
            [0, 255, 128, 1, 0]
        );
        assert_eq!(
            fs::metadata(dest.join("tools/program"))
                .unwrap()
                .permissions()
                .mode()
                & 0o777,
            0o751
        );
        assert_eq!(
            fs::read_link(dest.join("alias")).unwrap(),
            PathBuf::from("tools/program")
        );
        assert!(dest.join("empty").is_dir());
        assert!(stage_project_context(&snapshot, &dest).is_err());
    }
    #[test]
    fn unsafe_selection_links_and_nested_destinations_refuse_before_creation() {
        let (tmp, source, mut definition) = fixture();
        definition.symlinks = ContextSymlinks::Refuse;
        let dest = tmp.0.join("no-links");
        assert!(capture_project_context(&source, &dest, &definition).is_err());
        assert!(!dest.exists());
        definition.symlinks = ContextSymlinks::InternalClosed;
        for path in [".env.local", "target/object", ".git/config"] {
            let mut invalid = definition.clone();
            invalid.paths.push(path.into());
            let dest = tmp.0.join(path.replace('/', "-"));
            assert!(capture_project_context(&source, &dest, &invalid).is_err());
            assert!(!dest.exists());
        }
        let inside = source.join("snapshot");
        assert!(capture_project_context(&source, &inside, &definition).is_err());
        assert!(!inside.exists());
        symlink("../../outside", source.join("escape")).unwrap();
        definition.paths.push("escape".into());
        let dest = tmp.0.join("escape-snapshot");
        assert!(capture_project_context(&source, &dest, &definition).is_err());
        assert!(!dest.exists());
        let (tmp2, source2, mut definition2) = fixture();
        symlink("loop-b", source2.join("loop-a")).unwrap();
        symlink("loop-a", source2.join("loop-b")).unwrap();
        definition2.paths.extend(["loop-a".into(), "loop-b".into()]);
        assert!(capture_project_context(&source2, &tmp2.0.join("cycle"), &definition2).is_err());
    }
    #[test]
    fn parent_components_are_resolved_after_links_and_never_through_files() {
        for target in ["root-link/../tools/program", "tools/program/.."] {
            let (tmp, source, mut definition) = fixture();
            symlink(".", source.join("root-link")).unwrap();
            symlink(target, source.join("compound")).unwrap();
            definition
                .paths
                .extend(["root-link".into(), "compound".into()]);
            let destination = tmp.0.join("refused");
            assert!(capture_project_context(&source, &destination, &definition).is_err());
            assert!(!destination.exists());
        }
    }
    #[test]
    fn corrupt_blob_extra_members_and_rehashed_metadata_cannot_stage() {
        let (tmp, source, definition) = fixture();
        let snapshot = tmp.0.join("snapshot");
        capture_project_context(&source, &snapshot, &definition).unwrap();
        fs::write(snapshot.join("data/tools/program"), b"changed").unwrap();
        assert!(verify_project_context(&snapshot).is_err());
        let dest = tmp.0.join("corrupt");
        assert!(stage_project_context(&snapshot, &dest).is_err());
        assert!(!dest.exists());
        let (tmp, source, definition) = fixture();
        let snapshot = tmp.0.join("snapshot");
        capture_project_context(&source, &snapshot, &definition).unwrap();
        fs::write(snapshot.join("data/unlisted"), b"extra").unwrap();
        assert!(verify_project_context(&snapshot).is_err());
        let (tmp, source, definition) = fixture();
        let snapshot = tmp.0.join("snapshot");
        capture_project_context(&source, &snapshot, &definition).unwrap();
        let mut manifest: ProjectContextManifest =
            patamaps_contracts::parse(&fs::read(snapshot.join("manifest.json")).unwrap()).unwrap();
        manifest.entries.insert(
            "alias".into(),
            ProjectContextEntry::Symlink {
                target: "../outside".into(),
            },
        );
        manifest.digest = address(&manifest).unwrap();
        fs::write(
            snapshot.join("manifest.json"),
            canonical_bytes(&manifest).unwrap(),
        )
        .unwrap();
        assert!(verify_project_context(&snapshot).is_err());
        let dest = tmp.0.join("escape");
        assert!(stage_project_context(&snapshot, &dest).is_err());
        assert!(!dest.exists());
    }
}
