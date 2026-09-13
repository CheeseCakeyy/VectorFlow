"""Non-destructive project edits, expressed in each tracked path's anchor space."""
from pathlib import Path
import numpy as np
from .pipeline import read_json, write_json
from .tracking import transform, samples
from .curves import fit


def operations(project):
    file = Path(project)/'edits.json'
    return read_json(file) if file.exists() else []


def resolve_frame(project, index):
    data = read_json(Path(project)/'frames'/f'{index:06d}.json')
    paths = data['paths']
    ids = data.get('path_ids', [f'{index}:{i}' for i in range(len(paths))])
    matrices = data.get('transforms', [np.eye(3).tolist() for _ in paths])
    styles = data.get('styles', [{} for _ in paths])
    deleted = set()
    for op in operations(project):
        if op['frame'] is not None and op['frame'] != index:
            continue
        for i, identity in enumerate(ids):
            if op['id'] != identity:
                continue
            if op['action'] == 'delete':
                deleted.add(i)
            elif op['action'] == 'shape':
                paths[i] = transform(op['anchor'], matrices[i])
            elif op['action'] == 'simplify':
                points = samples(paths[i])
                # Split loops into arcs to avoid degeneracy at matching endpoints.
                paths[i] = [c for start in range(0, len(points)-1, 150)
                            for c in fit(points[start:start+151], op['tolerance'])]
    keep = [i for i in range(len(paths)) if i not in deleted]
    data.update(paths=[paths[i] for i in keep], path_ids=[ids[i] for i in keep],
                transforms=[matrices[i] for i in keep], styles=[styles[i] for i in keep])
    return data


def add_edit(project, index, path_index, action, whole_track=False, path=None, tolerance=3):
    data = resolve_frame(project, index)
    if not 0 <= path_index < len(data['paths']):
        raise ValueError('Choose a path first.')
    op = dict(id=data['path_ids'][path_index], frame=None if whole_track else index, action=action)
    if action == 'shape':
        op['anchor'] = transform(path, np.linalg.inv(data['transforms'][path_index]))
    elif action == 'simplify':
        op['tolerance'] = tolerance
    elif action != 'delete':
        raise ValueError('Unknown edit action.')
    edits = operations(project)
    edits.append(op)
    write_json(Path(project)/'edits.json', edits)


def undo(project):
    edits = operations(project)
    if edits:
        edits.pop()
        write_json(Path(project)/'edits.json', edits)
