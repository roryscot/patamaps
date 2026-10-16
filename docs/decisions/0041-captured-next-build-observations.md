# Captured Next build observations

Status: implemented and scoped native verification passed; new Linux CI pending.

Existing source AST observations do not describe compiled route aliases,
configured redirects or the resolved build configuration. Add next-build to
the existing native discovery provider dispatch and engine source identity.
Reuse captured request validation, process supervision, graph construction,
workspace composition and offline replay. No new graph or execution framework.

Require exactly three declared nonsecret inputs: version 3 App Router routes,
module aliases, and a separate typed owner configuration projection. Bind
projection manifest digests to exact captured bytes. Refuse unknown fields,
mixed generations, unsupported versions, Pages Router dataRoutes, invalid
conditions and private-valued configuration fields in this public-env profile.
Preserve category/index ordering. Treat RSC protocol data as opaque.

The provider observes data. It never executes config, regex, HTTP or secret
references, and it does not authenticate the declared build receipt address.
Actual compilation evidence remains an independent qualification record.
Owner mappings supply business meaning and preserve domain identities.

Native verification includes existing Rust workspace regressions, final affected
package tests/Clippy, six CLI controls and a retained actual Next 16.1.6 application.
The real comparison and offline replay passed without altering the original app.
The profile and remaining scope are documented in
[the guide](../guides/compiled-next-observations.md).
