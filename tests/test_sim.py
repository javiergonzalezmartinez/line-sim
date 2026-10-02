import unittest
from linesim.sim import Config, Station, simulate, sweep_buffer


def cfg(stations, buffers, **kw):
    kw.setdefault("duration", 200000.0)
    kw.setdefault("warmup", 2000.0)
    return Config(stations, buffers, **kw)


class SimTests(unittest.TestCase):
    def test_single_station_throughput_is_one_over_cycle(self):
        r = simulate(cfg([Station("A", 10.0)], []))
        self.assertAlmostEqual(r.throughput, 360.0, delta=0.5)
        self.assertGreater(r.stations[0].busy / r.window, 0.999)

    def test_two_stations_slow_one_sets_the_pace(self):
        r = simulate(cfg([Station("fast", 10.0), Station("slow", 20.0)], [5]))
        self.assertAlmostEqual(r.throughput, 180.0, delta=0.5)
        self.assertEqual(r.bottleneck, "slow")
        sh = r.stations[0].shares(r.window)
        self.assertAlmostEqual(sh["busy"], 0.5, delta=0.01)
        self.assertAlmostEqual(sh["blocked"], 0.5, delta=0.01)

    def test_starved_downstream(self):
        r = simulate(cfg([Station("slow", 20.0), Station("fast", 10.0)], [5]))
        self.assertAlmostEqual(r.throughput, 180.0, delta=0.5)
        self.assertAlmostEqual(r.stations[1].shares(r.window)["starved"], 0.5, delta=0.01)

    def test_time_shares_add_up_to_one(self):
        c = cfg([Station("A", 10, 0.3, 600, 60), Station("B", 12, 0.3, 900, 120), Station("C", 9, 0.2)], [3, 3])
        r = simulate(c)
        for s in r.stations:
            total = sum(s.shares(r.window).values())
            self.assertAlmostEqual(total, 1.0, delta=0.01, msg=s.name)

    def test_failures_cut_throughput_by_availability(self):
        # operation-dependent failures: expected rate = (1/ct) * MTBF/(MTBF+MTTR)
        st = Station("A", 10.0, 0.0, 900.0, 100.0)
        r = simulate(cfg([st], [], duration=4_000_000.0))
        expected = 360.0 * 900.0 / 1000.0
        self.assertAlmostEqual(r.throughput, expected, delta=expected * 0.02)

    def test_same_seed_same_result(self):
        c = cfg([Station("A", 10, 0.4, 500, 50), Station("B", 11, 0.4)], [2], duration=50000.0)
        self.assertEqual(simulate(c).parts, simulate(c).parts)

    def test_bigger_buffers_never_hurt_much(self):
        c = cfg([Station("A", 10, 0.4, 600, 80), Station("B", 10, 0.4, 600, 80), Station("C", 10, 0.4)], [1, 1],
                duration=300000.0)
        rows = sweep_buffer(c, [1, 2, 10], seeds=3)
        self.assertGreater(rows[1]["throughput"], rows[0]["throughput"])
        self.assertGreaterEqual(rows[2]["throughput"], rows[1]["throughput"] * 0.99)

    def test_bad_config(self):
        with self.assertRaises(ValueError):
            Config([Station("A", 1), Station("B", 1)], [])
        with self.assertRaises(ValueError):
            Config([Station("A", 1)], [], duration=10, warmup=10)


if __name__ == "__main__":
    unittest.main()


class DirectHandoffTests(unittest.TestCase):
    def test_equal_deterministic_stations_without_buffer_run_in_lockstep(self):
        r = simulate(cfg([Station("A", 10.0), Station("B", 10.0)], [0]))
        self.assertAlmostEqual(r.throughput, 360.0, delta=1.0)

    def test_slow_downstream_sets_pace_without_buffer(self):
        r = simulate(cfg([Station("fast", 10.0), Station("slow", 20.0)], [0]))
        self.assertAlmostEqual(r.throughput, 180.0, delta=1.0)
        self.assertAlmostEqual(r.stations[0].shares(r.window)["blocked"], 0.5, delta=0.01)
        self.assertEqual(r.mean_wip, [0.0])

    def test_slow_upstream_starves_downstream_without_buffer(self):
        r = simulate(cfg([Station("slow", 20.0), Station("fast", 10.0)], [0]))
        self.assertAlmostEqual(r.throughput, 180.0, delta=1.0)
        self.assertAlmostEqual(r.stations[1].shares(r.window)["starved"], 0.5, delta=0.01)

    def test_variability_makes_no_buffer_worse_and_more_buffer_better(self):
        st = [Station("A", 10, 0.3, 600, 60), Station("B", 10, 0.3, 600, 60), Station("C", 10, 0.3, 600, 60)]
        c = Config(st, [0, 0], duration=600000.0, warmup=5000.0)
        v = {b: sum(simulate(Config(st, [b, b], c.duration, c.warmup, s)).throughput for s in range(1, 6)) / 5 for b in (0, 1, 3, 10)}
        self.assertLess(v[0], v[1])
        self.assertLess(v[1], v[3])
        self.assertLess(v[3], v[10])

    def test_time_shares_and_levels_with_mixed_buffers(self):
        c = cfg([Station("A", 10, 0.3, 600, 60), Station("B", 12, 0.3, 900, 120), Station("C", 9, 0.2)], [0, 3])
        r = simulate(c)
        for s in r.stations:
            self.assertAlmostEqual(sum(s.shares(r.window).values()), 1.0, delta=0.01, msg=s.name)
        self.assertEqual(r.mean_wip[0], 0.0)
        self.assertLessEqual(r.mean_wip[1], 3.0)

    def test_negative_buffer_is_rejected(self):
        with self.assertRaises(ValueError):
            cfg([Station("A", 10.0), Station("B", 10.0)], [-1])
