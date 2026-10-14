# Fixed debugger stylesheet authorization

The pinned reference `debugger.test.ts` requires its sole stylesheet to be
authorized through a SHA-256 content-security-policy hash. The native renderer
escaped candidate values, but used `style-src 'unsafe-inline'`. That allowed more
inline stylesheet content than the reference guarantee permits.

Keep the existing static HTML, CSS, escaping and private `CheckedExplanation`.
Replace the broad style allowance with the exact SHA-256 base64 hash of the fixed
CSS bytes. No dependency, executable script, external resource or server is added.
The prior renderer is [byte-preserved](../history/debugger-style-transition-2026-10-14/receipt.json).

Native checks require the broad allowance to be absent. The installed workspace
driver independently extracts the sole stylesheet from actual CLI output,
computes its digest with Python's hashlib/base64, and checks the emitted policy.
It also checks executable-looking labels remain escaped and that executable tags
and external links are absent. These are static output checks. Interactive browser
rendering remains unverified because the browser refused the local file URL;
that policy restriction was not circumvented.
