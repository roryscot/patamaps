# Copy-on-write context staging on Norway

The real Seeder baseline stopped at its existing 2.2 GB growth reservation before
the Next.js build. That failure and the failed attempt are retained in
`w1-baseline-growth-stop-20261116.json` and the Norway attempt state.

Context staging now attempts an independent copy-on-write file clone on macOS
when the source has no extended attributes or BSD flags. It validates the
cloned content, source identity, and isolation, and retains the ordinary copy
path for unsupported filesystems and files with extra metadata. Other platforms
continue to use the existing copy path.

A guarded Norway preflight cloned a 106,138,548-byte Next.js dependency. The
source and clone had distinct inodes; modifying the clone left the source hash
unchanged. Reported free space was unchanged immediately after cloning, although
this does not directly measure shared blocks. Filesystem allocation statistics
still counted 106,139,648 bytes for each file, so the existing retained-storage
accounting can count shared blocks more than once. No storage limit was raised.

Verification on Norway:

- The first focused build failed on Rust type inference for the empty attribute
  buffer. Its full log remains in
  `.tools/context-clone-implementation-20261116/`.
- After correcting the buffer type, `cargo test --locked --offline --package
  patamaps-workspace --lib project_context::tests --jobs 2` passed eight tests,
  including write isolation and non-copying of extended attributes.
- `cargo build --locked --offline --package patamaps-cli --bin patamaps --jobs
  2` succeeded. Both commands ran under the existing supervisor. The Rust
  toolchain warned that its optional debug-symbol stripping failed because
  `libLLVM.dylib` was unavailable.
- The real Seeder baseline using the rebuilt CLI is a separate run; its
  acceptance and the later lifecycle checks are not established by the unit
  tests or the preflight.
