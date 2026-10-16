# Selected Next.js source observations

The optional Next parser can observe existing project layouts through explicit native input capture. Use scripts/project_next_qualification.py through the configured project storage supervisor. It requires a Patamaps CLI, Node, an explicit TypeScript package directory, a project profile, original source root, App Router root and a fresh retained output directory.

For example, the driver argv after the supervisor is:

```sh
python3 -B scripts/project_next_qualification.py   --compiler /tools/patamaps --node /tools/node   --typescript /project/node_modules/typescript   --definition /profiles/site-inputs.json --source /project   --app-router-root apps/site/src/app   --require-endpoint POST /api/items   --output /retained/site-observation-1
```

The definition is a patamaps-project-inputs-1 profile with nonsecretInputs:true, explicit project-relative inputs and a next-app component containing the router root. Select each special file to observe (page, layout, route, template, boundary or fallback) and separately select the package and Next configuration files whose bytes should be recorded. No recursive selection is implicit in this driver. Secret references remain unresolved labels. Native strict JSON, profile validation and descriptor-relative capture enforce the input contract.

The existing pinned Node adapter parses the captured special files; Rust owns process receipts, composition, projection and offline replay. Provider sources and TypeScript are copied into retained tooling, with license notices. Process dependency closure remains unproved and caching stays disabled. The driver requires every declared selected source to exist, rejects missing-input generation, checks optional endpoint expectations against observed method/path facts, and verifies the baseline after configured staged source/tool paths are renamed and PATH is empty. It recaptures the original selected bytes and requires the original Git HEAD/status and qualification driver to remain unchanged.

These are source observations. Next configuration files are captured as bytes, not executed or interpreted. Rewrites, environment resolution, Server Action semantics, proxy behavior, complete import closure, application compilation and runtime are not established. Retained source/tools remain available at their renamed paths; replay does not claim operating-system denial of those paths. Failures and partial runs remain for review. A commit during qualification invalidates the aggregate even if selected bytes recapture identically; use a fresh output directory for a new attempt.

For compiled route/configuration data, use the separate [native build observation profile](compiled-next-observations.md). Source AST facts and compiled facts do not establish runtime behavior.
