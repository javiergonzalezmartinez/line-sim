import json, unittest
from plantsim.negstock import _run, sweep, render_html
from plantsim.cli import load

class T(unittest.TestCase):
    def test_atomic_never_negative(self):
        dones = [i * 0.01 for i in range(1, 300)]
        for cover in (0.5, 0.98, 1.2):
            neg, rej, depth, expo, n = _run(dones, 0.0, 720.0, 10, cover, 0.0)
            self.assertEqual(neg, 0)
    def test_race_exact(self):
        # 2 lots/week, cover 0.5 -> delivery 10 units = one lot
        neg, rej, depth, expo, n = _run([100.0, 100.0 + 1 / 60.0], 0.0, 168.0, 10, 0.5, 5 / 60.0)
        self.assertEqual((neg, rej, depth, expo), (1, 0, [10.0], 1))
        neg, rej, depth, expo, n = _run([100.0, 100.0 + 1 / 60.0], 0.0, 168.0, 10, 0.5, 0.0)
        self.assertEqual((neg, rej), (0, 1))
        neg, rej, depth, expo, n = _run([100.0, 110.0], 0.0, 168.0, 10, 0.5, 5 / 60.0)
        self.assertEqual((neg, rej), (0, 1))
    def test_sweep(self):
        p = load("examples/pharma_flow.json")
        r = sweep(p, [0, 5, 60], 10, 0.95, 3)
        self.assertEqual(r[0]["neg"][0], 0)
        self.assertGreaterEqual(r[2]["exp"][0], r[1]["exp"][0])
        self.assertIn("Poisson", render_html(r, 10, 0.95, 3))
    def test_bad(self):
        with self.assertRaises(ValueError): sweep(load("examples/pharma_flow.json"), [], 10, 1, 1)
if __name__ == "__main__": unittest.main()
