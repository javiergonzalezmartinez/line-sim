import os, unittest
from plantsim.cli import load
from plantsim.replications import run, render_html

P = load(os.path.join(os.path.dirname(__file__), "..", "examples", "pharma_flow.json"))
A = run(P, 12, 0.05)


class T(unittest.TestCase):
    def test_validation(self):
        with self.assertRaises(ValueError):
            run(P, 3, 0.05, 5)

    def test_first_and_stable_consistent(self):
        for m in A["measures"]:
            if m["first"]:
                self.assertGreaterEqual(m["first"], 5)
                if m["stable"] is not None:                 # None = reached the target once but did not stay under it
                    self.assertGreaterEqual(m["stable"], m["first"])
                self.assertLessEqual(m["rel"][m["first"] - 1], 0.05 + 1e-12)
            else:
                self.assertIsNone(m["stable"])

    def test_rel_width_shrinks_roughly(self):
        m = next(x for x in A["measures"] if x["name"].startswith("Throughput"))
        self.assertLessEqual(m["rel"][-1], m["rel"][4] * 1.5)

    def test_tighter_precision_needs_no_fewer_reps(self):
        B = run(P, 12, 0.005)
        a = next(x for x in A["measures"] if x["name"].startswith("Throughput"))["first"]
        b = next(x for x in B["measures"] if x["name"].startswith("Throughput"))["first"]
        self.assertTrue(b is None or a is None or b >= a)

    def test_page(self):
        h = render_html(A)
        self.assertIn("Synthetic and illustrative", h); self.assertIn("not implemented", h)

if __name__ == "__main__":
    unittest.main()
