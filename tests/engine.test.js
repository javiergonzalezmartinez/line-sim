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

const cfgB = () => JSON.parse(fs.readFileSync(path.join(__dirname, '../examples/pharma_buffers.json'), 'utf8'));
test('finite buffers, no randomness: JS and Python give identical times and blocked hours', () => {
  const p = cfgB(); p.seed = 1; p.stages.forEach(s => { s.cv = 0; s.breakdown_p = 0; s.retest_p = 0; if (s.kind === 'hold') s.p = 0; });
  const j = simulate(p), z = ref.bufzero[0];
  z.done.forEach((d, i) => assert.ok(Math.abs(j.batches[i].d - d) < 1e-9, `batch ${i}: ${j.batches[i].d} vs ${d}`));
  assert.ok(Math.abs(j.throughput - z.tp) < 1e-9); assert.ok(Math.abs(j.leadDays - z.lt) < 1e-9);
  z.blocked.forEach((b, k) => assert.ok(Math.abs(j.stats[k].blocked - b) < 1e-6, `blocked ${k}: ${j.stats[k].blocked} vs ${b}`));
  z.maxq.forEach((m, k) => assert.strictEqual(j.stats[k].maxq, m));
  assert.ok(z.blocked.some(b => b > 0), 'the example must actually block');
});
test('finite buffers with randomness: means over 20 seeds agree within 3%', () => {
  let tp = 0, lt = 0;
  for (let s = 1; s <= 20; s++) { const p = cfgB(); p.seed = s; const j = simulate(p); tp += j.throughput; lt += j.leadDays; }
  const rtp = ref.bufstat.reduce((a, x) => a + x.tp, 0), rlt = ref.bufstat.reduce((a, x) => a + x.lt, 0);
  assert.ok(Math.abs(tp / rtp - 1) < 0.03, `throughput ${tp / 20} vs ${rtp / 20}`);
  assert.ok(Math.abs(lt / rlt - 1) < 0.03, `lead time ${lt / 20} vs ${rlt / 20}`);
});
test('buffer limits are respected', () => {
  const p = cfgB(); const j = simulate(p);
  p.stages.forEach((s, k) => { if (s.buffer != null) assert.ok(j.stats[k].maxq <= s.buffer, `${s.name}: ${j.stats[k].maxq} > ${s.buffer}`); });
});

test('capacity on a wait stage limits the flow (JS)', () => {
  const mk = cap => ({ stages: [Object.assign({ name: 'rack', kind: 'wait', hours: 20, cv: 0 }, cap ? { capacity: cap } : {})], products: ['A'], release_every: 10, horizon: 24 * 7 * 20, warmup: 24 * 7 * 2, seed: 1 });
  assert.ok(Math.abs(simulate(mk(0)).throughput - 16.8) < 0.6);
  assert.ok(Math.abs(simulate(mk(1)).throughput - 168 / 20) < 0.6);
  assert.ok(Math.abs(simulate(mk(2)).throughput - 16.8) < 0.6);
  assert.throws(() => simulate({ stages: [{ name: 'x', kind: 'process', hours: 1, capacity: 2 }], products: ['A'], release_every: 10, horizon: 500, warmup: 0 }));
});

test('daily breaks delay starts but never interrupt a running lot (JS)', () => {
  const mk = (h, br) => ({ stages: [{ name: 'S', kind: 'process', hours: h, cv: 0, breaks: br }], products: ['A'], release_every: 24, horizon: 24 * 7 * 20, warmup: 24 * 7 * 2, seed: 1 });
  assert.ok(Math.abs(simulate(mk(2, [[0, 6]])).leadDays * 24 - 8) < 0.01);
  assert.ok(Math.abs(simulate(mk(5, [[1, 2]])).leadDays * 24 - 5) < 0.01);
  assert.throws(() => simulate(mk(1, [[5, 5]])));
});

test('material shortage delays the start but is not working time (JS, both engines)', () => {
  const mk = buf => ({ stages: [Object.assign({ name: 'S', kind: 'process', hours: 2, cv: 0, shortage_p: 1, shortage_hours: 5 }, buf ? { buffer: 2 } : {})], products: ['A'], release_every: 24, horizon: 24 * 7 * 20, warmup: 24 * 7 * 2, seed: 1 });
  assert.ok(Math.abs(simulate(mk(false)).leadDays * 24 - 7) < 0.8);
  assert.ok(Math.abs(simulate(mk(true)).leadDays * 24 - 7) < 0.8);
  assert.throws(() => simulate({ stages: [{ name: 'x', kind: 'wave', waves: [8], shortage_p: 0.5 }], products: ['A'], release_every: 10, horizon: 500, warmup: 0 }));
});
