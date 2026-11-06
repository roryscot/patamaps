# Actual Next.js 14.2 manifest replay

This scoped replay passed against three generated manifests from an existing Next.js 14.2.14 App Router project. Patamaps ingested the paired route/module manifests and app-path mapping, then verified record bindings after the selected input directory was made unavailable and the replay environment could not access the original source or tools.

The parser observed 55 route modules and 55 routes: 34 static and 21 dynamic. It also recorded 55 app paths, 55 app-path mappings, and one redirect rule. No rewrite or header rules were present in these inputs. The source checkout was clean before and after the replay, and no files were deleted.

The run used Norway's native-exclusive supervisor path with a 256 MiB per-run growth reservation. The persistent supervisor policy was unchanged; parallel execution was not activated. The supervisor recorded 39,573,741,568 free bytes at start and 39,561,703,424 at end. That aggregate delta is not an isolated attribution of writes to this replay.

This does not prove that the manifests were generated from the recorded source revision: they contain no source identity. Patamaps did not run the application build or execute next.config.js; the recorded configuration projection was agent-authored static/default input, and the bundle digest used by the input was not a build receipt. No environment or secret values were read. Effective configuration, HTTP/browser behavior, Server Actions, dependency closure, and deployment remain open. Raw route values and the generated observation graph remain in private retained evidence.

See receipt.json for hashes, exact counts, command outcomes, and limits.
