# Captured Next build observations

Use the native process provider `next-build` with exactly three explicitly
nonsecret captured inputs: a routes manifest, an App Router module-to-route map,
and an independent owner configuration projection. This complements source AST
observations; it does not replace them or infer business correspondences.

The supported input profile is Next App Router, routes-manifest version 3,
with a declared stable 16.x version. The real qualified compiler is 16.1.6.
Other releases are not automatically runtime-qualified. Pages Router/dataRoutes,
unknown fields and unsupported rule shapes refuse.

Example process-source config:

```json
{
  "provider": "next-build",
  "nonsecretInputs": true,
  "routesManifest": "build-observations/routes.json",
  "appPathsManifest": "build-observations/apps.json",
  "configurationProjection": "build-observations/config.json"
}
```

Use the existing native `discover-native` invocation, with those same three paths
in its inputs array. A workspace may compose these observations with source AST
facts and owner-authored correspondences. Keep original business identities;
matching URLs alone never establish semantic equivalence.

An independent configuration input has this shape. Replace all digest placeholders
with SHA256 addresses of exact retained file bytes, not canonicalized JSON:

```json
{
  "profile": "patamaps-next-build-config-1",
  "frameworkVersion": "16.1.6",
  "buildReceiptDigest": "sha256:<64 lowercase hex>",
  "routesDigest": "sha256:<64 lowercase hex>",
  "appPathsDigest": "sha256:<64 lowercase hex>",
  "configuration": {
    "basePath": "",
    "output": "standalone",
    "trailingSlash": false,
    "environment": {"NEXT_PUBLIC_API_URL": "http://127.0.0.1:1"},
    "secretReferences": {"AUTH_TOKEN": "OWNER_AUTH_TOKEN"},
    "transpilePackages": [],
    "serverActions": null
  }
}
```

Project only reviewed nonsecret fields. Native project text capture excludes
.next/node_modules/target; copy reviewed manifest inputs into an explicitly
declared observation directory. Do not put raw environment files,
required-server-files configuration dumps or server-reference encryption
material into the capture. Secret references are labels and are never resolved.
This profile restricts environment values to explicit uppercase NEXT_PUBLIC_
keys; other configuration treatment remains separate work.

The reader checks both manifest byte digests and basePath consistency. It
records the build receipt digest and framework version as owner declarations,
not authenticated execution evidence. Preserve the actual build/tool receipts
separately. A fabricated manifest and receipt address cannot establish a build.

Outputs are next-build-route, next-build-rule, next-build-module,
next-build-configuration and next-build-protocol entities. Rule category and
array index preserve order and conditions. Regex strings are never executed.
RSC/rewrite protocol objects are preserved as opaque metadata. Module aliases
retain route groups and dynamic path labels as captured; HTTP methods and
Server Action handlers are not inferred. Optional serverActions config contains
only bodySizeLimit and allowedOrigins; observing a limit does not test it.

The [existing-project receipt](../acceptance/project-adoption/g3-next-compiled-20261016/receipt.json)
compares 43 static routes, 3 dynamic routes, 46 module aliases and the compiled
redirect against a retained Avaelus/Seeder build. A missing projection refuses;
offline baseline verification passes with source/provider paths unavailable.
Its real rewrite lists are empty. Nonempty rewrite records are covered by
controlled data cases, not real proxy execution. HTTP/browser, generated-contract
integration, complete contexts, deployment and installed qualification remain open.

Inputs total at most 8 MiB; at most 10000 observation entities are emitted. Selected arrays/maps and strings have further explicit bounds. This profile refuses control characters in observed text fields. It provides structured observations, not a complete validator for all Next runtime semantics.
