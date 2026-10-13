/** Preserve test cleanup by moving owned files; never remove user material. */
const fs = require("node:fs");
const path = require("node:path");
const { fileURLToPath } = require("node:url");
const { syncBuiltinESMExports } = require("node:module");
const original = {
  renameSync: fs.renameSync.bind(fs),
  lstatSync: fs.lstatSync.bind(fs),
  realpathSync: fs.realpathSync.bind(fs),
  mkdirSync: fs.mkdirSync.bind(fs),
  appendFileSync: fs.appendFileSync.bind(fs),
};
const roots = JSON.parse(process.env.PATAMAPS_RETAIN_ALLOWED ?? "[]").map((p) =>
  path.resolve(p),
);
const archive = path.resolve(process.env.PATAMAPS_RETAIN_ARCHIVE ?? "");
if (!roots.length || !process.env.PATAMAPS_RETAIN_ARCHIVE)
  throw new Error("Retention needs explicit owned roots and archive");
original.mkdirSync(archive, { recursive: true });
let counter = 0;
function move(input, options = {}) {
  const source = path.resolve(
    input instanceof URL
      ? fileURLToPath(input)
      : Buffer.isBuffer(input)
        ? input.toString()
        : input,
  );
  let stat;
  try {
    stat = original.lstatSync(source);
  } catch (error) {
    if (error.code === "ENOENT" && options.force) return;
    throw error;
  }
  // Resolve the parent as well as the leaf: deleting a symlink may be owned,
  // deleting through one into the reference's dependency tree is forbidden.
  const actual = path.join(
    original.realpathSync(path.dirname(source)),
    path.basename(source),
  );
  if (
    !roots.some((root) => actual === root || actual.startsWith(root + path.sep))
  )
    throw new Error(`Deletion refused outside retained test roots: ${source}`);
  if (actual === archive || actual.startsWith(archive + path.sep))
    throw new Error("Deletion refused inside the retention archive");
  if (
    stat.isDirectory() &&
    !options.recursive &&
    fs.readdirSync(source).length
  ) {
    const error = new Error(`Directory not empty: ${source}`);
    error.code = "ENOTEMPTY";
    throw error;
  }
  const destination = path.join(
    archive,
    `${process.pid}-${counter++}-${path.basename(source)}`,
  );
  original.renameSync(source, destination);
  original.appendFileSync(
    path.join(archive, "moves.ndjson"),
    JSON.stringify({
      source,
      destination,
      preserved: true,
      operation: "rename",
    }) + "\n",
  );
}
function callback(input, options, done) {
  if (typeof options === "function") {
    done = options;
    options = {};
  }
  try {
    move(input, options);
    done(null);
  } catch (error) {
    done(error);
  }
}
fs.rmSync = (input, options) => move(input, options);
fs.unlinkSync = (input) => move(input);
fs.rmdirSync = (input, options) => move(input, options);
fs.rm = callback;
fs.unlink = (input, done) => callback(input, {}, done);
fs.rmdir = callback;
fs.promises.rm = async (input, options) => move(input, options);
fs.promises.unlink = async (input) => move(input);
fs.promises.rmdir = async (input, options) => move(input, options);
syncBuiltinESMExports();
