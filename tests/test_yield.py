import dataclasses, unittest
from plantsim.cli import load
from plantsim.model import simulate
from plantsim.yieldsweep import sweep, render_html


class T(unittest.TestCase):
    def setUp(self):
        self.P = load("examples/pharma_flow.json")

    def test_off_by_default(self):
        r = simulate(self.P)
        self.assertTrue(all(s.low_yield == 0 for s in r.stats))

    def test_threshold_monotone(self):
        r = sweep(self.P, "Coating", 0.97, 0.02, [0.90, 0.96], 3)
        self.assertLess(r[0]["low"][0], r[1]["low"][0])
        self.assertGreater(r[1]["lt"][0], r[0]["lt"][0] - 1e-9)

    def test_counted_in_both_engines(self):
        st = [dataclasses.replace(s, yield_mean=0.97, yield_cv=0.02, yield_min=0.97) if s.name == "Coating" else s for s in self.P.stages]
        for P in (dataclasses.replace(self.P, stages=st), dataclasses.replace(self.P, stages=st, conwip=40)):
            c = next(s for s in simulate(P).stats if s.name == "Coating")
            self.assertGreater(c.low_yield, 0)
            self.assertGreaterEqual(c.reruns, c.low_yield)

    def test_validation(self):
        bad = [dataclasses.replace(s, yield_mean=0.0, yield_min=0.9) if s.name == "Coating" else s for s in self.P.stages]
        with self.assertRaises(ValueError):
            dataclasses.replace(self.P, stages=bad)
        with self.assertRaises(ValueError):
            sweep(self.P, "Nope", 0.97, 0.02, [0.9], 2)

    def test_page(self):
        h = render_html(sweep(self.P, "Coating", 0.97, 0.02, [0.93], 2), "Coating", 0.97, 0.02)
        self.assertIn("FME-022", h); self.assertIn("no source claimed", h)
