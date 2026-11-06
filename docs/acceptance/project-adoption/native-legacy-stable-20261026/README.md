# Exact original-owner legacy JSON utilities

stableLegacyJson and digestLegacyValue use the native read-only reporting
dispatcher and existing legacy serializers. They preserve the owner's0.5.0
generic data semantics without selecting executable/JCS pack rules from a root
schemaVersion. They confer no validation, admission or activation capability.

Canonical guarded commands passed: cargo test --locked --offline -p
patamaps-core --test legacy_reporting; the corresponding --test
legacy_projection; cargo build --locked --offline -p patamaps-cli;
scripts/parity/legacy_stable_contracts.mjs; and the repeated
scripts/parity/projection_typescript_contracts.mjs controls.

[The receipt](receipt.json) binds source, engine and output digests. Twelve
finite JSON cases each matched original compact JSON, pretty JSON and digest.
They cover null/scalars, numeric member enumeration, locale ties in both input
orders, version2 data, UTF-16 and own prototype-looking keys. A large compact
digest also matched; oversized pretty/wire expansion refused before formatting.
All four reporting and four projection regression tests passed, preserving the
66-case frozen projection corpus. All26 renderer controls passed again.

This closes the demonstrated utility interface gap. Actual unchanged owner
generator/test qualification and full G6 acceptance remain separate.
