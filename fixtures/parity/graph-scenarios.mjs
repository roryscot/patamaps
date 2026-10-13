/** Shared inputs only. Expected observations are frozen from the pinned original. */
const entity = (id) => ({ id, kind: "field" });
const mapping = (id, sources, targets, relation = "test:r") => ({
  id,
  relation,
  sources,
  targets,
  cardinality: "many-to-many",
  lossiness: "lossless",
  provenance: { status: "declared", assertedBy: "human:test" },
});
const authority = (id, mode, facts = ["type"], patch = {}) => ({
  id,
  concept: "urn:e:a",
  source: "urn:e:b",
  facts,
  mode,
  provenance: { status: "declared", assertedBy: "human:test" },
  ...patch,
});
const pack = (symmetric = false) => ({
  schemaVersion: "1.0.0",
  id: "urn:pack:graph-test",
  version: "1",
  relations: [{ id: "test:r", cyclePolicy: "allow", symmetric }],
});
const document = () => ({
  schemaVersion: "2.0.0",
  id: "urn:graph:test",
  namespace: "test",
  entities: ["a", "b", "c", "d"].map((id) => entity(`urn:e:${id}`)),
  mappings: [
    mapping("urn:m:z", ["urn:e:a"], ["urn:e:c", "urn:e:b"]),
    mapping("urn:m:a", ["urn:e:b"], ["urn:e:d"]),
  ],
  authorities: [],
});
const setup = (api, mutate = () => {}, options = {}, symmetric = false) => {
  const d = document(),
    p = pack(symmetric),
    r = new api.RelationRegistry([p]);
  mutate(d, p);
  const g = new api.MetamapGraph(d, { registry: r, ...options });
  return { d, p, r, g };
};
const visits = (g, options) =>
  g
    .trace("urn:e:a", options)
    .map((v) => [
      v.entity.id,
      v.depth,
      v.viaMapping?.id ?? null,
      v.predecessor ?? null,
    ]);
const neighbors = (g, id = "urn:e:a", options) =>
  g.neighbors(id, options).map((v) => [v.entity.id, v.mapping.id]);
const failure = (fn, api) => {
  try {
    fn();
    return null;
  } catch (error) {
    return {
      name: error.name,
      message: error.message,
      typeError: error instanceof TypeError,
      validationError: error instanceof api.MetamapValidationError,
      ...(error.issues ? { issues: error.issues } : {}),
    };
  }
};
export const scenarios = [
  [
    "constructor identities and valid issues",
    (api) => {
      const { g, d, r } = setup(api);
      return [g.document === d, g.registry === r, g.validationIssues];
    },
  ],
  [
    "from retains document and registry",
    (api) => {
      const { d, r } = setup(api);
      const g = api.MetamapGraph.from(d, { registry: r });
      return [
        g.document === d,
        g.registry === r,
        g.getEntity(d.entities[0].id) === d.entities[0],
      ];
    },
  ],
  [
    "entity and mapping lookup identity",
    (api) => {
      const { g, d } = setup(api);
      return [
        g.getEntity("urn:e:a") === d.entities[0],
        g.getMapping("urn:m:z") === d.mappings[0],
        g.getEntity("absent") === undefined,
        g.getMapping("absent") === undefined,
      ];
    },
  ],
  [
    "mapping bucket order and fresh arrays",
    (api) => {
      const { g, d } = setup(api);
      const a = g.mappingsFor("urn:e:b");
      const identity = a[0] === d.mappings[0] && a[1] === d.mappings[1];
      a.length = 0;
      return [
        identity,
        g.mappingsFor("urn:e:b").map((m) => m.id),
        a !== g.mappingsFor("urn:e:b"),
      ];
    },
  ],
  ...["both", "outgoing", "incoming"].map((direction) => [
    `mapping ${direction} direction`,
    (api) =>
      setup(api)
        .g.mappingsFor("urn:e:b", { direction })
        .map((m) => m.id),
  ]),
  [
    "explicit empty relation filter",
    (api) => {
      const { g } = setup(api);
      return [
        g.mappingsFor("urn:e:a", { relations: [] }),
        g.neighbors("urn:e:a", { relations: [] }),
        visits(g, { relations: [], maxDepth: 5 }),
      ];
    },
  ],
  [
    "relation inclusion filter",
    (api) => {
      const { g } = setup(api);
      return [
        neighbors(g, "urn:e:b", { relations: ["test:r"] }),
        neighbors(g, "urn:e:b", { relations: ["test:other"] }),
      ];
    },
  ],
  ["nary neighbor insertion order", (api) => neighbors(setup(api).g)],
  [
    "neighbor object identities",
    (api) => {
      const { g, d } = setup(api);
      const n = g.neighbors("urn:e:a");
      return [
        n[0].entity === d.entities[2],
        n[1].entity === d.entities[1],
        n[0].mapping === d.mappings[0],
        n[0] !== g.neighbors("urn:e:a")[0],
      ];
    },
  ],
  ...["both", "outgoing", "incoming"].map((direction) => [
    `symmetric ${direction} direction`,
    (api) =>
      neighbors(setup(api, () => {}, {}, true).g, "urn:e:b", { direction }),
  ]),
  [
    "self duplicate endpoints deduplicated",
    (api) => {
      const { g } = setup(
        api,
        (d) => {
          d.mappings = [
            mapping(
              "urn:m:self",
              ["urn:e:a", "urn:e:a"],
              ["urn:e:a", "urn:e:b", "urn:e:b"],
            ),
          ];
        },
        { validate: false },
      );
      return [g.mappingsFor("urn:e:a").length, neighbors(g)];
    },
  ],
  [
    "duplicate mapping keys replace neighbor value in first slot",
    (api) => {
      const { g, d } = setup(
        api,
        (d) => {
          d.mappings = [
            mapping("urn:m:same", ["urn:e:a"], ["urn:e:b", "urn:e:c"]),
            mapping("urn:m:same", ["urn:e:a"], ["urn:e:b"]),
          ];
        },
        { validate: false },
      );
      const n = g.neighbors("urn:e:a");
      return [
        neighbors(g),
        n[0].mapping === d.mappings[1],
        g.getMapping("urn:m:same") === d.mappings[1],
      ];
    },
  ],
  [
    "unknown endpoint skipped",
    (api) =>
      neighbors(
        setup(api, (d) => d.mappings[0].targets.push("urn:e:missing"), {
          validate: false,
        }).g,
      ),
  ],
  ["breadth first default depth", (api) => visits(setup(api).g)],
  [
    "breadth first insertion order and depth",
    (api) => visits(setup(api).g, { maxDepth: 3, direction: "outgoing" }),
  ],
  ["zero depth", (api) => visits(setup(api).g, { maxDepth: 0 })],
  [
    "trace identities",
    (api) => {
      const { g, d } = setup(api);
      const v = g.trace("urn:e:a", { maxDepth: 3 });
      return [
        v[0].entity === d.entities[0],
        !("viaMapping" in v[0]),
        v[1].viaMapping === d.mappings[0],
        v[3].predecessor,
      ];
    },
  ],
  ...[-1, 0.5, "2"].map((depth) => [
    `invalid depth ${depth}`,
    (api) =>
      failure(() => setup(api).g.trace("urn:e:a", { maxDepth: depth }), api),
  ]),
  [
    "absent trace start precedes invalid depth",
    (api) => setup(api).g.trace("absent", { maxDepth: -1 }),
  ],
  [
    "depth beyond native checked graph limit",
    (api) => {
      const { g } = setup(api, (d) => {
        d.entities = Array.from({ length: 71 }, (_, i) => entity(`urn:e:${i}`));
        d.mappings = d.entities
          .slice(1)
          .map((e, i) => mapping(`urn:m:${i}`, [d.entities[i].id], [e.id]));
      });
      const v = g.trace("urn:e:0", { maxDepth: 70, direction: "outgoing" });
      return [v.length, v.at(-1).depth, v.at(-1).entity.id];
    },
  ],
  [
    "large integer depth terminates on visited set",
    (api) => visits(setup(api).g, { maxDepth: 1e30 }),
  ],
  [
    "entity mutation retains original key",
    (api) => {
      const { g, d } = setup(api);
      d.entities[0].id = "urn:e:renamed";
      return [
        g.getEntity("urn:e:a") === d.entities[0],
        g.getEntity("urn:e:renamed") === undefined,
        visits(g, { maxDepth: 3 }),
      ];
    },
  ],
  [
    "document array replacement preserves indexed objects",
    (api) => {
      const { g, d } = setup(api);
      const e = d.entities[0],
        m = d.mappings[0];
      d.entities = [entity("urn:e:new")];
      d.mappings = [];
      return [
        g.document === d,
        g.getEntity("urn:e:a") === e,
        g.getMapping("urn:m:z") === m,
        neighbors(g),
      ];
    },
  ],
  [
    "mapping mutation changes filtering without reindexing",
    (api) => {
      const { g, d } = setup(api);
      d.mappings[0].id = "urn:m:changed";
      d.mappings[0].sources = ["urn:e:d"];
      return [
        g.getMapping("urn:m:z") === d.mappings[0],
        g.getMapping("urn:m:changed") === undefined,
        g.mappingsFor("urn:e:a", { direction: "outgoing" }).length,
        g.mappingsFor("urn:e:d").map((m) => m.id),
        neighbors(g, "urn:e:c"),
      ];
    },
  ],
  [
    "live relation symmetry mutation",
    (api) => {
      const { g, p } = setup(api);
      const before = neighbors(g, "urn:e:b", { direction: "outgoing" });
      p.relations[0].symmetric = true;
      return [before, neighbors(g, "urn:e:b", { direction: "outgoing" })];
    },
  ],
  [
    "unresolved authority",
    (api) => setup(api).g.resolveAuthority("urn:e:a", "type"),
  ],
  [
    "canonical identity and wildcard facts",
    (api) => {
      const { g, d } = setup(
        api,
        (d) => (d.authorities = [authority("urn:auth:a", "canonical", ["*"])]),
      );
      const r = g.resolveAuthority("urn:e:a", "any");
      return [
        r,
        r.canonical === d.authorities[0],
        r.effective === r.canonical,
        r.delegationChain[0] === r.canonical,
      ];
    },
  ],
  [
    "delegation chain and candidates",
    (api) => {
      const { g, d } = setup(
        api,
        (d) =>
          (d.authorities = [
            authority("urn:auth:a", "canonical"),
            authority("urn:auth:c", "candidate"),
            authority("urn:auth:b", "delegated", ["type"], {
              delegatedFrom: "urn:auth:a",
            }),
          ]),
      );
      const r = g.resolveAuthority("urn:e:a", "type");
      return [
        r,
        r.effective === d.authorities[2],
        r.candidates[0] === d.authorities[1],
      ];
    },
  ],
  [
    "fact filtered delegation",
    (api) =>
      setup(
        api,
        (d) =>
          (d.authorities = [
            authority("urn:auth:a", "canonical"),
            authority("urn:auth:b", "delegated", ["other"], {
              delegatedFrom: "urn:auth:a",
            }),
          ]),
      ).g.resolveAuthority("urn:e:a", "type"),
  ],
  [
    "ambiguous canonical preserves grouped order",
    (api) =>
      setup(
        api,
        (d) =>
          (d.authorities = [
            authority("urn:auth:c", "candidate"),
            authority("urn:auth:b", "canonical"),
            authority("urn:auth:d", "delegated", ["type"], {
              delegatedFrom: "urn:auth:b",
            }),
            authority("urn:auth:a", "canonical"),
          ]),
        { validate: false },
      ).g.resolveAuthority("urn:e:a", "type"),
  ],
  [
    "candidate alone ambiguous",
    (api) =>
      setup(
        api,
        (d) => (d.authorities = [authority("urn:auth:c", "candidate")]),
      ).g.resolveAuthority("urn:e:a", "type"),
  ],
  [
    "multiple delegation children ambiguous",
    (api) =>
      setup(
        api,
        (d) =>
          (d.authorities = [
            authority("urn:auth:a", "canonical"),
            authority("urn:auth:b", "delegated", ["type"], {
              delegatedFrom: "urn:auth:a",
            }),
            authority("urn:auth:c", "delegated", ["type"], {
              delegatedFrom: "urn:auth:a",
            }),
          ]),
        { validate: false },
      ).g.resolveAuthority("urn:e:a", "type"),
  ],
  [
    "mutated delegation cycle terminates ambiguous",
    (api) => {
      const { g, d } = setup(
        api,
        (d) =>
          (d.authorities = [
            authority("urn:auth:a", "canonical"),
            authority("urn:auth:b", "delegated", ["type"], {
              delegatedFrom: "urn:auth:a",
            }),
          ]),
      );
      d.authorities[1].id = "urn:auth:a";
      return g.resolveAuthority("urn:e:a", "type");
    },
  ],
  [
    "delegation mode and parent mutations retain buckets",
    (api) => {
      const { g, d } = setup(
        api,
        (d) =>
          (d.authorities = [
            authority("urn:auth:a", "canonical"),
            authority("urn:auth:b", "delegated", ["type"], {
              delegatedFrom: "urn:auth:a",
            }),
          ]),
      );
      d.authorities[1].mode = "candidate";
      delete d.authorities[1].delegatedFrom;
      return g.resolveAuthority("urn:e:a", "type");
    },
  ],
  [
    "authority concept mutation retains bucket",
    (api) => {
      const { g, d } = setup(
        api,
        (d) => (d.authorities = [authority("urn:auth:a", "canonical")]),
      );
      d.authorities[0].concept = "urn:e:c";
      d.authorities = [];
      return [
        g.resolveAuthority("urn:e:a", "type"),
        g.resolveAuthority("urn:e:c", "type"),
      ];
    },
  ],
  [
    "constructor validation error issues",
    (api) =>
      failure(
        () => setup(api, (d) => d.mappings[0].targets.push("urn:e:missing")),
        api,
      ),
  ],
  [
    "from refuses invalid despite validate false",
    (api) => {
      const { d, r } = setup(api);
      d.mappings[0].targets.push("urn:e:missing");
      return failure(
        () => api.MetamapGraph.from(d, { registry: r, validate: false }),
        api,
      );
    },
  ],
  [
    "validate false retains validation issues",
    (api) => {
      const { g } = setup(
        api,
        (d) => d.mappings[0].targets.push("urn:e:missing"),
        { validate: false },
      );
      return [g.validationIssues, neighbors(g)];
    },
  ],
  [
    "duplicate entities choose last retained identity",
    (api) => {
      const { g, d } = setup(api, (d) => d.entities.push(entity("urn:e:a")), {
        validate: false,
      });
      return [g.getEntity("urn:e:a") === d.entities.at(-1), visits(g)];
    },
  ],
];
