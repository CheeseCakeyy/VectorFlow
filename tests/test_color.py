import unittest
import numpy as np
import cv2
from vectorflow.color import ColorTracer
from vectorflow.curves import render, svg


class ColorTests(unittest.TestCase):
    def test_filled_regions_preserve_holes_and_palette(self):
        rgb = np.zeros((120, 160, 3), np.uint8)
        rgb[:] = (240, 240, 240)
        cv2.circle(rgb, (80, 60), 40, (220, 30, 40), -1)
        cv2.circle(rgb, (80, 60), 16, (240, 240, 240), -1)
        tracer = ColorTracer(3)
        paths, styles = tracer.trace(rgb)
        result = np.array(render(paths, (160, 120), styles=styles))
        self.assertGreater(result[60, 80, 1], 200)
        self.assertLess(result[60, 110, 1], 100)
        self.assertIn('fill-rule="evenodd"', svg(paths, 160, 120, styles))
        self.assertTrue(any(style['holes'] for style in styles))
        palette = tracer.palette.copy()
        tracer.trace(np.roll(rgb, 2, axis=1))
        np.testing.assert_array_equal(palette, tracer.palette)
