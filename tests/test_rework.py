import unittest
from plantsim.cli import load
from plantsim.rework import sweep, render_html


class T(unittest.TestCase):
    def setUp(self):
        self.P = load("examples/pharma_flow.json")

    def test_sweep(self):
        r = sweep(self.P, "Coating", [0.0, 0.3], 3)
        self.assertEqual(r[0]["reruns"][0], 0.0)
        self.assertGreater(r[1]["reruns"][0], 0.0)
        self.assertGreater(r[1]["share"][0], 0.1)
        self.assertLess(r[1]["share"][0], 0.6)

    def test_counters_both_engines(self):
        import dataclasses
        from plantsim.model import simulate
        for P in (self.P, dataclasses.replace(self.P, conwip=40)):
            r = simulate(P)
            qc = next(s for s in r.stats if s.name == "QC lab release testing")
            self.assertGreaterEqual(qc.reruns, 0)
            self.assertLessEqual(qc.rerun_hours, qc.busy + 1e-9)

    def test_validation(self):
        with self.assertRaises(ValueError):
            sweep(self.P, "Nope", [0.1], 2)
        with self.assertRaises(ValueError):
            sweep(self.P, "Coating", [1.0], 2)

    def test_page(self):
        h = render_html(sweep(self.P, "Coating", [0.0, 0.2], 2), "Coating")
        self.assertIn("No external source", h)
