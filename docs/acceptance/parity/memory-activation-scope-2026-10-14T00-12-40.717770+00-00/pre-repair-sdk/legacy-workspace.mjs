import { marshalLegacyObservationJson } from "./canonical.mjs";
import { legacyRegistryGraphSnapshot } from "./legacy-registry.mjs";
let defaultRegistryFactory;
/** The licensed adapter package supplies constructors; it supplies no workspace
 * cache, baseline, semantic validation or graph-assembly decisions. */
export function setLegacyDefaultAdapterRegistryFactory(factory) {
  defaultRegistryFactory = factory;
}
function restore(response, input) {
  const result = response.value;
  const at = (root, path) => path.reduce((value, key) => value[key], root);
  if (response.declared) {
    const declared = response.declared;
    for (const { path, position } of declared.undefinedProperties) {
      const parent = at(declared, path.slice(0, -2));
      const key = path.at(-1),
        slot = path.at(-2);
      const properties = Object.entries(parent[slot]);
      properties.splice(position, 0, [key, undefined]);
      parent[slot] = Object.fromEntries(properties);
    }
    for (const { target, source } of declared.bindings) {
      at(declared, target.slice(0, -1))[target.at(-1)] = at(
        { configurations: input.config.correspondences },
        source,
      );
    }
    for (const field of ["entities", "mappings", "authorities"])
      for (const record of declared.document[field])
        record.provenance = declared.provenance;
    input = { ...input, declared };
    for (let i = 0; i < declared.issues.length; i++)
      result.driftIssues[i] = declared.issues[i];
  }
  for (const { target, source } of response.bindings)
    at(result, target.slice(0, -1))[target.at(-1)] = at(input, source);
  return result;
}
export function createLegacyWorkspaceApi(
  invoke,
  invokeAsync,
  Registry,
  initializeProviders,
) {
  const call = (operation, input) =>
    invoke("workspace", "json", {
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
  class LegacyAdapterRegistry {
    #adapters = [];
    #request(action, id) {
      return call("adapter-registry", {
        action,
        ...(id === undefined ? {} : { id }),
        ids: this.#adapters.map((a) => a.id),
      });
    }
    register(adapter) {
      this.#request("register", adapter.id);
      this.#adapters.push({
        id: adapter.id,
        version: adapter.version,
        fingerprint: (config, context) => adapter.fingerprint(config, context),
        discover: (config, context) => adapter.discover(config, context),
      });
      return this;
    }
    get(id) {
      const index = this.#request("get", id);
      return index === null ? undefined : this.#adapters[index];
    }
    require(id) {
      return this.#adapters[this.#request("require", id)];
    }
    ids() {
      return this.#request("ids");
    }
  }
  const path = (loaded, value) =>
    call("resolve", { root: loaded.repositoryRoot, path: value });
  async function read(path) {
    const result = await io("read-json", { path });
    return result.present ? result.value : undefined;
  }
  async function configure(loaded, registry) {
    const packs = await Promise.all(
      (loaded.config.relationPacks ?? []).map(async (configuredPath) => ({
        configuredPath,
        pack: await api.loadLegacyRelationPack(path(loaded, configuredPath)),
      })),
    );
    for (const { pack } of packs) registry.registerPack(pack);
    return packs;
  }
  async function defaultRegistry() {
    const library = await import("patamaps-discovery-draft");
    initializeProviders(library);
    return defaultRegistryFactory(LegacyAdapterRegistry);
  }

  const api = {
    LegacyAdapterRegistry,
    createDefaultLegacyAdapterRegistry() {
      if (!defaultRegistryFactory)
        throw new Error(
          "Load the Patamaps discovery package before requesting built-in adapters",
        );
      return defaultRegistryFactory(LegacyAdapterRegistry);
    },
    assembleLegacyWorkspace(
      config,
      adapters,
      configuredPacks,
      relationRegistry,
      options = {},
    ) {
      const input = {
        config,
        adapters,
        configuredPacks,
        registry: legacyRegistryGraphSnapshot(relationRegistry),
        options: {
          ...(options.portablePackUris === undefined
            ? {}
            : { portablePackUris: options.portablePackUris }),
        },
      };
      return restore(call("assemble", input), input);
    },
    makeLegacyWorkspaceSnapshot(graph, adapters, configDigest) {
      const input = { graph, adapters, configDigest };
      return restore(call("snapshot", input), input);
    },
    legacyWorkspaceHasErrors(discovery) {
      return call("has-errors", { discovery });
    },
    async discoverLegacyWorkspace(loaded, options = {}) {
      const adapterRegistry =
        options.adapterRegistry ?? (await defaultRegistry());
      const relationRegistry = options.relationRegistry ?? new Registry();
      const configuredPacks = await configure(loaded, relationRegistry);
      const context = {
        namespace: loaded.config.namespace,
        repository: loaded.config.repository,
        repositoryRoot: loaded.repositoryRoot,
      };
      const cacheDirectory = path(
        loaded,
        loaded.config.outputs.cache ?? ".cache/metamap",
      );
      const sources = await Promise.all(
        loaded.config.sources.map(async (config) => {
          const adapter = adapterRegistry.require(config.adapter);
          const inputs = await adapter.fingerprint(config, context);
          const { key, filename } = call("cache-key", {
            adapter: adapter.id,
            adapterVersion: adapter.version,
            config,
            inputs,
          });
          const cachePath = call("resolve", {
            root: cacheDirectory,
            path: filename,
          });
          if (options.useCache ?? true) {
            const cached = await read(cachePath);
            const hit = call("cache-check", {
              key,
              ...(cached === undefined ? {} : { cached }),
            });
            if (hit.hit) return { result: hit.result, cacheHit: true };
          }
          const result = await adapter.discover(config, context);
          if (options.writeCache ?? true) {
            const content = call("cache-entry", { key, result });
            await io("write-file", { path: cachePath, content });
          }
          return { result, cacheHit: false };
        }),
      );
      const adapters = sources.map((entry) => entry.result);
      const cacheHits = sources
        .filter((entry) => entry.cacheHit)
        .map((entry) => entry.result.sourceId);
      return {
        ...api.assembleLegacyWorkspace(
          loaded.config,
          adapters,
          configuredPacks,
          relationRegistry,
          { portablePackUris: options.portablePackUris },
        ),
        cacheHits,
      };
    },
    async checkLegacyWorkspace(loaded, options = {}) {
      const current = await api.discoverLegacyWorkspace(loaded, options);
      const baselineValue = await read(
        path(loaded, loaded.config.outputs.graph),
      );
      const relationRegistry = options.relationRegistry ?? new Registry();
      await configure(loaded, relationRegistry);
      const response = call("check", {
        current,
        config: loaded.config,
        registry: legacyRegistryGraphSnapshot(relationRegistry),
        ...(baselineValue === undefined ? {} : { baseline: baselineValue }),
      });
      current.driftIssues.push(
        ...response.value.driftIssues.slice(current.driftIssues.length),
      );
      return {
        ...current,
        baseline: response.baselinePresent ? baselineValue : undefined,
        diff: response.value.diff,
        baselineSeverity: response.value.baselineSeverity,
      };
    },
    async writeLegacyWorkspaceOutputs(loaded, discovery) {
      const outputs = call("outputs", { config: loaded.config, discovery });
      await Promise.all(
        ["graph", "snapshot", "report", "documentation"].map((field) =>
          io("write-file", {
            path: path(loaded, loaded.config.outputs[field]),
            content: outputs[field],
          }),
        ),
      );
    },
  };
  // The existing loader belongs to the owning factory and is bound afterwards.
  return api;
}
