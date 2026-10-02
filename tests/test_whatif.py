import os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from plantsim.cli import load, main
from plantsim.whatif import compare, t_quantile, mean_ci, render_html

A = os.path.join(os.path.dirname(__file__), "..", "examples", "whatif_a.json")
B = os.path.join(os.path.dirname(__file__), "..", "examples", "whatif_b.json")


class T(unittest.TestCase):
    def test_t_quantile_matches_published_table(self):
            # textbook values of t(0.975, df)
        assert abs(t_quantile(0.975, 1) - 12.706) < 1e-3
        assert abs(t_quantile(0.975, 10) - 2.228) < 1e-3
        assert abs(t_quantile(0.975, 30) - 2.042) < 1e-3


    def test_mean_ci_simple(self):
        m, lo, hi, s = mean_ci([1.0, 2.0, 3.0])
        assert m == 2.0 and abs(s - 1.0) < 1e-12 and abs(hi - 2 - (2 - lo)) < 1e-12


    def test_identical_scenarios_have_zero_delta(self):
        c = compare(load(A), load(A), 5)
        for v in c["metrics"].values():
            assert abs(v["diff"][0]) < 1e-12 and not v["clear"]


    def test_ci_narrows_with_more_seeds(self):
        w = lambda n: (lambda d: d[2] - d[1])(compare(load(A), load(B), n)["metrics"]["Mean lead time (days)"]["diff"])
        assert w(24) < w(4)


    def test_second_coater_helps(self):
        c = compare(load(A), load(B), 12)["metrics"]
        assert c["Throughput (batches/week)"]["diff"][0] > 0 and c["Throughput (batches/week)"]["clear"]
        assert c["Mean lead time (days)"]["diff"][0] < 0


    def test_cli_and_page(self):
        out = os.path.join(tempfile.mkdtemp(), "w.html")
        main([A, "--whatif", B, "--seeds", "4", "--whatif-view", out])
        t = open(out, encoding="utf-8").read()
        assert "ILLUSTRATIVE" not in t and "Synthetic and illustrative" in t and "<svg" in t


if __name__ == "__main__":
    unittest.main()
