//! Shared descriptor-relative fresh staging. Partial outputs are always retained.
use crate::{Error, relative_path};
use rustix::fs::{Mode, OFlags, mkdirat, openat};
use std::{
    fs::{File, OpenOptions},
    os::unix::fs::{MetadataExt, OpenOptionsExt},
    path::{Path, PathBuf},
};
fn refuse() -> Error {
    Error::refused(
        "PROJECT_STAGE_FILESYSTEM",
        "Fresh descriptor-relative staging refused",
    )
}
fn stage_refused(code: &'static str) -> Error {
    Error::refused(code, "Fresh descriptor-relative staging refused")
}
fn flags() -> OFlags {
    OFlags::RDONLY | OFlags::DIRECTORY | OFlags::NOFOLLOW | OFlags::CLOEXEC
}
pub(crate) fn root(path: &Path) -> Result<File, Error> {
    let file = OpenOptions::new()
        .read(true)
        .custom_flags(flags().bits() as i32)
        .open(path)?;
    if !file.metadata()?.is_dir() {
        return Err(refuse());
    }
    Ok(file)
}
pub(crate) fn parent(root: &File, path: &str, create: bool) -> Result<(File, String), Error> {
    if !relative_path(path) {
        return Err(refuse());
    }
    let parts = path.split('/').collect::<Vec<_>>();
    let mut dir = root.try_clone()?;
    for part in &parts[..parts.len() - 1] {
        if create {
            match mkdirat(&dir, *part, Mode::from_bits_truncate(0o700)) {
                Ok(()) | Err(rustix::io::Errno::EXIST) => {}
                Err(_) => return Err(stage_refused("PROJECT_STAGE_DIRECTORY_UNAVAILABLE")),
            }
        }
        dir = File::from(
            openat(&dir, *part, flags(), Mode::empty())
                .map_err(|_| stage_refused("PROJECT_STAGE_DIRECTORY_UNAVAILABLE"))?,
        );
    }
    Ok((
        dir,
        parts.last().expect("nonempty validated path").to_string(),
    ))
}
pub(crate) fn directory(root: &File, path: &str) -> Result<File, Error> {
    if path.is_empty() || path == "." {
        return Ok(root.try_clone()?);
    }
    let (dir, leaf) = parent(root, path, false)?;
    Ok(File::from(
        openat(&dir, leaf.as_str(), flags(), Mode::empty()).map_err(std::io::Error::from)?,
    ))
}
pub(crate) struct StageRoot {
    pub(crate) directory: File,
    parent: File,
    leaf: String,
    path: PathBuf,
}
impl StageRoot {
    pub(crate) fn create(path: &Path) -> Result<Self, Error> {
        let leaf = path
            .file_name()
            .and_then(|v| v.to_str())
            .filter(|v| relative_path(v) && !v.contains('/'))
            .ok_or_else(|| stage_refused("PROJECT_STAGE_DESTINATION"))?
            .to_owned();
        let parent_path = path
            .parent()
            .filter(|p| !p.as_os_str().is_empty())
            .unwrap_or(Path::new("."));
        if std::fs::symlink_metadata(parent_path)?
            .file_type()
            .is_symlink()
        {
            return Err(stage_refused("PROJECT_STAGE_PARENT_SYMLINK"));
        }
        let parent = root(parent_path)?;
        mkdirat(&parent, leaf.as_str(), Mode::from_bits_truncate(0o700))
            .map_err(|_| stage_refused("PROJECT_STAGE_DESTINATION_UNAVAILABLE"))?;
        let directory = File::from(
            openat(&parent, leaf.as_str(), flags(), Mode::empty())
                .map_err(|_| stage_refused("PROJECT_STAGE_DIRECTORY_UNAVAILABLE"))?,
        );
        Ok(Self {
            directory,
            parent,
            leaf,
            path: path.to_owned(),
        })
    }
    pub(crate) fn file(&self, path: &str) -> Result<File, Error> {
        let (parent, leaf) = parent(&self.directory, path, true)?;
        Ok(File::from(
            openat(
                &parent,
                leaf.as_str(),
                OFlags::WRONLY | OFlags::CREATE | OFlags::EXCL | OFlags::NOFOLLOW | OFlags::CLOEXEC,
                Mode::from_bits_truncate(0o600),
            )
            .map_err(|_| stage_refused("PROJECT_STAGE_INPUT_UNAVAILABLE"))?,
        ))
    }
    pub(crate) fn mkdir(&self, path: &str) -> Result<File, Error> {
        let (parent, leaf) = parent(&self.directory, path, true)?;
        match mkdirat(&parent, leaf.as_str(), Mode::from_bits_truncate(0o700)) {
            Ok(()) | Err(rustix::io::Errno::EXIST) => {}
            Err(_) => return Err(stage_refused("PROJECT_STAGE_DIRECTORY_UNAVAILABLE")),
        }
        directory(&self.directory, path)
    }
    pub(crate) fn verify_identity(&self) -> Result<(), Error> {
        let expected = self.directory.metadata()?;
        for actual in [
            File::from(
                openat(&self.parent, self.leaf.as_str(), flags(), Mode::empty())
                    .map_err(|_| stage_refused("PROJECT_STAGE_DIRECTORY_CHANGED"))?,
            ),
            root(&self.path).map_err(|_| stage_refused("PROJECT_STAGE_DIRECTORY_CHANGED"))?,
        ] {
            let meta = actual.metadata()?;
            if (meta.dev(), meta.ino()) != (expected.dev(), expected.ino()) {
                return Err(stage_refused("PROJECT_STAGE_DIRECTORY_CHANGED"));
            }
        }
        Ok(())
    }
}
