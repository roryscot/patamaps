//! Digest-bound ELF target-header observation; never executes or authorizes a binary.
//! Header layout/values: https://gabi.xinuos.com/elf/02-eheader.html
//! Machines: https://gabi.xinuos.com/elf/a-emachine.html
use crate::Error;
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{fs::OpenOptions, io::Read, path::Path};

const LIMIT: u64 = 256 * 1024 * 1024;

fn machine(target: &str) -> Result<u16, Error> {
    match target {
        "linux/amd64" => Ok(62),
        "linux/arm64" => Ok(183),
        _ => Err(Error::refused(
            "ELF_TARGET",
            "Supported targets: linux/amd64, linux/arm64",
        )),
    }
}

fn validate_digest(digest: &str) -> Result<(), Error> {
    if !digest.strip_prefix("sha256:").is_some_and(|v| {
        v.len() == 64
            && v.bytes()
                .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
    }) {
        return Err(Error::refused(
            "ELF_DIGEST",
            "Expected a lowercase sha256: digest",
        ));
    }
    Ok(())
}

fn inspect(mut reader: impl Read, target: &str, expected: &str) -> Result<Value, Error> {
    let expected_machine = machine(target)?;
    validate_digest(expected)?;
    let mut hash = Sha256::new();
    let mut header = [0u8; 64];
    let mut count = 0u64;
    let mut buffer = [0u8; 65536];
    loop {
        let n = reader.read(&mut buffer)?;
        if n == 0 {
            break;
        }
        if count + n as u64 > LIMIT {
            return Err(Error::refused("ELF_LIMIT", "ELF input exceeds 256 MiB"));
        }
        let start = count.min(64) as usize;
        let copy = n.min(64 - start);
        header[start..start + copy].copy_from_slice(&buffer[..copy]);
        count += n as u64;
        hash.update(&buffer[..n]);
    }
    let digest = format!("sha256:{:x}", hash.finalize());
    if digest != expected {
        return Err(Error::refused(
            "ELF_BINDING",
            "Input differs from its declared digest",
        ));
    }
    let half = |at: usize| u16::from_le_bytes([header[at], header[at + 1]]);
    if count < 64
        || &header[..4] != b"\x7fELF"
        || header[4] != 2
        || header[5] != 1
        || header[6] != 1
        || !matches!(header[7], 0 | 3)
        || !matches!(half(16), 2 | 3)
        || header[20..24] != [1, 0, 0, 0]
        || half(52) != 64
    {
        return Err(Error::refused(
            "ELF_HEADER",
            "Requires an ELF64 little-endian executable/shared-object header, version 1, generic or Linux OSABI",
        ));
    }
    if half(18) != expected_machine {
        return Err(Error::refused(
            "ELF_ARCHITECTURE",
            "ELF machine differs from declared target",
        ));
    }
    Ok(json!({
        "status": "matched-elf-target-header",
        "target": target,
        "digest": digest,
        "bytes": count,
        "header": {"class":64,"byteOrder":"little-endian","machine":half(18),"type":half(16),"osAbi":header[7],"abiVersion":header[8]},
        "executionPerformed": false,
        "runtimeCompatibility": "not-established",
        "linuxOsEstablished": false,
        "authorization": "not-evaluated"
    }))
}

/// Check a bounded regular file against an owner-declared digest and target header.
/// This does not validate segments, loaders, libraries, OS compatibility or later execution.
/// Use an immutable captured artifact and independently qualify the actual runtime.
pub fn check_elf_target(path: &Path, target: &str, expected_digest: &str) -> Result<Value, Error> {
    machine(target)?;
    validate_digest(expected_digest)?;
    let mut options = OpenOptions::new();
    options.read(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.custom_flags(
            (rustix::fs::OFlags::NONBLOCK | rustix::fs::OFlags::NOFOLLOW).bits() as i32,
        );
    }
    // On other hosts reject known nonregular files before opening too.
    if !std::fs::symlink_metadata(path)?.file_type().is_file() {
        return Err(Error::refused(
            "ELF_FILE",
            "ELF input must be a regular file",
        ));
    }
    let file = options.open(path)?;
    let before = file.metadata()?;
    if !before.is_file() || before.len() > LIMIT {
        return Err(Error::refused(
            "ELF_FILE",
            "ELF input must be a regular file of at most 256 MiB",
        ));
    }
    let report = inspect((&file).take(LIMIT + 1), target, expected_digest)?;
    if file.metadata()?.len() != before.len() || report["bytes"].as_u64() != Some(before.len()) {
        return Err(Error::refused(
            "ELF_BINDING",
            "ELF input length changed during inspection",
        ));
    }
    Ok(report)
}

#[cfg(test)]
mod tests {
    use super::*;
    fn object(machine: u16, kind: u16) -> Vec<u8> {
        let mut b = vec![0u8; 97];
        b[..7].copy_from_slice(b"\x7fELF\x02\x01\x01");
        b[16..18].copy_from_slice(&kind.to_le_bytes());
        b[18..20].copy_from_slice(&machine.to_le_bytes());
        b[20] = 1;
        b[52] = 64;
        b
    }
    fn digest(b: &[u8]) -> String {
        format!("sha256:{:x}", Sha256::digest(b))
    }
    fn code(result: Result<Value, Error>) -> &'static str {
        match result {
            Err(Error::Refused { code, .. }) => code,
            other => panic!("Expected refusal: {other:?}"),
        }
    }
    #[test]
    fn elf_target_matches_both_machines_without_claiming_execution() {
        for (target, machine) in [("linux/amd64", 62), ("linux/arm64", 183)] {
            for kind in [2, 3] {
                let b = object(machine, kind);
                let report = inspect(&b[..], target, &digest(&b)).unwrap();
                assert_eq!(report["executionPerformed"], false);
                assert_eq!(report["runtimeCompatibility"], "not-established");
                assert_eq!(report["digest"], digest(&b));
                assert_eq!(report["bytes"], 97);
            }
        }
    }
    #[test]
    fn elf_target_refuses_architecture_and_unbound_bytes() {
        let b = object(183, 2);
        assert_eq!(
            code(inspect(&b[..], "linux/amd64", &digest(&b))),
            "ELF_ARCHITECTURE"
        );
        let mut changed = b.clone();
        changed[96] = 1;
        assert_eq!(
            code(inspect(&changed[..], "linux/arm64", &digest(&b))),
            "ELF_BINDING"
        );
    }
    #[test]
    fn elf_target_refuses_unsupported_targets_and_digests() {
        let b = object(62, 2);
        assert_eq!(
            code(inspect(&b[..], "darwin/amd64", &digest(&b))),
            "ELF_TARGET"
        );
        for invalid in ["", "sha256:abcd", &format!("sha256:{}", "A".repeat(64))] {
            assert_eq!(code(inspect(&b[..], "linux/amd64", invalid)), "ELF_DIGEST");
        }
    }
    #[test]
    fn elf_target_refuses_truncated_and_incompatible_headers() {
        let b = object(62, 2);
        for length in [0, 4, 16, 63] {
            let truncated = &b[..length];
            assert_eq!(
                code(inspect(truncated, "linux/amd64", &digest(truncated))),
                "ELF_HEADER"
            );
        }
        for (at, value) in [
            (0, 0),
            (4, 1),
            (5, 2),
            (6, 0),
            (7, 9),
            (16, 1),
            (20, 0),
            (52, 63),
        ] {
            let mut bad = b.clone();
            bad[at] = value;
            assert_eq!(
                code(inspect(&bad[..], "linux/amd64", &digest(&bad))),
                "ELF_HEADER"
            );
        }
    }
    #[test]
    fn elf_target_binds_short_reads_and_propagates_io_failures() {
        struct Short(std::io::Cursor<Vec<u8>>);
        impl Read for Short {
            fn read(&mut self, b: &mut [u8]) -> std::io::Result<usize> {
                let n = b.len().min(3);
                self.0.read(&mut b[..n])
            }
        }
        let b = object(62, 2);
        inspect(
            Short(std::io::Cursor::new(b.clone())),
            "linux/amd64",
            &digest(&b),
        )
        .unwrap();
        struct Broken;
        impl Read for Broken {
            fn read(&mut self, _: &mut [u8]) -> std::io::Result<usize> {
                Err(std::io::Error::other("read failed"))
            }
        }
        assert!(matches!(
            inspect(Broken, "linux/amd64", &digest(&b)),
            Err(Error::Io(_))
        ));
    }
}
