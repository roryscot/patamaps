#!/bin/sh
set -eu
destination=$1
mkdir -p "$destination/application" "$destination/rust" "$destination/crates"
cp service/LICENSE service/NOTICE "$destination/application/"
rust_docs="$(rustc --print sysroot)/share/doc/rust"
case "$(rustc --version)" in
    "rustc 1.99.0 "*) ;;
    *) printf 'This notice bundle requires Rust 1.99.0\n' >&2; exit 1 ;;
esac
(cd service/licenses/rust-1.99.0 && sha256sum --check SHA256SUMS)
for name in LICENSE-MIT LICENSE-APACHE COPYRIGHT SOURCE.json SHA256SUMS; do
    cp "service/licenses/rust-1.99.0/$name" "$destination/rust/"
done
for name in COPYRIGHT-library.html licenses/MIT.txt licenses/Apache-2.0.txt; do
    if ! test -f "$rust_docs/$name"; then
        printf 'Required installed Rust notice unavailable: %s\n' "$rust_docs/$name" >&2
        exit 1
    fi
done
cp "$rust_docs/COPYRIGHT-library.html" "$destination/rust/"
cp -R "$rust_docs/licenses" "$destination/rust/licenses"
for package in "${CARGO_HOME:-/usr/local/cargo}"/registry/src/*/*; do
    test -d "$package" || continue
    found=0
    for notice in "$package"/LICENSE* "$package"/LICENCE* "$package"/COPYRIGHT* "$package"/NOTICE*; do
        test -f "$notice" || continue
        mkdir -p "$destination/crates/$(basename "$package")"
        cp "$notice" "$destination/crates/$(basename "$package")/"
        found=1
    done
    if ! test "$found" = 1; then
        printf 'Required crate notices unavailable: %s\n' "$package" >&2
        exit 1
    fi
done
