import random, unittest
from plantsim.scalesettle import sweep, render_html, capture
from plantsim.cli import load

class T(unittest.TestCase):
    def test_capture_noiseless(self):
        rg = random.Random(1)
        t, x = capture(rg, 0.5, 20.0, 4.0, 1e-9, 0.5)
        self.assertIsNotNone(t); self.assertLessEqual(abs(x), 0.5 / (1 - __import__('math').exp(-0.5 / 4.0)) + 1e-6)
    def test_sweep(self):
        p = load("examples/pharma_flow.json")
        r = sweep(p, [0.25, 1, 5], 20, 4, 0.5, 0.5, 6, 3, 200)
        self.assertGreaterEqual(r[0]["time"][0], r[2]["time"][0])
        self.assertGreaterEqual(r[2]["err"][0], r[0]["err"][0])
        for x in r: self.assertAlmostEqual(x["acc"], x["acc_th"], delta=0.02)
        self.assertIn("Phi", render_html(r, 20, 4, 0.5, 0.5, 6, 3))
    def test_bad(self):
        p = load("examples/pharma_flow.json")
        with self.assertRaises(ValueError): sweep(p, [0], 20, 4, 0.5, 0.5, 6)
        with self.assertRaises(ValueError): sweep(p, [1], 20, 4, 0, 0.5, 6)
if __name__ == "__main__": unittest.main()
