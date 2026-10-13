import { marshalLegacyPackJson } from "./canonical.mjs";

const graphSnapshots = new WeakMap();
/** @internal Retained registration keys and only graph-observable fields. */
export function legacyRegistryGraphSnapshot(registry, extraFields = []) {
  const snapshot = graphSnapshots.get(registry);
  if (!snapshot)
    throw new TypeError("Expected a Patamaps legacy relation registry");
  return snapshot(extraFields);
}
export function bindLegacyRegistryGraphSnapshot(wrapper, registry) {
  graphSnapshots.set(wrapper, (extraFields) =>
    legacyRegistryGraphSnapshot(registry, extraFields),
  );
}

/** @internal Host identity handles only. Every decision executes in Rust. */
export function createLegacyRegistryClass(invoke, corePack) {
  return class LegacyRelationRegistry {
    #packs = [];
    #definitions = [];
    #laws = [];

    constructor(packs = [corePack()]) {
      graphSnapshots.set(this, (extraFields = []) => ({
        packs: this.#packs.map(({ key, value }) => ({
          key,
          ...(value.version === undefined ? {} : { version: value.version }),
        })),
        definitions: this.#definitions.map(({ key, value }) => ({
          key,
          value: Object.fromEntries(
            [
              "id",
              "cyclePolicy",
              "sourceKinds",
              "targetKinds",
              "cardinalities",
              "symmetric",
              ...extraFields,
            ]
              .filter((field) => value[field] !== undefined)
              .map((field) => [field, value[field]]),
          ),
        })),
      }));
      for (const pack of packs) this.registerPack(pack);
    }

    #request(action) {
      const full = ["register", "get-law"].includes(action.operation);
      const state = {
        packs: this.#packs.map(({ key, value }) => ({
          key,
          json: full
            ? marshalLegacyPackJson(value)
            : marshalLegacyPackJson(
                action.operation === "has-pack"
                  ? value.version === undefined
                    ? {}
                    : { version: value.version }
                  : action.operation === "executable-packs"
                    ? { schemaVersion: value.schemaVersion }
                    : {},
              ),
        })),
        definitions: this.#definitions.map(({ key }) => key),
        laws: this.#laws.map(({ id, pack, index }) => ({ id, pack, index })),
      };
      return invoke("registry", "json", { state, action });
    }

    registerPack(value) {
      const raw = marshalLegacyPackJson(value);
      const result = this.#request({ operation: "register", json: raw });
      if (!result.inserted) return;
      if (result.executable) {
        value = JSON.parse(raw);
        const pending = [value];
        while (pending.length) {
          const item = pending.pop();
          if (item !== null && typeof item === "object") {
            pending.push(...Object.values(item));
            Object.freeze(item);
          }
        }
      }
      // Commit retained references only after all native checks succeed.
      this.#packs.push({ key: result.packId, value });
      result.relationIds.forEach((key, index) => {
        this.#definitions.push({ key, value: value.relations[index] });
      });
      result.lawIds.forEach((id, index) => {
        this.#laws.push({ id, pack: result.packId, index });
      });
    }

    getPack(id) {
      const index = this.#request({ operation: "get-pack", id });
      return index === null ? undefined : this.#packs[index].value;
    }
    get(id) {
      const index = this.#request({ operation: "get", id });
      return index === null ? undefined : this.#definitions[index].value;
    }
    hasPack(id, version) {
      return this.#request({
        operation: "has-pack",
        id,
        ...(version === undefined ? {} : { version }),
      });
    }
    getLaw(id) {
      const result = this.#request({ operation: "get-law", id });
      if (result === null) return undefined;
      const pack = this.#packs[result.pack].value;
      return { pack, law: pack.laws[result.law] };
    }
    all() {
      return this.#request({ operation: "all" }).map(
        (index) => this.#definitions[index].value,
      );
    }
    allPacks() {
      return this.#request({ operation: "all-packs" }).map(
        (index) => this.#packs[index].value,
      );
    }
    executablePacks() {
      return this.#request({ operation: "executable-packs" }).map(
        (index) => this.#packs[index].value,
      );
    }
  };
}
