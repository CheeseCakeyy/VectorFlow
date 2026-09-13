import tempfile
import unittest
from pathlib import Path
import numpy as np
from vectorflow.pipeline import write_json
from vectorflow.edits import add_edit, resolve_frame, undo
from vectorflow.tracking import transform


class EditTests(unittest.TestCase):
    def test_edits_follow_motion_and_undo(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            (project/'frames').mkdir()
            path = [[[10, 10], [20, 10], [30, 10], [40, 10]]]
            for i in range(2):
                matrix = np.array([[1, 0, i*20], [0, 1, 0], [0, 0, 1]])
                write_json(project/'frames'/f'{i:06d}.json', dict(paths=[transform(path, matrix)], path_ids=[7], transforms=[matrix.tolist()]))
            edited = [[[10, 10], [20, 25], [30, 10], [40, 10]]]
            add_edit(project, 0, 0, 'shape', True, edited)
            self.assertEqual(resolve_frame(project, 1)['paths'][0][0][1], [40., 25.])
            add_edit(project, 0, 0, 'delete', False)
            self.assertEqual(resolve_frame(project, 0)['paths'], [])
            self.assertTrue(resolve_frame(project, 1)['paths'])
            undo(project)
            self.assertTrue(resolve_frame(project, 0)['paths'])
