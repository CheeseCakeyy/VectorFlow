import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from vectorflow.app import Window


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_themes_and_mapping(self):
        window = Window()
        window.show()
        self.app.processEvents()
        self.assertFalse(window.convert_button.isEnabled())
        self.assertTrue(window.dark)
        window.toggle_theme()
        self.assertFalse(window.canvas.dark)
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
            window.grab().save('test-output/ui-light.png')
            window.toggle_theme()
            self.app.processEvents()
            window.grab().save('test-output/ui-dark.png')
        window.close()


if __name__ == '__main__':
    unittest.main()
