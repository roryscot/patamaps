// Bind the actual compiled fork's source inputs, including its active manifest.
use sha2::{Digest, Sha256};
use std::{
    fs,
    path::{Path, PathBuf},
};

fn collect(root: &Path, paths: &mut Vec<PathBuf>) {
    println!("cargo:rerun-if-changed={}", root.display());
    for entry in fs::read_dir(root).expect("collator sources") {
        let entry = entry.expect("collator source entry");
        let kind = entry.file_type().expect("collator source type");
        assert!(!kind.is_symlink(), "collator source symlink");
        if kind.is_dir() {
            collect(&entry.path(), paths);
        } else if kind.is_file() {
            paths.push(entry.path());
        } else {
            panic!("unsupported collator source type");
        }
    }
}

fn main() {
    let manifest = std::env::var("CARGO_MANIFEST_DIR").expect("collator crate root");
    let root = Path::new(&manifest);
    let mut paths = vec![root.join("Cargo.toml"), root.join("build.rs")];
    collect(&root.join("src"), &mut paths);
    if root.join("data").is_dir() {
        collect(&root.join("data"), &mut paths);
    }
    paths.sort();
    let mut hash = Sha256::new();
    for path in paths {
        println!("cargo:rerun-if-changed={}", path.display());
        let bytes = fs::read(&path).expect("collator source bytes");
        hash.update(
            path.strip_prefix(root)
                .expect("collator relative path")
                .to_string_lossy()
                .as_bytes(),
        );
        hash.update([0]);
        hash.update(bytes.len().to_string().as_bytes());
        hash.update([0]);
        hash.update(bytes);
    }
    println!(
        "cargo:rustc-env=PATAMAPS_COLLATOR_SOURCE_DIGEST=sha256:{:x}",
        hash.finalize()
    );
}
