import tempfile
import threading
import unittest
from pathlib import Path

import cv2
import numpy as np

from vectorflow.pipeline import Cancelled, Settings, convert, export_video, read_json


class PipelineTests(unittest.TestCase):
    def test_conversion_export_and_cancellation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root/'input.avi'
            writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*'MJPG'), 10, (160, 120))
            for i in range(10):
                frame = np.full((120, 160, 3), 255, dtype=np.uint8)
                cv2.circle(frame, (40+i*4, 60), 22, (0, 0, 0), 3)
                writer.write(frame)
            writer.release()
            project = convert(source, root/'project', Settings(fps=5))
            info = read_json(project/'project.json')
            self.assertEqual(info['frames'], 5)
            self.assertEqual(info['status'], 'complete')
            self.assertNotEqual(read_json(project/'frames/000000.json')['paths'],
                                read_json(project/'frames/000004.json')['paths'])
            result = export_video(project, root/'result.mp4')
            cap = cv2.VideoCapture(str(result))
            self.assertEqual(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), 5)
            self.assertAlmostEqual(cap.get(cv2.CAP_PROP_FPS), 5)
            self.assertTrue(cap.read()[0])
            cap.release()
            event = threading.Event()
            def progress(*_):
                event.set()
            with self.assertRaises(Cancelled):
                convert(source, root/'cancelled', progress=progress, cancel=event)
            self.assertEqual(read_json(root/'cancelled/project.json')['status'], 'cancelled')


if __name__ == '__main__':
    unittest.main()
