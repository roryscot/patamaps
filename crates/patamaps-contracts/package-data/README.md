# Packaged test asset mirrors

These files mirror authoritative repository files under `fixtures/`. They keep
the contracts crate's existing tests self-contained when packaged. Do not edit
them independently. From the repository root, run
`python3 -B scripts/core_package_assets.py --sync` after changing an
authoritative file, then run the default check. The sync never deletes files.
