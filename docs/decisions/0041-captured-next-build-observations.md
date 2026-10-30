# Captured Next build observations

Status: adapter correction in progress after actual Next 14.2.14 manifest
inspection exposed a module-file versus public-route mapping mismatch in the
synthetic fixture contract.

Existing source AST observations do not describe compiled route aliases,
configured redirects or the resolved build configuration. Add next-build to
the existing native discovery provider dispatch and engine source identity.
Reuse captured request validation, process supervision, graph construction,
workspace composition and offline replay. No new graph or execution framework.

Require exactly four declared nonsecret inputs: version 3 App Router routes,
`app-paths-manifest` module keys and emitted relative file values,
`app-path-routes-manifest` normalized public routes, and a separate typed owner
configuration projection. Require matching module keys and bind all three
manifest digests to exact captured bytes. Treat the route map as captured output;
do not reimplement Next normalization. Refuse unsafe module paths, unknown fields,
mixed generations, unsupported versions, Pages Router dataRoutes, invalid
conditions and private-valued configuration fields in this public-env profile.
Preserve category/index ordering. Treat RSC protocol data as opaque. Upstream
Next 14.2.14 and 16.1.6 build sources both generate the route map separately from
the module-file map; see the versioned implementation links in the guide.

The provider observes data. It never executes config, regex, HTTP or secret
references, and it does not authenticate the declared build receipt address.
Actual compilation evidence remains an independent qualification record.
Owner mappings supply business meaning and preserve domain identities.

Native verification includes existing Rust workspace regressions, final affected
package tests/Clippy, six CLI controls and a retained actual Next 16.1.6 application.
The real comparison and offline replay passed without altering the original app.
The profile and remaining scope are documented in
[the guide](../guides/compiled-next-observations.md).
