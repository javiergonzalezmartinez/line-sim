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
        self.assertAlmostEqual(r.throughput_per_week, 168 / 20, delta=0.5)
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
