#!/bin/sh
set -eu
export CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0
# Called inside a disposable official Rust container as root. Host source and
# registry mounts are read-only; all compilation/activation stays in /work.
test "$(id -u)" = 0
mkdir -p /work/project /usr/local/cargo/registry
cp -a /cached-registry/. /usr/local/cargo/registry/
cp -R /source/crates /source/fixtures /source/relation-packs /source/schemas /work/project/
cp /source/Cargo.toml /source/Cargo.lock /source/rust-toolchain.toml /source/LICENSE /source/NOTICE /work/project/
cd /work/project
cargo build --workspace --locked --offline
cargo clippy --workspace --all-targets --locked --offline -- -D warnings
PATAMAPS_TEST_COMPILER_BINARY=/work/project/target/debug/patamaps PATAMAPS_TEST_ACTIVATOR_BINARY=/work/project/target/debug/patamaps-activator cargo test --workspace --locked --offline -- --test-threads=1
rustc --version
cargo --version
stat -f -c 'filesystem=%T' /work
