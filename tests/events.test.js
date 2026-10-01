const test = require('node:test'), assert = require('node:assert'), fs = require('node:fs'), path = require('node:path');
const { simulate, buildEvents, eventsCsv } = require('../plantsim/engine.js');
const cfg = JSON.parse(fs.readFileSync(path.join(__dirname, '../examples/pharma_flow.json'), 'utf8'));
const R = simulate(cfg), t0 = cfg.warmup, ev = buildEvents(cfg, R, t0, cfg.horizon);
const lots = [...new Set(ev.map(e => e.lot))];

test('events exist for all four kinds and are chronological', () => {
  for (const k of ['PLC', 'WMS', 'ERP', 'QA']) assert.ok(ev.some(e => e.kind === k), k);
  for (let i = 1; i < ev.length; i++) assert.ok(ev[i].t >= ev[i - 1].t);
  assert.ok(ev.length > 1000);
});
test('every lot goes receipt -> release -> goods issue, in that order, inside its own lifetime', () => {
  const byLot = {}; R.batches.forEach(b => byLot['LOT-' + String(b.id + 1).padStart(4, '0')] = b);
  for (const l of lots) {
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
  const l = lots[5], pal = ev.filter(e => e.lot === l && e.src === 'Palletizer').map(e => e.detail);
  assert.deepStrictEqual(pal, ['State: picking layer 1', 'Layer 3 of 5 complete', 'Pallet complete']);
});
test('CSV export has one row per event and the right column count', () => {
  const rows = eventsCsv(ev, t0).split('\n'); assert.strictEqual(rows.length, ev.length + 1);
  assert.strictEqual(rows[0].split(',').length, 9);
});
