// Cross-check of the JS engine against the Python model. Run: node --test tests/
const test = require('node:test'), assert = require('node:assert');
const { spawnSync } = require('node:child_process'), fs = require('node:fs'), os = require('node:os'), path = require('node:path');
const { simulate } = require('../plantsim/engine.js');
const cfg = () => JSON.parse(fs.readFileSync(path.join(__dirname, '../examples/pharma_flow.json'), 'utf8'));
const tmp = path.join(os.tmpdir(), 'plantsim_ref.json');
const r = spawnSync('python3', ['-m', 'tests.dump_ref', tmp], { cwd: path.join(__dirname, '..') });
assert.strictEqual(r.status, 0, String(r.stderr));
const ref = JSON.parse(fs.readFileSync(tmp, 'utf8'));

test('no randomness: JS and Python give identical batch completion times', () => {
  const p = cfg(); p.seed = 1; p.stages.forEach(s => { s.cv = 0; s.breakdown_p = 0; s.retest_p = 0; if (s.kind === 'hold') s.p = 0; });
  const j = simulate(p);
  ref.zero[0].done.forEach((d, i) => assert.ok(Math.abs(j.batches[i].d - d) < 1e-9, `batch ${i}: ${j.batches[i].d} vs ${d}`));
  assert.ok(Math.abs(j.throughput - ref.zero[0].tp) < 1e-9);
  assert.ok(Math.abs(j.leadDays - ref.zero[0].lt) < 1e-9);
});

test('with randomness: means over 20 seeds agree within 3%', () => {
  let tp = 0, lt = 0;
  for (let s = 1; s <= 20; s++) { const p = cfg(); p.seed = s; const j = simulate(p); tp += j.throughput; lt += j.leadDays; }
  const rtp = ref.stat.reduce((a, x) => a + x.tp, 0), rlt = ref.stat.reduce((a, x) => a + x.lt, 0);
  assert.ok(Math.abs(tp / rtp - 1) < 0.03, `throughput ${tp / 20} vs ${rtp / 20}`);
  assert.ok(Math.abs(lt / rlt - 1) < 0.03, `lead time ${lt / 20} vs ${rlt / 20}`);
});

test('same seed, same result; different seed differs', () => {
  const a = cfg(), b = cfg(), c = cfg(); c.seed = 99;
  assert.strictEqual(simulate(a).throughput, simulate(b).throughput);
  assert.notStrictEqual(simulate(a).leadDays, simulate(c).leadDays);
});

test('one forklift and slow moves raise lead time; forklift pool utilisation grows', () => {
  const base = simulate(cfg());
  const p = cfg(); p.speed_kmh = 0.4; p.handling_min = 30; p.stages.forEach(s => { if (s.pool) s.servers = 1; });
  const slow = simulate(p);
  assert.ok(slow.leadDays > base.leadDays);
  assert.ok(slow.pools.Forklifts > base.pools.Forklifts * 3);
});

test('more compression capacity does not hurt throughput', () => {
  const p = cfg(); p.release_every = 12;
  const a = simulate(p).throughput; p.stages.find(s => s.name === 'Coating').servers = 2;
  assert.ok(simulate(p).throughput >= a - 0.2);
});
