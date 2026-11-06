# Real Next rewrite runtime increment

Status: plan and frozen expectations before implementation; no new runtime pass.
Baseline: c3ecead44e67f07a411f22edbad1f1e2e1e6cbaf.
This advances G3/G6 of the existing adoption goal; C01–C19 parity is separate.

## Scope and dependencies

Reuse pinned vercel/chatbot c2f8235e1f3ea903ad8b7f61447c4f74164b5c58,
Next16.2.10, pnpm10.32.1 and the existing source/native-observation/production
auth lane. No replacement app, new build framework, native Rust API change,
private owner configuration, external BotID call or production activation.

The upstream next.config.ts SHA-256 is
856cc04806b203481ad9722b92d3f52907a618468ee79129f98373b4ae86e075.
It has no internal rewrites; withBotId adds two external afterFiles rules.
Freeze the original source/context digest. Apply a separately recorded, bounded
qualification overlay only to the fresh staged candidate, preserve original
source, capture the derived configuration/profile as declared nonsecret inputs,
and bind original/derived bytes independently. Default auth qualification keeps
its unchanged-source path. Never describe the derived app as unchanged upstream.

The explicit profile adds:
- beforeFiles: /qualified/auth/:page(login|register) -> /:page;
  has header x-patamaps-rewrite=enabled; missing query blocked.
- afterFiles: /qualified/session -> /api/auth/session;
  has query view=session; missing header x-patamaps-block.

These are qualification aliases, not inferred domain semantics. The original
BotID rules, redirect and header records must remain byte-equivalent after
filtering out only the two named additions; rule indexes may shift.
The [Next contract](https://nextjs.org/docs/app/api-reference/config/next-config-js/rewrites)
defines these phases/conditions. Test the pinned actual framework; the current
documentation alone does not prove pinned behavior.

## Frozen acceptance

Use the existing owned HTTPS loopback, new CI-only PostgreSQL, secure guest
session and Chromium. Bootstrap a genuine guest through the existing login
flow before alias probes because the unchanged owner proxy runs first.
Keep passwords, cookies, database URLs, key material and raw HTTP private.

| Control | Required observation |
| --- | --- |
| login alias | HTTP200; Welcome back heading visible; original alias URL retained; no redirect |
| register alias | HTTP200; Create account heading visible; original alias URL retained; no redirect |
| missing required header | HTTP404 with redirects disabled |
| wrong header value | HTTP404 with redirects disabled |
| blocked query present | HTTP404 with redirects disabled |
| wrong path prefix | HTTP404 with redirects disabled |
| extra path segment | HTTP404 with redirects disabled |
| unsupported page parameter | HTTP404 with redirects disabled |
| session alias with required query | HTTP200 JSON; guest user identity equals direct /api/auth/session response |
| missing session query | HTTP404 with redirects disabled |
| wrong session query | HTTP404 with redirects disabled |
| blocking session header | HTTP404 with redirects disabled |

Native checks must additionally prove:
1. Actual compiled manifests contain both exact rule/condition/phase declarations,
   and native observations preserve their full compiled rule/regex bytes while
   still reporting matchingAndExecution=not-performed.
2. Original external rules/redirect/header records remain unchanged.
3. Missing configuration-projection input refuses NATIVE_NEXT_BUILD.
4. A changed routes manifest with recomputed request/input hashes but stale
   projection route digest refuses NATIVE_NEXT_BUILD.
5. A changed captured next.config.ts refuses native execution before a marker;
   restore retained original derived bytes and verify the full selected inventory.

All original sixteen auth/document groups and four unchanged upstream page
tests must still pass; neither aliases nor their tests bypass those checks.
All owned browsers, HTTPS proxy, processes and listeners must stop. Audit source
exclusions, original and derived bytes/modes, bound driver digests and absence of
generated secrets in uploaded evidence. Do not relax conditions to make a run pass.

## Execution and retention

Add an opt-in to the existing reusable workflow/qualifier, preserving the old
default. Run focused deterministic overlay controls first, then the actual Linux
production lane. Follow existing 4GB growth /500MB reserve and bounded private
logs; no Intel heavy build, extra VM, policy increase or file deletion.
Retain only compact public receipts/observations in Git and the existing bounded
14-day CI evidence. Verify artifact digest and source/head/engine bindings before
acceptance. Commit and push plan, implementation and accepted/failed checkpoint
separately with the configured Rory identity.

Completion closes only this explicit internal-rewrite profile. Full Next grammar,
external BotID behavior, installed Next replay, applicable dependency closure,
deployment and exclusive actual-project performance remain separate original
requirements of the active adoption goal.
