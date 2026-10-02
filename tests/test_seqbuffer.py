import random, unittest
from plantsim.seqbuffer import run_stream, sweep, render_html
from plantsim.cli import load

class Fixed:
    """Delays given explicitly: expovariate returns the next value."""
    def __init__(self, delays): self.d = list(delays)
    def expovariate(self, lam): return self.d.pop(0)

class T(unittest.TestCase):
    def test_in_order(self):
        sw, sk, lat = run_stream(Fixed([0, 0, 0, 0]), 4, 1.0, 1.0, 5.0)
        self.assertEqual((sw, sk, len(lat)), (0, 0, 4)); self.assertEqual(sum(lat), 0)
    def test_swap_waits(self):
        # msg0 arrives at 3, msg1 at 1+0=1: msg1 held 2 s until msg0 arrives
        sw, sk, lat = run_stream(Fixed([3, 0, 0]), 3, 1.0, 1.0, 10.0)
        self.assertEqual(sw, 1); self.assertEqual(sk, 0); self.assertEqual(len(lat), 3)
        self.assertAlmostEqual(sum(lat), 2.0 + 1.0)  # msg1 waits 2, msg2 (arr 2) waits 1
    def test_timeout_skips(self):
        # msg0 arrives at 20; timeout 2 s from arrival of msg1 (t=1) -> skip at 3
        sw, sk, lat = run_stream(Fixed([20, 0, 0]), 3, 1.0, 1.0, 2.0)
        self.assertEqual(sk, 1); self.assertEqual(len(lat), 2)
    def test_sweep(self):
        p = load("examples/pharma_flow.json")
        r = sweep(p, [0, 2, 10], 8, 2.0, 1.5, 3, 200)
        self.assertGreaterEqual(r[0]["skip"][0], r[2]["skip"][0])
        self.assertLessEqual(r[0]["lat"][0], r[2]["lat"][0] + 1e-9)
        for x in r: self.assertAlmostEqual(x["swap"][0], x["swap_th"], delta=0.03)
        self.assertIn("1/2 exp", render_html(r, 8, 2.0, 1.5, 3))
    def test_bad(self):
        p = load("examples/pharma_flow.json")
        with self.assertRaises(ValueError): sweep(p, [1], 1, 1, 1)
if __name__ == "__main__": unittest.main()
