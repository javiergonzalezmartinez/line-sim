import os, tempfile, unittest
from plantsim.cli import load, main
from plantsim.model import simulate
from plantsim.bottleneck import active_periods, detect

A = os.path.join(os.path.dirname(__file__), "..", "examples", "whatif_a.json")
P = load(A); R = simulate(P)


class B(unittest.TestCase):
    def test_periods_are_disjoint_and_sorted(self):
        for per in active_periods(P, R).values():
            for (s, e), (s2, e2) in zip(per, per[1:]):
                self.assertLess(s, e); self.assertLess(e, s2)

    def test_shares_sum_to_one_and_count_matches(self):
        d = detect(P, R)
        self.assertAlmostEqual(sum(d["share"].values()), 1.0, 9)
        self.assertEqual(len(d["seq"]), int(R.window / d["step_h"]))

    def test_margin_makes_more_unclear(self):
        lo = detect(P, R, margin=0.0)["share"].get("unclear", 0)
        hi = detect(P, R, margin=0.5)["share"].get("unclear", 0)
        self.assertLessEqual(lo, hi)
        self.assertGreater(hi, lo)

    def test_shifts_ignore_unclear(self):
        d = detect(P, R)
        clear = [s for s in d["seq"] if s not in ("unclear", "none")]
        self.assertEqual(d["shifts"], sum(1 for a, b in zip(clear, clear[1:]) if a != b))

    def test_single_machine_line_is_always_that_machine(self):
        import dataclasses
        keep = [s for s in P.stages if s.kind == "process"][:1]
        q = dataclasses.replace(P, stages=keep)
        d = detect(q, simulate(q))
        self.assertTrue(set(d["seq"]) <= {keep[0].name, "none"})
        self.assertEqual(d["shifts"], 0)

    def test_cli_page(self):
        out = os.path.join(tempfile.mkdtemp(), "b.html")
        main([A, "--bottleneck-view", out])
        self.assertIn("Roser", open(out, encoding="utf-8").read())
