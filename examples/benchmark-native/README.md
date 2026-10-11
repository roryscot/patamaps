# Native SDK benchmark driver

This unpublished development workspace uses the public Patamaps SDK to measure
strict decoding, canonical hashing, graph checks, admission, projection batches,
emission, capture/replay and bounded repair. It creates checked branching proofs
through `derive`; it implements no alternate admission rules.

Build with the repository's pinned toolchain:

```sh
cargo build --manifest-path examples/benchmark-native/Cargo.toml --release --locked --offline
python3 scripts/bench_phases.py --cli target/release/patamaps --driver examples/benchmark-native/target/release/patamaps-benchmark-native --node /absolute/path/to/node --reference /absolute/path/to/metamap --output /absolute/path/to/results
```

`CARGO_TARGET_DIR` may select another object-cache location. The actual recorded
run used `target/benchmark-native`; macOS builds used SDK 26.5. The measurement
runner currently uses macOS `otool` to inventory linked system libraries.
See [method and limits](../../docs/acceptance/benchmarks/METHOD.md) and its actual
raw samples. It does not provide a protected activator or performance guarantee.
