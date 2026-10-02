import unittest
from plantsim.whatif import _need_n


class T(unittest.TestCase):
    def test_scaling(self):
        # diff 1, half-width 2 at n=10: half-width must shrink 2x -> n x 4
        self.assertEqual(_need_n(10, 1.0, 3.0), 40)
        self.assertEqual(_need_n(20, -1.0, 1.0), 80)       # CI [-3, 1]... half-width 2

    def test_none_when_clear_or_zero(self):
        self.assertIsNone(_need_n(10, 3.0, 4.0))            # half-width 1 < diff: already clear
        self.assertIsNone(_need_n(10, 0.0, 1.0))
        self.assertIsNone(_need_n(10, 1e-15, 1.0))

if __name__ == "__main__":
    unittest.main()
