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
/// Explicit sealed context reference for a native retained build.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ProjectBuildContext {
    pub profile: String,
    pub snapshot: String,
    pub digest: String,
    pub overlays: BTreeMap<String, String>,
    pub writable_paths: Vec<String>,
}
impl ProjectBuildContext {
    pub(crate) fn validate(&self) -> Result<(), Error> {
        let digest = |v: &str| {
            v.strip_prefix("sha256:").is_some_and(|h| {
                h.len() == 64
                    && h.bytes()
                        .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
            })
        };
        if self.profile != "patamaps-project-build-context-1"
            || !std::path::Path::new(&self.snapshot).is_absolute()
            || self.snapshot.len() > 4096
            || self.snapshot.chars().any(char::is_control)
            || !digest(&self.digest)
            || self.overlays.len() > 8192
            || self.writable_paths.len() > 64
            || self.overlays.iter().any(|(p, d)| !allowed(p) || !digest(d))
        {
            return Err(refuse());
        }
        let mut paths = BTreeSet::new();
        for p in &self.writable_paths {
            if !crate::relative_path(p)
                || p.split('/').count() > 128
                || !paths.insert(p.as_str())
                || p.split('/')
                    .any(|v| v == ".git" || v.starts_with(".env") || v == ".npmrc")
            {
                return Err(refuse());
            }
        }
        if paths
            .iter()
            .any(|p| p.match_indices('/').any(|(i, _)| paths.contains(&p[..i])))
        {
            return Err(refuse());
        }
        Ok(())
    }
}
fn refuse() -> Error {
    Error::refused(
        "PROJECT_CONTEXT",
        "Explicit retained context refused; partial outputs retained",
    )
}
pub(crate) fn allowed(path: &str) -> bool {
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
    // Traverse closed trees from held directory descriptors. Each file still
    // gets a complete hash and metadata check; ancestor paths are not reopened
    // for every leaf. Collect names before descending to keep FD use bounded.
    fn verify_tree(
        root: &File,
        expected: &BTreeMap<String, ProjectContextEntry>,
        skipped: &[String],
        permissions: bool,
    ) -> Result<(), Error> {
        fn identity(parent: &File, name: &str, meta: &std::fs::Metadata) -> Result<(), Error> {
            let visible = if meta.is_dir() {
                project_fs::directory(parent, name)?.metadata()?
            } else {
                crate::project::open_project_file(parent, name)?.metadata()?
            };
            if (
                visible.dev(),
                visible.ino(),
                visible.len(),
                visible.mode(),
                visible.mtime(),
                visible.mtime_nsec(),
                visible.ctime(),
                visible.ctime_nsec(),
            ) != (
                meta.dev(),
                meta.ino(),
                meta.len(),
                meta.mode(),
                meta.mtime(),
                meta.mtime_nsec(),
                meta.ctime(),
                meta.ctime_nsec(),
            ) {
                return Err(refuse());
            }
            Ok(())
        }
        fn stamp(meta: &std::fs::Metadata) -> (u64, u64, u32, i64, i64, i64, i64) {
            (
                meta.dev(),
                meta.ino(),
                meta.mode(),
                meta.mtime(),
                meta.mtime_nsec(),
                meta.ctime(),
                meta.ctime_nsec(),
            )
        }
        fn walk(
            dir: &File,
            prefix: &str,
            depth: usize,
            expected: &BTreeMap<String, ProjectContextEntry>,
            skipped: &[String],
            permissions: bool,
            seen: &mut usize,
        ) -> Result<(), Error> {
            if depth > 128 {
                return Err(refuse());
            }
            let before = dir.metadata()?;
            let children = {
                let mut children = Vec::new();
                for item in Dir::read_from(dir).map_err(std::io::Error::from)? {
                    let item = item.map_err(std::io::Error::from)?;
                    let name = item.file_name().to_str().map_err(|_| refuse())?;
                    if name == "." || name == ".." {
                        continue;
                    }
                    let path = if prefix.is_empty() {
                        name.to_owned()
                    } else {
                        format!("{prefix}/{name}")
                    };
                    if skipped.contains(&path) {
                        continue;
                    }
                    if !allowed(&path)
                        || !expected.contains_key(&path)
                        || children.len() + *seen >= 262144
                    {
                        return Err(refuse());
                    }
                    children.push((name.to_owned(), path));
                }
                children
            };
            for (name, path) in children {
                *seen += 1;
                if *seen > 262144 {
                    return Err(refuse());
                }
                match &expected[&path] {
                    ProjectContextEntry::Directory { mode: want } => {
                        let child = project_fs::directory(dir, &name)?;
                        let metadata = child.metadata()?;
                        if permissions && mode(&child)? != *want {
                            return Err(refuse());
                        }
                        walk(
                            &child,
                            &path,
                            depth + 1,
                            expected,
                            skipped,
                            permissions,
                            seen,
                        )?;
                        identity(dir, &name, &metadata)?;
                    }
                    ProjectContextEntry::File {
                        digest,
                        byte_length,
                        mode: want,
                    } => {
                        let file = crate::project::open_project_file(dir, &name)?;
                        let metadata = file.metadata()?;
                        if permissions && mode(&file)? != *want {
                            return Err(refuse());
                        }
                        if bytes(file, None)? != (digest.clone(), byte_length.get()) {
                            return Err(refuse());
                        }
                        identity(dir, &name, &metadata)?;
                    }
                    ProjectContextEntry::Symlink { target } => {
                        let metadata = statat(dir, name.as_str(), AtFlags::SYMLINK_NOFOLLOW)
                            .map_err(std::io::Error::from)?;
                        if FileType::from_raw_mode(metadata.st_mode) != FileType::Symlink {
                            return Err(refuse());
                        }
                        let actual = readlinkat(dir, name.as_str(), Vec::new())
                            .map_err(std::io::Error::from)?;
                        if actual.into_string().map_err(|_| refuse())? != *target {
                            return Err(refuse());
                        }
                        let after = statat(dir, name.as_str(), AtFlags::SYMLINK_NOFOLLOW)
                            .map_err(std::io::Error::from)?;
                        if (metadata.st_dev, metadata.st_ino) != (after.st_dev, after.st_ino) {
                            return Err(refuse());
                        }
                    }
                }
            }
            if stamp(&before) != stamp(&dir.metadata()?) {
                return Err(refuse());
            }
            Ok(())
        }
        let mut seen = 0;
        walk(root, "", 0, expected, skipped, permissions, &mut seen)?;
        if seen != expected.len() {
            return Err(refuse());
        }
        Ok(())
    }
    fn copy_context_tree(
        source: &File,
        destination: &File,
        entries: &BTreeMap<String, ProjectContextEntry>,
    ) -> Result<(), Error> {
        let mut children: BTreeMap<&str, Vec<&str>> = BTreeMap::new();
        for path in entries.keys() {
            let parent = path.rsplit_once('/').map_or("", |(parent, _)| parent);
            children.entry(parent).or_default().push(path);
        }
        fn walk(
            source_root: &File,
            destination: &File,
            prefix: &str,
            depth: usize,
            children: &BTreeMap<&str, Vec<&str>>,
            entries: &BTreeMap<String, ProjectContextEntry>,
        ) -> Result<(), Error> {
            if depth > 128 {
                return Err(refuse());
            }
            let Some(paths) = children.get(prefix) else {
                return Ok(());
            };
            let mut source: Option<File> = None;
            for path in paths {
                let name = path.rsplit('/').next().ok_or_else(refuse)?;
                match &entries[*path] {
                    ProjectContextEntry::Directory { mode: want } => {
                        drop(source.take());
                        rustix::fs::mkdirat(destination, name, Mode::from_bits_truncate(0o700))
                            .map_err(std::io::Error::from)?;
                        let output = project_fs::directory(destination, name)?;
                        walk(source_root, &output, path, depth + 1, children, entries)?;
                        rustix::fs::fchmod(
                            &output,
                            Mode::from_bits_truncate(want.get().try_into().map_err(|_| refuse())?),
                        )
                        .map_err(std::io::Error::from)?;
                    }
                    ProjectContextEntry::File {
                        digest,
                        byte_length,
                        mode: want,
                    } => {
                        if source.is_none() {
                            source = Some(project_fs::directory(source_root, prefix)?);
                        }
                        let mut output = File::from(
                            rustix::fs::openat(
                                destination,
                                name,
                                rustix::fs::OFlags::WRONLY
                                    | rustix::fs::OFlags::CREATE
                                    | rustix::fs::OFlags::EXCL
                                    | rustix::fs::OFlags::NOFOLLOW
                                    | rustix::fs::OFlags::CLOEXEC,
                                Mode::from_bits_truncate(0o600),
                            )
                            .map_err(std::io::Error::from)?,
                        );
                        if bytes(
                            crate::project::open_project_file(
                                source.as_ref().ok_or_else(refuse)?,
                                name,
                            )?,
                            Some(&mut output),
                        )? != (digest.clone(), byte_length.get())
                        {
                            return Err(refuse());
                        }
                        rustix::fs::fchmod(
                            &output,
                            Mode::from_bits_truncate(want.get().try_into().map_err(|_| refuse())?),
                        )
                        .map_err(std::io::Error::from)?;
                    }
                    ProjectContextEntry::Symlink { target } => {
                        rustix::fs::symlinkat(target.as_str(), destination, name)
                            .map_err(std::io::Error::from)?;
                    }
                }
            }
            Ok(())
        }
        walk(source, destination, "", 0, &children, entries)
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
        file_limits: Option<(&str, usize, u64)>,
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
        if let Some((digest, maximum_files, maximum_bytes)) = file_limits {
            if manifest.digest != digest {
                return Err(refuse());
            }
            let mut files = 0usize;
            let mut bytes = 0u64;
            for entry in manifest.entries.values() {
                match entry {
                    ProjectContextEntry::File { byte_length, .. } => {
                        files += 1;
                        bytes = bytes.checked_add(byte_length.get()).ok_or_else(refuse)?;
                    }
                    ProjectContextEntry::Directory { .. } => {}
                    ProjectContextEntry::Symlink { .. } => return Err(refuse()),
                }
            }
            if files > maximum_files
                || manifest.entries.len() > maximum_files.saturating_mul(8)
                || bytes > maximum_bytes
            {
                return Err(Error::refused(
                    "PROJECT_CONTEXT_LIMIT",
                    "Bounded file-context inventory exceeded before payload traversal",
                ));
            }
        }
        let data = project_fs::directory(&root, "data")?;
        let expected = manifest
            .entries
            .iter()
            .filter(|(_, entry)| !matches!(entry, ProjectContextEntry::Symlink { .. }))
            .map(|(path, entry)| (path.clone(), entry.clone()))
            .collect::<BTreeMap<_, _>>();
        verify_tree(&data, &expected, &[], false)?;
        let visible = project_fs::directory(&root, "data")?.metadata()?;
        let held = data.metadata()?;
        if (visible.dev(), visible.ino()) != (held.dev(), held.ino()) {
            return Err(refuse());
        }
        root_identity(snapshot, &root)?;
        Ok((root, definition, manifest))
    }
    fn build_metadata(
        path: &Path,
    ) -> Result<(ProjectContextDefinition, ProjectContextManifest), Error> {
        let root = project_fs::root(path)?;
        let definition = read_json(&root, "selection.json")?;
        let manifest = read_json(&root, "manifest.json")?;
        validate(&definition, &manifest)?;
        root_identity(path, &root)?;
        Ok((definition, manifest))
    }
    fn effective_entries(
        binding: &ProjectBuildContext,
        manifest: &ProjectContextManifest,
        inputs: &[crate::SuppliedInput],
    ) -> Result<BTreeMap<String, ProjectContextEntry>, Error> {
        binding.validate()?;
        if binding.digest != manifest.digest {
            return Err(refuse());
        }
        crate::project::validate_selected_paths(inputs)?;
        let mut entries = manifest.entries.clone();
        let mut used = BTreeSet::new();
        for input in inputs {
            let path = &input.receipt.path;
            if !allowed(path) {
                return Err(refuse());
            }
            if patamaps_contracts::byte_digest(input.content.as_bytes()) != input.receipt.digest
                || input.content.len() as u64 != input.receipt.byte_length.get()
            {
                return Err(refuse());
            }
            let mode = match manifest.entries.get(path) {
                Some(ProjectContextEntry::File { digest, mode, .. }) => {
                    if digest != &input.receipt.digest {
                        if binding.overlays.get(path) != Some(digest) {
                            return Err(refuse());
                        }
                        used.insert(path.clone());
                    }
                    *mode
                }
                None => integer(0o600),
                _ => return Err(refuse()),
            };
            entries.insert(
                path.clone(),
                ProjectContextEntry::File {
                    digest: input.receipt.digest.clone(),
                    byte_length: input.receipt.byte_length,
                    mode,
                },
            );
            add_parents(&mut entries, path)?;
        }
        if used != binding.overlays.keys().cloned().collect() {
            return Err(refuse());
        }
        for path in &binding.writable_paths {
            if entries
                .keys()
                .any(|p| p == path || p.starts_with(&(path.clone() + "/")))
            {
                return Err(refuse());
            }
            add_parents(&mut entries, path)?;
        }
        let total = entries
            .values()
            .filter_map(|v| match v {
                ProjectContextEntry::File { byte_length, .. } => Some(byte_length.get()),
                _ => None,
            })
            .sum::<u64>();
        if entries.len() > 262144 || total > 16 * 1024 * 1024 * 1024 {
            return Err(refuse());
        }
        Ok(entries)
    }
    fn add_parents(
        entries: &mut BTreeMap<String, ProjectContextEntry>,
        path: &str,
    ) -> Result<(), Error> {
        for (i, _) in path.match_indices('/') {
            if entries.len() > 262144 {
                return Err(refuse());
            }
            match entries.get(&path[..i]) {
                Some(ProjectContextEntry::Directory { .. }) => {}
                Some(_) => return Err(refuse()),
                None => {
                    entries.insert(
                        path[..i].into(),
                        ProjectContextEntry::Directory {
                            mode: integer(0o700),
                        },
                    );
                }
            }
        }
        Ok(())
    }
    pub(crate) fn verify_build_context(
        binding: &ProjectBuildContext,
        inputs: &[crate::SuppliedInput],
        metadata: &Path,
        candidate: &Path,
    ) -> Result<(), Error> {
        let (_, manifest) = build_metadata(metadata)?;
        let expected = effective_entries(binding, &manifest, inputs)?;
        let root = project_fs::root(candidate)?;
        verify_tree(&root, &expected, &binding.writable_paths, true)?;
        root_identity(candidate, &root)?;
        Ok(())
    }
    fn preparation_preimages(
        outputs: &BTreeMap<String, Option<String>>,
        manifest: &ProjectContextManifest,
    ) -> Result<(), Error> {
        for (path, preimage) in outputs {
            if !allowed(path) {
                return Err(refuse());
            }
            match (manifest.entries.get(path), preimage) {
                (Some(ProjectContextEntry::File { digest, .. }), Some(expected))
                    if digest == expected => {}
                (None, None) => {}
                _ => return Err(refuse()),
            }
        }
        Ok(())
    }
    pub(crate) fn verify_preparation_preimages(
        outputs: &BTreeMap<String, Option<String>>,
        metadata: &Path,
        candidate: &Path,
    ) -> Result<(), Error> {
        let (_, manifest) = build_metadata(metadata)?;
        preparation_preimages(outputs, &manifest)?;
        let root = project_fs::root(candidate)?;
        for (path, expected) in outputs {
            let mut dir = root.try_clone()?;
            let parts = path.split('/').collect::<Vec<_>>();
            let mut actual = None;
            for (index, part) in parts.iter().enumerate() {
                let last = index == parts.len() - 1;
                let flags = rustix::fs::OFlags::RDONLY
                    | rustix::fs::OFlags::NOFOLLOW
                    | rustix::fs::OFlags::CLOEXEC
                    | if last {
                        rustix::fs::OFlags::NONBLOCK
                    } else {
                        rustix::fs::OFlags::DIRECTORY
                    };
                match rustix::fs::openat(&dir, *part, flags, Mode::empty()) {
                    Err(rustix::io::Errno::NOENT) => break,
                    Err(_) => return Err(refuse()),
                    Ok(fd) => {
                        let file = File::from(fd);
                        if last {
                            if !file.metadata()?.is_file() {
                                return Err(refuse());
                            }
                            actual = Some(bytes(file, None)?.0);
                        } else {
                            dir = file;
                        }
                    }
                }
            }
            if &actual != expected {
                return Err(refuse());
            }
        }
        root_identity(candidate, &root)?;
        Ok(())
    }
    pub(crate) fn prepared_context_binding(
        binding: &ProjectBuildContext,
        outputs: &BTreeMap<String, Option<String>>,
        inputs: &[crate::SuppliedInput],
        metadata: &Path,
    ) -> Result<ProjectBuildContext, Error> {
        let (_, manifest) = build_metadata(metadata)?;
        preparation_preimages(outputs, &manifest)?;
        let mut result = binding.clone();
        for (path, preimage) in outputs {
            if result.overlays.contains_key(path) {
                return Err(refuse());
            }
            let input = inputs
                .iter()
                .find(|i| &i.receipt.path == path)
                .ok_or_else(refuse)?;
            if let Some(preimage) = preimage
                && preimage != &input.receipt.digest
            {
                result.overlays.insert(path.clone(), preimage.clone());
            }
        }
        result.validate()?;
        // Validate explicit preimages, paths and all generated content, including replay.
        effective_entries(&result, &manifest, inputs)?;
        Ok(result)
    }
    pub(crate) fn verify_prepared_build_context(
        binding: &ProjectBuildContext,
        inputs: &[crate::SuppliedInput],
        metadata: &Path,
        candidate: &Path,
    ) -> Result<(), Error> {
        let (_, manifest) = build_metadata(metadata)?;
        let expected = effective_entries(binding, &manifest, inputs)?;
        let root = project_fs::root(candidate)?;
        // Build write roots are NOT available to preparation. Only declared
        // generated files may differ before the immutable candidate capture.
        verify_tree(&root, &expected, &[], true)?;
        root_identity(candidate, &root)?;
        Ok(())
    }
    pub(crate) fn stage_build_context(
        binding: &ProjectBuildContext,
        inputs: &[crate::SuppliedInput],
        candidate: &Path,
        metadata: &Path,
    ) -> Result<(), Error> {
        binding.validate()?;
        let snapshot = Path::new(&binding.snapshot);
        let (definition, manifest) = build_metadata(snapshot)?;
        let expected = effective_entries(binding, &manifest, inputs)?;
        let report = stage_project_context(snapshot, candidate)?;
        if report["digest"] != binding.digest {
            return Err(refuse());
        }
        let saved = StageRoot::create(metadata)?;
        write_json(&saved, "selection.json", &definition)?;
        write_json(&saved, "manifest.json", &manifest)?;
        saved.verify_identity()?;
        let root = project_fs::root(candidate)?;
        for path in &binding.writable_paths {
            project_fs::parent(&root, path, true)?;
        }
        for (index, input) in inputs.iter().enumerate() {
            if matches!(manifest.entries.get(&input.receipt.path),Some(ProjectContextEntry::File{digest,..}) if digest==&input.receipt.digest)
            {
                continue;
            }
            let (parent, leaf) = project_fs::parent(&root, &input.receipt.path, true)?;
            let temp = format!(".patamaps-overlay-{}-{index}", std::process::id());
            let mut file = File::from(
                rustix::fs::openat(
                    &parent,
                    temp.as_str(),
                    rustix::fs::OFlags::WRONLY
                        | rustix::fs::OFlags::CREATE
                        | rustix::fs::OFlags::EXCL
                        | rustix::fs::OFlags::NOFOLLOW
                        | rustix::fs::OFlags::CLOEXEC,
                    Mode::from_bits_truncate(0o600),
                )
                .map_err(std::io::Error::from)?,
            );
            file.write_all(input.content.as_bytes())?;
            let ProjectContextEntry::File { mode, .. } = &expected[&input.receipt.path] else {
                return Err(refuse());
            };
            rustix::fs::fchmod(
                &file,
                Mode::from_bits_truncate(mode.get().try_into().map_err(|_| refuse())?),
            )
            .map_err(std::io::Error::from)?;
            file.sync_all()?;
            rustix::fs::renameat(&parent, temp.as_str(), &parent, leaf.as_str())
                .map_err(std::io::Error::from)?;
        }
        root_identity(candidate, &root)?;
        verify_build_context(binding, inputs, metadata, candidate)
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
    pub(crate) fn verified_file_context(
        snapshot: &Path,
        digest: &str,
    ) -> Result<ProjectContextManifest, Error> {
        let (_, _, manifest) = load(snapshot, Some((digest, 1024, 512 * 1024 * 1024)))?;
        Ok(manifest)
    }
    pub fn verify_project_context(snapshot: &Path) -> Result<serde_json::Value, Error> {
        let (_, _, manifest) = load(snapshot, None)?;
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
        let (root, _, manifest) = load(snapshot, None)?;
        let data = project_fs::directory(&root, "data")?;
        let stage = StageRoot::create(destination)?;
        copy_context_tree(&data, &stage.directory, &manifest.entries)?;
        verify_tree(&stage.directory, &manifest.entries, &[], true)?;
        let visible = project_fs::directory(&root, "data")?.metadata()?;
        let held = data.metadata()?;
        if (visible.dev(), visible.ino()) != (held.dev(), held.ino()) {
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
#[cfg(unix)]
pub(crate) use unix::{
    prepared_context_binding, stage_build_context, verified_file_context, verify_build_context,
    verify_preparation_preimages, verify_prepared_build_context,
};
#[cfg(not(unix))]
pub fn capture_project_context(
    _: &std::path::Path,
    _: &std::path::Path,
    _: &ProjectContextDefinition,
) -> Result<serde_json::Value, Error> {
    Err(refuse())
}
#[cfg(not(unix))]
pub(crate) fn verified_file_context(
    _: &std::path::Path,
    _: &str,
) -> Result<ProjectContextManifest, Error> {
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

    #[test]
    fn closed_walk_preserves_maximum_depth_siblings_and_repeat_verification() {
        let base = Temp::new();
        let source = base.0.join("owner");
        fs::create_dir(&source).unwrap();
        let deep = std::iter::repeat_n("d", 127).collect::<Vec<_>>().join("/") + "/payload.bin";
        fs::create_dir_all(source.join(&deep).parent().unwrap()).unwrap();
        fs::write(source.join(&deep), [0, 255, 128, 1]).unwrap();
        let mut paths = vec![deep.clone()];
        for i in 0..24 {
            let name = format!("sibling-{i}.bin");
            fs::write(source.join(&name), [i as u8, 0, 255]).unwrap();
            paths.push(name);
        }
        let definition = ProjectContextDefinition {
            profile: CONTEXT_PROFILE.into(),
            id: "urn:test:maximum-depth-context".into(),
            nonsecret_inputs: true,
            paths,
            symlinks: ContextSymlinks::Refuse,
        };
        let snapshot = base.0.join("snapshot");
        let captured = capture_project_context(&source, &snapshot, &definition).unwrap();
        for _ in 0..2 {
            assert_eq!(
                verify_project_context(&snapshot).unwrap()["digest"],
                captured["digest"]
            );
        }
        let staged = base.0.join("staged");
        assert_eq!(
            stage_project_context(&snapshot, &staged).unwrap()["digest"],
            captured["digest"]
        );
        assert_eq!(fs::read(staged.join(&deep)).unwrap(), [0, 255, 128, 1]);
        for i in 0..24 {
            assert_eq!(
                fs::read(staged.join(format!("sibling-{i}.bin"))).unwrap(),
                [i as u8, 0, 255]
            );
        }
    }
    #[test]
    fn bounded_file_context_refuses_inventory_before_payload_traversal() {
        for case in ["bytes", "files", "entries"] {
            let tmp = Temp::new();
            let snapshot = tmp.0.join("bounded");
            fs::create_dir(&snapshot).unwrap();
            fs::create_dir(snapshot.join("data")).unwrap();
            let count = if case == "files" { 1025 } else { 1 };
            let mut entries = BTreeMap::new();
            for index in 0..count {
                entries.insert(
                    format!("file-{index}"),
                    ProjectContextEntry::File {
                        digest: format!("sha256:{}", "0".repeat(64)),
                        byte_length: SafeInteger::new(if case == "bytes" {
                            512 * 1024 * 1024 + 1
                        } else {
                            1
                        })
                        .unwrap(),
                        mode: SafeInteger::new(0o644).unwrap(),
                    },
                );
            }
            if case == "entries" {
                for index in 0..8192 {
                    entries.insert(
                        format!("directory-{index}"),
                        ProjectContextEntry::Directory {
                            mode: SafeInteger::new(0o700).unwrap(),
                        },
                    );
                }
            }
            let definition = ProjectContextDefinition {
                profile: CONTEXT_PROFILE.into(),
                id: "urn:test:bounded-docker-context".into(),
                nonsecret_inputs: true,
                paths: entries.keys().cloned().collect(),
                symlinks: ContextSymlinks::Refuse,
            };
            let mut manifest = ProjectContextManifest {
                profile: CONTEXT_RECORD.into(),
                definition_digest: canonical_digest(&definition).unwrap(),
                entries,
                digest: String::new(),
            };
            manifest.digest = address(&manifest).unwrap();
            validate(&definition, &manifest).unwrap();
            fs::write(
                snapshot.join("selection.json"),
                canonical_bytes(&definition).unwrap(),
            )
            .unwrap();
            fs::write(
                snapshot.join("manifest.json"),
                canonical_bytes(&manifest).unwrap(),
            )
            .unwrap();
            // No file payload exists: the distinct limit error demonstrates
            // refusal before any attempt to open or hash those payloads.
            let error = verified_file_context(&snapshot, &manifest.digest).unwrap_err();
            assert!(
                error.to_string().contains("PROJECT_CONTEXT_LIMIT"),
                "{case}: {error}"
            );
        }
    }
}
