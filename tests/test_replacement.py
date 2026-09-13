import tempfile
import threading
import unittest
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from vectorflow.pipeline import write_json
from vectorflow.replacement import create_text, replacements, composite, composite_svg


class ReplacementTests(unittest.TestCase):
    def test_text_tracks_motion_timing_and_survives_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'frames').mkdir()
            write_json(root/'project.json', dict(width=240, height=160, frames=3, fps=12))
            base = np.full((160, 240, 3), 210, np.uint8)
            cv2.putText(base, 'OLD', (45, 85), cv2.FONT_HERSHEY_SIMPLEX, 1, (20, 20, 20), 2)
            for i in range(3):
                rgb = cv2.warpAffine(base, np.float32([[1, 0, i*4], [0, 1, i*2]]), (240, 160), borderValue=(210, 210, 210))
                Image.fromarray(rgb).save(root/'frames'/f'{i:06d}.jpg')
            create_text(root, [40/240, 55/160, 85/240, 40/160], 0, 1, 'NEW', '#ff0000', lambda *_: None, threading.Event())
            record = replacements(root)[0]
            self.assertNotIn('2', record['frames'])
            self.assertFalse(record['frames']['1']['lost'])
            np.testing.assert_allclose(np.array(record['frames']['1']['matrix'])[:2, 2], [4, 2], atol=1)
            first, second = np.array(composite(root, 0)), np.array(composite(root, 1))
            y0, x0 = np.where((first[:, :, 0] > 230) & (first[:, :, 1] < 60))
            y1, x1 = np.where((second[:, :, 0] > 230) & (second[:, :, 1] < 60))
            self.assertGreater(len(x0), 10)
            self.assertAlmostEqual(x1.mean()-x0.mean(), 4, delta=1)
            self.assertIn('>NEW</text>', composite_svg(root, 1))
