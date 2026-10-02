import os, unittest
from collections import defaultdict
from plantsim.cli import load
from plantsim.model import simulate
from plantsim.quality import quality, quality_kpis
from plantsim.events import validate
from plantsim.fsm import Machine
from tests.test_events import PLANT, RES, SCHEMA

ROOT = os.path.join(os.path.dirname(__file__), "..")
SP = load(os.path.join(ROOT, "examples", "seed_scenario.json"))
SR = simulate(SP)
CFG = {"sample_h": 1.0, "lab_h": 8.0, "hold_p": 0.5, "hold_h": 6.0}


def by_lot(ev):
    d = defaultdict(list)
    for e in ev:
        d[e["object_ids"][0]].append(e)
    return d


class QualityTests(unittest.TestCase):
    def test_sequences_legal_and_end_in_a_final_disposition(self):
        ev = quality(SP, SR, CFG)
        for lot, l in by_lot(ev).items():
            m = Machine("QUALITY_STATUS", "QUARANTINE", lot)
            for e in l:
                m.fire(e["event_type"])
            self.assertIn(m.state, ("RELEASED", "REJECTED"))
        for e in ev[:1500]:
            self.assertEqual(validate(e, SCHEMA), [])

    def test_rejections_match_the_plant_model(self):
        ev = quality(SP, SR, CFG)
        rej = {f"LOT-{b.id + 1:06d}" for b in SR.batches if b.rejected and b.done is not None}
        got = {e["object_ids"][0] for e in ev if e["event_type"] == "sample.status_rejected"}
        self.assertEqual(rej, got)
        self.assertTrue(rej)

    def test_release_delay_is_sample_plus_lab(self):
        ev = quality(SP, SR, {"sample_h": 1.0, "lab_h": 8.0})
        from plantsim.kpis import hours
        for lot, l in list(by_lot(ev).items()):
            t = {e["event_type"]: hours(e["event_time"]) for e in l}
            if "sample.status_released" in t:
                self.assertAlmostEqual(t["sample.status_released"] - t["sample.request_created"], 9.0, places=4)

    def test_defaults_add_no_holds_beyond_the_plant(self):
        k = quality_kpis(quality(PLANT, RES))
        self.assertEqual(k["lots_with_hold"], sum(1 for b in RES.batches if b.done is not None and not b.rejected and any(PLANT.stages[r[0]].kind == "hold" and r[3] > r[2] + 1e-9 for r in b.trace)))

    def test_hold_exposure_scales_with_hu_per_lot(self):
        ev = quality(SP, SR, CFG)
        a = list(quality_kpis(ev, 1).values())[-1]
        b = list(quality_kpis(ev, 6).values())[-1]
        self.assertAlmostEqual(b, 6 * a, places=1)
        self.assertGreater(a, 0)

    def test_bad_parameters_and_determinism(self):
        for bad in ({"hold_p": 2}, {"lab_h": -1}, {"nope": 1}):
            with self.assertRaises(ValueError):
                quality(SP, SR, bad)
        self.assertEqual([e["event_id"] for e in quality(SP, SR, CFG)], [e["event_id"] for e in quality(SP, SR, CFG)])
