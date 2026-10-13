/** Shared inputs; the runner freezes original outcomes before observing Rust. */
const entity = (id = "urn:e:a", patch = {}) => ({
  id,
  kind: "field",
  ...patch,
});
const mapping = (id = "urn:m:a", patch = {}) => ({
  id,
  relation: "core:references",
  sources: ["urn:e:a"],
  targets: ["urn:e:b"],
  cardinality: "one-to-one",
  lossiness: "lossless",
  provenance: { status: "declared", assertedBy: "test" },
  ...patch,
});
const authority = (id = "urn:auth:a", patch = {}) => ({
  id,
  concept: "urn:e:a",
  source: "urn:e:b",
  mode: "canonical",
  facts: ["type"],
  provenance: { status: "declared", assertedBy: "test" },
  ...patch,
});
const pack = (id = "urn:pack:a", patch = {}) => ({
  id,
  version: "1",
  ...patch,
});
const shard = (id = "urn:shard:a", patch = {}) => ({
  schemaVersion: "2.0.0",
  id,
  namespace: "input",
  entities: [entity()],
  mappings: [],
  authorities: [],
  ...patch,
});
const options = { id: "urn:graph:composed", namespace: "output" };
const compose = (api, docs, opts = options) =>
  api.composeMetamapDocuments(docs, opts);
const failure = (api, fn) => {
  try {
    fn();
    return null;
  } catch (error) {
    return {
      name: error.name,
      message: error.message,
      identifier: error.identifier,
      hasIdentifier: Object.hasOwn(error, "identifier"),
      compositionError: error instanceof api.MetamapCompositionError,
      typeError: error instanceof TypeError,
    };
  }
};
export const scenarios = [
  ["empty shard list", (api) => failure(api, () => compose(api, []))],
  [
    "single shard header and metadata",
    (api) =>
      compose(
        api,
        [
          shard("urn:shard:a", {
            label: "ignored",
            revision: "input",
            metadata: { input: true },
            extensions: { unused: 1 },
          }),
        ],
        { ...options, label: "output label", revision: "output revision" },
      ),
  ],
  [
    "omitted option fields remain own undefined properties",
    (api) => {
      const c = compose(api, [shard()]);
      return [
        Object.keys(c),
        Object.hasOwn(c, "label"),
        Object.hasOwn(c, "revision"),
        c.label === undefined,
        c.revision === undefined,
      ];
    },
  ],
  [
    "first object identities and fresh arrays",
    (api) => {
      const d = shard("urn:shard:a", {
        mappings: [mapping()],
        authorities: [authority()],
        relationPacks: [pack()],
      });
      const c = compose(api, [d]);
      return [
        c.entities[0] === d.entities[0],
        c.mappings[0] === d.mappings[0],
        c.authorities[0] === d.authorities[0],
        c.relationPacks[0] === d.relationPacks[0],
        c.entities !== d.entities,
        c.mappings !== d.mappings,
        c.authorities !== d.authorities,
        c !== d,
      ];
    },
  ],
  [
    "first equal object retained",
    (api) => {
      const a = shard(),
        b = shard("urn:shard:b");
      const c = compose(api, [a, b]);
      return [
        c.entities.length,
        c.entities[0] === a.entities[0],
        c.entities[0] === b.entities[0],
        c.metadata,
      ];
    },
  ],
  [
    "entity insertion order",
    (api) =>
      compose(api, [
        shard("urn:shard:z", {
          entities: [entity("urn:e:z"), entity("urn:e:a")],
        }),
        shard("urn:shard:a", {
          entities: [entity("urn:e:a"), entity("urn:e:c")],
        }),
      ]).entities.map((e) => e.id),
  ],
  [
    "mapping and authority insertion order",
    (api) => {
      const c = compose(api, [
        shard("urn:shard:z", {
          mappings: [mapping("urn:m:z"), mapping()],
          authorities: [authority("urn:auth:z")],
        }),
        shard("urn:shard:a", {
          mappings: [mapping(), mapping("urn:m:c")],
          authorities: [authority(), authority("urn:auth:z")],
        }),
      ]);
      return [c.mappings.map((m) => m.id), c.authorities.map((a) => a.id)];
    },
  ],
  [
    "relation pack insertion order and first identity",
    (api) => {
      const a = shard("urn:shard:a", {
          relationPacks: [pack("urn:pack:z"), pack()],
        }),
        b = shard("urn:shard:b", {
          relationPacks: [pack(), pack("urn:pack:b")],
        });
      const c = compose(api, [a, b]);
      return [
        c.relationPacks.map((p) => p.id),
        c.relationPacks[1] === a.relationPacks[1],
      ];
    },
  ],
  [
    "missing or null relation packs",
    (api) =>
      compose(api, [shard(), shard("urn:shard:b", { relationPacks: null })])
        .relationPacks,
  ],
  [
    "duplicate shard IDs",
    (api) => failure(api, () => compose(api, [shard(), shard()])),
  ],
  [
    "unsupported schema before duplicate ID",
    (api) =>
      failure(api, () =>
        compose(api, [shard(), shard("urn:shard:a", { schemaVersion: "9" })]),
      ),
  ],
  [
    "all shard IDs checked before entity merge",
    (api) =>
      failure(api, () =>
        compose(api, [
          shard("urn:shard:a", {
            entities: [entity("urn:e:a", { label: "first" })],
          }),
          shard("urn:shard:b", {
            entities: [entity("urn:e:a", { label: "conflict" })],
          }),
          shard("urn:shard:a"),
        ]),
      ),
  ],
  [
    "unsupported schema diagnostic",
    (api) =>
      failure(api, () =>
        compose(api, [shard("urn:shard:a", { schemaVersion: "1.0.0" })]),
      ),
  ],
  [
    "entity conflict",
    (api) =>
      failure(api, () =>
        compose(api, [
          shard(),
          shard("urn:shard:b", {
            entities: [entity("urn:e:a", { label: "different" })],
          }),
        ]),
      ),
  ],
  [
    "mapping conflict",
    (api) =>
      failure(api, () =>
        compose(api, [
          shard("urn:shard:a", { mappings: [mapping()] }),
          shard("urn:shard:b", {
            mappings: [mapping("urn:m:a", { lossiness: "lossy" })],
          }),
        ]),
      ),
  ],
  [
    "authority conflict",
    (api) =>
      failure(api, () =>
        compose(api, [
          shard("urn:shard:a", { authorities: [authority()] }),
          shard("urn:shard:b", {
            authorities: [authority("urn:auth:a", { facts: ["other"] })],
          }),
        ]),
      ),
  ],
  [
    "relation version conflict",
    (api) =>
      failure(api, () =>
        compose(api, [
          shard("urn:shard:a", { relationPacks: [pack()] }),
          shard("urn:shard:b", {
            relationPacks: [pack("urn:pack:a", { version: "2" })],
          }),
        ]),
      ),
  ],
  [
    "relation reference conflict",
    (api) =>
      failure(api, () =>
        compose(api, [
          shard("urn:shard:a", {
            relationPacks: [pack("urn:pack:a", { digest: "first" })],
          }),
          shard("urn:shard:b", {
            relationPacks: [pack("urn:pack:a", { digest: "second" })],
          }),
        ]),
      ),
  ],
  [
    "pack version conflict before reference conflict",
    (api) =>
      failure(api, () =>
        compose(api, [
          shard("urn:shard:a", {
            relationPacks: [pack("urn:pack:a", { digest: "first" })],
          }),
          shard("urn:shard:b", {
            relationPacks: [
              pack("urn:pack:a", { version: "2", digest: "second" }),
            ],
          }),
        ]),
      ),
  ],
  [
    "pack conflict precedes entity conflict",
    (api) =>
      failure(api, () =>
        compose(api, [
          shard("urn:shard:a", { relationPacks: [pack()] }),
          shard("urn:shard:b", {
            entities: [entity("urn:e:a", { label: "different" })],
            relationPacks: [pack("urn:pack:a", { version: "2" })],
          }),
        ]),
      ),
  ],
  [
    "entity conflict precedes mapping and authority conflicts",
    (api) =>
      failure(api, () =>
        compose(api, [
          shard("urn:shard:a", {
            mappings: [mapping()],
            authorities: [authority()],
          }),
          shard("urn:shard:b", {
            entities: [entity("urn:e:a", { label: "different" })],
            mappings: [mapping("urn:m:a", { lossiness: "lossy" })],
            authorities: [authority("urn:auth:a", { facts: ["other"] })],
          }),
        ]),
      ),
  ],
  [
    "same document duplicate equal entities",
    (api) => {
      const d = shard();
      d.entities.push(entity());
      const c = compose(api, [d]);
      return [c.entities.length, c.entities[0] === d.entities[0]];
    },
  ],
  [
    "same document duplicate conflicting entities",
    (api) =>
      failure(api, () =>
        compose(api, [
          shard("urn:shard:a", {
            entities: [entity(), entity("urn:e:a", { label: "conflict" })],
          }),
        ]),
      ),
  ],
  [
    "deep reordered member equivalence",
    (api) => {
      const a = shard("urn:shard:a", {
          entities: [
            entity("urn:e:a", {
              attributes: { z: [{ b: 2, a: 1 }], a: { y: 2, x: 1 } },
            }),
          ],
        }),
        b = shard("urn:shard:b", {
          entities: [
            {
              attributes: { a: { x: 1, y: 2 }, z: [{ a: 1, b: 2 }] },
              kind: "field",
              id: "urn:e:a",
            },
          ],
        });
      const c = compose(api, [a, b]);
      return [c.entities.length, c.entities[0] === a.entities[0]];
    },
  ],
  [
    "array order remains significant",
    (api) =>
      failure(api, () =>
        compose(api, [
          shard("urn:shard:a", {
            entities: [entity("urn:e:a", { attributes: { v: [1, 2] } })],
          }),
          shard("urn:shard:b", {
            entities: [entity("urn:e:a", { attributes: { v: [2, 1] } })],
          }),
        ]),
      ),
  ],
  [
    "negative zero and zero compare equally",
    (api) => {
      const a = shard("urn:shard:a", {
          entities: [entity("urn:e:a", { attributes: { v: -0 } })],
        }),
        b = shard("urn:shard:b", {
          entities: [entity("urn:e:a", { attributes: { v: 0 } })],
        });
      const c = compose(api, [a, b]);
      return [
        Object.is(c.entities[0].attributes.v, -0),
        c.entities[0] === a.entities[0],
      ];
    },
  ],
  [
    "distinct primitive types conflict",
    (api) =>
      failure(api, () =>
        compose(api, [
          shard("urn:shard:a", {
            entities: [entity("urn:e:a", { attributes: { v: 1 } })],
          }),
          shard("urn:shard:b", {
            entities: [entity("urn:e:a", { attributes: { v: "1" } })],
          }),
        ]),
      ),
  ],
  [
    "integer-index keys enumerate consistently",
    (api) => {
      const a = shard("urn:shard:a", {
          entities: [
            entity("urn:e:a", {
              attributes: { 10: 1, 2: 2, "01": 3, 4294967295: 4 },
            }),
          ],
        }),
        b = shard("urn:shard:b", {
          entities: [
            entity("urn:e:a", {
              attributes: { 4294967295: 4, "01": 3, 2: 2, 10: 1 },
            }),
          ],
        });
      return compose(api, [a, b]).entities.length;
    },
  ],
  [
    "locale-equal canonical Unicode keys preserve order",
    (api) =>
      failure(api, () =>
        compose(api, [
          shard("urn:shard:a", {
            entities: [
              entity("urn:e:a", { attributes: { é: 1, "e\u0301": 2 } }),
            ],
          }),
          shard("urn:shard:b", {
            entities: [
              entity("urn:e:a", { attributes: { "e\u0301": 2, é: 1 } }),
            ],
          }),
        ]),
      ),
  ],
  [
    "locale-equal ignorable keys preserve order",
    (api) =>
      failure(api, () =>
        compose(api, [
          shard("urn:shard:a", {
            entities: [
              entity("urn:e:a", { attributes: { a: 1, "a\u200b": 2 } }),
            ],
          }),
          shard("urn:shard:b", {
            entities: [
              entity("urn:e:a", { attributes: { "a\u200b": 2, a: 1 } }),
            ],
          }),
        ]),
      ),
  ],
  [
    "locale key sorting retains case and accents",
    (api) => {
      const a = shard("urn:shard:a", {
          entities: [
            entity("urn:e:a", { attributes: { z: 1, A: 2, a: 3, ä: 4, é: 5 } }),
          ],
        }),
        b = shard("urn:shard:b", {
          entities: [
            entity("urn:e:a", { attributes: { é: 5, ä: 4, a: 3, A: 2, z: 1 } }),
          ],
        });
      return compose(api, [a, b]).entities.length;
    },
  ],
  [
    "string values are not normalized",
    (api) =>
      failure(api, () =>
        compose(api, [
          shard("urn:shard:a", {
            entities: [entity("urn:e:a", { label: "é" })],
          }),
          shard("urn:shard:b", {
            entities: [entity("urn:e:a", { label: "e\u0301" })],
          }),
        ]),
      ),
  ],
  [
    "prototype-named fields retained as data",
    (api) => {
      const e = JSON.parse(
        '{"id":"urn:e:a","kind":"field","attributes":{"__proto__":{"x":1},"constructor":2}}',
      );
      const a = shard("urn:shard:a", { entities: [e] }),
        b = shard("urn:shard:b", { entities: [structuredClone(e)] });
      const c = compose(api, [a, b]);
      return [
        c.entities[0] === e,
        c.entities[0].attributes,
        Object.getPrototypeOf(c.entities[0].attributes) === Object.prototype,
      ];
    },
  ],
  [
    "merged object mutation reflects caller changes",
    (api) => {
      const a = shard(),
        b = shard("urn:shard:b");
      const c = compose(api, [a, b]);
      c.entities[0].label = "changed";
      a.entities = [];
      return [
        c.entities[0].label,
        b.entities[0].label === undefined,
        c.entities.length,
      ];
    },
  ],
  [
    "composition does not validate cross-shard endpoints",
    (api) => {
      const c = compose(api, [
        shard("urn:shard:a", { mappings: [mapping()] }),
        shard("urn:shard:b", { entities: [entity("urn:e:b")] }),
      ]);
      const g = new api.MetamapGraph(c);
      return [g.validationIssues, g.getEntity("urn:e:b") === c.entities[1]];
    },
  ],
  [
    "composition preserves unresolved endpoints until graph validation",
    (api) => {
      const c = compose(api, [shard("urn:shard:a", { mappings: [mapping()] })]);
      return [c.mappings.length, failure(api, () => new api.MetamapGraph(c))];
    },
  ],
];
