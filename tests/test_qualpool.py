import unittest
from plantsim.qualpool import sweep, render_html, erlang_c
from plantsim.cli import load

class T(unittest.TestCase):
    def test_erlang(self):
        self.assertAlmostEqual(erlang_c(1, 0.5), 0.5)
        self.assertAlmostEqual(erlang_c(2, 1.0), 1 / 3, places=6)
        self.assertEqual(erlang_c(2, 3.0), 1.0)
    def test_sweep(self):
        p = load("examples/pharma_flow.json")
        r = sweep(p, [1, 2, 4], 8, 3)
        self.assertGreaterEqual(r[0]["wait"][0], r[1]["wait"][0]); self.assertGreaterEqual(r[1]["wait"][0], r[2]["wait"][0])
        self.assertAlmostEqual(r[0]["util"][0], r[0]["rho"], delta=0.15)
        self.assertIn("Erlang C", render_html(r, 8, 3))
    def test_bad(self):
        p = load("examples/pharma_flow.json")
        with self.assertRaises(ValueError): sweep(p, [0], 8)
        with self.assertRaises(ValueError): sweep(p, [1], 0)
if __name__ == "__main__": unittest.main()
