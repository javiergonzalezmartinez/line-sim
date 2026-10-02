import os, tempfile, unittest
from plantsim.cli import load, main
from plantsim.calibrate import calibrate, summary, loss

A = os.path.join(os.path.dirname(__file__), "..", "examples", "whatif_a.json")
P = load(A)


class C(unittest.TestCase):
    def test_recovers_hidden_value(self):
        r = calibrate(P, "Coating", 10.0, 8.0, 14.0)
        self.assertLess(abs(r["error"]), 0.5)
        self.assertLess(abs(r["start"] - r["truth"]), 1.5)

    def test_deterministic(self):
        a = calibrate(P, "Coating", 10.0, 9.0, 12.0, seeds=3, ref_seeds=3)
        b = calibrate(P, "Coating", 10.0, 9.0, 12.0, seeds=3, ref_seeds=3)
        self.assertEqual(a["fitted"], b["fitted"]); self.assertEqual(a["points"], b["points"])

    def test_loss_zero_at_reference(self):
        ref = summary(P, 3, 0)
        self.assertEqual(loss(ref[0], ref[1], ref), 0.0)

    def test_search_does_not_use_truth(self):
        # the truth is outside the search range: the fit must stop at the edge, not at the truth
        r = calibrate(P, "Coating", 10.0, 11.0, 14.0, seeds=3, ref_seeds=3)
        self.assertAlmostEqual(r["fitted"], 11.0, 6)

    def test_unknown_stage(self):
        with self.assertRaises(ValueError):
            calibrate(P, "Nope", 10.0, 8.0, 12.0)

    def test_cli_page(self):
        out = os.path.join(tempfile.mkdtemp(), "c.html")
        main([A, "--calibrate-view", out, "--calibrate-truth", "10"])
        self.assertIn("Synthetic and illustrative", open(out, encoding="utf-8").read())
