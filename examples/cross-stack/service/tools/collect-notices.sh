#!/bin/sh
set -eu
destination=$1
mkdir -p "$destination/application" "$destination/rust" "$destination/crates"
cp service/LICENSE service/NOTICE "$destination/application/"
rust_docs="$(rustc --print sysroot)/share/doc/rust"
for name in LICENSE-MIT LICENSE-APACHE COPYRIGHT; do
    test -f "$rust_docs/$name"
    cp "$rust_docs/$name" "$destination/rust/"
done
for package in "${CARGO_HOME:-/usr/local/cargo}"/registry/src/*/*; do
    test -d "$package" || continue
    found=0
    for notice in "$package"/LICENSE* "$package"/LICENCE* "$package"/COPYRIGHT* "$package"/NOTICE*; do
        test -f "$notice" || continue
        mkdir -p "$destination/crates/$(basename "$package")"
        cp "$notice" "$destination/crates/$(basename "$package")/"
        found=1
    done
    test "$found" = 1
done
