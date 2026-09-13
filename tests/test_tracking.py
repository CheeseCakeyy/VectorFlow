import unittest
import cv2
import numpy as np
from vectorflow.curves import trace
from vectorflow.tracking import PathTracker


class TrackingTests(unittest.TestCase):
    def test_identity_follows_translation_and_resets_at_cut(self):
        image = np.zeros((150, 200, 3), np.uint8)
        cv2.rectangle(image, (30, 40), (85, 110), (255, 255, 255), 3)
        tracker = PathTracker()
        first = tracker.update(image, trace(image))
        shifted = cv2.warpAffine(image, np.float32([[1, 0, 5], [0, 1, 2]]), (200, 150))
        second = tracker.update(shifted, trace(shifted))
        self.assertEqual(first[0]['id'], second[0]['id'])
        np.testing.assert_allclose(np.array(second[0]['transform'])[:2, 2], [5, 2], atol=.5)
        cut = 255-shifted
        third = tracker.update(cut, trace(cut))
        self.assertTrue(set(r['id'] for r in second).isdisjoint(r['id'] for r in third))
