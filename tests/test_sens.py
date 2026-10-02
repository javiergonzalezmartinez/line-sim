import os, unittest
from plantsim.cli import load
from plantsim.sensitivity import run, render_html, _with

P = load(os.path.join(os.path.dirname(__file__), "..", "examples", "pharma_flow.json"))
A = run(P, 0.2, 5)


class T(unittest.TestCase):
    def test_with_scales_only_one_input(self):
        q = _with(P, 0, "hours", 1.2)
        self.assertAlmostEqual(q.stages[0].hours, P.stages[0].hours * 1.2)
        self.assertEqual([s.hours for i, s in enumerate(q.stages) if i != 0], [s.hours for i, s in enumerate(P.stages) if i != 0])
        self.assertAlmostEqual(_with(P, None, "release_every", 0.8).release_every, P.release_every * 0.8)

    def test_only_nonzero_inputs_and_release_present(self):
        labels = [r["label"] for r in A["rows"]]
        self.assertIn("Plant: release interval", labels)
        self.assertFalse(any("breakdown_p" in l and P.stages[[s.name for s in P.stages].index(l.split(":")[0])].breakdown_p == 0 for l in labels if ":" in l and l.split(":")[0] in [s.name for s in P.stages]))

    def test_release_interval_lowers_throughput_when_longer(self):
        r = next(x for x in A["rows"] if x["label"] == "Plant: release interval")["thr"]
        self.assertGreater(r["low"], r["high"])          # shorter interval (-20%) -> more batches released

    def test_validation_and_page(self):
        with self.assertRaises(ValueError):
            run(P, 1.5, 5)
        h = render_html(A)
        self.assertIn("Synthetic and illustrative", h); self.assertIn("within noise", h)

if __name__ == "__main__":
    unittest.main()
