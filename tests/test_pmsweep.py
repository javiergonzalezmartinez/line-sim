import unittest
from plantsim.cli import load
from plantsim.pmsweep import sweep, render_html


class T(unittest.TestCase):
    def test_sweep(self):
        P = load("examples/pm_b.json")
        r = sweep(P, [None, 50.0, 600.0], 3)
        self.assertEqual(len(r), 3)
        self.assertEqual(r[0]["pm"][0], 0.0)                 # no PM, no PM hours
        self.assertGreater(r[1]["pm"][0], r[2]["pm"][0])     # more frequent PM, more PM hours
        self.assertGreater(r[0]["rep"][0], r[1]["rep"][0])   # PM cuts repair hours in this config
        h = render_html(r)
        self.assertIn("Preventive_maintenance", h); self.assertIn("never", h)
