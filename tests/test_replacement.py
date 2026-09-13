import tempfile
import threading
import unittest
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from vectorflow.pipeline import write_json
from vectorflow.replacement import create_text, create_artwork, replacements, composite, composite_svg


class ReplacementTests(unittest.TestCase):
    def test_artwork_follows_rotation_and_scale_with_alpha(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'frames').mkdir()
            write_json(root/'project.json', dict(width=240, height=160, frames=2, fps=12))
            image = np.full((160, 240, 3), 210, np.uint8)
            cv2.putText(image, 'OLD', (65, 85), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
            motion = cv2.getRotationMatrix2D((100, 75), 8, 1.05)
            moved = cv2.warpAffine(image, motion, (240, 160), borderValue=(210, 210, 210))
            Image.fromarray(image).save(root/'frames/000000.jpg')
            Image.fromarray(moved).save(root/'frames/000001.jpg')
            asset = Image.new('RGBA', (60, 40))
            from PIL import ImageDraw
            ImageDraw.Draw(asset).polygon([(8, 32), (30, 4), (52, 32)], fill=(0, 250, 20, 255))
            asset.save(root/'art.png')
            create_artwork(root, [55/240, 50/160, 105/240, 50/160], 0, 1, root/'art.png', lambda *_: None, threading.Event())
            record = replacements(root)[0]
            self.assertFalse(record['frames']['1']['lost'])
            actual = np.array(record['frames']['1']['matrix'])[:2]
            np.testing.assert_allclose(actual[:, :2], motion[:, :2], atol=.03)
            with Image.open(root/record['asset']) as saved:
                self.assertEqual(saved.getpixel((0, 0))[3], 0)
            rendered = np.array(composite(root, 1))
            self.assertTrue(((rendered[:, :, 1] > 230) & (rendered[:, :, 0] < 30)).any())

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
