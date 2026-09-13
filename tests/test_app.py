import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import unittest
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from vectorflow.app import Window


class AppTests(unittest.TestCase):
    def setUp(self):
        self.warning_patch = patch('vectorflow.app.QMessageBox.warning', return_value=None)
        self.warnings = self.warning_patch.start()
        self.addCleanup(self.warning_patch.stop)

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def wait_for_worker(self, window):
        deadline = time.monotonic() + 20
        while window.worker is not None and time.monotonic() < deadline:
            self.app.processEvents()
            QTest.qWait(20)
        self.assertIsNone(window.worker, 'Background task did not complete')

    def test_choose_convert_play_map_and_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root/'moving-circle.avi'
            writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*'MJPG'), 12, (160, 120))
            for i in range(12):
                frame = np.full((120, 160, 3), 250, np.uint8)
                cv2.circle(frame, (30+6*i, 60), 20, (10, 10, 10), 3)
                writer.write(frame)
            writer.release()
            window = Window()
            window.show()
            with patch('vectorflow.app.ROOT', root), patch('vectorflow.app.QFileDialog.getOpenFileName', return_value=(str(source), '')):
                QTest.mouseClick(window.choose, Qt.MouseButton.LeftButton)
                self.assertTrue(window.convert_button.isEnabled())
                QTest.mouseClick(window.convert_button, Qt.MouseButton.LeftButton)
                self.assertFalse(window.choose.isEnabled())
                self.wait_for_worker(window)
            self.assertFalse(self.warnings.called, str(self.warnings.call_args_list))
            self.assertIsNotNone(window.info, window.status.text())
            self.assertEqual(window.info['frames'], 12)
            self.assertTrue(window.export_button.isEnabled())
            QTest.mouseClick(window.play, Qt.MouseButton.LeftButton)
            window.play_start -= .4
            window.tick()
            self.assertGreater(window.timeline.value(), 0)
            QTest.mouseClick(window.map_button, Qt.MouseButton.LeftButton)
            self.assertFalse(window.playing)
            window.map_start -= 3
            window.tick()
            self.assertIn('x(t)', window.equation.text())
            self.assertEqual(window.canvas.mode, 'Mapping')
            with patch('vectorflow.app.QFileDialog.getSaveFileName', return_value=(str(root/'export.mp4'), '')):
                QTest.mouseClick(window.export_button, Qt.MouseButton.LeftButton)
                self.wait_for_worker(window)
            self.assertTrue((root/'export.mp4').is_file())
            window.toggle_theme()
            self.assertFalse(window.dark)
            window.close()

    def test_themes_and_mapping(self):
        window = Window()
        window.show()
        self.app.processEvents()
        self.assertFalse(window.convert_button.isEnabled())
        self.assertTrue(window.dark)
        Path('test-output').mkdir(exist_ok=True)
        window.grab().save('test-output/redesign-empty-dark.png')
        window.toggle_theme()
        self.assertFalse(window.canvas.dark)
        self.app.processEvents()
        window.grab().save('test-output/redesign-empty-light.png')
        for tab in window.mode_buttons.buttons():
            QTest.mouseClick(tab, Qt.MouseButton.LeftButton)
            self.assertEqual(window.canvas.mode, tab.text())
            self.assertTrue(tab.active)
        window.resize(1060, 780)
        self.app.processEvents()
        window.grab().save('test-output/redesign-compact.png')
        window.resize(1360, 940)
        project = Path('test-output/reference')
        if project.exists():
            window.load_project(project)
            window.timeline.setValue(20)
            self.assertTrue(window.canvas.paths)
            window.watch_mapping()
            window.map_start -= 3
            window.tick()
            self.assertGreater(window.canvas.reveal, .4)
            self.assertLess(window.canvas.reveal, .7)
            self.app.processEvents()
            QTest.qWait(150)
            window.grab().save('test-output/ui-light.png')
            window.toggle_theme()
            self.app.processEvents()
            QTest.qWait(150)
            window.grab().save('test-output/ui-dark.png')
        window.close()


if __name__ == '__main__':
    unittest.main()
