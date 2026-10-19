// Generated from scripts/crate_package_build.rs; run scripts/sync_crate_inputs.py.
use sha2::{Digest, Sha256};
use std::{
    fs,
    path::{Component, Path},
};

fn relative(value: &str) -> &Path {
    let path = Path::new(value);
    assert!(
        !value.is_empty() && path.components().all(|c| matches!(c, Component::Normal(_))),
        "invalid packaged input path: {value}"
    );
    path
}

fn main() {
    let manifest = std::env::var("CARGO_MANIFEST_DIR").expect("crate root");
    let root = Path::new(&manifest);
    let origins = root.join("package-inputs.tsv");
    println!("cargo:rerun-if-changed={}", origins.display());
    let workspace = root.join("../..");
    let marker = workspace.join(".patamaps-crate-inputs");
    println!("cargo:rerun-if-changed={}", marker.display());
    let source_workspace = match fs::read(&marker) {
        Ok(bytes) => {
            assert_eq!(
                bytes, b"patamaps-crate-inputs-v1\n",
                "invalid workspace input marker"
            );
            true
        }
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => false,
        Err(error) => panic!("workspace input marker: {error}"),
    };
    let inputs = fs::read_to_string(&origins).expect("packaged input origins");
    let mut hash = Sha256::new();
    hash.update(b"patamaps-package-inputs-v1\0");
    hash.update(inputs.as_bytes());
    for line in inputs.lines() {
        let (local, original) = line.split_once('\t').expect("packaged input origin pair");
        let path = root.join(relative(local));
        println!("cargo:rerun-if-changed={}", path.display());
        assert!(
            !fs::symlink_metadata(&path)
                .expect("packaged input metadata")
                .file_type()
                .is_symlink(),
            "packaged input must be an ordinary file"
        );
        let bytes = fs::read(&path).expect("required packaged input missing");
        hash.update(local.as_bytes());
        hash.update([0]);
        hash.update(bytes.len().to_string().as_bytes());
        hash.update([0]);
        hash.update(&bytes);
        if source_workspace {
            let original = workspace.join(relative(original));
            println!("cargo:rerun-if-changed={}", original.display());
            assert_eq!(
                bytes,
                fs::read(original).expect("workspace input missing"),
                "stale packaged input {local}; run scripts/sync_crate_inputs.py"
            );
        }
    }
    println!(
        "cargo:rustc-env=PATAMAPS_PACKAGE_INPUTS_DIGEST=sha256:{:x}",
        hash.finalize()
    );
}
