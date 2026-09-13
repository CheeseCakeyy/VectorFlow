"""Conservative motion tracking; uncertain matches start new track identities."""
import cv2
import numpy as np
from .curves import evaluate


def transform(points, matrix):
    p = np.asarray(points, dtype=float)
    return (p @ np.asarray(matrix)[:2, :2].T + np.asarray(matrix)[:2, 2]).tolist()


def samples(path):
    return np.concatenate([evaluate(c, np.linspace(0, 1, 5)) for c in path])


class Motion:
    def __init__(self, before, after):
        self.a = self.b = np.empty((0, 2), np.float32)
        # Large illumination/scene changes invalidate identities.
        self.cut = np.mean(cv2.absdiff(before, after)) > 65
        if self.cut:
            return
        points = cv2.goodFeaturesToTrack(before, 1000, .01, 5)
        if points is None:
            return
        moved, ok, _ = cv2.calcOpticalFlowPyrLK(before, after, points, None)
        if moved is None:
            return
        back, reverse, _ = cv2.calcOpticalFlowPyrLK(after, before, moved, None)
        if back is None:
            return
        keep = ok.ravel().astype(bool) & reverse.ravel().astype(bool)
        keep &= np.linalg.norm(points[:, 0]-back[:, 0], axis=1) < 1.5
        self.a, self.b = points[keep, 0], moved[keep, 0]

    def within(self, polygon):
        polygon = np.asarray(polygon, np.float32)
        mask = np.array([cv2.pointPolygonTest(polygon, tuple(map(float, p)), False) >= 0 for p in self.a], bool)
        a, b = self.a[mask], self.b[mask]
        if len(a) < 3:
            return None
        matrix, inliers = cv2.estimateAffinePartial2D(a, b, method=cv2.RANSAC, ransacReprojThreshold=2)
        if matrix is None or inliers.mean() < .6:
            return None
        scale = np.linalg.norm(matrix[:, 0])
        if not .7 < scale < 1.4:
            return None
        return np.vstack([matrix, [0, 0, 1]])


class PathTracker:
    def __init__(self):
        self.previous = None
        self.records = []
        self.next_id = 0

    def update(self, rgb, paths):
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        motion = Motion(self.previous, gray) if self.previous is not None else None
        current = [samples(p) for p in paths]
        centers = np.array([p.mean(axis=0) for p in current])
        candidates = []
        predictions = {}
        if motion is not None and not motion.cut and len(current):
            for old in self.records:
                p = samples(old['path'])
                lo, hi = p.min(axis=0)-10, p.max(axis=0)+10
                polygon = [lo, [hi[0], lo[1]], hi, [lo[0], hi[1]]]
                matrix = motion.within(polygon)
                if matrix is None:
                    # No motion evidence: only allow almost identical stationary paths.
                    matrix = np.eye(3)
                predicted = np.asarray(transform(p, matrix))
                nearby = np.flatnonzero(np.linalg.norm(centers-predicted.mean(axis=0), axis=1) < 18)
                for j in nearby:
                    q = current[j]
                    # Bidirectional sample distance penalizes partial/disappearing paths.
                    d = np.linalg.norm(predicted[::max(1, len(predicted)//80), None] - q[None, ::max(1, len(q)//80)], axis=2)
                    score = max(d.min(axis=0).mean(), d.min(axis=1).mean())
                    if score < 3:
                        candidates.append((score, old['id'], int(j)))
                        predictions[(old['id'], int(j))] = (old, matrix)
        used_old, used_new, matches = set(), set(), {}
        for score, identity, j in sorted(candidates):
            if identity not in used_old and j not in used_new:
                matches[j] = (*predictions[(identity, j)], score)
                used_old.add(identity)
                used_new.add(j)
        result = []
        for j, path in enumerate(paths):
            if j in matches:
                old, matrix, score = matches[j]
                # Preserve a fitted path's topology while it still explains the image.
                if score < 1.2:
                    path = transform(old['path'], matrix)
                result.append(dict(id=old['id'], path=path, transform=(matrix @ old['transform']).tolist()))
            else:
                result.append(dict(id=self.next_id, path=path, transform=np.eye(3).tolist()))
                self.next_id += 1
        self.previous, self.records = gray, result
        return result


class RegionTracker:
    def __init__(self, regions):
        self.specs = regions
        self.records = []
        self.previous = None

    def update(self, rgb):
        h, w = rgb.shape[:2]
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        if self.previous is None:
            for i, spec in enumerate(self.specs):
                x, y, rw, rh = np.array(spec['rect'])*[w, h, w, h]
                corners = [[x, y], [x+rw, y], [x+rw, y+rh], [x, y+rh]]
                self.records.append(dict(id=i, mode=spec['mode'], corners=corners,
                                         transform=np.eye(3).tolist(), lost=False))
        else:
            motion = Motion(self.previous, gray)
            for record in self.records:
                if record['lost']:
                    continue
                matrix = motion.within(record['corners']) if not motion.cut else None
                if matrix is None:
                    # A truly stationary region needs no feature motion estimate.
                    mask = np.zeros_like(gray)
                    cv2.fillPoly(mask, [np.int32(record['corners'])], 255)
                    delta = cv2.absdiff(self.previous, gray)[mask > 0]
                    if len(delta) and delta.mean() < 2:
                        matrix = np.eye(3)
                    else:
                        record['lost'] = True
                        continue
                record['corners'] = transform(record['corners'], matrix)
                record['transform'] = (matrix @ record['transform']).tolist()
        self.previous = gray
        include = any(r['mode'] == 'include' for r in self.records)
        mask = np.zeros((h, w), np.uint8) if include else np.full((h, w), 255, np.uint8)
        for record in self.records:
            if record['mode'] == 'include' and not record['lost']:
                cv2.fillPoly(mask, [np.int32(record['corners'])], 255)
        for record in self.records:
            if record['mode'] == 'exclude':
                if record['lost']:
                    mask[:] = 0
                else:
                    cv2.fillPoly(mask, [np.int32(record['corners'])], 0)
        return mask, self.records
