# Canonical owner-session proxy profile

Status: revision2 independently verified in [run 40055414930](https://github.com/roryscot/patamaps/actions/runs/40055414930) at `3cfe969`. [Evidence](../acceptance/project-adoption/g3-next-rewrite-runtime-20261024/accepted-40055414930/independent-verification.json) proves the twelve rewrite/proxy cases, original sixteen auth/document groups, four upstream page tests and all native/ownership/cleanup controls. The original internal-session profile remains failed.
Continue the original G3/G6 adoption goal, preserving all requirements in the
[rewrite increment](2026-10-24-next-rewrite-runtime.md). This changes the
configuration recipe after contrary evidence, not its positive/refusal behavior.

## Evidence and boundary

[Diagnostic40054799502](../acceptance/project-adoption/g3-next-rewrite-runtime-20261024/attempt-5/ci.json)
at005edaf matched the same query on both paths: /api/auth/session?view=session
returned200; the internal alias /qualified/session?view=session returned400 JSON
without a redirect. Both alias pages and all six beforeFiles refusals passed;
all browsers/proxies/processes/listeners stopped. The original internal-session
profile remains failed and must never be labeled accepted.

Pinned next-auth5.0.0-beta.25 /@auth/core0.37.2 source, each inspected from its
original npm archive against the pinned lockfile SHA-512, parses the request
pathname against /api/auth. This supplies a source-based explanation for the
observed incompatibility; it does not establish arbitrary NextAuth behavior.

## Explicit configuration

Keep the same alias paths, query/header conditions, canonical session endpoint,
HTTP 200/same-guest-identity positive, all HTTP 404 refusals, original rule/phase
preservation, native projection/config mutation refusals and all original
sixteen auth/document groups/four page tests. No target substitution, handler
patch, skipped typecheck, changed success threshold or fabricated user response.

The derived profile adds a declared canonical owner origin:
http://127.0.0.1:OWNED_NEXT_PORT. Reserve an ephemeral candidate port before build,
capture that exact nonsecret integer/origin in the profile and derived config,
and require the production owner runtime to bind that same port. Refuse invalid
port types/ranges and an occupied configured port. The afterFiles destination is
the exact origin plus /api/auth/session; the beforeFiles login/register aliases
stay internal. This makes a new HTTP request at the canonical owner pathname.

This is a trusted-owner loopback proxy, not the original internal session rewrite.
It uses the same HTTP loopback listener already behind the owned HTTPS proxy.
Only a literal loopback address and validated integer port may be constructed;
no arbitrary remote origin, credentials, host networking change, new process,
raw environment ingestion or app auth/CSRF policy change. The URL/port/config
must stay digest-bound and observable. No external BotID behavior is accepted.

## Acceptance and provenance

Use an explicit version2 profile identity. Keep all twelve frozen runtime cases
and five native binding checks, plus invalid-port/no-write preflight controls.
Verify actual source/build/compiled/native/HTTP/browser behavior with the same
existing opt-in workflow. Type checks, capacity limits, original/derived source
audits, driver digests, private evidence barriers and owned stop proof remain.
A pass closes only this declared internal-page/canonical-session-proxy profile;
it cannot retroactively accept the failed internal-session profile.
