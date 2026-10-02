import json, os, unittest
from plantsim.kpis import kpis, render_html, hours
from plantsim.signals import telemetry
from tests.test_events import PLANT, RES, EV

TL = telemetry(PLANT, RES)
K = kpis(PLANT, EV, TL)


class KpiTests(unittest.TestCase):
    def test_throughput_and_lead_time_equal_the_simulators_numbers(self):
        self.assertAlmostEqual(K["KPI-001 Throughput (lots/week)"], RES.throughput_per_week, places=6)
        self.assertAlmostEqual(K["KPI-002 LeadTime (days, mean)"], RES.mean_lead_time_days, places=6)

    def test_scrap_rate_matches_rejected_count(self):
        closed = sum(1 for b in RES.batches if b.done is not None and PLANT.warmup <= b.done <= PLANT.horizon)
        self.assertAlmostEqual(K["KPI-026 ScrapRate (lot basis)"], RES.rejected / closed, places=9)

    def test_utilisation_from_events_equals_simulator_busy_plus_repair(self):
        n = 0
        for s, st, rs in zip(K["stages"], RES.stats, PLANT.stages):
            if s["kind"] in ("process", "move"):
                n += 1
                self.assertAlmostEqual(s["utilisation"], (st.busy + st.repair) / (st.servers * RES.window), places=5, msg=s["stage"])
        self.assertGreater(n, 10)

    def test_queue_wait_equals_simulator_when_no_changeover_and_is_larger_with_it(self):
        for s, st, rs in zip(K["stages"], RES.stats, PLANT.stages):
            if rs.kind not in ("process", "move") or st.batches == 0:
                continue
            sim = st.wait / st.batches
            if rs.changeover == 0:
                self.assertAlmostEqual(s["queue_wait_h"], sim, places=6, msg=s["stage"])
            else:
                self.assertGreaterEqual(s["queue_wait_h"], sim - 1e-9, s["stage"])

    def test_wip_follows_littles_law_roughly(self):
        closed = [b for b in RES.batches if b.done is not None and PLANT.warmup <= b.done <= PLANT.horizon]
        rate = len(closed) / RES.window
        lt = sum(b.done - b.released for b in closed) / len(closed)
        self.assertAlmostEqual(K["KPI-005 WIP (lots, time average)"], rate * lt, delta=0.2 * rate * lt)

    def test_ids_exist_in_the_spec_and_quality_is_good(self):
        spec = {r["ID"]: r["KPI"] for r in json.load(open(os.path.join(os.path.dirname(__file__), "..", "spec", "kpis.json"), encoding="utf-8"))["records"]}
        for name in K:
            if name.startswith("KPI-"):
                sid, label = name.split(" ")[0], name.split(" ")[1]
                self.assertEqual(spec[sid], label)
        self.assertEqual(K["KPI-018 SensorGoodQuality"], 1.0)

    def test_html_has_no_scripts(self):
        h = render_html(K)
        self.assertIn("Queue wait", h)
        self.assertNotIn("<script", h)

    def test_time_helper_roundtrip(self):
        self.assertAlmostEqual(hours("2026-01-06T12:00:00.000Z"), 36.0)
