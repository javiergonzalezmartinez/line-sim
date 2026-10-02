import json, os, re, subprocess, tempfile, unittest
from plantsim.cli import load
from plantsim.dashboard import build

ROOT = os.path.join(os.path.dirname(__file__), "..")
CFG = os.path.join(ROOT, "examples", "dashboard_demo.json")
PAGE = build(load(CFG), json.load(open(CFG, encoding="utf-8")))


class DashboardTests(unittest.TestCase):
    def test_single_file_no_network(self):
        self.assertNotRegex(PAGE, r"(src|href)=\"https?://")
        self.assertIn("default-src 'none'", PAGE)
        self.assertIn("Digital twin layer", PAGE)
        self.assertIn("illustrative placeholders", PAGE)

    def test_embedded_data_matches_python_results(self):
        tw = json.loads(re.search(r"const TW=(\{.*?\});\nfunction TWSTALE", PAGE, re.S).group(1))
        from plantsim.model import simulate
        from plantsim.events import events
        p = load(CFG)
        r = simulate(p)
        self.assertEqual(len(tw["series"]["disp"]), sum(1 for e in events(p, r) if e["event_type"] == "lot.dispatched"))
        for k, v in tw["series"].items():
            self.assertEqual(v, sorted(v), k)
        self.assertEqual(tw["st"], sorted(tw["st"]))
        self.assertEqual(len(tw["st"]), len(tw["s"]))
        self.assertGreaterEqual(len(tw["series"]["tt"]), 100)

    def test_stale_panel_hook_installed(self):
        self.assertIn("function schedule(){TWSTALE();", PAGE)
        self.assertIn("draw();twDraw();requestAnimationFrame(loop)", PAGE)

    def test_embedded_script_parses(self):
        js = re.findall(r"<script>(.*?)</script>", PAGE, re.S)[-1]
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(js)
        r = subprocess.run(["node", "--check", f.name], capture_output=True, text=True)
        os.unlink(f.name)
        self.assertEqual(r.returncode, 0, r.stderr)
