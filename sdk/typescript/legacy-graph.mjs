import { legacyRegistryGraphSnapshot } from "./legacy-registry.mjs";
import { marshalJson } from "./canonical.mjs";

const constraintGraphs = new WeakMap();
/** @internal Fixed graph indexes with live caller objects for constraint calls. */
export const legacyConstraintGraphSnapshot = (graph) =>
  constraintGraphs.get(graph)?.();
export const bindLegacyConstraintGraphSnapshot = (wrapper, graph) =>
  constraintGraphs.set(wrapper, () => legacyConstraintGraphSnapshot(graph));

// A declared optional undefined property is absent to the original schema.
// Preserve the caller's object/property; omit only known optional fields in the
// JSON snapshot. Undefined metadata, unknown fields and mandatory fields still
// reach the strict marshaller and are refused rather than silently discarded.
const fields = (object, optional, children = {}) => {
  if (object === null || typeof object !== "object" || Array.isArray(object))
    return object;
  const descriptors = Object.getOwnPropertyDescriptors(object);
  const retained = [];
  for (const key of Reflect.ownKeys(descriptors)) {
    const descriptor = descriptors[key];
    if (Object.hasOwn(descriptor, "value")) {
      if (descriptor.value === undefined && optional.includes(key)) continue;
      if (Object.hasOwn(children, key))
        descriptor.value = children[key](descriptor.value);
    }
    retained.push([key, descriptor]);
  }
  return Object.create(
    Object.getPrototypeOf(object),
    Object.fromEntries(retained),
  );
};
const array = (project) => (value) => {
  if (!Array.isArray(value)) return value;
  const descriptors = Object.getOwnPropertyDescriptors(value);
  for (let index = 0; index < value.length; index++) {
    const descriptor = descriptors[index];
    if (descriptor && Object.hasOwn(descriptor, "value"))
      descriptor.value = project(descriptor.value);
  }
  return Object.defineProperties([], descriptors);
};
const provenance = (value) =>
  fields(value, ["observedAt", "sourceRevision", "confidence"]);
const locator = (value) => fields(value, ["mediaType", "revision", "digest"]);
const entity = (value) =>
  fields(value, ["label", "schema", "locators", "attributes", "provenance"], {
    locators: array(locator),
    provenance,
  });
const mapping = (value) =>
  fields(value, ["transform", "invariants", "attributes"], {
    provenance,
    transform: (v) =>
      fields(v, ["entrypoint", "deterministic", "reversible", "configuration"]),
  });
const authority = (value) => fields(value, ["delegatedFrom"], { provenance });
const objects = (value) =>
  fields(value, [], {
    entities: array(entity),
    mappings: array(mapping),
    authorities: array(authority),
  });
const document = (value) =>
  fields(
    value,
    ["$schema", "label", "revision", "relationPacks", "metadata", "extensions"],
    {
      entities: array(entity),
      mappings: array(mapping),
      authorities: array(authority),
      relationPacks: array((v) => fields(v, ["uri", "digest"])),
    },
  );

/** @internal JSON representation of typed optional fields, not an admission. */
export const marshalLegacyGraphDocument = (value) =>
  marshalJson(document(value));

export const marshalLegacyGraphRequest = (request) => {
  const snapshot = fields(request, [], {
    document,
    objects,
    options: (value) =>
      fields(value, ["direction", "relations", "maxDepth"], {
        maxDepth: (depth) =>
          typeof depth === "number" && !Number.isFinite(depth) ? null : depth,
      }),
  });
  // Describe the caller's numeric value without putting NaN/Infinity in JSON.
  // Rust still decides when it is invalid, including the missing-start order.
  const depth =
    request.options && typeof request.options === "object"
      ? Object.getOwnPropertyDescriptor(request.options, "maxDepth")
      : undefined;
  if (
    depth &&
    Object.hasOwn(depth, "value") &&
    typeof depth.value === "number" &&
    !Number.isFinite(depth.value)
  ) {
    Object.defineProperty(snapshot, "nonFiniteMaxDepth", {
      value: true,
      enumerable: true,
    });
  }
  return marshalJson(snapshot);
};

export class LegacyGraphValidationError extends Error {
  constructor(issues) {
    super(
      `Metamap validation failed with ${issues.filter((issue) => issue.severity === "error").length} error(s)`,
    );
    this.issues = issues;
    this.name = "MetamapValidationError";
  }
}

/** @internal Native decisions select retained host objects; no JS traversal or
 * authority policy is implemented here. Observations authorize no transaction. */
export function createLegacyGraphClass(invoke, Registry) {
  return class LegacyGraph {
    #index;
    #entities;
    #mappings;
    #authorities;
    constructor(document, options = {}) {
      this.document = document;
      this.registry = options.registry ?? new Registry();
      const report = invoke("graph", "json", {
        operation: "build",
        document,
        registry: legacyRegistryGraphSnapshot(this.registry),
        allowInvalid: options.validate === false,
      });
      this.validationIssues = report.validation.issues;
      if (options.validate !== false && !report.validation.valid)
        throw new LegacyGraphValidationError(this.validationIssues);
      this.#index = report.index;
      this.#entities = [...document.entities];
      this.#mappings = [...document.mappings];
      this.#authorities = [...document.authorities];
      constraintGraphs.set(this, () => ({
        index: this.#index,
        objects: {
          entities: this.#entities,
          mappings: this.#mappings,
          authorities: this.#authorities,
        },
      }));
    }
    static from(value, options = {}) {
      const registry = options.registry ?? new Registry();
      const report = invoke("graph", "json", {
        operation: "build",
        document: value,
        registry: legacyRegistryGraphSnapshot(registry),
      });
      if (!report.validation.valid)
        throw new LegacyGraphValidationError(report.validation.issues);
      return new LegacyGraph(value, { ...options, registry, validate: false });
    }
    #query(operation, id, options = {}, fact) {
      return invoke("graph", "json", {
        operation,
        id,
        ...(fact === undefined ? {} : { fact }),
        options,
        index: this.#index,
        registry: legacyRegistryGraphSnapshot(this.registry),
        objects: {
          entities: this.#entities,
          mappings: this.#mappings,
          authorities: this.#authorities,
        },
      });
    }
    getEntity(id) {
      const index = this.#query("get-entity", id);
      return index === null ? undefined : this.#entities[index];
    }
    getMapping(id) {
      const index = this.#query("get-mapping", id);
      return index === null ? undefined : this.#mappings[index];
    }
    mappingsFor(id, options = {}) {
      return this.#query("mappings-for", id, options).map(
        (index) => this.#mappings[index],
      );
    }
    neighbors(id, options = {}) {
      return this.#query("neighbors", id, options).map(
        ({ entity, mapping }) => ({
          entity: this.#entities[entity],
          mapping: this.#mappings[mapping],
        }),
      );
    }
    trace(id, options = {}) {
      return this.#query("trace", id, options).map(
        ({ entity, viaMapping, ...rest }) => ({
          entity: this.#entities[entity],
          ...rest,
          ...(viaMapping === undefined
            ? {}
            : { viaMapping: this.#mappings[viaMapping] }),
        }),
      );
    }
    resolveAuthority(concept, fact) {
      const { canonical, effective, delegationChain, candidates, ...rest } =
        this.#query("resolve-authority", concept, {}, fact);
      return {
        ...rest,
        ...(canonical === undefined
          ? {}
          : { canonical: this.#authorities[canonical] }),
        ...(effective === undefined
          ? {}
          : { effective: this.#authorities[effective] }),
        ...(delegationChain === undefined
          ? {}
          : {
              delegationChain: delegationChain.map(
                (index) => this.#authorities[index],
              ),
            }),
        candidates: candidates.map((index) => this.#authorities[index]),
      };
    }
  };
}
