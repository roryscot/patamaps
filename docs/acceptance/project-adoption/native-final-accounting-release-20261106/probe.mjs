import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const fixture = path.dirname(fileURLToPath(import.meta.url));
const variant = process.argv[2];
assert.ok(['baseline', 'candidate'].includes(variant));
const { guardedCommand } = await import(pathToFileURL(path.join(fixture, variant, 'guarded-run.mjs')));
const policy = {
  version: 1, minimumFreeBytes: 0, reserveFreeBytes: 500000000,
  maximumRunGrowthBytes: 67108864, maximumRetainedBytes: 100000000000,
  monitorIntervalMs: 2000, terminationGraceMs: 15000,
};

function read(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function requests(lease) {
  const dir = path.join(lease, 'scheduler', 'requests');
  return fs.readdirSync(dir).filter(name => name.endsWith('.json'))
    .map(name => read(path.join(dir, name)));
}

async function run(label, { capacityError = false, rootsError = false, uncertainOwnership = false } = {}) {
  const root = path.join(fixture, variant + '-' + label);
  const lease = path.join(root, 'lease');
  const work = path.join(root, 'work');
  fs.mkdirSync(work, { recursive: true, mode: 0o700 });
  let snapshots = 0;
  let failure = null;
  let exitCode = null;
  const options = {
    root: work, cwd: work, temporary: work, directory: path.join(root, 'control'),
    childControlDirectory: path.join(root, 'control'), leaseDirectory: lease, policy,
    environment: { PATH: '/usr/bin:/bin', LANG: 'C' },
    capacity: () => {
      if (snapshots === 2 && capacityError) throw Error('fixture terminal volume accounting unavailable');
      return 10000000000;
    },
    retentionRoots: () => {
      if (snapshots === 2 && rootsError) throw Error('fixture terminal retained roots unavailable');
      return [work];
    },
    containerSnapshot: () => {
      snapshots += 1;
      return { known: snapshots !== 2 || !uncertainOwnership, ids: [] };
    },
  };
  try {
    exitCode = await guardedCommand(label, '/usr/bin/true', [], options);
  } catch (error) {
    failure = error.message;
  }
  assert.equal(snapshots, 2);
  const [request] = requests(lease);
  const active = path.join(lease, 'active-run');
  const activeLease = fs.existsSync(active);
  const archived = path.join(lease, 'runs');
  const records = fs.existsSync(archived) ? fs.readdirSync(archived)
    .map(name => path.join(archived, name, 'run.json')).filter(p => fs.existsSync(p)) : [];
  const receipt = records.length ? read(records[0]) :
    fs.existsSync(path.join(active, 'retained-run.json')) ? read(path.join(active, 'retained-run.json')) : null;
  const result = {
    label, exitCode, failure, activeLease, state: request.state,
    ownershipSealed: request.ownershipSealed,
    releaseCompleted: request.leaseReleaseCompleted === true,
    receiptCompleted: receipt?.completed ?? null,
    receiptExitCode: receipt?.exitCode ?? null,
    terminalErrorFields: (receipt?.finalAccountingErrors ?? []).map(row => row.field),
    reason: receipt?.stopReason ?? null,
  };
  if (variant === 'candidate' && !uncertainOwnership) {
    assert.equal(activeLease, false);
    assert.equal(request.state, 'finished');
    assert.equal(request.leaseReleaseCompleted, true);
    assert.equal(records.length, 1);
    if (capacityError || rootsError) {
      assert.equal(exitCode, 75);
      assert.equal(receipt.exitCode, 75);
      assert.equal(receipt.completed, false);
      assert.equal(receipt.stopReason, 'Storage guard: final accounting unavailable');
    } else {
      assert.equal(exitCode, 0);
      assert.equal(receipt.completed, true);
    }
    // A following request must actually acquire this same isolated lease.
    snapshots = 0;
    const next = await guardedCommand(label + '-follow-up', '/usr/bin/true', [], {
      ...options, capacity: () => 10000000000, retentionRoots: () => [work],
    });
    assert.equal(next, 0);
    assert.equal(fs.existsSync(active), false);
    assert.equal(requests(lease).length, 2);
    result.followUpReleased = true;
  }
  return result;
}

const capacity = await run('capacity', { capacityError: true });
if (variant === 'baseline') {
  assert.equal(capacity.failure, 'fixture terminal volume accounting unavailable');
  assert.equal(capacity.activeLease, true);
  assert.equal(capacity.state, 'running');
  assert.equal(capacity.releaseCompleted, false);
  assert.equal(capacity.receiptCompleted, null);
  console.log(JSON.stringify({ baselineReproduced: true, cases: [capacity] }));
} else {
  const roots = await run('roots', { rootsError: true });
  const both = await run('both', { capacityError: true, rootsError: true });
  const hold = await run('uncertain', { capacityError: true, uncertainOwnership: true });
  const normal = await run('normal');
  assert.deepEqual(capacity.terminalErrorFields, ['freeBytesAtEnd']);
  assert.deepEqual(roots.terminalErrorFields, ['retainedRootsAtEnd']);
  assert.deepEqual(both.terminalErrorFields, ['freeBytesAtEnd', 'retainedRootsAtEnd']);
  assert.equal(hold.activeLease, true);
  assert.equal(hold.state, 'needs-review');
  assert.equal(hold.releaseCompleted, false);
  assert.match(hold.failure, /Owned workload stop unconfirmed/);
  assert.deepEqual(hold.terminalErrorFields, ['freeBytesAtEnd']);
  assert.equal(normal.terminalErrorFields.length, 0);
  console.log(JSON.stringify({ candidatePassed: true, cases: [capacity, roots, both, hold, normal] }));
}
