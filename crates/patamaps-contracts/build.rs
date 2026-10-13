use sha2::{Digest, Sha256};
use std::{fs, path::Path};

fn files(directory: &Path, output: &mut Vec<std::path::PathBuf>) {
    for entry in fs::read_dir(directory).expect("vendored collation sources") {
        let path = entry.expect("source entry").path();
        if path.is_dir() {
            files(&path, output);
        } else {
            output.push(path);
        }
    }
}

fn main() {
    let manifest = std::env::var("CARGO_MANIFEST_DIR").expect("Cargo manifest path");
    let root = Path::new(&manifest).join("../../vendor/icu_collator");
    // Watch additions/removals as well as changes to already inventoried files.
    println!("cargo:rerun-if-changed={}", root.display());
    let mut paths = Vec::new();
    files(&root, &mut paths);
    paths.sort();
    let mut hash = Sha256::new();
    for path in paths {
        println!("cargo:rerun-if-changed={}", path.display());
        let relative = path.strip_prefix(&root).expect("vendor relative source");
        let bytes = fs::read(&path).expect("vendored source bytes");
        hash.update(relative.to_string_lossy().as_bytes());
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
