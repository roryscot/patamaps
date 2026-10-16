# Staging diagnostic compatibility repair

CI run [38889600706](https://github.com/roryscot/patamaps/actions/runs/38889600706), source job 116935608577, failed its existing discovery assertion: an occupied destination returned PROJECT_STAGE_FILESYSTEM instead of PROJECT_STAGE_DESTINATION_UNAVAILABLE. Linux x86_64, aarch64 and image/browser jobs passed. The source job stopped before the new context CLI controls.

The shared staging helper now preserves the earlier destination, parent-symlink, directory, file and identity-change diagnostic codes. Fresh creation, descriptor-relative operations and no-overwrite behavior remain. The existing preservation test now requires the exact occupied-directory/file/symlink and parent-symlink refusal codes while still checking sentinel bytes and membership. The frozen CI assertion is unchanged.

Intel verification passed cargo fmt --all; cargo test --locked --offline -p patamaps-workspace (32 unit, 3 legacy IO, 11 project, 5 command, 5 source evaluation, 22 workspace and 2 compile-fail doc tests); cargo clippy --locked --offline -p patamaps-workspace -p patamaps-cli --all-targets -- -D warnings; cargo build --locked --offline -p patamaps-cli.

These checks ran in guard 403a978a-07e0-43d0-98e9-34df7d43427f, before a separately scoped reconstructed Next build in the same shell chain. The guard ultimately exited 1 because that later application wrapper hit a macOS EPERM cleanup error. Application build acceptance is not established by this repair.

Retained CI diagnostic artifact 12041386182 was verified against API size 23,769 bytes and SHA-256 3239a883932e95179e4c04ea5e1f0675a1429c580fb6cd4293af308ea88ffd31 before inspecting the actual refusal stderr.
