import { legacyRegistryGraphSnapshot } from "./legacy-registry.mjs";
import { marshalLegacyObservationJson } from "./canonical.mjs";
const provenance = {
  status: "declared",
  assertedBy: "adapter:legacy-sources-of-truth",
};
export function createLegacyCliApi(invoke, invokeAsync, api) {
  const call = (operation, input) =>
    invoke("cli", "json", {
      operation,
      input: marshalLegacyObservationJson(input),
      locale: new Intl.Collator().resolvedOptions().locale,
    });
  const io = (operation, input) =>
    invokeAsync("workspace", "json", {
      operation,
      input: marshalLegacyObservationJson(input),
      locale: new Intl.Collator().resolvedOptions().locale,
    });
  const path = (p) =>
    invoke("workspace", "json", {
      operation: "resolve",
      input: marshalLegacyObservationJson({ root: process.cwd(), path: p }),
    });
  const read = async (p) =>
    (await io("read-json", { path: path(p), optional: false })).value;
  const isLegacySourceOfTruthDocument = (value) =>
    call("is-migration", { value });
  function adaptLegacySourcesOfTruth(legacy, options = {}) {
    const response = call("migration", { legacy, options, provenance });
    const result = response.value;
    for (const i of response.undefinedLocators) {
      const e = result.document.entities[i];
      result.document.entities[i] = {
        id: e.id,
        kind: e.kind,
        label: e.label,
        locators: undefined,
        attributes: e.attributes,
        provenance: e.provenance,
      };
    }
    for (const e of [
      ...result.document.entities,
      ...result.document.mappings,
      ...result.document.authorities,
    ])
      e.provenance = provenance;
    return result;
  }
  async function runLegacyCli(args) {
    let pendingStderr = "";
    try {
      const plan = call("plan", { args });
      if (plan.exitCode !== undefined) return plan;
      let data, config, loaded, discovery;
      if (["generate", "check"].includes(plan.command)) {
        loaded = await api.loadLegacyMetamapConfig(plan.positions[0]);
        config = loaded.config;
        discovery =
          plan.command === "generate"
            ? await api.discoverLegacyWorkspace(loaded, {
                useCache: plan.useCache,
              })
            : await api.checkLegacyWorkspace(loaded, {
                useCache: plan.useCache,
              });
        data = discovery;
      } else if (plan.command === "migrate-sources") {
        const legacy = await read(plan.positions[0]);
        const valid = isLegacySourceOfTruthDocument(legacy);
        data = {
          valid,
          ...(valid ? { result: adaptLegacySourcesOfTruth(legacy) } : {}),
        };
      } else {
        const registry = new api.LegacyRelationRegistry();
        for (const p of plan.packPaths)
          registry.registerPack(await api.loadLegacyRelationPack(path(p)));
        const graph = await read(plan.positions[0]);
        if (plan.command === "validate")
          data = call("validate", {
            document: graph,
            registry: legacyRegistryGraphSnapshot(registry),
          });
        else if (plan.command === "diff") {
          const after = await read(plan.positions[1]);
          const validations = [
            call("validate", {
              document: graph,
              registry: legacyRegistryGraphSnapshot(registry),
            }),
            call("validate", {
              document: after,
              registry: legacyRegistryGraphSnapshot(registry),
            }),
          ];
          data = {
            validations,
            ...(validations.every((v) => v.valid)
              ? { diff: api.diffLegacyDocuments(graph, after) }
              : {}),
          };
        } else if (plan.command === "trace") {
          try {
            const value = api.LegacyGraph.from(graph, { registry });
            const depth =
              plan.depthKind === "nan"
                ? Number.NaN
                : plan.depthKind === "positive-infinity"
                  ? Infinity
                  : plan.depthKind === "negative-infinity"
                    ? -Infinity
                    : plan.depth;
            data = {
              visits: value.trace(plan.positions[1], {
                direction: plan.direction,
                maxDepth: depth,
                ...(plan.positions[4]
                  ? { relations: [plan.positions[4]] }
                  : {}),
              }),
            };
          } catch (e) {
            if (e instanceof api.LegacyGraphValidationError)
              data = { validationIssues: e.issues };
            else throw e;
          }
        } else if (plan.command === "authority")
          data = api.LegacyGraph.from(graph, { registry }).resolveAuthority(
            plan.positions[1],
            plan.positions[2],
          );
      }
      const result = call("render", {
        plan,
        data,
        ...(config ? { config } : {}),
      });
      pendingStderr = result.stderr;
      if (result.writeWorkspace)
        await api.writeLegacyWorkspaceOutputs(loaded, discovery);
      if (result.writeFile)
        await io("write-file", {
          path: path(result.writeFile.path),
          content: result.writeFile.content,
          createParents: false,
        });
      return {
        exitCode: result.exitCode,
        stdout: result.stdout,
        stderr: result.stderr,
      };
    } catch (e) {
      return call("failure", {
        message: e instanceof Error ? e.message : String(e),
        stderr: pendingStderr,
      });
    }
  }
  return {
    runLegacyCli,
    isLegacySourceOfTruthDocument,
    adaptLegacySourcesOfTruth,
  };
}
