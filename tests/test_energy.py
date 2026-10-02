import json, os, tempfile, unittest
from plantsim.cli import load, main
from plantsim.model import simulate
from plantsim.energy import energy

EX = os.path.join(os.path.dirname(__file__), "..", "examples", "energy_demo.json")
P = load(EX); R = simulate(P); CFG = json.load(open(EX))["energy"]


class E(unittest.TestCase):
    def test_kwh_is_kw_times_hours(self):
        e = energy(P, R, CFG)
        for r in e["rows"]:
            for s, v in r["kwh"].items():
                kw = {**(CFG["default"] if r["stage"] in [x.name for x in P.stages if x.kind == "process"] else {}), **CFG["stages"].get(r["stage"], {})}.get(s, 0.0)
                self.assertAlmostEqual(v, kw * r["hours"][s], 6)

    def test_hours_add_up_to_capacity(self):
        e = energy(P, R, CFG)
        for r, st in zip(e["rows"], R.stats):
            if r["configured"]:
                self.assertAlmostEqual(sum(r["hours"].values()), st.servers * R.window, 6)

    def test_doubling_power_doubles_energy(self):
        d = json.loads(json.dumps(CFG))
        for k in d["stages"].values():
            for s in k: k[s] *= 2
        d["default"] = {s: v * 2 for s, v in d["default"].items()}
        self.assertAlmostEqual(energy(P, R, d)["total_kwh"], 2 * energy(P, R, CFG)["total_kwh"], 6)

    def test_nothing_configured_is_zero_and_flagged(self):
        e = energy(P, R, None)
        self.assertEqual(e["total_kwh"], 0.0)
        self.assertTrue(all(not r["configured"] for r in e["rows"]))

    def test_default_only_for_machines(self):
        e = energy(P, R, {"default": {"idle": 1.0}})
        kinds = {s.name: s.kind for s in P.stages}
        for r in e["rows"]:
            self.assertEqual(r["configured"], kinds[r["stage"]] == "process")

    def test_cli_page(self):
        out = os.path.join(tempfile.mkdtemp(), "e.html")
        main([EX, "--energy", out])
        t = open(out, encoding="utf-8").read()
        self.assertIn("placeholder", t); self.assertIn("kWh", t)
