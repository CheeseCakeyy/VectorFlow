import unittest
import numpy as np
from vectorflow.curves import evaluate, fit, trace, render, svg


class CurveTests(unittest.TestCase):
    def test_line_geometry(self):
        points = np.column_stack([np.linspace(0, 100, 40), np.linspace(10, 70, 40)])
        curves = fit(points, .1)
        self.assertEqual(len(curves), 1)
        np.testing.assert_allclose(evaluate(curves[0], np.linspace(0, 1, 40)), points, atol=.01)

    def test_circle_fit_stays_close(self):
        angles = np.linspace(0, np.pi, 100)
        points = np.column_stack([50+40*np.cos(angles), 50+40*np.sin(angles)])
        curves = fit(points, .5)
        samples = np.concatenate([evaluate(c, np.linspace(0, 1, 100)) for c in curves])
        distance = np.linalg.norm(points[:, None]-samples[None, :], axis=2).min(axis=1)
        self.assertLess(distance.max(), .8)

    def test_image_to_real_vectors(self):
        rgb = np.full((100, 100, 3), 255, np.uint8)
        rgb[20:80, 20:80] = 0
        paths = trace(rgb)
        self.assertTrue(paths)
        self.assertIn('C ', svg(paths, 100, 100))
        output = np.array(render(paths, (100, 100)))
        self.assertGreater(output.std(), 10)
        self.assertEqual(trace(np.zeros_like(rgb)), [])


if __name__ == '__main__':
    unittest.main()
