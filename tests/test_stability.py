import unittest
import numpy as np
from vectorflow.stability import Stabilizer


class StabilityTests(unittest.TestCase):
    def test_static_noise_reduced_without_ghosting_motion_or_cuts(self):
        s = Stabilizer()
        base = np.full((40, 40, 3), 100, np.uint8)
        s.apply(base)
        noisy = base.copy()
        noisy[::2] += 6
        filtered = s.apply(noisy)
        self.assertLess(filtered.std(), noisy.std())
        moving = noisy.copy()
        moving[10:20, 10:20] = 240
        np.testing.assert_array_equal(s.apply(moving)[10:20, 10:20], moving[10:20, 10:20])
        cut = np.full_like(base, 255)
        np.testing.assert_array_equal(s.apply(cut), cut)
