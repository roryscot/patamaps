# Captured Next build observations

Use the native process provider `next-build` with exactly four explicitly
nonsecret captured inputs: the routes manifest, the App Router module manifest,
the separately generated App Router route map, and an independent owner
configuration projection. This complements source AST observations; it does not
replace them or infer business correspondences.

The parser accepts reviewed Next App Router version-3 manifest shapes from
14.2.x and 16.x. Next 14.2.14 and 16.1.6 both write `app-paths-manifest.json`
with module-file values, then write `app-path-routes-manifest.json` from each
module key and Next's normalized route. The two maps must have the same keys;
Patamaps preserves the module file as a bounded relative path and takes the
public route only from the paired route manifest. It does not execute or
reimplement Next's normalization. See the [Next 14.2.14 build source](https://github.com/vercel/next.js/blob/v14.2.14/packages/next/src/build/index.ts#L1619-L1631)
and [Next 16.1.6 build source](https://github.com/vercel/next.js/blob/v16.1.6/packages/next/src/build/index.ts#L1916-L1928).
A real Next 16.1.6 application remains the qualified application version; the
Next 14.2.14 existing-project replay is a separate compatibility check. Pages
Router/dataRoutes, unknown fields and unsupported rule shapes refuse.

Example process-source config:

```json
{
  "provider": "next-build",
  "nonsecretInputs": true,
  "routesManifest": "build-observations/routes.json",
  "appPathsManifest": "build-observations/app-paths.json",
  "appPathRoutesManifest": "build-observations/app-path-routes.json",
  "configurationProjection": "build-observations/config.json"
}
```

Use the existing native `discover-native` invocation, with those same four paths
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
  "appPathRoutesDigest": "sha256:<64 lowercase hex>",
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

The reader checks all three manifest byte digests, paired app-map key equality,
relative module-file paths, and basePath consistency. It records the build receipt
digest and framework version as owner declarations, not authenticated execution
evidence. The paired route map is trusted as captured output after its structural
checks; its derivation from a Next build is not re-executed or authenticated.
Preserve the actual build/tool receipts separately. A fabricated manifest and
receipt address cannot establish a build.

Outputs are next-build-route, next-build-rule, next-build-module,
next-build-configuration and next-build-protocol entities. Rule category and
array index preserve order and conditions. Regex strings are never executed.
RSC/rewrite protocol objects are preserved as opaque metadata. Module aliases
retain route groups and dynamic path labels as captured; HTTP methods and
Server Action handlers are not inferred. Optional serverActions config contains
only bodySizeLimit and allowedOrigins; observing a limit does not test it.

Module entities retain the app-path key, bounded emitted `moduleFile`, and
`routePath` from `app-path-routes-manifest.json`; the file mapping is not treated
as a route. The [existing-project receipt](../acceptance/project-adoption/g3-next-compiled-20261016/receipt.json)
compares 43 static routes, 3 dynamic routes, 46 module aliases and the compiled
redirect against a retained Avaelus/Seeder build. That earlier receipt's retained
`apps.json` contains normalized slash-prefixed route values; it does not verify
the emitted module-file values now captured separately by `appPathsManifest`.
A missing projection refuses; offline baseline verification passes with
source/provider paths unavailable. Its real rewrite lists are empty. Nonempty
rewrite records are covered by
controlled data cases, not real proxy execution. HTTP/browser, generated-contract
integration, complete contexts, deployment and installed qualification remain open.

Inputs total at most 8 MiB; at most 10000 observation entities are emitted. Selected arrays/maps and strings have further explicit bounds. This profile refuses control characters in observed text fields. It provides structured observations, not a complete validator for all Next runtime semantics.
