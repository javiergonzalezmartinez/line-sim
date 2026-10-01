import unittest
from plantsim.model import Plant, Stage, simulate, _next_open, _next_wave
from plantsim.cli import load


def plant(stages, rel=10, **k):
    return Plant(stages, ["A"], rel, horizon=24 * 7 * 20, warmup=24 * 7 * 2, **k)


class T(unittest.TestCase):
    def test_throughput_follows_release_when_underloaded(self):
        r = simulate(plant([Stage("S", "process", hours=5, cv=0)], rel=10))
        self.assertAlmostEqual(r.throughput_per_week, 16.8, delta=0.6)

    def test_overloaded_stage_caps_throughput_and_is_bottleneck(self):
        r = simulate(plant([Stage("fast", "process", hours=2, cv=0), Stage("slow", "process", hours=20, cv=0)], rel=10))
        self.assertLessEqual(r.throughput_per_week, 168 / 20 + 0.5)  # cannot beat the forklift capacity
        self.assertGreater(r.throughput_per_week, 0)
        self.assertEqual(r.bottleneck, "slow")

    def test_two_servers_double_capacity(self):
        r = simulate(plant([Stage("S", "process", servers=2, hours=20, cv=0)], rel=10))
        self.assertAlmostEqual(r.throughput_per_week, 16.8, delta=0.6)

    def test_lead_time_equals_sum_of_times_when_empty(self):
        r = simulate(plant([Stage("a", "process", hours=3, cv=0), Stage("b", "wait", hours=4, cv=0)], rel=50))
        self.assertAlmostEqual(r.mean_lead_time_days * 24, 7, delta=0.01)

    def test_changeover_only_when_product_changes(self):
        st = [Stage("S", "process", hours=1, cv=0, changeover=5)]
        one = Plant(st, ["A"], 20, 24 * 7 * 10, 24 * 7, 1)
        two = Plant(st, ["A", "B"], 20, 24 * 7 * 10, 24 * 7, 1)
        self.assertEqual(simulate(one).stats[0].setup, 0)
        self.assertGreater(simulate(two).stats[0].setup, 0)

    def test_calendar_blocks_weekend(self):
        s = Stage("QC", "process", hours=1, window=(8, 16), workdays=5)
        sat_10 = 5 * 24 + 10
        self.assertEqual(_next_open(sat_10, s), 7 * 24 + 8)   # Monday 08:00
        self.assertEqual(_next_open(2 * 24 + 17, s), 3 * 24 + 8)
        self.assertEqual(_next_open(2 * 24 + 9, s), 2 * 24 + 9)

    def test_waves(self):
        self.assertEqual(_next_wave(11, [10, 15]), 15)
        self.assertEqual(_next_wave(16, [10, 15]), 34)

    def test_seed_reproducible_and_example_runs(self):
        p = load("examples/pharma.json")
        a, b = simulate(p), simulate(p)
        self.assertEqual([x.done for x in a.batches], [x.done for x in b.batches])
        self.assertGreater(a.throughput_per_week, 0)

    def test_bad_config(self):
        with self.assertRaises(ValueError):
            Plant([], ["A"], 10)
        with self.assertRaises(ValueError):
            plant([Stage("x", "wave")])

    def test_utilisation_matches_hand_calc(self):
        r = simulate(plant([Stage("S", "process", hours=5, cv=0)], rel=10))
        self.assertAlmostEqual(r.utilisation(r.stats[0])["process"], 0.5, delta=0.01)

if __name__ == "__main__":
    unittest.main()


class TFlow(unittest.TestCase):
    def test_pool_is_shared_between_move_stages(self):
        from plantsim.model import Plant, Stage, simulate
        a = Stage("m1", "move", servers=1, hours=10, cv=0, pool="F", loc=None)
        b = Stage("m2", "move", servers=1, hours=10, cv=0, pool="F", loc=None)
        st = [Stage("s0", "process", hours=1, cv=0, loc="x"), a, Stage("s1", "process", hours=1, cv=0, loc="y"), b,
              Stage("s2", "process", hours=1, cv=0, loc="z")]
        lay = [{"id": i, "name": i, "x": 0, "y": 0, "w": 1, "h": 1} for i in "xyz"]
        pl = Plant(st, ["A"], 12, 24 * 7 * 6, 24 * 7, 1, lay)
        r = simulate(pl)
        # 20 h of moves per lot on ONE shared forklift: saturated (separate forklifts would each be ~83% busy)
        self.assertGreater(r.pool_utilisation(pl)["F"], 0.95)
        self.assertLessEqual(r.throughput_per_week, 168 / 20 + 0.5)  # cannot beat the forklift capacity
        self.assertGreater(r.throughput_per_week, 0)

    def test_layout_validation(self):
        from plantsim.model import Plant, Stage
        lay = [{"id": "x", "name": "x", "x": 0, "y": 0, "w": 1, "h": 1}]
        with self.assertRaises(ValueError):
            Plant([Stage("m", "move", hours=1), Stage("s", "process", loc="x")], ["A"], 10, layout=lay)
        with self.assertRaises(ValueError):
            Plant([Stage("s", "process", loc="nope")], ["A"], 10, layout=lay)

    def test_view_is_offline_and_complete(self):
        from plantsim.cli import load
        from plantsim.view import render
        h = render(load("examples/pharma_flow.json"))
        self.assertIn("default-src 'none'", h)
        self.assertNotIn("http://", h.replace("http://www.w3.org/2000/svg", ""))
        self.assertNotIn("https://", h)
        self.assertNotIn("fetch(", h)
        self.assertIn("function simulate", h)
        self.assertIn("Fictitious plant", h)


class THold(unittest.TestCase):
    def test_rejecting_hold_removes_lots_from_throughput(self):
        from plantsim.model import Plant, Stage, simulate
        st = [Stage("a", "process", hours=1, cv=0), Stage("qa", "hold", p=1.0, hours=2, cv=0, reject_p=1.0), Stage("b", "process", hours=1, cv=0)]
        r = simulate(Plant(st, ["A"], 10, 24 * 7 * 6, 24 * 7, 1))
        self.assertEqual(r.throughput_per_week, 0)
        self.assertGreater(r.rejected, 0)
        self.assertEqual(r.stats[2].batches, 0)          # nothing reaches the stage after the hold

    def test_hold_with_zero_probability_is_transparent(self):
        from plantsim.model import Plant, Stage, simulate
        mk = lambda h: [Stage("a", "process", hours=1, cv=0), Stage("qa", "hold", p=h, hours=50, cv=0), Stage("b", "process", hours=1, cv=0)]
        a = simulate(Plant(mk(0.0), ["A"], 10, 24 * 7 * 6, 24 * 7, 1))
        self.assertAlmostEqual(a.mean_lead_time_days * 24, 2.0, places=6)

    def test_move_time_from_layout_distance(self):
        from plantsim.model import Plant, Stage
        lay = [{"id": "x", "name": "x", "x": 0, "y": 0, "w": 100, "h": 100}, {"id": "y", "name": "y", "x": 300, "y": 100, "w": 100, "h": 100}]
        st = [Stage("s0", "process", loc="x"), Stage("m", "move", servers=1, pool="F", hours=99), Stage("s1", "process", loc="y")]
        p = Plant(st, ["A"], 10, layout=lay, m_per_px=0.5, speed_kmh=6, handling_min=6)
        metres = (300 + 100) * 0.5            # centre to centre, Manhattan
        self.assertAlmostEqual(p.stages[1].hours, (metres / 100 + 6) / 60, places=9)   # 6 km/h = 100 m/min
