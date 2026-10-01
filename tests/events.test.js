const test = require('node:test'), assert = require('node:assert'), fs = require('node:fs'), path = require('node:path');
const { simulate, buildEvents, eventsCsv } = require('../plantsim/engine.js');
const cfg = JSON.parse(fs.readFileSync(path.join(__dirname, '../examples/pharma_flow.json'), 'utf8'));
const R = simulate(cfg), t0 = cfg.warmup, ev = buildEvents(cfg, R, t0, cfg.horizon);
const lots = [...new Set(ev.map(e => e.lot))];
const rejLots = new Set(R.batches.filter(b => b.rej).map(b => 'LOT-' + String(b.id + 1).padStart(4, '0')));

test('events exist for all four kinds and are chronological', () => {
  for (const k of ['PLC', 'WMS', 'ERP', 'QA']) assert.ok(ev.some(e => e.kind === k), k);
  for (let i = 1; i < ev.length; i++) assert.ok(ev[i].t >= ev[i - 1].t);
  assert.ok(ev.length > 1000);
});
test('every lot goes receipt -> release -> goods issue, in that order, inside its own lifetime', () => {
  const byLot = {}; R.batches.forEach(b => byLot['LOT-' + String(b.id + 1).padStart(4, '0')] = b);
  for (const l of lots.filter(x => !rejLots.has(x))) {
    const es = ev.filter(e => e.lot === l), b = byLot[l];
    const gr = es.findIndex(e => /Goods receipt posted against purchase order/.test(e.detail));
    const rel = es.findIndex(e => /Batch disposition: released/.test(e.detail));
    const gi = es.findIndex(e => /Goods issue posted for outbound delivery/.test(e.detail));
    assert.ok(gr >= 0 && gr < rel && rel < gi, l);
    assert.strictEqual(es.filter(e => /Goods receipt posted against purchase order/.test(e.detail)).length, 1);
    es.forEach(e => { assert.ok(e.t + t0 >= b.r - 1e-9 && e.t + t0 <= b.d + 1e-9, l + ' ' + e.detail); });
  }
});
test('SAP-style movement types are limited to those confirmed in public SAP Learning pages (101, 261, 321)', () => {
  const used = new Set(); ev.forEach(e => { const m = e.detail.match(/MvT (\d+)/); if (m) used.add(m[1]); });
  assert.deepStrictEqual([...used].sort(), ['101', '261', '321']);
  ev.filter(e => e.kind === 'ERP').forEach(e => assert.ok(e.src.includes('SAP-style, simulated')));
});
test('document numbers are unique and increasing; palletizer states in order', () => {
  const docs = ev.filter(e => e.doc).map(e => +e.doc); assert.strictEqual(new Set(docs).size, docs.length);
  for (let i = 1; i < docs.length; i++) assert.ok(docs[i] > docs[i - 1]);
  const l = lots[5], pal = ev.filter(e => e.lot === l && /^Palletizer/.test(e.src)).map(e => e.detail);
  assert.strictEqual(pal.length, 12);
  assert.match(pal[0], /State: running/); assert.match(pal[11], /pallet complete, 60 cases/);
  for (let i = 1; i <= 5; i++) assert.ok(pal.indexOf(`Picking layer ${i} of 5, vacuum gripper OK`) < pal.indexOf(`Layer ${i} of 5 placed: 12 cases, interlocked pattern`));
});
test('CSV export has one row per event and the right column count', () => {
  const rows = eventsCsv(ev, t0).split('\n'); assert.strictEqual(rows.length, ev.length + 1);
  assert.strictEqual(rows[0].split(',').length, 9);
});

test('deviation holds: some lots are held, rejected lots never reach dispatch, others continue', () => {
  assert.ok(rejLots.size > 0);
  for (const l of rejLots) {
    const es = ev.filter(e => e.lot === l);
    assert.ok(es.some(e => /REJECTED/.test(e.detail)));
    assert.ok(!es.some(e => /Goods issue posted for outbound delivery/.test(e.detail)));
    assert.ok(!es.some(e => /Batch disposition: released/.test(e.detail)));
  }
  const held = new Set(ev.filter(e => /Deviation raised/.test(e.detail)).map(e => e.lot));
  assert.ok(held.size > rejLots.size, 'some held lots were accepted');
  assert.ok(R.rejected >= 0);
});
test('transport time follows layout distance and speed', () => {
  const { simulate: sim } = require('../plantsim/engine.js');
  const p = JSON.parse(JSON.stringify(cfg)); const mv = () => p.stages.filter(s => s.kind === 'move').map(s => s.hours);
  sim(p); const a = mv(); p.speed_kmh = 12; sim(p); const b = mv();
  a.forEach((h, i) => assert.ok(b[i] < h));
  const pos = {}; p.layout.forEach(l => pos[l.id] = [l.x + l.w / 2, l.y + l.h / 2]);
  const i = p.stages.findIndex(s => s.name === 'Dock to warehouse'), A = pos[p.stages[i - 1].loc], B = pos[p.stages[i + 1].loc];
  const m = (Math.abs(A[0] - B[0]) + Math.abs(A[1] - B[1])) * p.m_per_px;
  assert.ok(Math.abs(p.stages[i].hours - (m / (12 * 1000 / 60) + 6) / 60) < 1e-9);
});

test('FEFO picks the earliest expiry among released unconsumed lots (independent brute-force check) and differs from FIFO', () => {
  const { buildEvents: be, shelfDays } = require('../plantsim/engine.js');
  const e1 = be(cfg, R, t0, cfg.horizon, 'FEFO'), pk = e1.pick;
  assert.ok(pk.picks > 50 && pk.diff > 0, JSON.stringify([pk.picks, pk.diff]));
  const picks = e1.filter(e => /FEFO pick/.test(e.detail));
  assert.strictEqual(picks.length, pk.picks);
  const m = picks.map(e => ({ t: e.t, id: +e.detail.match(/MAT-(\d+)/)[1] - 1 }));
  const seen = new Set(m.map(x => x.id)); assert.strictEqual(seen.size, m.length, 'a lot is picked only once');
  const rel = {}; R.batches.filter(b => b.r >= t0 && b.d != null && b.r < cfg.horizon).forEach(b => { const x = b.t.find(y => /QC sampling/.test(cfg.stages[y[0]].name)); if (x) rel[b.id] = x[3]; });
  const exp = id => rel[id] + shelfDays(id) * 24;
  const used = new Set();
  m.forEach(x => {
    const avail = Object.keys(rel).map(Number).filter(i => rel[i] - t0 <= x.t + 1e-9 && !used.has(i) && i >= 0);
    const best = avail.reduce((a, b) => (exp(b) < exp(a) || (exp(b) === exp(a) && b < a)) ? b : a);
    assert.strictEqual(x.id, best); used.add(x.id);
  });
  const e2 = be(cfg, R, t0, cfg.horizon, 'FIFO');
  assert.ok(e2.some(e => /FIFO pick/.test(e.detail)));
  assert.notDeepStrictEqual(picks.map(e => e.detail.match(/MAT-\d+/)[0]), e2.filter(e => /FIFO pick/.test(e.detail)).map(e => e.detail.match(/MAT-\d+/)[0]));
});
test('MQTT-style messages: topic shape, valid JSON payload, no real-world claims', () => {
  const { mqtt, mqttLines } = require('../plantsim/engine.js');
  const m = mqtt(ev[10], t0); assert.match(m.topic, /^fictitious-plant\/[a-z0-9-]+\/[a-z0-9-]+$/);
  assert.match(m.payload.ts, /^2026-\d\d-\d\dT\d\d:\d\d:\d\d$/);
  const lines = mqttLines(ev, t0).split('\n'); assert.strictEqual(lines.length, ev.length);
  lines.forEach(l => { const o = JSON.parse(l); assert.ok(o.topic && o.payload.msg && o.payload.lot); });
});
