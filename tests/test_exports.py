import tempfile
import unittest
import threading
import zipfile
import json
import subprocess
import imageio_ffmpeg
import numpy as np
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
from vectorflow.pipeline import write_json
from vectorflow.exports import export_assets, FORMATS


class ExportTests(unittest.TestCase):
    def test_vector_sequences_and_alpha(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'frames').mkdir()
            write_json(root/'project.json', dict(frames=2, fps=12, width=80, height=60, source='unavailable.mp4'))
            for i in range(2):
                write_json(root/'frames'/f'{i:06d}.json', dict(paths=[[[[10+i, 10], [20, 20], [30, 20], [40, 10]]]]))
            for j, (kind, suffix) in enumerate(FORMATS.items()):
                result = export_assets(root, root/f'export{j}{suffix}', kind, lambda *_: None, threading.Event())
                self.assertGreater(result.stat().st_size, 0)
                if kind.startswith('Transparent PNG'):
                    with zipfile.ZipFile(result) as archive:
                        with archive.open('000000.png') as file:
                            image = Image.open(file)
                            self.assertEqual(image.mode, 'RGBA')
                            self.assertEqual(image.getpixel((0, 0))[3], 0)
                if kind.startswith('Animated SVG'):
                    doc = ET.parse(result)
                    self.assertEqual(len(doc.findall('.//{http://www.w3.org/2000/svg}animate')), 2)
                if kind.startswith('Vector animation'):
                    self.assertEqual(len(json.loads(result.read_text())['frames']), 2)
                if kind.startswith('ProRes'):
                    decoded = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error', '-i', str(result),
                                              '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-'], capture_output=True, check=True)
                    pixels = np.frombuffer(decoded.stdout, np.uint8).reshape(60, 80, 4)
                    self.assertEqual(pixels[0, 0, 3], 0)
                    self.assertGreater(pixels[:, :, 3].max(), 100)
