# Packaged asset mirrors

These files are byte-for-byte mirrors of the authoritative repository paths
under `fixtures/` and `relation-packs/`. They make the core crate and its
existing tests self-contained when Cargo packages it outside the workspace.
Do not edit mirrors independently. After changing an authoritative file, run
`python3 -B scripts/core_package_assets.py --sync` from the repository root,
then run the default check and review both changes. The sync updates referenced
mirrors only and never deletes files.
