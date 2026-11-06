# Cross-stack Linux fixture qualification

This evidence preserves the bounded cross-stack fixture checks from GitHub Actions run [39634269456](https://github.com/roryscot/patamaps/actions/runs/39634269456), pull request #1. The workflow checked out merge revision `2ed8ce46d05c9facd38ff7894fd96cb3e22e612a`, merging source commit `0bfa766903cef778ecd0b41cb51efbf70d206dc8` into `27dedef0186981d9fca60c1a2e665f34ab88da86`.

The retained receipts cover these scoped results:

- A Linux x86_64 BuildKit image with builder/runtime stages and an independently compiled Rust service; HTTP and Chromium exercised a real Next-to-Rust request/response round trip, Unicode identifiers, delayed hydration, backend failure and dynamic navigation.
- Twenty-one named image, HTTP/browser, BuildKit and refusal controls, including malformed/stale client data, broken copies, wrong stage, absent config/library, wrong listener, wrong architecture, and absent qualification lanes.
- An exact locally built CLI package installed into a relocated consumer workspace. The owner workflow verified 1,016 files, removed the configured compiler from the request path, then repeated the real Next/Rust round trip. This is not a fresh registry install.
- Ten targeted MetaMap comparison cases that compare independently observed facts and decisions; they do not require matching engine hashes.

The receipts report `fullCrossStackAcceptance: false` and `fullReleaseAccepted: false`; production activation was not performed. This qualifies the repository's cross-stack example and does not establish general support for external Next.js or Rust projects. The selected inputs remained unchanged, and the recorded deletion lists are empty.

The original CI diagnostics artifact was 938,623 bytes with GitHub SHA-256 `56409df9a11642e0a146865de270cc821ff1413dd1cdbf1630784d2614a9a64b` (artifact ID 12361211104). Its downloaded receipt files are copied here and hashed in [SHA256SUMS](SHA256SUMS). The separate 757,668,137-byte Linux image archive (artifact ID 12361860071, SHA-256 `389473f4286d60703be7490ef6ac6910cc6d19e57850723cb3b8eb245267abda`) remains a temporary GitHub artifact and is not included in the repository.
