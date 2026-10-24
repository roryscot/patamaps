# Next page rewrites and canonical session proxy

This bounded profile passed on pinned vercel/chatbot
c2f8235e1f3ea903ad8b7f61447c4f74164b5c58 with Next 16.2.10.
[Independent review](../acceptance/project-adoption/g3-next-rewrite-runtime-20261024/accepted-40055414930/independent-verification.json)
binds the exact source, derived configuration, compiled rules, driver bytes and
actual production HTTP/browser results in [run 40055414930](https://github.com/roryscot/patamaps/actions/runs/40055414930)
at `3cfe969`. This is an explicit qualification configuration, not unchanged
upstream behavior or a turnkey configuration for another application.

## Declared configuration

The original source stays separate and unchanged. Only the fresh staged
next.config.ts and an added nonsecret profile file define the derived variant.
Both contexts/digests are recorded. The BotID wrapper runs first; its original
flat rewrite array is preserved in afterFiles before the additions are composed.
All four original rewrite/redirect/header records retain their exact rule/phase.

| Phase and source | Condition | Destination / verified behavior |
| --- | --- | --- |
| beforeFiles /qualified/auth/:page(login\|register) | Header x-patamaps-rewrite=enabled; query blocked absent | /:page; login/register render with the original alias URL and HTTP 200 |
| afterFiles /qualified/session | Query view=session; header x-patamaps-block absent | Captured owned loopback origin + /api/auth/session; HTTP 200 JSON matches the direct guest identity |

A real bound socket reserves the owner port before the build. Its validated
integer and literal http://127.0.0.1 origin enter the captured profile/config;
the runtime must consume that same port and releases the reservation only for
owner-server startup. Arbitrary remote origins and invalid port types/ranges are
not accepted. Failure cleanup closes the reservation. The observed port belongs
to that CI run; it is not a reusable public endpoint.

The browser first establishes a real guest through the unchanged owner's login
flow. This respects its existing proxy/session requirements. The canonical
session proxy makes an HTTP request at the owner's canonical pathname, on the
same owned loopback listener already behind the HTTPS test proxy. No auth
handler, CSRF policy, credential resolution or production configuration is changed.

## What passed

All twelve declared rewrite/proxy controls passed: both rendered aliases and
preserved browser URLs; required/mismatched header, blocked query, prefix, extra
segment and page-parameter refusals; matched direct/aliased session identity;
missing/wrong query and blocking-header refusals. Refusals require actual404
without following redirects. All sixteen existing auth/document groups and
four unchanged upstream page tests also passed.

The native checks preserve complete compiled regex/condition/phase bytes.
Missing projection and stale projection after request/input rehash refuse;
changed captured configuration refuses before a marker effect. Original and
derived bytes/modes, source exclusions, exact driver digests and finite generated
secret barriers passed. Browsers, HTTPS proxy, owned processes/listeners and the
port reservation stopped. Native discovery still reports matching/HTTP execution
not performed; the separate actual runtime evidence supplies those results.

## Known boundary and reproduction

The original purely internal session alias failed: the matched canonical query
returned200 while the alias returned400 JSON without a redirect.
[That diagnostic](../acceptance/project-adoption/g3-next-rewrite-runtime-20261024/attempt-5/ci.json)
remains failed. The [revision2 plan](../plans/2026-10-24-next-canonical-proxy.md)
changes the configuration recipe to an explicit canonical loopback proxy while
retaining the same positive/refusal expectations and endpoint. Do not label the
original internal-session profile accepted or infer arbitrary NextAuth aliases.

Repeat the exact maintainer case with the existing workflow:

    gh workflow run native-capabilities.yml --repo roryscot/patamaps --ref feat/retained-owner-preparation -f qualification=next-rewrites

The default next-server-actions choice retains the unchanged-source auth path.
The [original plan](../plans/2026-10-24-next-rewrite-runtime.md) and five failed
attempts remain preserved. Compact public evidence is committed; the 367,037-byte
CI artifact has 14-day retention. No raw runtime logs, HTTP, cookies, database
credentials or private keys are published.

This result does not accept external BotID execution, every rewrite pattern or
HTTP method, installed Next workflows, full dependency/toolchain closure,
performance or production activation. Declare another owner's actual intent,
configuration and verification requirements explicitly.


## Fresh installed command qualification

The same pinned profile now passes with fresh source and native installations in
[run40061124534](https://github.com/roryscot/patamaps/actions/runs/40061124534)
at13faaa4; [independent review](../acceptance/project-adoption/g5-installed-next-20261024/accepted-40061124534/independent-verification.json)
checks exact packages/source/engine and both actual owner workflows. This adds
installed command usability. Full retained Next runtime-bundle selection and
producer/build-tool-unavailable replay remain open in the
[I1/I2 plan](../plans/2026-10-24-installed-next.md).

Maintainers can repeat this CI-only Linux qualification with:

    gh workflow run native-capabilities.yml --ref feat/retained-owner-preparation -f qualification=next-installed

The installed source package supplies its own qualifier and guides. An explicit
expected source-inventory digest replaces Git provenance; every source path and
byte is checked before commands and after execution. Checkout CLI/qualifier paths
are unavailable. Owner states remain separate; only newly created public pnpm/
browser caches are shared sequentially. The combined4GB growth/500MB reserve and
all previous native/browser refusals stay required. The test database uses
authenticated IPv4 loopback TCP, with its actual settings queried before
migrations. Generated credentials, Action keys and detailed output inventories
stay private. These development-profile packages are scoped CI evidence, not a
new registry publication or an arbitrary-project installer claim.
