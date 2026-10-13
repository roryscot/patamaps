/** Inputs/observations shared by both engines; expected results are frozen from
 * the pinned original before any candidate observation. No engine code here. */
const relation = (id = "test:r", patch = {}) => ({
  id,
  cyclePolicy: "allow",
  ...patch,
});
const portable = (id = "urn:pack:p", relations = [relation()]) => ({
  schemaVersion: "1.0.0",
  id,
  version: "1",
  relations,
});
const law = (patch = {}) => ({
  id: "urn:law:r",
  operation: "reverse",
  operands: ["test:r"],
  resultRelation: "test:r",
  handling: {
    authority: "none",
    lossiness: "conservative",
    uncertainty: "conservative",
  },
  ...patch,
});
const executable = (patch = {}) => ({
  ...portable(),
  schemaVersion: "2.0.0",
  laws: [law()],
  ...patch,
});
const failure = (fn) => {
  try {
    fn();
    return null;
  } catch (error) {
    return { name: error.name, message: error.message };
  }
};
export const scenarios = [
  [
    "empty queries",
    ({ RelationRegistry: R }) => {
      const r = new R([]);
      return [
        r.all(),
        r.allPacks(),
        r.executablePacks(),
        r.get("missing"),
        r.getPack("missing"),
        r.getLaw("missing"),
        r.hasPack("missing"),
      ].map((v) => (v === undefined ? "undefined" : v));
    },
  ],
  [
    "default original core identity",
    ({ RelationRegistry: R, coreRelationPack: core }) => {
      const r = new R();
      return [
        r.getPack(core.id) === core,
        r.get(core.relations[0].id) === core.relations[0],
        r.allPacks().length,
        r.executablePacks().length,
      ];
    },
  ],
  [
    "ordered packs and definitions",
    ({ RelationRegistry: R }) => {
      const a = portable("urn:pack:a", [relation("test:a")]),
        b = portable("urn:pack:b", [relation("test:b")]);
      const r = new R([b, a]);
      return [
        r.allPacks().map((p) => p.id),
        r.all().map((d) => d.id),
        r.getPack(a.id) === a,
        r.get("test:b") === b.relations[0],
      ];
    },
  ],
  [
    "query arrays are fresh",
    ({ RelationRegistry: R }) => {
      const p = portable(),
        r = new R([p]);
      const all = r.all(),
        packs = r.allPacks();
      all.length = 0;
      packs.length = 0;
      return [
        r.all().length,
        r.allPacks().length,
        r.all() !== r.all(),
        r.allPacks() !== r.allPacks(),
        r.executablePacks() !== r.executablePacks(),
      ];
    },
  ],
  [
    "same object registration idempotent",
    ({ RelationRegistry: R }) => {
      const p = portable(),
        r = new R([p]);
      r.registerPack(p);
      return [r.all().length, r.allPacks().length, r.getPack(p.id) === p];
    },
  ],
  [
    "equal clone preserves first identity",
    ({ RelationRegistry: R }) => {
      const p = portable(),
        r = new R([p]);
      r.registerPack(structuredClone(p));
      return [r.getPack(p.id) === p, r.get("test:r") === p.relations[0]];
    },
  ],
  [
    "member order conflict",
    ({ RelationRegistry: R }) => {
      const p = portable(),
        r = new R([p]);
      return failure(() =>
        r.registerPack({
          id: p.id,
          schemaVersion: p.schemaVersion,
          version: p.version,
          relations: p.relations,
        }),
      );
    },
  ],
  [
    "version conflict before relation conflict",
    ({ RelationRegistry: R }) => {
      const p = portable(),
        r = new R([p]);
      return failure(() => r.registerPack({ ...p, version: "2" }));
    },
  ],
  [
    "legacy shape is unchecked",
    ({ RelationRegistry: R }) => {
      const p = {
        ...portable(),
        unknown: true,
        relations: [{ id: "test:r", cyclePolicy: "unknown", symmetric: true }],
      };
      const r = new R([p]);
      return [
        r.getPack(p.id) === p,
        r.get("test:r") === p.relations[0],
        Object.isFrozen(p),
      ];
    },
  ],
  [
    "duplicate incoming relation atomic",
    ({ RelationRegistry: R }) => {
      const r = new R([]),
        p = portable("urn:pack:p", [relation(), relation()]);
      const err = failure(() => r.registerPack(p));
      return [err, r.all(), r.allPacks(), r.get("test:r") === undefined];
    },
  ],
  [
    "existing relation conflict atomic",
    ({ RelationRegistry: R }) => {
      const p = portable(),
        r = new R([p]);
      const err = failure(() =>
        r.registerPack(
          portable("urn:pack:q", [relation("test:new"), relation()]),
        ),
      );
      return [
        err,
        r.get("test:new") === undefined,
        r.allPacks().map((p) => p.id),
      ];
    },
  ],
  [
    "pack ID mutation preserves registration key",
    ({ RelationRegistry: R }) => {
      const p = portable(),
        r = new R([p]);
      p.id = "urn:pack:changed";
      return [
        r.getPack("urn:pack:p") === p,
        r.getPack(p.id) === undefined,
        r.hasPack("urn:pack:p"),
        r.hasPack(p.id),
      ];
    },
  ],
  [
    "version queries read live object",
    ({ RelationRegistry: R }) => {
      const p = portable(),
        r = new R([p]);
      p.version = "2";
      return [
        r.hasPack(p.id),
        r.hasPack(p.id, "1"),
        r.hasPack(p.id, "2"),
        r.hasPack(p.id, ""),
        r.hasPack("absent", ""),
      ];
    },
  ],
  [
    "relation ID mutation preserves registration key",
    ({ RelationRegistry: R }) => {
      const p = portable(),
        d = p.relations[0],
        r = new R([p]);
      d.id = "test:changed";
      return [
        r.get("test:r") === d,
        r.get(d.id) === undefined,
        r.all().map((d) => d.id),
      ];
    },
  ],
  [
    "replacing relation array retains original objects",
    ({ RelationRegistry: R }) => {
      const p = portable(),
        d = p.relations[0],
        r = new R([p]);
      p.relations = [relation("test:new")];
      return [
        r.get("test:r") === d,
        r.get("test:new") === undefined,
        r.getPack(p.id).relations === p.relations,
      ];
    },
  ],
  [
    "mutated schema tag changes executable filter",
    ({ RelationRegistry: R }) => {
      const p = portable(),
        r = new R([p]);
      p.schemaVersion = "2.0.0";
      return [r.executablePacks()[0] === p, r.getLaw("missing") === undefined];
    },
  ],
  [
    "executable copied and recursively frozen",
    ({ RelationRegistry: R }) => {
      const p = executable({
          laws: [
            law({
              conditions: {
                context: { all: [{ key: "x", operator: "exists" }] },
              },
            }),
          ],
        }),
        r = new R([p]),
        entry = r.getLaw("urn:law:r");
      return [
        entry.pack !== p,
        Object.isFrozen(entry.pack),
        Object.isFrozen(entry.pack.relations),
        Object.isFrozen(entry.pack.relations[0]),
        Object.isFrozen(entry.law),
        Object.isFrozen(entry.law.operands),
        Object.isFrozen(entry.law.conditions.context.all[0]),
        Object.isFrozen(p),
        r.get("test:r") === entry.pack.relations[0],
      ];
    },
  ],
  [
    "law wrapper fresh with stable pack and law",
    ({ RelationRegistry: R }) => {
      const r = new R([executable()]),
        a = r.getLaw("urn:law:r"),
        b = r.getLaw("urn:law:r");
      return [
        a !== b,
        a.pack === b.pack,
        a.law === b.law,
        r.executablePacks()[0] === a.pack,
        r.getPack(a.pack.id) === a.pack,
      ];
    },
  ],
  [
    "caller executable edits do not change registry",
    ({ RelationRegistry: R }) => {
      const p = executable(),
        r = new R([p]);
      p.description = "changed";
      p.laws[0].id = "urn:law:changed";
      p.relations[0].id = "test:changed";
      return [
        r.getLaw("urn:law:r").law.id,
        r.getLaw("urn:law:changed") === undefined,
        r.get("test:r").id,
      ];
    },
  ],
  [
    "executable duplicate law atomic",
    ({ RelationRegistry: R }) => {
      const p = executable({ laws: [law(), law()] }),
        r = new R([]),
        err = failure(() => r.registerPack(p));
      return [err, r.all(), r.allPacks(), r.getLaw("urn:law:r") === undefined];
    },
  ],
  [
    "cross pack duplicate law",
    ({ RelationRegistry: R }) => {
      const r = new R([executable()]);
      return failure(() =>
        r.registerPack(
          executable({
            id: "urn:pack:q",
            relations: [relation("test:q")],
            laws: [law({ operands: ["test:q"], resultRelation: "test:q" })],
          }),
        ),
      );
    },
  ],
  [
    "legacy description drift invalidates law",
    ({ RelationRegistry: R, relationPackDigest: digest }) => {
      const p = portable(),
        x = executable({
          id: "urn:pack:x",
          relations: [],
          imports: [{ id: p.id, version: p.version, digest: digest(p) }],
        }),
        r = new R([p, x]);
      p.description = "changed";
      return failure(() => r.getLaw("urn:law:r"));
    },
  ],
  [
    "legacy new relation visible to exact imports",
    ({ RelationRegistry: R, relationPackDigest: digest }) => {
      const p = portable(),
        r = new R([p]);
      p.relations = [relation("test:new")];
      const x = executable({
        id: "urn:pack:x",
        relations: [],
        imports: [{ id: p.id, version: p.version, digest: digest(p) }],
        laws: [law({ operands: ["test:new"], resultRelation: "test:new" })],
      });
      r.registerPack(x);
      return [
        r.get("test:new") === undefined,
        r.getLaw("urn:law:r").law.operands,
      ];
    },
  ],
  [
    "empty imported kind restriction",
    ({ RelationRegistry: R, relationPackDigest: digest }) => {
      const p = portable("urn:pack:p", [
        relation("test:r", { sourceKinds: [] }),
      ]);
      return failure(
        () =>
          new R([
            p,
            executable({
              id: "urn:pack:x",
              relations: [],
              imports: [{ id: p.id, version: p.version, digest: digest(p) }],
            }),
          ]),
      );
    },
  ],
  [
    "reverse inverse contradiction",
    ({ RelationRegistry: R }) =>
      failure(
        () =>
          new R([
            executable({
              relations: [
                relation("test:r", { inverse: "test:q" }),
                relation("test:q"),
              ],
              laws: [law()],
            }),
          ]),
      ),
  ],
  [
    "reverse non symmetry contradiction",
    ({ RelationRegistry: R }) =>
      failure(
        () =>
          new R([
            executable({
              relations: [relation("test:r", { symmetric: false })],
            }),
          ]),
      ),
  ],
  [
    "unconditional reverse satisfies symmetric flag",
    ({ RelationRegistry: R }) => {
      const p = executable({
        relations: [relation("test:r", { symmetric: true })],
        laws: [law({ conditions: {} })],
      });
      return new R([p]).getLaw("urn:law:r").law.conditions;
    },
  ],
  [
    "conditional reverse cannot satisfy symmetric flag",
    ({ RelationRegistry: R }) =>
      failure(
        () =>
          new R([
            executable({
              relations: [relation("test:r", { symmetric: true })],
              laws: [law({ conditions: { sourceKinds: ["x"] } })],
            }),
          ]),
      ),
  ],
  [
    "missing composition law",
    ({ RelationRegistry: R }) =>
      failure(
        () =>
          new R([
            executable({
              relations: [
                relation("test:r", { composesWith: ["test:q"] }),
                relation("test:q"),
              ],
              laws: [],
            }),
          ]),
      ),
  ],
  [
    "missing disjoint relation",
    ({ RelationRegistry: R }) =>
      failure(
        () =>
          new R([
            executable({
              relations: [
                relation("test:r", { disjointWith: ["test:missing"] }),
              ],
              laws: [],
            }),
          ]),
      ),
  ],
  [
    "self disjoint relation",
    ({ RelationRegistry: R }) =>
      failure(
        () =>
          new R([
            executable({
              relations: [relation("test:r", { disjointWith: ["test:r"] })],
              laws: [],
            }),
          ]),
      ),
  ],
  [
    "law outside pack before symmetric flag",
    ({ RelationRegistry: R }) =>
      failure(
        () =>
          new R([
            executable({
              relations: [relation("test:r", { symmetric: true })],
              laws: [law({ operands: ["test:missing"] })],
            }),
          ]),
      ),
  ],
  [
    "legacy private use identifiers and values",
    ({ RelationRegistry: R }) => {
      const p = portable("urn:pack:\ue000", [relation("test:\ue000")]),
        r = new R([p]);
      return [
        r.getPack(p.id) === p,
        r.get(p.relations[0].id) === p.relations[0],
        r.allPacks()[0].id,
      ];
    },
  ],
  [
    "legacy UTF16 description retains identity",
    ({ RelationRegistry: R }) => {
      const p = { ...portable(), description: "\ud800" },
        r = new R([p]);
      return [r.getPack(p.id) === p, r.getPack(p.id).description];
    },
  ],
  [
    "unchecked executable digest before registration",
    ({ RelationRegistry: R, relationPackDigest: digest }) => {
      const p = executable({ unknown: true });
      return [digest(p), failure(() => new R([p]))];
    },
  ],
];
