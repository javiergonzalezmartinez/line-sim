import unittest
from plantsim.cli import load
from plantsim.multicalib import run, render_html


class T(unittest.TestCase):
    def setUp(self):
        self.P = load("examples/pharma_flow.json")

    def test_run(self):
        r = run(self.P, "Coating", "Granulation + drying", (11.0, 9.0), steps=3, seeds=2, ref_seeds=3)
        self.assertEqual(len(r["cells"]), 3)
        self.assertEqual(r["cells_total"], 9)
        self.assertGreaterEqual(r["l1_near"], 1)
        self.assertAlmostEqual(r["va"][1], 11.0)           # centre of the grid is the truth

    def test_validation(self):
        with self.assertRaises(ValueError):
            run(self.P, "Coating", "Coating", (1, 1))
        with self.assertRaises(ValueError):
            run(self.P, "Coating", "Nope", (1, 1))
        with self.assertRaises(ValueError):
            run(self.P, "Coating", "Dispensing", (1, 1), steps=4)

    def test_page(self):
        r = run(self.P, "Coating", "Dispensing", (11.0, 6.0), steps=3, seeds=2, ref_seeds=3)
        h = render_html(r)
        self.assertIn("Sargent", h); self.assertIn("No real data", h)
