use crate::error::{Result, fail};
use patamaps_contracts::MAX_INPUT_BYTES;
use rustix::fs::{self, Mode, OFlags};
use std::{
    collections::BTreeSet,
    fs::File,
    io::{Read, Write},
    os::unix::fs::{MetadataExt, PermissionsExt},
    path::Path,
};

fn directory(file: &File, ancestor: bool, immutable: bool) -> Result<()> {
    let m = file.metadata()?;
    let sticky = ancestor && m.mode() & 0o1000 != 0;
    if !m.is_dir()
        || m.uid() != 0
        || (m.mode() & 0o022 != 0 && !sticky)
        || (immutable && m.mode() & 0o222 != 0)
    {
        return fail(
            "ACTIVATION_UNPROTECTED_DIRECTORY",
            "Expected root-owned protected directory",
        );
    }
    Ok(())
}
fn regular(file: &File, immutable: bool) -> Result<()> {
    let m = file.metadata()?;
    if !m.is_file()
        || m.uid() != 0
        || m.nlink() != 1
        || m.mode() & 0o022 != 0
        || (immutable && m.mode() & 0o222 != 0)
    {
        return fail(
            "ACTIVATION_UNPROTECTED_FILE",
            "Expected root-owned single-link regular file with protected permissions",
        );
    }
    Ok(())
}
pub(crate) fn normalized_path(path: &Path) -> Result<Vec<&str>> {
    let Some(s) = path.to_str() else {
        return fail("ACTIVATION_INVALID_PATH", "Path must be UTF-8");
    };
    if !s.starts_with('/')
        || s.len() <= 1
        || s.len() > 4096
        || s.ends_with('/')
        || s.chars().any(char::is_control)
        || s.split('/')
            .skip(1)
            .any(|p| p.is_empty() || p == "." || p == "..")
    {
        return fail(
            "ACTIVATION_INVALID_PATH",
            "Path must be normalized and absolute",
        );
    }
    Ok(s.split('/').skip(1).collect())
}
#[derive(Debug)]
pub(crate) struct Directory(File);
impl Directory {
    pub fn absolute(path: &Path) -> Result<Self> {
        let parts = if path == Path::new("/") {
            Vec::new()
        } else {
            normalized_path(path)?
        };
        let mut current = Self(File::from(
            fs::open(
                "/",
                OFlags::RDONLY | OFlags::DIRECTORY | OFlags::CLOEXEC,
                Mode::empty(),
            )
            .map_err(std::io::Error::from)?,
        ));
        directory(&current.0, true, false)?;
        for (i, part) in parts.iter().enumerate() {
            current = current.open_directory(part, i + 1 < parts.len(), false)?;
        }
        Ok(current)
    }
    fn open_directory(&self, name: &str, ancestor: bool, immutable: bool) -> Result<Self> {
        name_check(name)?;
        let file = File::from(
            fs::openat(
                &self.0,
                name,
                OFlags::RDONLY | OFlags::DIRECTORY | OFlags::NOFOLLOW | OFlags::CLOEXEC,
                Mode::empty(),
            )
            .map_err(std::io::Error::from)?,
        );
        directory(&file, ancestor, immutable)?;
        Ok(Self(file))
    }
    pub fn child(&self, name: &str, immutable: bool) -> Result<Self> {
        self.open_directory(name, false, immutable)
    }
    pub fn ensure_child(&self, name: &str) -> Result<Self> {
        name_check(name)?;
        match fs::mkdirat(&self.0, name, Mode::from_raw_mode(0o755)) {
            Ok(()) => self.sync()?,
            Err(rustix::io::Errno::EXIST) => (),
            Err(e) => return Err(std::io::Error::from(e).into()),
        }
        self.child(name, false)
    }
    pub fn create_child(&self, name: &str) -> Result<Self> {
        name_check(name)?;
        fs::mkdirat(&self.0, name, Mode::from_raw_mode(0o700)).map_err(std::io::Error::from)?;
        self.child(name, false)
    }
    pub fn sync(&self) -> Result<()> {
        Ok(self.0.sync_all()?)
    }
    pub fn immutable(&self) -> Result<()> {
        self.0
            .set_permissions(std::fs::Permissions::from_mode(0o555))?;
        self.sync()
    }
    pub fn local_filesystem(&self) -> Result<()> {
        #[cfg(target_os = "linux")]
        {
            // Linux UAPI filesystem magic: ext4, XFS, Btrfs, tmpfs, overlayfs.
            // Overlay/tmpfs are accepted for process/permission tests; this is
            // not evidence of power-loss durability for volatile storage.
            let kind = fs::fstatfs(&self.0).map_err(std::io::Error::from)?.f_type as u64;
            if ![0xef53, 0x58465342, 0x9123683e, 0x01021994, 0x794c7630].contains(&kind) {
                return fail(
                    "ACTIVATION_UNSUPPORTED_FILESYSTEM",
                    "Selected profile requires ext4, XFS, Btrfs, tmpfs or overlayfs",
                );
            }
            Ok(())
        }
        #[cfg(not(target_os = "linux"))]
        fail(
            "ACTIVATION_UNSUPPORTED_HOST",
            "Protected persistence requires Linux",
        )
    }
    pub fn same_directory(&self, other: &Self) -> Result<bool> {
        let (a, b) = (self.0.metadata()?, other.0.metadata()?);
        Ok(a.dev() == b.dev() && a.ino() == b.ino())
    }
    pub fn lock(&self) -> Result<File> {
        let file = File::from(
            fs::openat(
                &self.0,
                ".promotion.lock",
                OFlags::RDWR
                    | OFlags::CREATE
                    | OFlags::NOFOLLOW
                    | OFlags::CLOEXEC
                    | OFlags::NONBLOCK,
                Mode::from_raw_mode(0o600),
            )
            .map_err(std::io::Error::from)?,
        );
        regular(&file, false)?;
        if file.metadata()?.mode() & 0o077 != 0 {
            return fail(
                "ACTIVATION_UNPROTECTED_LOCK",
                "Lock must be private to root",
            );
        }
        match file.try_lock() {
            Ok(()) => (),
            Err(std::fs::TryLockError::WouldBlock) => {
                return fail(
                    "ACTIVATION_BUSY",
                    "Promotion lock is held; retry with current baseline",
                );
            }
            Err(std::fs::TryLockError::Error(e)) => return Err(e.into()),
        }
        self.assert_lock(&file)?;
        Ok(file)
    }
    pub fn assert_lock(&self, held: &File) -> Result<()> {
        let other = self.open_file(".promotion.lock", false)?;
        let (a, b) = (held.metadata()?, other.metadata()?);
        if a.dev() != b.dev() || a.ino() != b.ino() || a.nlink() != 1 || a.mode() & 0o077 != 0 {
            return fail(
                "ACTIVATION_LOST_LOCK",
                "Lock identity changed while transaction was held",
            );
        }
        Ok(())
    }
    fn open_file(&self, name: &str, immutable: bool) -> Result<File> {
        name_check(name)?;
        let file = File::from(
            fs::openat(
                &self.0,
                name,
                OFlags::RDONLY | OFlags::NOFOLLOW | OFlags::NONBLOCK | OFlags::CLOEXEC,
                Mode::empty(),
            )
            .map_err(std::io::Error::from)?,
        );
        regular(&file, immutable)?;
        Ok(file)
    }
    pub fn read_optional(&self, name: &str, immutable: bool) -> Result<Option<Vec<u8>>> {
        match self.read(name, immutable) {
            Ok(bytes) => Ok(Some(bytes)),
            Err(crate::ActivationError::Io(e)) if e.kind() == std::io::ErrorKind::NotFound => {
                Ok(None)
            }
            Err(e) => Err(e),
        }
    }
    pub fn read(&self, name: &str, immutable: bool) -> Result<Vec<u8>> {
        let mut file = self.open_file(name, immutable)?;
        if file.metadata()?.len() > MAX_INPUT_BYTES as u64 {
            return fail(
                "ACTIVATION_RESOURCE_LIMIT",
                "Protected file exceeds wire bound",
            );
        }
        let mut bytes = Vec::new();
        (&mut file)
            .take(MAX_INPUT_BYTES as u64 + 1)
            .read_to_end(&mut bytes)?;
        if bytes.len() > MAX_INPUT_BYTES {
            return fail(
                "ACTIVATION_RESOURCE_LIMIT",
                "Protected file exceeds wire bound",
            );
        }
        Ok(bytes)
    }
    pub fn write_new(&self, name: &str, bytes: &[u8]) -> Result<()> {
        name_check(name)?;
        if bytes.len() > MAX_INPUT_BYTES {
            return fail("ACTIVATION_RESOURCE_LIMIT", "Output exceeds wire bound");
        }
        let mut file = File::from(
            fs::openat(
                &self.0,
                name,
                OFlags::WRONLY | OFlags::CREATE | OFlags::EXCL | OFlags::NOFOLLOW | OFlags::CLOEXEC,
                Mode::from_raw_mode(0o600),
            )
            .map_err(std::io::Error::from)?,
        );
        regular(&file, false)?;
        file.write_all(bytes)?;
        file.set_permissions(std::fs::Permissions::from_mode(0o444))?;
        file.sync_all()?;
        Ok(())
    }
    pub fn names(&self) -> Result<BTreeSet<String>> {
        let mut result = BTreeSet::new();
        for entry in fs::Dir::read_from(&self.0).map_err(std::io::Error::from)? {
            let entry = entry.map_err(std::io::Error::from)?;
            let name = entry
                .file_name()
                .to_str()
                .map_err(|_| crate::ActivationError::Refusal {
                    code: "ACTIVATION_INVALID_PATH",
                    message: "Non UTF-8 inventory name",
                })?;
            if name == "." || name == ".." {
                continue;
            }
            if result.len() >= 256 {
                return fail(
                    "ACTIVATION_RESOURCE_LIMIT",
                    "Artifact inventory exceeds bound",
                );
            }
            result.insert(name.into());
        }
        Ok(result)
    }
    pub fn rename(&self, source: &str, target_dir: &Self, target: &str) -> Result<()> {
        name_check(source)?;
        name_check(target)?;
        Ok(fs::renameat(&self.0, source, &target_dir.0, target).map_err(std::io::Error::from)?)
    }
    pub fn publish_new(&self, source: &str, target: &str) -> Result<()> {
        name_check(source)?;
        name_check(target)?;
        #[cfg(target_os = "linux")]
        {
            Ok(
                fs::renameat_with(&self.0, source, &self.0, target, fs::RenameFlags::NOREPLACE)
                    .map_err(std::io::Error::from)?,
            )
        }
        #[cfg(not(target_os = "linux"))]
        {
            fail(
                "ACTIVATION_UNSUPPORTED_HOST",
                "Protected persistence requires Linux",
            )
        }
    }
}
fn name_check(name: &str) -> Result<()> {
    if name.is_empty()
        || name.len() > 255
        || name == "."
        || name == ".."
        || name.contains('/')
        || name.contains('\0')
    {
        return fail(
            "ACTIVATION_INVALID_PATH",
            "Expected a single bounded filename",
        );
    }
    Ok(())
}
pub(crate) fn installation_file(path: &Path) -> Result<()> {
    let parts = normalized_path(path)?;
    let parent = Directory::absolute(path.parent().ok_or(crate::ActivationError::Refusal {
        code: "ACTIVATION_INVALID_PATH",
        message: "Missing installation parent",
    })?)?;
    parent.open_file(parts.last().expect("nonempty absolute path"), true)?;
    Ok(())
}
